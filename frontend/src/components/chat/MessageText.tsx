import Link from '@mui/material/Link';
import { splitMessageLinks } from '@/utils/messageLinks';

function renderText(text: string, keyPrefix: string) {
  return text.split(/(\*\*[\s\S]+?\*\*)/g).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={key} style={{ fontWeight: 700 }}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

/** Renders chat message text, including bold Markdown and safe links. */
export function MessageText({ content }: { content: string }) {
  return (
    <>
      {splitMessageLinks(content).map((segment, i) =>
        segment.type === 'link' ? (
          <Link
            key={i}
            href={segment.href}
            target="_blank"
            rel="noopener noreferrer"
            color="inherit"
            underline="always"
          >
            {segment.text}
          </Link>
        ) : (
          renderText(segment.text, `text-${i}`)
        ),
      )}
    </>
  );
}
