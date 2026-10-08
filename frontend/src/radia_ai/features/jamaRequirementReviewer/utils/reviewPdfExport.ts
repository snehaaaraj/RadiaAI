/**
 * Generates exportable PDF reports for requirement reviews.
 *
 * Used by both Single Review (one requirement, one result) and Set Review
 * (many requirements, one result each - exportable individually or as a
 * single consolidated PDF covering every reviewed requirement in the set).
 */
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type {
  CategoryResult,
  FinalRecommendation,
  ReviewFinding,
  RequirementReviewResponse,
} from '@/types/api';
import { getReviewQualityScore, getCategoryScore } from '@/utils/reviewQuality';
import { CONTRIBUTION_STATUS_LABEL, findingSourceLabel } from './recommendationEvidence';

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
  const contentWidth = doc.internal.pageSize.getWidth() - PAGE_MARGIN * 2;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  const titleLines = doc.splitTextToSize(title, contentWidth);
  doc.text(titleLines, PAGE_MARGIN, cursorY);
  cursorY += titleLines.length * 20;
  if (subtitle) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(90);
    const subtitleLines = doc.splitTextToSize(subtitle, contentWidth);
    doc.text(subtitleLines, PAGE_MARGIN, cursorY);
    doc.setTextColor(0);
    cursorY += subtitleLines.length * 12 + 6;
  }
  return cursorY;
}

function addMetadataTable(doc: jsPDF, cursorY: number, rows: [string, string][]): number {
  autoTable(doc, {
    startY: cursorY,
    theme: 'plain',
    styles: { fontSize: 9, cellPadding: 2, overflow: 'linebreak', valign: 'top' },
    columnStyles: { 0: { fontStyle: 'bold', cellWidth: 130 } },
    body: rows,
    tableWidth: 'auto',
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
    styles: { fontSize: 9, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
    headStyles: { fillColor: [27, 79, 216] },
    tableWidth: 'auto',
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
      styles: { fontSize: 9, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
      body: [['No findings were detected for this review.']],
      tableWidth: 'auto',
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
    tableWidth: 'auto',
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

function ensureSpace(doc: jsPDF, cursorY: number, needed = 60): number {
  if (cursorY > doc.internal.pageSize.getHeight() - PAGE_MARGIN - needed) {
    doc.addPage();
    return PAGE_MARGIN;
  }
  return cursorY;
}

function lastTableY(doc: jsPDF): number {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (doc as any).lastAutoTable.finalY;
}

const RECOMMENDATION_STATUS_LABEL: Record<FinalRecommendation['status'], string> = {
  ready: 'Ready to replace',
  needs_review: 'Needs review',
  no_change: 'No change needed',
  failed: 'Not generated',
};

function addRecommendationSection(
  doc: jsPDF,
  cursorY: number,
  recommendation: FinalRecommendation,
  findings: ReviewFinding[]
): number {
  cursorY = ensureSpace(doc, cursorY);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('Final recommended requirement', PAGE_MARGIN, cursorY);
  cursorY += 8;

  const rows: [string, string][] = [
    ['Status', RECOMMENDATION_STATUS_LABEL[recommendation.status]],
    ['Skillz', recommendation.skillz_status_message || recommendation.skillz_status],
    ['Original Description', recommendation.original_description],
    [
      'Recommended Description',
      recommendation.recommended_description ?? recommendation.failure_message ?? 'Not generated',
    ],
  ];
  if (recommendation.summary) rows.push(['Summary', recommendation.summary]);
  autoTable(doc, {
    startY: cursorY,
    theme: 'grid',
    styles: { fontSize: 9, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
    columnStyles: { 0: { fontStyle: 'bold', cellWidth: 130 } },
    body: rows,
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });
  cursorY = lastTableY(doc) + 12;

  if (recommendation.contributions.length > 0) {
    const findingById = new Map(findings.map((f, i) => [f.finding_id ?? `F${i + 1}`, f]));
    autoTable(doc, {
      startY: cursorY,
      head: [['Suggestion', 'Treatment', 'Effect on final text', 'Reason', 'Source']],
      body: recommendation.contributions.map((c) => {
        const finding = findingById.get(c.finding_id);
        const overriddenBy = c.overridden_by_rule_ids.length
          ? ` (Skillz ${c.overridden_by_rule_ids.join(', ')})`
          : '';
        return [
          c.finding_id,
          `${CONTRIBUTION_STATUS_LABEL[c.status]}${overriddenBy}`,
          c.contribution,
          c.reason,
          findingSourceLabel(finding ?? null),
        ];
      }),
      styles: { fontSize: 8, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
      headStyles: { fillColor: [27, 79, 216] },
      columnStyles: { 0: { cellWidth: 50 }, 1: { cellWidth: 90 } },
      margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
    });
    cursorY = lastTableY(doc) + 12;
  }

  const notes: [string, string][] = [
    ...recommendation.skillz_changes.map((c): [string, string] => [`Skillz ${c.rule_id}`, c.change]),
    ...recommendation.conflicts.map((c): [string, string] => [
      `Conflict ${c.conflict_id} (${c.resolution === 'unresolved' ? 'unresolved' : 'resolved by Skillz'})`,
      `${c.description} [${c.finding_ids.join(', ')}]`,
    ]),
    ...recommendation.open_items.map((o): [string, string] => [
      o.rule_id ? `Follow-up (Skillz ${o.rule_id})` : 'Follow-up',
      o.description,
    ]),
    ...recommendation.skillz_check_issues.map((i): [string, string] => [`Skillz check ${i.rule_id}`, i.message]),
  ];
  if (notes.length > 0) {
    autoTable(doc, {
      startY: cursorY,
      theme: 'plain',
      styles: { fontSize: 8, cellPadding: 3, overflow: 'linebreak', valign: 'top' },
      columnStyles: { 0: { fontStyle: 'bold', cellWidth: 150 } },
      body: notes,
      margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
    });
    cursorY = lastTableY(doc) + 16;
  }
  return cursorY;
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
  if (section.result.final_recommendation) {
    cursorY = addRecommendationSection(
      doc,
      cursorY,
      section.result.final_recommendation,
      section.result.findings
    );
  }
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
    styles: { fontSize: 9, cellPadding: 4, overflow: 'linebreak', valign: 'top' },
    headStyles: { fillColor: [27, 79, 216] },
    tableWidth: 'auto',
    margin: { left: PAGE_MARGIN, right: PAGE_MARGIN },
  });

  sections.forEach((section) => {
    doc.addPage();
    renderSection(doc, section, PAGE_MARGIN, true);
  });

  doc.save(timestampedFilename(setName));
}
