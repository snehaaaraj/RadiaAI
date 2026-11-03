import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';

const BOTTOM_THRESHOLD = 48;

export function ChatConversation({ children, padding = 2 }: { children?: ReactNode; padding?: number }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  const scrollToEnd = () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    followingRef.current = true;
    setShowScrollButton(false);
  };

  // Follow committed messages, streamed tokens, and asynchronously restored history.
  useLayoutEffect(() => {
    if (followingRef.current) scrollToEnd();
  });

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    const content = contentRef.current;
    if (!viewport || !content || typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(() => {
      if (followingRef.current) {
        viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      } else {
        const awayFromBottom =
          viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop > BOTTOM_THRESHOLD;
        followingRef.current = !awayFromBottom;
        setShowScrollButton(awayFromBottom);
      }
    });
    observer.observe(viewport);
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  return (
    <Box sx={{ position: 'relative', display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0 }}>
      <Box
        ref={viewportRef}
        role="region"
        aria-label="Conversation"
        onScroll={() => {
          const viewport = viewportRef.current;
          if (!viewport) return;
          const awayFromBottom =
            viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop > BOTTOM_THRESHOLD;
          followingRef.current = !awayFromBottom;
          setShowScrollButton(awayFromBottom);
        }}
        sx={{
          flexGrow: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          overflowAnchor: 'none',
          bgcolor: 'background.default',
          p: padding,
        }}
      >
        <Box ref={contentRef} sx={{ minHeight: '100%' }}>
          {children}
        </Box>
      </Box>
      {showScrollButton && (
        <IconButton
          aria-label="Scroll to latest message"
          title="Scroll to latest message"
          onClick={scrollToEnd}
          sx={{
            position: 'absolute',
            bottom: 12,
            left: '50%',
            transform: 'translateX(-50%)',
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            boxShadow: 2,
            '&:hover': { bgcolor: 'background.default' },
          }}
        >
          <ArrowDownwardIcon />
        </IconButton>
      )}
    </Box>
  );
}
