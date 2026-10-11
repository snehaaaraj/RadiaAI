import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatStreamHandlers } from '@/api/chat';
import type { ChatData, ChatRequest } from '@/types/api';
import { useChatStream } from './useChatStream';

const mocks = vi.hoisted(() => ({
  stream: vi.fn<(request: ChatRequest, handlers: ChatStreamHandlers, signal: AbortSignal) => Promise<void>>(),
}));
vi.mock('@/api/chat', () => ({ streamChatMessage: mocks.stream }));

const answer: ChatData = { answer: 'Answer', citations: [], model: 'test', retrieval_count: 0 };

describe('chat stream lifecycle', () => {
  let frame: FrameRequestCallback;
  const schedule = vi.fn();
  const cancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.stream.mockResolvedValue(undefined);
    schedule.mockImplementation((callback: FrameRequestCallback) => {
      frame = callback;
      return 1;
    });
    vi.stubGlobal('requestAnimationFrame', schedule);
    vi.stubGlobal('cancelAnimationFrame', cancel);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('delivers a completed answer normally', () => {
    const { result } = renderHook(() => useChatStream());
    const onDone = vi.fn();
    act(() => result.current.sendMessage({ question: 'Question' }, { onDone, onError: vi.fn() }));
    const [, handlers] = mocks.stream.mock.calls[0];
    act(() => handlers.onDone(answer));
    act(() => frame(0));
    expect(onDone).toHaveBeenCalledWith(answer);
    expect(result.current.isStreaming).toBe(false);
  });

  it('aborts on unmount and ignores late callbacks from that account', () => {
    const { result, unmount } = renderHook(() => useChatStream());
    const onDone = vi.fn();
    const onError = vi.fn();
    act(() => result.current.sendMessage({ question: 'Question' }, { onDone, onError }));
    const [, handlers, signal] = mocks.stream.mock.calls[0];
    act(() => handlers.onDelta('Partial answer'));
    unmount();
    expect(signal.aborted).toBe(true);
    expect(cancel).toHaveBeenCalledWith(1);
    schedule.mockClear();
    act(() => {
      handlers.onDelta('Late text');
      handlers.onDone(answer);
      handlers.onNoAnswer(answer);
      handlers.onError('Late error');
    });
    expect(schedule).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('ignores callbacks from a replaced request', () => {
    const { result } = renderHook(() => useChatStream());
    const onDone = vi.fn();
    const onError = vi.fn();
    act(() => result.current.sendMessage({ question: 'First' }, { onDone, onError }));
    const [, oldHandlers, oldSignal] = mocks.stream.mock.calls[0];
    act(() => result.current.sendMessage({ question: 'Second' }, { onDone, onError }));
    expect(oldSignal.aborted).toBe(true);
    act(() => {
      oldHandlers.onDone(answer);
      oldHandlers.onError('Old request error');
    });
    expect(result.current.isStreaming).toBe(true);
    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(schedule).not.toHaveBeenCalled();
  });
});
