import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import useMediaQuery from '@mui/material/useMediaQuery';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';

const BOTTOM_THRESHOLD = 48;

export function ChatConversation({
  children,
  padding = 2,
  reduceMotion = false,
}: { children?: ReactNode; padding?: number; reduceMotion?: boolean }) {
  const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef(true);
  const smoothScrollingRef = useRef(false);
  const [showScrollButton, setShowScrollButton] = useState(false);

  const scrollToEnd = () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (!reduceMotion && !prefersReducedMotion) {
      smoothScrollingRef.current = true;
      followingRef.current = false;
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
      return;
    }
    viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    smoothScrollingRef.current = false;
    followingRef.current = true;
    setShowScrollButton(false);
  };

  const interruptScroll = () => {
    const viewport = viewportRef.current;
    if (!viewport || !smoothScrollingRef.current) return;
    smoothScrollingRef.current = false;
    followingRef.current = false;
    viewport.scrollTo({ top: viewport.scrollTop, behavior: 'instant' });
  };

  // Follow committed messages, streamed tokens, and asynchronously restored history.
  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (smoothScrollingRef.current) {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
    } else if (followingRef.current) {
      viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    }
  });

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    const content = contentRef.current;
    if (!viewport || !content || typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(() => {
      if (smoothScrollingRef.current) {
        viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
      } else if (followingRef.current) {
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
        onWheel={interruptScroll}
        onTouchStart={interruptScroll}
        onKeyDown={(event) => {
          if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) {
            interruptScroll();
          }
        }}
        onScroll={() => {
          const viewport = viewportRef.current;
          if (!viewport) return;
          const awayFromBottom =
            viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop > BOTTOM_THRESHOLD;
          if (smoothScrollingRef.current) {
            const atEnd = viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop <= 1;
            smoothScrollingRef.current = !atEnd;
            followingRef.current = atEnd;
            setShowScrollButton(!atEnd);
            return;
          }
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
