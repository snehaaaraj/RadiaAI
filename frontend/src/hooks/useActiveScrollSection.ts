/**
 * useActiveScrollSection
 *
 * Tracks which section ID is "active" in the sidebar based on scroll position.
 *
 * Strategy: the active section is the one whose top edge is closest to (but
 * still above) the threshold line (header + buffer). On a sidebar click the
 * target is locked immediately and scroll events are suppressed for a short
 * window so the smooth-scroll animation doesn't fight the highlight.
 */

import { useEffect, useRef, useState } from 'react';
import { HEADER_HEIGHT } from '@/utils/constants';

const THRESHOLD = HEADER_HEIGHT + 32;   // px from viewport top — "past this = active"
const SCROLL_LOCK_MS = 800;             // ignore scroll events after a programmatic click
const HASH_SETTLE_MS = 120;             // debounce before writing the URL hash

function getActiveSection(sectionIds: readonly string[]): string | null {
  // Walk sections in order; keep updating `active` as long as a section's top
  // has crossed the threshold. Result = the deepest section that is "above" the line.
  let active: string | null = null;
  for (const id of sectionIds) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (el.getBoundingClientRect().top <= THRESHOLD) {
      active = id;
    }
  }
  return active;
}

export function useActiveScrollSection(
  sectionIds: readonly string[],
  enabled: boolean,
  fallback: string,
): [string, (id: string) => void] {
  const [activeId, setActiveId] = useState<string>(() => {
    if (!enabled) return fallback;
    return (getActiveSection(sectionIds) ?? window.location.hash.replace('#', '')) || fallback;
  });

  const sectionIdsRef = useRef(sectionIds);
  sectionIdsRef.current = sectionIds;

  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  const hashTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lockTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollLockedRef = useRef(false);

  // Called by the sidebar on a manual click — locks scroll tracking briefly.
  const setTarget = (id: string) => {
    if (lockTimerRef.current) clearTimeout(lockTimerRef.current);
    scrollLockedRef.current = true;
    setActiveId(id);
    if (window.location.hash !== `#${id}`) {
      window.history.replaceState(null, '', `#${id}`);
    }
    lockTimerRef.current = setTimeout(() => {
      scrollLockedRef.current = false;
    }, SCROLL_LOCK_MS);
  };

  useEffect(() => {
    if (!enabled) return;

    // Seed on entry
    const seed =
      (getActiveSection(sectionIdsRef.current) ?? window.location.hash.replace('#', '')) ||
      fallbackRef.current;
    setActiveId(seed);

    const handleScroll = () => {
      if (scrollLockedRef.current) return; // ignore while a click-scroll is in flight

      const next = getActiveSection(sectionIdsRef.current) ?? fallbackRef.current;
      setActiveId((prev) => (prev === next ? prev : next));

      if (hashTimerRef.current) clearTimeout(hashTimerRef.current);
      hashTimerRef.current = setTimeout(() => {
        if (window.location.hash !== `#${next}`) {
          window.history.replaceState(null, '', `#${next}`);
        }
      }, HASH_SETTLE_MS);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (hashTimerRef.current)  clearTimeout(hashTimerRef.current);
      if (lockTimerRef.current)  clearTimeout(lockTimerRef.current);
    };
  }, [enabled]);

  return [activeId, setTarget];
}

