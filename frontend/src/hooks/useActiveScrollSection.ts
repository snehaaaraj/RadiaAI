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
const HASH_SETTLE_MS = 120; // debounce before writing the URL hash

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

  // Keep stable refs to avoid re-registering the listener on every render
  const sectionIdsRef = useRef(sectionIds);
  sectionIdsRef.current = sectionIds;

  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  const hashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled) return;

    // Seed immediately in case the page is already scrolled (e.g. hash in URL)
    const seed =
      (getActiveSection(sectionIdsRef.current) ?? window.location.hash.replace('#', '')) ||
      fallbackRef.current;
    setActiveId(seed);

    const handleScroll = () => {
      const next = getActiveSection(sectionIdsRef.current) ?? fallbackRef.current;

      // Update sidebar highlight immediately
      setActiveId((prev) => (prev === next ? prev : next));

      // Debounce URL hash update so it only writes once the scroll settles
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
      if (hashTimerRef.current) clearTimeout(hashTimerRef.current);
    };
  }, [enabled]);

  return activeId;
}
