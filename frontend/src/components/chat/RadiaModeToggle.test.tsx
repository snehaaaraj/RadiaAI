import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Chat from '@/pages/Chat';
import { ChatWidget } from './ChatWidget';
import { resetChatHistoryCache } from '@/hooks/useChatHistory';

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  isStreaming: false,
}));

vi.mock('@/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: { tenant_id: 'test-tenant', user_id: 'test-user' } }),
}));

vi.mock('@/context/useAppContext', () => ({
  useAppContext: () => ({ motionPreference: 'reduced' }),
}));

vi.mock('@/hooks/useChatStream', () => ({
  useChatStream: () => ({
    isStreaming: mocks.isStreaming,
    streamingText: '',
    sendMessage: mocks.sendMessage,
  }),
}));

beforeEach(() => {
  localStorage.clear();
  resetChatHistoryCache();
  mocks.sendMessage.mockReset();
  mocks.isStreaming = false;
  Element.prototype.scrollIntoView = vi.fn();
});

describe.each(['page', 'widget'] as const)('Radia AI switch in the %s', (surface) => {
  function renderChat() {
    const result = render(surface === 'page' ? <Chat /> : <ChatWidget />);
    if (surface === 'widget') {
      fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
    }
    return result;
  }

  it('toggles locally, routes both modes, retains drafts, and restores after remount', () => {
    const { unmount } = renderChat();
    const toggle = screen.getByRole('switch', { name: 'Radia AI mode' });
    expect(toggle).not.toBeChecked();
    expect(screen.getByText('OFF')).toBeVisible();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Draft question' } });
    fireEvent.click(toggle);
    expect(toggle).toBeChecked();
    expect(screen.getByText('ON')).toBeVisible();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('Ask about engineering data…')).toHaveValue('Draft question');
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(mocks.sendMessage).toHaveBeenLastCalledWith(
      expect.objectContaining({ mode: 'radiaai', question: 'Draft question', conversation_history: [] }),
      expect.anything(),
    );

    unmount();
    resetChatHistoryCache();
    renderChat();
    expect(screen.getByRole('switch', { name: 'Radia AI mode' })).toBeChecked();
    fireEvent.click(screen.getByRole('switch', { name: 'Radia AI mode' }));
    expect(screen.getByRole('switch', { name: 'Radia AI mode' })).not.toBeChecked();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Standards question' } });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(mocks.sendMessage).toHaveBeenLastCalledWith(
      expect.objectContaining({ mode: 'standards', question: 'Standards question', conversation_history: [] }),
      expect.anything(),
    );
    expect(screen.queryByText('/radiaai')).not.toBeInTheDocument();
    expect(screen.queryByText('/exit')).not.toBeInTheDocument();
  });

  it('disables the switch while a response is streaming', () => {
    mocks.isStreaming = true;
    renderChat();
    expect(screen.getByRole('switch', { name: 'Radia AI mode' })).toBeDisabled();
  });

  it('shows a hover hint for the current mode', async () => {
    renderChat();
    const label = screen.getByText('Radia AI').closest('label');
    expect(label).not.toBeNull();
    if (!label) throw new Error('Radia AI toggle label is missing');
    fireEvent.mouseOver(label);
    expect(await screen.findByRole('tooltip'))
      .toHaveTextContent('Turn it on to connect to Jama contents');

    fireEvent.click(screen.getByRole('switch', { name: 'Radia AI mode' }));
    expect(screen.getByRole('tooltip'))
      .toHaveTextContent('Turn it off to switch back to Radia Chatbot');
  });
});

it('shares the selected mode between the page and widget', () => {
  render(<><Chat /><ChatWidget /></>);
  fireEvent.click(screen.getByRole('switch', { name: 'Radia AI mode' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
  const toggles = screen.getAllByRole('switch', { name: 'Radia AI mode' });
  expect(toggles).toHaveLength(2);
  toggles.forEach((toggle) => expect(toggle).toBeChecked());
  fireEvent.click(toggles[1]);
  toggles.forEach((toggle) => expect(toggle).not.toBeChecked());
});
