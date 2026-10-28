import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ChatData, ChatRequest } from '@/types/api';
import type { UseChatStreamHandlers } from '@/hooks/useChatStream';
import Chat from './Chat';

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn<(request: ChatRequest, handlers: UseChatStreamHandlers) => void>(),
  setHistory: vi.fn(),
  history: [] as Array<{ role: 'user' | 'assistant'; content: string }>,
}));

vi.mock('@/hooks/useChatStream', () => ({
  useChatStream: () => ({ isStreaming: false, streamingText: '', sendMessage: mocks.sendMessage }),
}));

vi.mock('@/hooks/useChatHistory', () => ({
  useChatHistory: () => ({ history: mocks.history, setHistory: mocks.setHistory, clearHistory: vi.fn() }),
}));

describe('Chat page - MCP engineering-data indicator', () => {
  it('shows an "Engineering data" chip and source link when a reply used MCP', () => {
    mocks.sendMessage.mockImplementation((_request, handlers) => {
      const data: ChatData = {
        answer: 'SRS-42 requires battery state-of-charge reporting.',
        citations: [],
        model: 'test',
        retrieval_count: 0,
        used_mcp: true,
        sources: [{ label: 'SRS-42', url: 'https://example.jamacloud.com/perspective.req#/items/42' }],
      };
      handlers.onDone(data);
    });
    // Simulate setHistory capturing the functional update so the component re-renders
    // with the assistant turn appended, the same way useChatHistory's real setter does.
    mocks.setHistory.mockImplementation((update) => {
      mocks.history =
        typeof update === 'function' ? update(mocks.history) : update;
    });

    const { rerender } = render(<Chat />);
    const input = screen.getByPlaceholderText('Ask a question about your documents…');
    fireEvent.change(input, { target: { value: 'What does Jama item 42 say?' } });
    screen.getByRole('button').click();
    rerender(<Chat />);

    expect(screen.getByText('Engineering data')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'SRS-42' });
    expect(link).toHaveAttribute('href', 'https://example.jamacloud.com/perspective.req#/items/42');
  });

  it('renders no chip for an ordinary (non-MCP) reply', () => {
    mocks.history = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there.' },
    ];

    render(<Chat />);

    expect(screen.queryByText('Engineering data')).not.toBeInTheDocument();
  });
});
