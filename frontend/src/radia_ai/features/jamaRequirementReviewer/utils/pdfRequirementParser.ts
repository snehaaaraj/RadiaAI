import * as pdfjsLib from 'pdfjs-dist';

// Use the bundled worker from pdfjs-dist
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

export interface ParsedRequirement {
  id: string;
  title: string;
  text: string;
  section: string;
}

/**
 * Extract full text from a PDF file.
 */
async function extractTextFromPdf(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const pages: string[] = [];

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const pageText = content.items
      .map((item) => ('str' in item ? item.str : ''))
      .join(' ');
    pages.push(pageText);
  }

  return pages.join('\n');
}

/**
 * Parse extracted PDF text to find individual requirements.
 * Matches the Jama export format: WR-ACR-XXX or WR-TXT-XXXX requirement IDs
 * followed by their title and description text.
 */
function parseRequirementsFromText(fullText: string): ParsedRequirement[] {
  // Match requirement blocks: ID pattern followed by title and body text
  // Pattern: WR-ACR-### or WR-TXT-#### followed by title text
  const reqPattern = /(?:[\d.]+\s+)?(WR-(?:ACR|TXT|PLR)-\d+)\s+([^\n]+?)(?:\n|$)([\s\S]*?)(?=(?:[\d.]+\s+)?WR-(?:ACR|TXT|PLR)-\d+\s|$)/g;

  const requirements: ParsedRequirement[] = [];
  const seen = new Set<string>();

  let match: RegExpExecArray | null;

  while ((match = reqPattern.exec(fullText)) !== null) {
    const id = match[1].trim();
    const title = match[2].trim();
    const bodyRaw = match[3]?.trim() ?? '';

    if (seen.has(id)) continue;
    seen.add(id);

    // Extract the requirement statement — text before the metadata table
    // The requirement text is typically the first paragraph(s) before "Title"
    const titleFieldIndex = bodyRaw.indexOf('Title');
    const reqText = titleFieldIndex > 0
      ? bodyRaw.substring(0, titleFieldIndex).trim()
      : bodyRaw.substring(0, 500).trim();

    if (!reqText) continue;

    // Determine section from context
    const section = extractSection(fullText, match.index);

    requirements.push({
      id,
      title,
      text: reqText,
      section,
    });
  }

  // If regex didn't match well, fall back to a simpler line-based approach
  if (requirements.length === 0) {
    return parseRequirementsFallback(fullText);
  }

  return requirements;
}

/**
 * Fallback parser: split by WR-ACR/WR-TXT IDs found in text.
 */
function parseRequirementsFallback(fullText: string): ParsedRequirement[] {
  const lines = fullText.split(/\n/);
  const requirements: ParsedRequirement[] = [];
  const seen = new Set<string>();

  const idPattern = /\b(WR-(?:ACR|TXT|PLR)-\d+)\b/;

  for (let i = 0; i < lines.length; i++) {
    const match = idPattern.exec(lines[i]);
    if (!match) continue;

    const id = match[1];
    if (seen.has(id)) continue;
    seen.add(id);

    // Collect the title from the same line (after the ID)
    const afterId = lines[i].substring(match.index + match[0].length).trim();
    const title = afterId || id;

    // Collect body text: next lines until we hit another requirement ID or "Title" table row
    const bodyLines: string[] = [];
    for (let j = i + 1; j < lines.length && j < i + 30; j++) {
      if (idPattern.test(lines[j])) break;
      if (/^Title\s/.test(lines[j].trim())) break;
      bodyLines.push(lines[j]);
    }

    const text = bodyLines.join(' ').trim();
    if (!text) continue;

    requirements.push({ id, title, text, section: '' });
  }

  return requirements;
}

/**
 * Extract the section heading context for a requirement position in text.
 */
function extractSection(fullText: string, position: number): string {
  const before = fullText.substring(0, position);
  // Look for numbered section headings like "1.1 Mission" or "2.4 Design & Construction"
  const sectionMatches = before.match(/\d+(?:\.\d+)*\s+[A-Z][A-Za-z &\-,]+/g);
  return sectionMatches ? sectionMatches[sectionMatches.length - 1].trim() : '';
}

/**
 * Parse a PDF file and extract all requirements from it.
 */
export async function parseRequirementsFromPdf(file: File): Promise<ParsedRequirement[]> {
  const text = await extractTextFromPdf(file);
  return parseRequirementsFromText(text);
}
