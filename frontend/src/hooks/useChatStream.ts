/**
 * Drives a single streamed chat turn (ChatGPT-style token-by-token rendering)
 * against POST /chat/stream, exposing the in-progress answer text as it
 * arrives so the UI can render it incrementally instead of waiting for the
 * full response.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { streamChatMessage } from '@/api/chat';
import type { ChatData, ChatRequest } from '@/types/api';

export interface UseChatStreamHandlers {
  /** Called once with the final answer, either fully grounded or a "not found" refusal. */
  onDone: (data: ChatData) => void;
  /** Called once if the request fails outright (network error, bad response, or a mid-stream failure). */
  onError: (message: string) => void;
}

/**
 * Minimum fraction of the buffered-but-unrevealed backlog to reveal per
 * animation frame. On localhost (or any very fast model) whole answers can
 * arrive in a single network read, faster than the eye can register - the
 * reveal loop below decouples "text received" from "text shown" so it always
 * animates: it eats through a big backlog quickly (an easing catch-up) but
 * settles into a steady per-character trickle once caught up to the network,
 * rather than ever dumping the remaining buffer in one paint.
 */
const REVEAL_BACKLOG_FRACTION = 0.1;

/** Terminal event awaiting delivery once the reveal loop has caught up. */
type PendingTerminal = { kind: 'done' | 'no_answer'; data: ChatData };

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  // Reveal-loop state, kept in refs since it's updated far more often (every
  // animation frame) than React should re-render for.
  const pendingTextRef = useRef('');
  const displayedTextRef = useRef('');
  const pendingTerminalRef = useRef<PendingTerminal | null>(null);
  const rafRef = useRef<number | null>(null);
  const handlersRef = useRef<UseChatStreamHandlers | null>(null);

  const stopReveal = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  // Cancel any in-flight stream/animation if the component using this hook unmounts.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      stopReveal();
    };
  }, [stopReveal]);

  const tick = useCallback(() => {
    rafRef.current = null;
    const pending = pendingTextRef.current;

    if (pending.length > 0) {
      const take = Math.max(1, Math.ceil(pending.length * REVEAL_BACKLOG_FRACTION));
      displayedTextRef.current += pending.slice(0, take);
      pendingTextRef.current = pending.slice(take);
      setStreamingText(displayedTextRef.current);
      rafRef.current = requestAnimationFrame(tick);
      return;
    }

    // Backlog fully drained - deliver the terminal event now, if one arrived
    // mid-reveal, so the UI never shows a half-typed answer as "final".
    const terminal = pendingTerminalRef.current;
    if (terminal) {
      pendingTerminalRef.current = null;
      setIsStreaming(false);
      setStreamingText('');
      handlersRef.current?.onDone(terminal.data);
    }
  }, []);

  const ensureRevealing = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(tick);
    }
  }, [tick]);

  const sendMessage = useCallback(
    (request: ChatRequest, handlers: UseChatStreamHandlers) => {
      abortRef.current?.abort();
      stopReveal();
      const controller = new AbortController();
      abortRef.current = controller;
      handlersRef.current = handlers;

      pendingTextRef.current = '';
      displayedTextRef.current = '';
      pendingTerminalRef.current = null;
      setIsStreaming(true);
      setStreamingText('');

      const finishWithError = (message: string) => {
        stopReveal();
        pendingTextRef.current = '';
        pendingTerminalRef.current = null;
        setIsStreaming(false);
        setStreamingText('');
        handlers.onError(message);
      };

      streamChatMessage(
        request,
        {
          onDelta: (text) => {
            pendingTextRef.current += text;
            ensureRevealing();
          },
          onDone: (data) => {
            pendingTerminalRef.current = { kind: 'done', data };
            ensureRevealing();
          },
          onNoAnswer: (data) => {
            pendingTerminalRef.current = { kind: 'no_answer', data };
            ensureRevealing();
          },
          onError: finishWithError,
        },
        controller.signal
      ).catch((err: unknown) => {
        if (controller.signal.aborted) return;
        finishWithError(err instanceof Error ? err.message : 'A network error occurred');
      });
    },
    [ensureRevealing, stopReveal]
  );

  return { isStreaming, streamingText, sendMessage };
}
