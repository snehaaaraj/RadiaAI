import { useCallback } from 'react';
import { useAppContext } from '@/context/AppContext';

/**
 * Plays a short two-tone chime using the Web Audio API when a review completes.
 * Respects the `soundOnReviewComplete` preference from AppContext.
 * No external audio files needed — synthesized directly in the browser.
 */
export function useReviewCompleteSound() {
  const { soundOnReviewComplete } = useAppContext();

  const play = useCallback(() => {
    if (!soundOnReviewComplete) return;

    try {
      const ctx = new AudioContext();

      // Two-note ascending chime: C5 then E5
      const notes = [523.25, 659.25];
      notes.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.18);

        gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.18);
        gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + i * 0.18 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.35);

        osc.start(ctx.currentTime + i * 0.18);
        osc.stop(ctx.currentTime + i * 0.18 + 0.35);
      });

      // Close context after sound finishes
      setTimeout(() => ctx.close(), 800);
    } catch {
      // Web Audio not supported — silently ignore
    }
  }, [soundOnReviewComplete]);

  return play;
}
