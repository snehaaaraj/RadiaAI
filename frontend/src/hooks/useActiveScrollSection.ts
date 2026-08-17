/**
 * useActiveScrollSection
 *
 * Tracks which section ID is currently "active" based on window scroll
 * position. Active = the last section whose top edge has scrolled past
 * the top threshold (header height + a small buffer).
 *
 * Uses a passive scroll listener so it never blocks the main thread.
 * Automatically re-attaches when `enabled` changes (e.g. entering/leaving
 * the Settings page).
 */

import { useEffect, useRef, useState } from 'react';
import { HEADER_HEIGHT } from '@/utils/constants';

const THRESHOLD = HEADER_HEIGHT + 32; // px from top of viewport

function getActiveSection(sectionIds: readonly string[]): string | null {
  let active: string | null = null;
  for (const id of sectionIds) {
    const el = document.getElementById(id);
    if (!el) continue;
    const top = el.getBoundingClientRect().top;
    if (top <= THRESHOLD) {
      active = id;
    }
  }
  return active;
}

export function useActiveScrollSection(
  sectionIds: readonly string[],
  enabled: boolean,
  fallback: string,
): string {
  const [activeId, setActiveId] = useState<string>(() => {
    if (!enabled) return fallback;
    return (getActiveSection(sectionIds) ?? window.location.hash.replace('#', '')) || fallback;
  });

  // Keep a stable ref to sectionIds to avoid re-registering the listener
  const sectionIdsRef = useRef(sectionIds);
  sectionIdsRef.current = sectionIds;

  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  useEffect(() => {
    if (!enabled) return;

    // Seed immediately in case the page is already scrolled (e.g. hash in URL)
    const seed = (getActiveSection(sectionIdsRef.current) ??
      window.location.hash.replace('#', '')) ||
      fallbackRef.current;
    setActiveId(seed);

    const handleScroll = () => {
      const next = getActiveSection(sectionIdsRef.current) ?? fallbackRef.current;
      setActiveId((prev) => {
        if (prev === next) return prev; // avoid unnecessary re-renders
        if (window.location.hash !== `#${next}`) {
          window.history.replaceState(null, '', `#${next}`);
        }
        return next;
      });
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [enabled]);

  return activeId;
}
