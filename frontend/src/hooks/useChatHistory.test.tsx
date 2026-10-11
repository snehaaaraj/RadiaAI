import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage, CurrentUser } from '@/types/api';
import { useChatHistory } from './useChatHistory';

const auth = vi.hoisted(() => ({ user: undefined as CurrentUser | undefined }));
vi.mock('@/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: auth.user }),
}));

const alice: CurrentUser = {
  tenant_id: 'tenant-1',
  user_id: 'alice',
  display_name: 'Alice',
  email: 'alice@example.test',
  roles: ['Radia.User'],
  auth_method: 'entra',
  can_manage_documents: false,
  is_admin: false,
};
const conversation: ChatMessage[] = [
  { role: 'user', content: 'My private question' },
  { role: 'assistant', content: 'My private answer' },
];

describe('user-scoped chat history', () => {
  beforeEach(() => {
    localStorage.clear();
    auth.user = alice;
  });

  it.each(['page', 'widget'] as const)('persists %s history across remounts', (surface) => {
    const first = renderHook(() => useChatHistory(surface));
    act(() => first.result.current.setHistory(conversation));
    first.unmount();
    const second = renderHook(() => useChatHistory(surface));
    expect(second.result.current.history).toEqual(conversation);
  });

  it.each(['page', 'widget'] as const)('isolates %s history from users and admins', (surface) => {
    const { result, rerender } = renderHook(() => useChatHistory(surface));
    act(() => result.current.setHistory(conversation));
    const aliceSetter = result.current.setHistory;

    auth.user = { ...alice, user_id: 'bob' };
    rerender();
    expect(result.current.history).toEqual([]);
    act(() => result.current.setHistory([{ role: 'user', content: 'Bob question' }]));

    // A late response from Alice must not enter Bob's conversation.
    act(() => aliceSetter((previous) => [...previous, { role: 'assistant', content: 'Late answer' }]));
    expect(result.current.history).toEqual([{ role: 'user', content: 'Bob question' }]);

    auth.user = { ...alice, user_id: 'admin', is_admin: true, roles: ['Radia.Admin', 'Radia.User'] };
    rerender();
    expect(result.current.history).toEqual([]);
    act(() => result.current.setHistory([{ role: 'user', content: 'Admin question' }]));

    auth.user = alice;
    rerender();
    expect(result.current.history).toEqual(conversation);
    auth.user = { ...alice, user_id: 'admin', is_admin: true };
    rerender();
    expect(result.current.history).toEqual([{ role: 'user', content: 'Admin question' }]);
  });

  it('separates identical user IDs in different tenants', () => {
    const { result, rerender } = renderHook(() => useChatHistory('widget'));
    act(() => result.current.setHistory(conversation));
    auth.user = { ...alice, tenant_id: 'tenant-2' };
    rerender();
    expect(result.current.history).toEqual([]);
  });

  it('does not expose or write history without a verified user', () => {
    auth.user = undefined;
    const { result, rerender } = renderHook(() => useChatHistory('page'));
    act(() => result.current.setHistory(conversation));
    expect(result.current.history).toEqual([]);
    expect(localStorage.length).toBe(0);
    auth.user = alice;
    rerender();
    act(() => result.current.setHistory(conversation));
    auth.user = undefined;
    rerender();
    expect(result.current.history).toEqual([]);
    auth.user = alice;
    rerender();
    expect(result.current.history).toEqual(conversation);
  });

  it('keeps page and pop-up conversations separate and clears only the current conversation', () => {
    const page = renderHook(() => useChatHistory('page'));
    const widget = renderHook(() => useChatHistory('widget'));
    act(() => page.result.current.setHistory(conversation));
    expect(widget.result.current.history).toEqual([]);
    act(() => widget.result.current.setHistory(conversation));
    act(() => widget.result.current.clearHistory());
    expect(widget.result.current.history).toEqual([]);
    expect(page.result.current.history).toEqual(conversation);
  });

  it('does not assign the old shared pop-up history to any user', () => {
    localStorage.setItem('radia-chat-widget-history', JSON.stringify(conversation));
    const { result } = renderHook(() => useChatHistory('widget'));
    expect(result.current.history).toEqual([]);
  });

  it('logs malformed stored data instead of rendering it', () => {
    localStorage.setItem('radia-chat-page-history:tenant-1:alice', '[{"role":"invalid","content":1}]');
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    try {
      const { result } = renderHook(() => useChatHistory('page'));
      expect(result.current.history).toEqual([]);
      expect(log).toHaveBeenCalledWith('Unable to load chat history', expect.any(Error));
    } finally {
      log.mockRestore();
    }
  });

  it('logs storage failures while retaining the current in-memory conversation', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Storage full');
    });
    try {
      const { result } = renderHook(() => useChatHistory('page'));
      act(() => result.current.setHistory(conversation));
      expect(result.current.history).toEqual(conversation);
      expect(log).toHaveBeenCalledWith('Unable to save chat history', expect.any(Error));
    } finally {
      write.mockRestore();
      log.mockRestore();
    }
  });
});
