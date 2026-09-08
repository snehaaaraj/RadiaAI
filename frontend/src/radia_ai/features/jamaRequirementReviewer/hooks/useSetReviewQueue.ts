import { useCallback, useEffect, useRef, useState } from 'react';
import { reviewRequirement } from '@/radia_ai/features/jamaRequirementReviewer/api/review';
import { extractErrorInfo } from '@/utils/errorInfo';
import type { RequirementReviewInput, RequirementReviewResponse } from '@/types/api';

/** Maximum number of requirement reviews executed concurrently. */
export const SET_REVIEW_CONCURRENCY = 10;

export type SetReviewItemState = 'pending' | 'queued' | 'reviewing' | 'done' | 'error';

export interface SetReviewQueueItem {
  key: string;
  payload: RequirementReviewInput;
}

export interface SetReviewItemError {
  /** Backend error code, e.g. LLM_ERROR, RATE_LIMITED, TIMEOUT_ERROR. */
  code: string;
  /** Human-readable reason straight from the backend where available. */
  message: string;
  detail: Record<string, unknown>;
  /** Correlation id for tracing the failure in backend logs. */
  requestId: string;
  /** The original rejection value, for ErrorDisplay's full breakdown. */
  raw: unknown;
}

export interface SetReviewItemStatus {
  state: SetReviewItemState;
  result?: RequirementReviewResponse;
  error?: SetReviewItemError;
}

type StatusMap = Record<string, SetReviewItemStatus>;

/**
 * Pulls the most specific human-readable text out of a backend error `detail`
 * payload. Generic envelope messages like "Request validation failed" are
 * useless in a list row, so we surface the underlying cause where present.
 */
function detailSummary(detail: Record<string, unknown>): string | null {
  // Pydantic/FastAPI validation errors: { errors: [{ loc, msg, type }] }
  const errors = detail.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    const parts = errors.slice(0, 3).map((entry) => {
      if (!entry || typeof entry !== 'object') return String(entry);
      const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
      const field = Array.isArray(loc) ? loc.filter((p) => p !== 'body').join('.') : '';
      return field ? `${field}: ${String(msg ?? '')}` : String(msg ?? '');
    });
    const suffix = errors.length > 3 ? ` (+${errors.length - 3} more)` : '';
    return parts.filter(Boolean).join('; ') + suffix;
  }

  // Azure/LLM failures wrap the upstream reason.
  for (const key of ['original_error', 'reason', 'stage', 'detail']) {
    const value = detail[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }

  return null;
}

/**
 * Normalises any rejection into the same structured shape ErrorDisplay uses, so
 * a failed item can report the real backend code/message instead of a generic
 * "unknown reason" placeholder.
 */
function toItemError(err: unknown): SetReviewItemError {
  const info = extractErrorInfo(err);
  return { ...info, raw: err };
}

/** One-line summary suitable for a list row or inline alert. */
export function formatSetReviewError(error: SetReviewItemError): string {
  const message = error.message?.trim() ?? '';
  const specifics = detailSummary(error.detail ?? {});
  const status = error.detail?.http_status;

  const body = specifics && specifics !== message
    ? message
      ? `${message} - ${specifics}`
      : specifics
    : message;

  const code = error.code && error.code !== 'UNKNOWN_ERROR' ? error.code : null;
  const statusSuffix = typeof status === 'number' ? ` [HTTP ${status}]` : '';

  if (code) return `${code}: ${body || 'Review failed'}${statusSuffix}`;
  return `${body || 'Review failed'}${statusSuffix}`;
}

/**
 * Runs a batch of requirement reviews with bounded concurrency so the user only
 * has to trigger the review once for the whole set. Items start as soon as a
 * worker slot frees up rather than waiting for the user to step to them.
 */
export function useSetReviewQueue() {
  const [statuses, setStatuses] = useState<StatusMap>({});
  const [isRunning, setIsRunning] = useState(false);
  const inFlightRef = useRef<Set<string>>(new Set());
  const cancelledRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cancelledRef.current = true;
    };
  }, []);

  const patch = useCallback((key: string, status: SetReviewItemStatus) => {
    if (!mountedRef.current) return;
    setStatuses((prev) => ({ ...prev, [key]: status }));
  }, []);

  const runOne = useCallback(
    async (item: SetReviewQueueItem) => {
      inFlightRef.current.add(item.key);
      patch(item.key, { state: 'reviewing' });
      try {
        const result = await reviewRequirement(item.payload);
        patch(item.key, { state: 'done', result });
      } catch (err) {
        patch(item.key, { state: 'error', error: toItemError(err) });
      } finally {
        inFlightRef.current.delete(item.key);
      }
    },
    [patch]
  );

  /** Enqueues every provided item and processes them with bounded concurrency. */
  const runQueue = useCallback(
    async (items: SetReviewQueueItem[]) => {
      const pending = items.filter((item) => !inFlightRef.current.has(item.key));
      if (pending.length === 0) return;

      cancelledRef.current = false;
      setIsRunning(true);
      setStatuses((prev) => {
        const next = { ...prev };
        for (const item of pending) next[item.key] = { state: 'queued' };
        return next;
      });

      let cursor = 0;
      const worker = async () => {
        while (!cancelledRef.current) {
          const index = cursor;
          cursor += 1;
          if (index >= pending.length) return;
          await runOne(pending[index]);
        }
      };

      const workerCount = Math.min(SET_REVIEW_CONCURRENCY, pending.length);
      await Promise.all(Array.from({ length: workerCount }, worker));

      if (mountedRef.current) setIsRunning(false);
    },
    [runOne]
  );

  /** Re-runs a single item, e.g. after a failure. */
  const runSingle = useCallback(
    async (item: SetReviewQueueItem) => {
      if (inFlightRef.current.has(item.key)) return;
      cancelledRef.current = false;
      await runOne(item);
    },
    [runOne]
  );

  const reset = useCallback(() => {
    cancelledRef.current = true;
    inFlightRef.current.clear();
    setStatuses({});
    setIsRunning(false);
  }, []);

  return { statuses, isRunning, runQueue, runSingle, reset };
}
