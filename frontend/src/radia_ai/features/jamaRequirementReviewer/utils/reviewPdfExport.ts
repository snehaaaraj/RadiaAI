/**
 * Generates exportable PDF reports for requirement reviews.
 *
 * Used by both Single Review (one requirement, one result) and Set Review
 * (many requirements, one result each - exportable individually or as a
 * single consolidated PDF covering every reviewed requirement in the set).
 */
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { CategoryResult, ReviewFinding, RequirementReviewResponse } from '@/types/api';
import { getReviewQualityScore, getCategoryScore } from '@/utils/reviewQuality';

export interface ReviewPdfMetadataItem {
  label: string;
  value: string | number;
}

export interface ReviewPdfSection {
  /** Human-readable requirement identifier shown in the section heading. */
  requirementId: string;
  requirementTitle?: string;
  result: RequirementReviewResponse;
  metadata?: ReviewPdfMetadataItem[];
}

const CATEGORY_LABEL_MAP: Record<string, string> = {
  language: 'Language',
  structure: 'Structure',
  verifiability: 'Verifiability',
  certification: 'Certification',
};

function categoryLabel(category: string): string {
  const key = category.trim().toLowerCase();
  return (
    CATEGORY_LABEL_MAP[key] ??
    category
      .split(/[_\s-]+/)
      .filter(Boolean)
      .map((part) => part[0].toUpperCase() + part.slice(1))
      .join(' ')
  );
}

function statusScoreLabel(category: CategoryResult): string {
  if (category.status === 'Not Evaluated') return 'Not scored';
  return `${getCategoryScore(category).toFixed(1)} (${category.status})`;
}

const PAGE_MARGIN = 40;

function addHeading(doc: jsPDF, title: string, subtitle: string | undefined, cursorY: number): number {
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.text(title, PAGE_MARGIN, cursorY);
  cursorY += 20;
  if (subtitle) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(90);
    doc.text(subtitle, PAGE_MARGIN, cursorY);
    doc.setTextColor(0);
    cursorY += 18;
  }
  return cursorY;
}

function addMetadataTable(doc: jsPDF, cursorY: number, rows: [string, string][]): number {
  autoTable(doc, {
    startY: cursorY,
    theme: 'plain',
    styles: { fontSize: 9, cellPadding: 2 },
    columnStyles: { 0: { fontStyle: 'bold', cellWidth: 130 } },
    body: rows,
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (doc as any).lastAutoTable.finalY + 14;
}

function addCategoryTable(doc: jsPDF, cursorY: number, categories: CategoryResult[]): number {
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('Category scoring', PAGE_MARGIN, cursorY);
  cursorY += 8;

  autoTable(doc, {
    startY: cursorY,
    head: [['Category', 'Score']],
    body: categories.map((c) => [categoryLabel(c.category), statusScoreLabel(c)]),
    styles: { fontSize: 9, cellPadding: 4 },
    headStyles: { fillColor: [27, 79, 216] },
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (doc as any).lastAutoTable.finalY + 16;
}

function addFindingsSection(doc: jsPDF, cursorY: number, findings: ReviewFinding[]): number {
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);

  const pageHeight = doc.internal.pageSize.getHeight();
  if (cursorY > pageHeight - PAGE_MARGIN) {
    doc.addPage();
    cursorY = PAGE_MARGIN;
  }

  doc.text(`Findings (${findings.length})`, PAGE_MARGIN, cursorY);
  cursorY += 8;

  if (findings.length === 0) {
    autoTable(doc, {
      startY: cursorY,
      theme: 'plain',
      styles: { fontSize: 9, cellPadding: 4 },
      body: [['No findings were detected for this review.']],
      margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (doc as any).lastAutoTable.finalY + 16;
  }

  autoTable(doc, {
    startY: cursorY,
    head: [['#', 'Category', 'Severity', 'Rule', 'Explanation', 'Recommendation', 'Reference']],
    body: findings.map((f, i) => [
      String(i + 1),
      categoryLabel(f.category),
      f.severity,
      f.rule,
      f.explanation,
      f.recommendation,
      f.reference,
    ]),
    styles: { fontSize: 8, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
    headStyles: { fillColor: [27, 79, 216] },
    columnStyles: {
      0: { cellWidth: 20 },
      1: { cellWidth: 60 },
      2: { cellWidth: 45 },
      3: { cellWidth: 70 },
      4: { cellWidth: 110 },
      5: { cellWidth: 110 },
      6: { cellWidth: 60 },
    },
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (doc as any).lastAutoTable.finalY + 16;
}

/** Renders one requirement's review result onto the given document, returning the new cursor Y. */
function renderSection(doc: jsPDF, section: ReviewPdfSection, cursorY: number, isFirst: boolean): number {
  if (!isFirst) {
    doc.addPage();
    cursorY = PAGE_MARGIN;
  }

  const heading = section.requirementTitle
    ? `${section.requirementId} - ${section.requirementTitle}`
    : section.requirementId;
  cursorY = addHeading(doc, heading, 'Requirement Review Report', cursorY);

  const score = getReviewQualityScore(section.result.category_results);
  const rows: [string, string][] = [
    ['Overall status', section.result.overall],
    ['Overall score', score.toFixed(1)],
    ['Review ID', section.result.review_id ?? 'N/A'],
    ['Completion', section.result.completion.status],
    ...(section.metadata ?? []).map((m): [string, string] => [m.label, String(m.value)]),
  ];
  cursorY = addMetadataTable(doc, cursorY, rows);
  cursorY = addCategoryTable(doc, cursorY, section.result.category_results);
  cursorY = addFindingsSection(doc, cursorY, section.result.findings);

  return cursorY;
}

function timestampedFilename(prefix: string): string {
  const now = new Date();
  const stamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
  return `${prefix}-${stamp}.pdf`;
}

/** Exports a single requirement's review result as a standalone PDF. */
export function exportReviewToPdf(section: ReviewPdfSection): void {
  const doc = new jsPDF({ unit: 'pt', format: 'letter' });
  renderSection(doc, section, PAGE_MARGIN, true);
  doc.save(timestampedFilename(`review-${section.requirementId || 'requirement'}`));
}

/** Exports a consolidated PDF covering every reviewed requirement in a set. */
export function exportReviewSetToPdf(sections: ReviewPdfSection[], setName = 'set-review'): void {
  if (sections.length === 0) return;
  const doc = new jsPDF({ unit: 'pt', format: 'letter' });

  const cursorY = addHeading(
    doc,
    'Set Review - Consolidated Report',
    `${sections.length} requirement${sections.length === 1 ? '' : 's'} reviewed`,
    PAGE_MARGIN
  );

  autoTable(doc, {
    startY: cursorY,
    head: [['#', 'Requirement ID', 'Title', 'Overall status', 'Score', 'Findings']],
    body: sections.map((s, i) => [
      String(i + 1),
      s.requirementId,
      s.requirementTitle ?? '',
      s.result.overall,
      getReviewQualityScore(s.result.category_results).toFixed(1),
      String(s.result.findings.length),
    ]),
    styles: { fontSize: 9, cellPadding: 4 },
    headStyles: { fillColor: [27, 79, 216] },
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });

  sections.forEach((section) => {
    doc.addPage();
    renderSection(doc, section, PAGE_MARGIN, true);
  });

  doc.save(timestampedFilename(setName));
}
