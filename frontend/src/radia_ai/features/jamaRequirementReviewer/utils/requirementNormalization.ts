/**
 * Client-side port of the backend requirement normalization logic.
 *
 * Mirrors backend/radia_ai/features/jama_requirement_reviewer/utils/requirement_normalization.py
 * with an additional pre-processing step for PDF-extracted text where all content
 * is collapsed into a single line (pdfjs joins tokens with spaces).
 *
 * If the text looks like a fielded document, only the "Description" / requirement
 * body is returned. Otherwise the full text is returned as-is.
 */

const FIELD_LABELS: [label: string, field: string][] = [
  ['project id', 'project_id'],
  ['global id', 'global_id'],
  ['status', 'status'],
  ['release', 'release'],
  ['rev', 'release'],
  ['assigned to', 'assigned_to'],
  ['title', 'title'],
  ['description', 'description'],
  ['requirement volatility', 'requirement_volatility'],
  ['rationale', 'rationale'],
  ['fdal', 'fdal'],
  ['sal', 'sal'],
  ['derived requirement', 'derived_requirement'],
  ['safety requirement', 'safety_requirement'],
  ['security effectiveness requirement', 'security_effectiveness_requirement'],
  ['validation method', 'validation_method'],
  ['verification method', 'verification_method'],
  ['reference information', 'reference_information'],
  ['created by', 'created_by'],
  ['created date', 'created_date'],
  ['modified by', 'modified_by'],
  ['modified date', 'modified_date'],
  ['last activity date', 'last_activity_date'],
];

/**
 * Build a regex that splits on any known field label (case-insensitive).
 * Sorted longest-first so multi-word labels match before their substrings.
 */
function buildFieldSplitRegex(): RegExp {
  const sorted = [...FIELD_LABELS]
    .map(([label]) => label)
    .sort((a, b) => b.length - a.length)
    .map((l) => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')); // escape regex chars
  return new RegExp(`(?=${sorted.join('|')})`, 'gi');
}

const FIELD_SPLIT_RE = buildFieldSplitRegex();

function stripMarkdownLinks(line: string): string {
  return line.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
}

function normalizeLine(line: string): string {
  let l = line.replace(/\t/g, ' ').replace(/\s+/g, ' ').trim();
  l = l.replace(/^\s*[-*•]+\s*/, '');
  l = stripMarkdownLinks(l);
  l = l.replace(/^\*{1,2}/, '').replace(/\*{1,2}$/, '');
  return l.trim();
}

/**
 * Pre-process raw extracted text.
 * If the text is heavily collapsed (few newlines relative to length) this
 * inserts synthetic newlines before each field label so the parser can work.
 */
function preProcess(raw: string): string {
  const normalised = raw.replace(/\r\n?/g, '\n');
  const lineCount = (normalised.match(/\n/g) ?? []).length;
  const charCount = normalised.length;

  // Heuristic: if fewer than 1 newline per 200 chars, treat as collapsed
  if (charCount > 200 && lineCount < charCount / 200) {
    return normalised.replace(FIELD_SPLIT_RE, '\n');
  }
  return normalised;
}

/** Try to match a known field label starting at `index` in `lines`. */
function consumeLabel(
  lines: string[],
  index: number,
): { field: string; span: number; remainder: string } | null {
  const maxWidth = Math.min(4, lines.length - index);
  for (let width = maxWidth; width >= 1; width--) {
    const candidateParts = lines.slice(index, index + width).filter(Boolean);
    if (!candidateParts.length) continue;
    const candidate = candidateParts.join(' ');
    const lowered = candidate.toLowerCase().replace(/:$/, '').trimEnd();
    for (const [label, field] of FIELD_LABELS) {
      if (lowered === label) {
        return { field, span: width, remainder: '' };
      }
      if (lowered.startsWith(label + ' ') || lowered.startsWith(label + ':')) {
        const remainder = candidate.slice(label.length).replace(/^[\s:\t-]+/, '').trim();
        return { field, span: width, remainder };
      }
    }
  }
  return null;
}

/**
 * Canonicalize structured requirement text into the plain requirement statement.
 *
 * Returns the description field value if the text is fielded Jama output,
 * otherwise returns the full cleaned text.
 */
export function normalizeRequirementText(raw: string): string {
  const processed = preProcess(raw);
  const lines = processed
    .split('\n')
    .map(normalizeLine);

  const descriptionParts: string[] = [];
  const preFieldParts: string[] = []; // text before any field label is encountered
  let currentField: string | null = null;
  let descriptionActive = false;
  let currentValueParts: string[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line) { i++; continue; }

    const match = consumeLabel(lines, i);
    if (match !== null) {
      currentField = match.field;
      currentValueParts = [];
      descriptionActive = match.field === 'description';
      if (match.remainder) {
        currentValueParts.push(match.remainder);
        if (descriptionActive) descriptionParts.push(match.remainder);
      }
      i += match.span;
      continue;
    }

    if (currentField === null) {
      // Text before any field label — likely the requirement body from a PDF export
      preFieldParts.push(line);
    } else {
      currentValueParts.push(line);
      if (descriptionActive) descriptionParts.push(line);
    }
    i++;
  }

  // Prefer an explicit Description field
  if (descriptionParts.length) {
    return descriptionParts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // Fall back to text that appeared before metadata fields (PDF pattern)
  if (preFieldParts.length && currentField !== null) {
    // currentField !== null means we did encounter field labels, so preFieldParts
    // is the requirement body that preceded the metadata block.
    return preFieldParts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // No structured fields found — return the cleaned text as-is
  return lines.filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
