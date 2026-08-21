/**
 * Client-side port of the backend requirement normalization logic.
 *
 * Mirrors backend/radia_ai/features/jama_requirement_reviewer/utils/requirement_normalization.py
 *
 * Given PDF-extracted text from a Jama export, strips boilerplate (cover, TOC, section
 * headings) and returns just the requirement statement (the "shall" text), with
 * the metadata fields preserved for context but not sent to the AI.
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

const FIELD_LABEL_SET = new Set(FIELD_LABELS.map(([label]) => label));

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

/** Returns the matching field key if this line is exactly a known field label. */
function matchFieldLabel(line: string): string | null {
  const lowered = line.toLowerCase().replace(/:$/, '').trim();
  for (const [label, field] of FIELD_LABELS) {
    if (lowered === label) return field;
    // label + value on same line: "Project ID WR-ACR-732" or "Status Draft"
    if (lowered.startsWith(label + ' ') || lowered.startsWith(label + ':')) return field;
  }
  return null;
}

/** True if the line looks like a Jama section heading: "1 WR-ACR-732 Some Title" */
function isSectionHeading(line: string): boolean {
  return /^\d+\s+[A-Z]{2,}-[A-Z]+-\d+\b/.test(line);
}

/** True if this line starts with a known field label (label is inline prefix). */
function startsWithFieldLabel(line: string): boolean {
  const lowered = line.toLowerCase();
  for (const label of FIELD_LABEL_SET) {
    if (lowered.startsWith(label + ' ') || lowered.startsWith(label + ':')) return true;
  }
  return false;
}

/**
 * Canonicalize a Jama PDF export into just the requirement statement.
 *
 * Strategy:
 * 1. Split into lines, discard section headings.
 * 2. Parse field label / value pairs (label on its own line, value on next line(s)).
 * 3. Return the `description` field if found, otherwise the text that appeared
 *    before any metadata fields (the requirement body in Jama PDF exports).
 */
export function normalizeRequirementText(raw: string): string {
  const lines = raw
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(normalizeLine);

  const bodyParts: string[] = [];       // text before any field label
  const descriptionParts: string[] = []; // explicit Description field value
  let currentField: string | null = null;
  let currentValueParts: string[] = [];
  let descriptionActive = false;
  let seenFields = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line) continue;

    // Skip section headings like "1 WR-ACR-732 Semi-Prepared Runway Operations (SPRO)"
    if (isSectionHeading(line)) continue;

    const fieldKey = matchFieldLabel(line);
    if (fieldKey !== null) {
      seenFields = true;
      // Flush previous field
      currentField = fieldKey;
      currentValueParts = [];
      descriptionActive = fieldKey === 'description';

      // Check if value is inline on the same line
      const lowered = line.toLowerCase();
      for (const [label] of FIELD_LABELS) {
        if (lowered.startsWith(label + ' ') || lowered.startsWith(label + ':')) {
          const remainder = line.slice(label.length).replace(/^[\s:\t-]+/, '').trim();
          if (remainder) {
            currentValueParts.push(remainder);
            if (descriptionActive) descriptionParts.push(remainder);
          }
          break;
        }
      }
      continue;
    }

    if (seenFields) {
      // Line after a field label but not itself a label → it's the field value
      if (currentField !== null) {
        currentValueParts.push(line);
        if (descriptionActive) descriptionParts.push(line);
      }
    } else {
      // Before any field labels → requirement body text
      bodyParts.push(line);
    }
  }

  // Prefer an explicit Description field
  if (descriptionParts.length) {
    return descriptionParts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // Requirement body appeared before the metadata table (Jama PDF export pattern)
  if (bodyParts.length && seenFields) {
    return bodyParts.join(' ').replace(/\s+/g, ' ').trim();
  }

  // No structure detected — return the full cleaned text
  return lines.filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
}
