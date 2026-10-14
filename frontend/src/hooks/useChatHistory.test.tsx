import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage, CurrentUser } from '@/types/api';
import { resetChatHistoryCache, useChatHistory } from './useChatHistory';

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
    resetChatHistoryCache();
    auth.user = alice;
  });

  it('persists history across remounts', () => {
    const first = renderHook(() => useChatHistory());
    act(() => first.result.current.setHistory(conversation));
    first.unmount();
    const second = renderHook(() => useChatHistory());
    expect(second.result.current.history).toEqual(conversation);
  });

  it('isolates history from users and admins', () => {
    const { result, rerender } = renderHook(() => useChatHistory());
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
    const { result, rerender } = renderHook(() => useChatHistory());
    act(() => result.current.setHistory(conversation));
    auth.user = { ...alice, tenant_id: 'tenant-2' };
    rerender();
    expect(result.current.history).toEqual([]);
  });

  it('does not expose or write history without a verified user', () => {
    auth.user = undefined;
    const { result, rerender } = renderHook(() => useChatHistory());
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

  it('shares one conversation between the page and the pop-up', () => {
    const page = renderHook(() => useChatHistory());
    const widget = renderHook(() => useChatHistory());
    act(() => page.result.current.setHistory(conversation));
    expect(widget.result.current.history).toEqual(conversation);
    act(() => widget.result.current.setHistory((prev) => [...prev, { role: 'user', content: 'Follow-up' }]));
    expect(page.result.current.history).toEqual([...conversation, { role: 'user', content: 'Follow-up' }]);
    act(() => widget.result.current.clearHistory());
    expect(page.result.current.history).toEqual([]);
  });

  it('records a reply that arrives after the sending surface unmounts', () => {
    const widget = renderHook(() => useChatHistory());
    act(() => widget.result.current.setHistory([conversation[0]]));
    const widgetSetter = widget.result.current.setHistory;
    widget.unmount();
    const page = renderHook(() => useChatHistory());
    act(() => widgetSetter((prev) => [...prev, conversation[1]]));
    expect(page.result.current.history).toEqual(conversation);
  });

  it('merges the former separate page and pop-up histories for the same user', () => {
    const widgetTurn: ChatMessage = { role: 'user', content: 'Pop-up question' };
    localStorage.setItem('radia-chat-page-history:tenant-1:alice', JSON.stringify(conversation));
    localStorage.setItem('radia-chat-widget-history:tenant-1:alice', JSON.stringify([widgetTurn]));
    const { result } = renderHook(() => useChatHistory());
    expect(result.current.history).toEqual([...conversation, widgetTurn]);
    expect(localStorage.getItem('radia-chat-page-history:tenant-1:alice')).toBeNull();
    expect(localStorage.getItem('radia-chat-widget-history:tenant-1:alice')).toBeNull();
    expect(JSON.parse(localStorage.getItem('radia-chat-history:tenant-1:alice') ?? '[]')).toEqual([
      ...conversation,
      widgetTurn,
    ]);
  });

  it('does not assign the old shared pop-up history to any user', () => {
    localStorage.setItem('radia-chat-widget-history', JSON.stringify(conversation));
    const { result } = renderHook(() => useChatHistory());
    expect(result.current.history).toEqual([]);
  });

  it('restores the same user history after signing out and back in', () => {
    const before = renderHook(() => useChatHistory());
    act(() => before.result.current.setHistory(conversation));
    before.unmount();

    // logoutRedirect clears MSAL's session cache and reloads the app.
    sessionStorage.clear();
    resetChatHistoryCache();
    auth.user = undefined;
    const signedOut = renderHook(() => useChatHistory());
    expect(signedOut.result.current.history).toEqual([]);
    signedOut.unmount();

    resetChatHistoryCache();
    auth.user = { ...alice };
    const after = renderHook(() => useChatHistory());
    expect(after.result.current.history).toEqual(conversation);
  });

  it('logs malformed stored data instead of rendering it', () => {
    localStorage.setItem('radia-chat-history:tenant-1:alice', '[{"role":"invalid","content":1}]');
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    try {
      const { result } = renderHook(() => useChatHistory());
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
      const { result } = renderHook(() => useChatHistory());
      act(() => result.current.setHistory(conversation));
      expect(result.current.history).toEqual(conversation);
      expect(log).toHaveBeenCalledWith('Unable to save chat history', expect.any(Error));
    } finally {
      write.mockRestore();
      log.mockRestore();
    }
  });
});
