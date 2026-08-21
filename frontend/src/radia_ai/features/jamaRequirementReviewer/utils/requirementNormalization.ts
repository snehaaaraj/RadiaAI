/**
 * Client-side port of the backend requirement normalization logic.
 *
 * Given PDF-extracted text from a Jama export, extracts the key fields
 * (Title, Description/body, Rationale) and returns a clean structured string
 * that is shown in the UI preview and sent to the AI for review.
 */

/** Known Jama metadata field labels, longest first for greedy matching. */
const FIELD_LABELS: [label: string, field: string][] = [
  ['security effectiveness requirement', 'security_effectiveness_requirement'],
  ['requirement volatility', 'requirement_volatility'],
  ['derived requirement', 'derived_requirement'],
  ['safety requirement', 'safety_requirement'],
  ['last activity date', 'last_activity_date'],
  ['verification method', 'verification_method'],
  ['validation method', 'validation_method'],
  ['reference information', 'reference_information'],
  ['modified date', 'modified_date'],
  ['created date', 'created_date'],
  ['modified by', 'modified_by'],
  ['created by', 'created_by'],
  ['assigned to', 'assigned_to'],
  ['global id', 'global_id'],
  ['project id', 'project_id'],
  ['description', 'description'],
  ['rationale', 'rationale'],
  ['release', 'release'],
  ['status', 'status'],
  ['title', 'title'],
  ['fdal', 'fdal'],
  ['sal', 'sal'],
  ['rev', 'release'],
];

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

/** Returns [fieldKey, inlineValue] if the line starts with a known field label, else null. */
function matchFieldLabel(line: string): [string, string] | null {
  const lowered = line.toLowerCase().replace(/:$/, '').trim();
  for (const [label, field] of FIELD_LABELS) {
    if (lowered === label) return [field, ''];
    if (lowered.startsWith(label + ' ') || lowered.startsWith(label + ':')) {
      const remainder = line.slice(label.length).replace(/^[\s:\t-]+/, '').trim();
      return [field, remainder];
    }
  }
  return null;
}

/** True if the line looks like a Jama section heading: "1 WR-ACR-732 Some Title" */
function isSectionHeading(line: string): boolean {
  return /^\d+\s+[A-Z]{2,}-[A-Z]+-\d+\b/.test(line);
}

/**
 * Parse a Jama PDF export into its key fields.
 *
 * Returns the requirement body (text before the metadata table), title, and rationale
 * as separate strings. The body maps to what Jama calls "Description".
 */
function extractFields(raw: string): { body: string; title: string; rationale: string } {
  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(normalizeLine);

  const bodyParts: string[] = [];
  const fields: Record<string, string[]> = {};
  let currentField: string | null = null;
  // Track whether the current field already received its value inline (label + value on
  // same line). If so, the next non-label line is NOT a continuation — it belongs to
  // the next field or is unrelated. This matches how Jama PDF tables work: each row
  // has label | value on one line; multi-line labels (split across rows) have an empty
  // value cell and the value appears on the next line.
  let currentFieldHasInlineValue = false;
  let seenFields = false;

  for (const line of lines) {
    if (!line) continue;
    if (isSectionHeading(line)) continue;

    const match = matchFieldLabel(line);
    if (match !== null) {
      const [fieldKey, inlineValue] = match;
      seenFields = true;
      currentField = fieldKey;
      currentFieldHasInlineValue = inlineValue.length > 0;
      if (!fields[fieldKey]) fields[fieldKey] = [];
      if (inlineValue) fields[fieldKey].push(inlineValue);
      continue;
    }

    if (!seenFields) {
      bodyParts.push(line);
    } else if (currentField !== null && !currentFieldHasInlineValue) {
      // Only accumulate continuation lines when the label was alone on its line
      // (value-on-next-line pattern). Stop when we see a non-label line after an
      // inline-value field — that line is likely the next field's label split across rows.
      if (!fields[currentField]) fields[currentField] = [];
      fields[currentField].push(line);
      currentFieldHasInlineValue = true; // treat as satisfied after first continuation
    }
  }

  const joinField = (key: string) =>
    (fields[key] ?? []).join(' ').replace(/\s+/g, ' ').trim();

  // "description" field wins over the pre-field body if both exist
  const body = joinField('description') || bodyParts.join(' ').replace(/\s+/g, ' ').trim();
  const title = joinField('title');
  const rationale = joinField('rationale');

  return { body, title, rationale };
}

/**
 * Normalize a Jama PDF export into a structured string containing
 * Title, Description, and Rationale — the fields the AI uses for review.
 *
 * Falls back to the full cleaned text when no structure is detected.
 */
export function normalizeRequirementText(raw: string): string {
  const { body, title, rationale } = extractFields(raw);

  // If no structure was found, return the raw text as-is
  if (!body && !title && !rationale) {
    return raw
      .replace(/\r\n?/g, '\n')
      .split('\n')
      .map(normalizeLine)
      .filter(Boolean)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  const parts: string[] = [];
  if (title) parts.push(`Title: ${title}`);
  if (body) parts.push(`Description: ${body}`);
  if (rationale) parts.push(`Rationale: ${rationale}`);

  return parts.join('\n\n');
}
