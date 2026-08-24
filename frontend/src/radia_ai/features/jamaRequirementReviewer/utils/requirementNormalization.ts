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

const CORE_FIELD_LABELS = new Set(['title', 'description', 'rationale']);
const TRAILING_METADATA_LABELS = FIELD_LABELS.map(([label]) => label).filter((label) => !CORE_FIELD_LABELS.has(label));

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

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function truncateAtTrailingMetadata(line: string): string {
  const lowered = line.toLowerCase();
  let cutoff = line.length;
  for (const label of TRAILING_METADATA_LABELS) {
    const regex = new RegExp(`\\b${escapeRegex(label)}\\b`, 'i');
    const match = regex.exec(lowered);
    if (match && match.index < cutoff) {
      cutoff = match.index;
    }
  }
  return line.slice(0, cutoff).trimEnd();
}

function containsTrailingMetadata(line: string): boolean {
  return TRAILING_METADATA_LABELS.some((label) => {
    const regex = new RegExp(`\\b${escapeRegex(label)}\\b`, 'i');
    return regex.test(line);
  });
}

/** True if the line looks like a Jama section heading: "1 WR-ACR-732 Some Title" */
function isSectionHeading(line: string): boolean {
  return /^\d+\s+[A-Z]{2,}-[A-Z]+-\d+\b/.test(line);
}

function extractHeadingTitle(line: string): string {
  return line.replace(/^\d+\s+[A-Z]{2,}-[A-Z]+-\d+\s+/, '').trim();
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
  let seenFields = false;
  let stopParsing = false;
  let headingTitle = '';

  for (const line of lines) {
    if (!line) continue;
    if (stopParsing) break;
    if (isSectionHeading(line)) {
      if (!headingTitle) headingTitle = extractHeadingTitle(line);
      continue;
    }

    const match = matchFieldLabel(line);
    if (match !== null) {
      const [fieldKey, inlineValue] = match;
      seenFields = true;
      currentField = fieldKey;
      if (!fields[fieldKey]) fields[fieldKey] = [];
      const content = truncateAtTrailingMetadata(inlineValue);
      if (content) fields[fieldKey].push(content);
      if (containsTrailingMetadata(inlineValue)) stopParsing = true;
      continue;
    }

    if (!seenFields) {
      bodyParts.push(line);
    } else if (currentField !== null) {
      const content = truncateAtTrailingMetadata(line);
      if (content) {
        if (!fields[currentField]) fields[currentField] = [];
        fields[currentField].push(content);
      }
      if (containsTrailingMetadata(line)) {
        stopParsing = true;
      }
    }
  }

  const joinField = (key: string) =>
    (fields[key] ?? []).join(' ').replace(/\s+/g, ' ').trim();

  // "description" field wins over the pre-field body if both exist
  const body = joinField('description') || bodyParts.join(' ').replace(/\s+/g, ' ').trim();
  const title = joinField('title') || headingTitle;
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
