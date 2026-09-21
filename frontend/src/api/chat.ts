import apiClient from './client';
import type { APIResponse, ChatData, ChatRequest } from '@/types/api';
import { API_BASE } from '@/utils/constants';

export async function sendChatMessage(request: ChatRequest): Promise<ChatData> {
  const { data } = await apiClient.post<APIResponse<ChatData>>('/chat', request);
  return data.data;
}

/** Callbacks driving a single streamed chat turn - see `streamChatMessage`. */
export interface ChatStreamHandlers {
  /** Called for every incremental chunk of answer text, in order. */
  onDelta: (text: string) => void;
  /** Called once with the full answer + citations when generation completes normally. */
  onDone: (data: ChatData) => void;
  /** Called once if nothing grounded the question (equivalent shape to `onDone`). */
  onNoAnswer: (data: ChatData) => void;
  /** Called once if the request fails (network error, non-2xx response, or an in-band error event). */
  onError: (message: string) => void;
}

/**
 * Streams a chat answer via Server-Sent Events from POST /chat/stream.
 *
 * Bypasses the shared axios `apiClient` because axios (in the browser) buffers
 * the full response body before resolving, which defeats incremental
 * rendering; the native Fetch API's `ReadableStream` body reader is used
 * instead so each SSE frame can be parsed and dispatched as soon as it
 * arrives. Exactly one of `onDone` / `onNoAnswer` / `onError` fires per call,
 * after zero or more `onDelta` calls.
 */
export async function streamChatMessage(
  request: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': crypto.randomUUID(),
      },
      body: JSON.stringify(request),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    handlers.onError(err instanceof Error ? err.message : 'A network error occurred');
    return;
  }

  if (!response.ok) {
    let message = `HTTP ${response.status} ${response.statusText}`.trim();
    try {
      const body = (await response.json()) as APIResponse<never> & { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // Non-JSON error body (e.g. a proxy error page) - keep the status-line message.
    }
    handlers.onError(message);
    return;
  }

  if (!response.body) {
    handlers.onError('Streaming responses are not supported in this browser.');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let frameEnd = buffer.indexOf('\n\n');
    while (frameEnd !== -1) {
      dispatchSSEFrame(buffer.slice(0, frameEnd), handlers);
      buffer = buffer.slice(frameEnd + 2);
      frameEnd = buffer.indexOf('\n\n');
    }
  }
}

/** Parse one `event: ...\ndata: ...` SSE frame and invoke the matching handler. */
function dispatchSSEFrame(frame: string, handlers: ChatStreamHandlers): void {
  if (!frame.trim()) return;

  let event = 'message';
  let dataLine = '';
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) {
      event = line.slice('event: '.length);
    } else if (line.startsWith('data: ')) {
      dataLine = line.slice('data: '.length);
    }
  }
  if (!dataLine) return;

  const data: Record<string, unknown> = JSON.parse(dataLine);
  switch (event) {
    case 'delta':
      handlers.onDelta(data.text as string);
      break;
    case 'done':
      handlers.onDone(data as unknown as ChatData);
      break;
    case 'no_answer':
      handlers.onNoAnswer(data as unknown as ChatData);
      break;
    case 'error':
      handlers.onError((data.message as string) ?? 'Answer generation failed. Please try again.');
      break;
  }
}
