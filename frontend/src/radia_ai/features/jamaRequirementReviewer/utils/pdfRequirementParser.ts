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
  /** Full raw text of the requirement block (including metadata fields) for normalization. */
  rawText: string;
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
 *
 * Strategy: anchor on "Title <value> Release" patterns in the metadata tables,
 * then look backwards to find the WR-xxx-### ID that owns each Title field.
 * This naturally excludes cross-references (like "see WR-ACR-155") because
 * they don't have their own Title metadata fields.
 */
function parseRequirementsFromText(fullText: string): ParsedRequirement[] {
  // Step 1: find all "Title <Value> Release" metadata field patterns
  // These mark the metadata table of each real requirement
  const titleFieldRegex = /\bTitle\s+(\S[\s\S]{1,200}?)\s+Release\b/g;
  const titleAnchors: { titleValue: string; index: number }[] = [];
  let tm: RegExpExecArray | null;
  while ((tm = titleFieldRegex.exec(fullText)) !== null) {
    // Skip TOC entries
    const nearby = fullText.substring(Math.max(0, tm.index - 30), tm.index + 20);
    if (/\.{4,}/.test(nearby)) continue;
    titleAnchors.push({
      titleValue: tm[1].replace(/\s+/g, ' ').trim(),
      index: tm.index,
    });
  }

  if (titleAnchors.length === 0) return [];

  // Step 2: for each Title anchor, search backwards to find the nearest WR-xxx-### ID
  // That ID is the requirement this Title field belongs to
  const idRegex = /\b(WR-(?:ACR|TXT|PLR)-\d+)\b/g;
  const allIdHits: { id: string; index: number }[] = [];
  let im: RegExpExecArray | null;
  while ((im = idRegex.exec(fullText)) !== null) {
    allIdHits.push({ id: im[1], index: im.index });
  }

  interface ReqAnchor { id: string; idIndex: number; titleValue: string; titleIndex: number }
  const anchors: ReqAnchor[] = [];
  const usedIds = new Set<string>();
  let searchFromPos = 0; // start of text (after previous requirement's end)

  for (const ta of titleAnchors) {
    // Find the FIRST un-claimed WR-xxx ID that appears between the previous
    // requirement's end and this Title field. This is the heading ID, not cross-refs.
    let bestHit: { id: string; index: number } | null = null;
    for (const h of allIdHits) {
      if (h.index < searchFromPos) continue; // before our search window
      if (h.index >= ta.index) break; // past this Title field
      // Skip TOC entries
      const nearId = fullText.substring(h.index, Math.min(fullText.length, h.index + 200));
      if (/\.{4,}/.test(nearId)) continue;
      // Skip if this ID was already claimed by an earlier Title
      if (usedIds.has(h.id)) continue;
      // Take the first match — it's the heading ID
      bestHit = h;
      break;
    }
    if (!bestHit) continue;
    usedIds.add(bestHit.id);
    anchors.push({
      id: bestHit.id,
      idIndex: bestHit.index,
      titleValue: ta.titleValue,
      titleIndex: ta.index,
    });
    // Next requirement should start after this Title field's metadata block
    // (after "Security Effectiveness Requirement No")
    searchFromPos = ta.index;
  }

  if (anchors.length === 0) return [];

  // Step 3: build blocks — each requirement runs from its ID to the next requirement's ID
  const requirements: ParsedRequirement[] = [];

  for (let i = 0; i < anchors.length; i++) {
    const a = anchors[i];
    const endPos = i + 1 < anchors.length ? anchors[i + 1].idIndex : fullText.length;

    let rawBlock = fullText.substring(a.idIndex, endPos).trim();
    rawBlock = rawBlock.replace(/\s*Radia Production\s+Page \d+ of \d+\s*/g, ' ').trim();
    if (!rawBlock) continue;

    // Description: text between the ID and the Title field
    const descStart = a.id.length;
    const descEnd = a.titleIndex - a.idIndex;
    const description = descEnd > descStart
      ? rawBlock.substring(descStart, descEnd).replace(/\s+/g, ' ').trim()
      : '';

    const section = extractSection(fullText, a.idIndex);

    requirements.push({
      id: a.id,
      title: a.titleValue,
      text: description || rawBlock.substring(0, 300),
      rawText: rawBlock,
      section,
    });
  }

  // Step 4: second pass — find heading-level WR-xxx IDs that have no Title/Release
  // metadata table (e.g., WR-TXT-6529, WR-TXT-6523). These are identified by being
  // preceded by a section number (like "1.1.4.1") in the flat text.
  const claimedIds = new Set(anchors.map((a) => a.id));
  const headingIdRegex = /(?:\d+(?:\.\d+)+\s+)(WR-(?:ACR|TXT|PLR)-\d+)\b/g;
  interface HeadingOnly { id: string; index: number }
  const headingOnlyItems: HeadingOnly[] = [];
  let hm: RegExpExecArray | null;
  while ((hm = headingIdRegex.exec(fullText)) !== null) {
    const hid = hm[1];
    if (claimedIds.has(hid)) continue;
    // Skip TOC
    const nearH = fullText.substring(hm.index, Math.min(fullText.length, hm.index + 200));
    if (/\.{4,}/.test(nearH)) continue;
    if (claimedIds.has(hid)) continue; // double-check
    claimedIds.add(hid);
    headingOnlyItems.push({ id: hid, index: hm.index + hm[0].length - hid.length });
  }

  // Merge heading-only items into the requirements list
  for (const ho of headingOnlyItems) {
    // Find next requirement or heading that starts after this one
    let endPos = fullText.length;
    // Check against both anchored reqs and other heading-only items
    for (const a of anchors) {
      if (a.idIndex > ho.index) { endPos = Math.min(endPos, a.idIndex); break; }
    }
    for (const other of headingOnlyItems) {
      if (other.index > ho.index && other.index < endPos) { endPos = other.index; }
    }

    let rawBlock = fullText.substring(ho.index, endPos).trim();
    rawBlock = rawBlock.replace(/\s*Radia Production\s+Page \d+ of \d+\s*/g, ' ').trim();
    if (!rawBlock) continue;

    // Extract heading name: text immediately after the ID until first sentence end
    const afterId = rawBlock.substring(ho.id.length).replace(/^\s+/, '');
    const headingEnd = afterId.search(/(?:The |While |All |Unless |Equipment |Major |Mechanical |Aircraft |Mating |The |\d+\.\d+)/);
    const title = headingEnd > 0
      ? afterId.substring(0, headingEnd).replace(/\s+/g, ' ').trim()
      : afterId.substring(0, 80).replace(/\s+/g, ' ').trim();

    const description = headingEnd > 0
      ? afterId.substring(headingEnd).replace(/\s+/g, ' ').trim().substring(0, 500)
      : '';

    const section = extractSection(fullText, ho.index);

    requirements.push({
      id: ho.id,
      title: title || ho.id,
      text: description || rawBlock.substring(0, 300),
      rawText: rawBlock,
      section,
    });
  }

  // Sort all requirements by their position in the document
  requirements.sort((a, b) => {
    const posA = fullText.indexOf(a.id);
    const posB = fullText.indexOf(b.id);
    return posA - posB;
  });

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
