import Link from '@mui/material/Link';
import { splitMessageLinks } from '@/utils/messageLinks';

/** Renders chat message text, turning safe Markdown links into clickable links. */
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
          <span key={i}>{segment.text}</span>
        ),
      )}
    </>
  );
}
