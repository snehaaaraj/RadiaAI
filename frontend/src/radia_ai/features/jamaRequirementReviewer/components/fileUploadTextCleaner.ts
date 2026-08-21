const TRAILING_METADATA_LABELS = [
  'Requirement Volatility',
  'Derived Requirement',
  'Safety Requirement',
  'Security Effectiveness Requirement',
  'Validation Method',
  'Verification Method',
  'Last Activity Date',
  'Modified Date',
];

/**
 * Cleans raw text extracted from a PDF.
 * - Removes Jama export cover/TOC pages (header lines like "Radia Production Page N of M",
 *   "TABLE OF CONTENTS", "Produced by ...", dotted TOC lines)
 * - Strips page-number-only lines
 * - Collapses excessive blank lines
 * - Truncates trailing Jama metadata after the rationale section
 */
export function cleanExtractedText(raw: string): string {
  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n');

  const cleaned = lines.filter((line) => {
    const t = line.trim();
    if (!t) return true;
    if (/^Radia Production(\s+Page \d+ of \d+)?$/i.test(t)) return false;
    if (/^Page \d+ of \d+$/i.test(t)) return false;
    if (/^Produced by .+\d{4}/i.test(t)) return false;
    if (/^Radia WindRunner Aircraft Project/i.test(t)) return false;
    if (/^Item:\s+/i.test(t)) return false;
    if (/,\s*Radia Production\b/i.test(t)) return false;
    if (/^T\s*A\s*B\s*L\s*E\s+O\s*F\s+C\s*O\s*N\s*T\s*E\s*N\s*T\s*S$/i.test(t)) return false;
    if (/\.{5,}\s*\d+\s*$/.test(t)) return false;
    if (/^\s*\d+\s*$/.test(t)) return false;
    return true;
  });

  const structured = truncateTrailingMetadata(cleaned);

  return structured
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .trim();
}

function truncateTrailingMetadata(lines: string[]): string[] {
  const rationaleIndex = lines.findIndex((line) => /^Rationale\b/i.test(line.trim()));
  if (rationaleIndex === -1) return lines;

  const metadataIndex = findTrailingMetadataIndex(lines, rationaleIndex + 1);
  if (metadataIndex === -1) return lines;

  return lines.slice(0, metadataIndex);
}

function findTrailingMetadataIndex(lines: string[], startIndex: number): number {
  for (let index = startIndex; index < lines.length; index += 1) {
    for (let width = 4; width >= 1; width -= 1) {
      const candidate = lines.slice(index, index + width);
      if (candidate.length !== width) continue;
      if (candidate.some((line) => !line.trim())) continue;

      const joined = candidate.join(' ').toLowerCase().replace(/[:]/g, '').replace(/\s+/g, ' ').trim();
      if (TRAILING_METADATA_LABELS.some((label) => isMetadataLabelMatch(joined, label))) {
        return index;
      }
    }
  }

  return -1;
}

function isMetadataLabelMatch(candidate: string, label: string): boolean {
  const normalizedLabel = label.toLowerCase();
  return candidate === normalizedLabel || candidate.startsWith(`${normalizedLabel} `);
}
