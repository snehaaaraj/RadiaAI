/**
 * Splits chat message text into plain-text and link segments.
 *
 * Only Markdown inline links (`[label](https://...)`) become links, and only
 * for http(s) URLs; anything else (including `javascript:` URLs) stays as the
 * literal text. The backend additionally strips links to untrusted hosts from
 * live-data answers before they reach the browser.
 */

export type MessageSegment =
  | { type: 'text'; text: string }
  | { type: 'link'; text: string; href: string };

const MARKDOWN_LINK = /\[([^[\]\n]+)\]\(([^()\s]+)\)/g;

function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
  } catch {
    return null;
  }
}

export function splitMessageLinks(content: string): MessageSegment[] {
  const segments: MessageSegment[] = [];
  let last = 0;
  const pushText = (text: string) => {
    if (!text) return;
    const previous = segments[segments.length - 1];
    if (previous?.type === 'text') previous.text += text;
    else segments.push({ type: 'text', text });
  };

  for (const match of content.matchAll(MARKDOWN_LINK)) {
    const start = match.index ?? 0;
    pushText(content.slice(last, start));
    const href = safeHref(match[2]);
    if (href) segments.push({ type: 'link', text: match[1], href });
    else pushText(match[0]);
    last = start + match[0].length;
  }
  pushText(content.slice(last));
  return segments;
}
