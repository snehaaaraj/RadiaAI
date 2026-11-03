import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatConversation } from './ChatConversation';
import { ChatWidget } from './ChatWidget';

vi.mock('@/hooks/useChatHistory', () => ({
  useChatHistory: () => ({
    history: [{ role: 'assistant', content: 'Restored answer' }],
    setHistory: vi.fn(),
    clearHistory: vi.fn(),
  }),
}));

vi.mock('@/hooks/useChatStream', () => ({
  useChatStream: () => ({ isStreaming: false, streamingText: '', sendMessage: vi.fn() }),
}));

vi.mock('@/context/useAppContext', () => ({
  useAppContext: () => ({ motionPreference: 'reduced' }),
}));

function motionQuery(matches: boolean): MediaQueryList {
  return {
    matches,
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
}

describe('chat conversation scrolling', () => {
  let contentHeight: number;
  let viewportHeight: number;
  let notifyResize: () => void;
  const disconnect = vi.fn();
  const scrollTo = vi.fn();

  beforeEach(() => {
    contentHeight = 1000;
    viewportHeight = 400;
    disconnect.mockClear();
    scrollTo.mockClear();
    vi.stubGlobal('matchMedia', vi.fn(() => motionQuery(false)));
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(() => contentHeight);
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(() => viewportHeight);
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) {
        notifyResize = callback;
      }
      observe = vi.fn();
      disconnect = disconnect;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('starts at the end of restored history and does so again after remounting', () => {
    const first = render(<ChatConversation>Restored history</ChatConversation>);
    expect(screen.getByRole('region', { name: 'Conversation' }).scrollTop).toBe(600);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();

    first.unmount();
    render(<ChatConversation>Restored history</ChatConversation>);
    expect(screen.getByRole('region', { name: 'Conversation' }).scrollTop).toBe(600);
  });

  it('follows history loaded after mount, streaming tokens, and the final reply', () => {
    contentHeight = 400;
    const { rerender } = render(<ChatConversation />);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    expect(viewport.scrollTop).toBe(0);

    contentHeight = 1000;
    rerender(<ChatConversation>Loaded history</ChatConversation>);
    expect(viewport.scrollTop).toBe(600);

    contentHeight = 1100;
    rerender(<ChatConversation>Loaded history + streamed tokens</ChatConversation>);
    expect(viewport.scrollTop).toBe(700);

    contentHeight = 1200;
    rerender(<ChatConversation>Loaded history + final answer</ChatConversation>);
    expect(viewport.scrollTop).toBe(800);
  });

  it('pauses when scrolled up and resumes when the down arrow is clicked', () => {
    const { rerender } = render(<ChatConversation reduceMotion>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    fireEvent.scroll(viewport, { target: { scrollTop: 200 } });
    expect(screen.getByRole('button', { name: 'Scroll to latest message' })).toBeVisible();

    contentHeight = 1300;
    rerender(<ChatConversation reduceMotion>Longer answer</ChatConversation>);
    act(() => notifyResize());
    expect(viewport.scrollTop).toBe(200);

    fireEvent.click(screen.getByRole('button', { name: 'Scroll to latest message' }));
    expect(viewport.scrollTop).toBe(900);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();

    contentHeight = 1400;
    rerender(<ChatConversation reduceMotion>Even longer answer</ChatConversation>);
    expect(viewport.scrollTop).toBe(1000);
  });

  it('animates the arrow scroll without jumping during streaming, then resumes following', () => {
    const { rerender } = render(<ChatConversation>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    viewport.scrollTo = scrollTo;
    fireEvent.scroll(viewport, { target: { scrollTop: 200 } });
    fireEvent.click(screen.getByRole('button', { name: 'Scroll to latest message' }));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1000, behavior: 'smooth' });
    expect(viewport.scrollTop).toBe(200);

    contentHeight = 1200;
    rerender(<ChatConversation>More streamed text</ChatConversation>);
    act(() => notifyResize());
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1200, behavior: 'smooth' });
    expect(viewport.scrollTop).toBe(200);
    fireEvent.scroll(viewport, { target: { scrollTop: 780 } });
    expect(viewport.scrollTop).toBe(780);
    expect(screen.getByRole('button', { name: 'Scroll to latest message' })).toBeVisible();
    fireEvent.scroll(viewport, { target: { scrollTop: 800 } });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();

    contentHeight = 1300;
    rerender(<ChatConversation>Final answer</ChatConversation>);
    expect(viewport.scrollTop).toBe(900);
  });

  it.each(['wheel', 'touchStart', 'keyDown'])('lets the user interrupt the animation with %s', (event) => {
    const { rerender } = render(<ChatConversation>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    viewport.scrollTo = scrollTo;
    fireEvent.scroll(viewport, { target: { scrollTop: 200 } });
    fireEvent.click(screen.getByRole('button', { name: 'Scroll to latest message' }));
    if (event === 'wheel') fireEvent.wheel(viewport, { deltaY: -100 });
    else if (event === 'touchStart') fireEvent.touchStart(viewport);
    else fireEvent.keyDown(viewport, { key: 'PageUp' });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 200, behavior: 'instant' });
    contentHeight = 1300;
    rerender(<ChatConversation>More text</ChatConversation>);
    expect(viewport.scrollTop).toBe(200);
  });

  it('uses an immediate arrow scroll for system reduced-motion preferences', () => {
    vi.mocked(window.matchMedia).mockReturnValue(motionQuery(true));
    render(<ChatConversation>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    viewport.scrollTo = scrollTo;
    fireEvent.scroll(viewport, { target: { scrollTop: 200 } });
    fireEvent.click(screen.getByRole('button', { name: 'Scroll to latest message' }));
    expect(viewport.scrollTop).toBe(600);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('resumes following when the user manually returns within 48px of the bottom', () => {
    const { rerender } = render(<ChatConversation>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    fireEvent.scroll(viewport, { target: { scrollTop: 551 } });
    expect(screen.getByRole('button', { name: 'Scroll to latest message' })).toBeVisible();
    fireEvent.scroll(viewport, { target: { scrollTop: 552 } });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();

    contentHeight = 1200;
    rerender(<ChatConversation>Longer answer</ChatConversation>);
    expect(viewport.scrollTop).toBe(800);
  });

  it('follows content and viewport resizes and disconnects on unmount', () => {
    const { unmount } = render(<ChatConversation>Answer</ChatConversation>);
    const viewport = screen.getByRole('region', { name: 'Conversation' });

    contentHeight = 1200;
    act(() => notifyResize());
    expect(viewport.scrollTop).toBe(800);

    viewportHeight = 300;
    act(() => notifyResize());
    expect(viewport.scrollTop).toBe(900);
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it('keeps short or empty conversations at the top without an arrow', () => {
    contentHeight = 100;
    render(<ChatConversation />);
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    expect(viewport.scrollTop).toBe(0);
    fireEvent.scroll(viewport);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('opens and reopens the floating chat at the end of restored history', async () => {
    render(<ChatWidget />);
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
    const viewport = screen.getByRole('region', { name: 'Conversation' });
    expect(viewport.scrollTop).toBe(600);
    fireEvent.scroll(viewport, { target: { scrollTop: 0 } });
    expect(screen.getByRole('button', { name: 'Scroll to latest message' })).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => {
      expect(screen.queryByRole('region', { name: 'Conversation' })).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
    expect(screen.getByRole('region', { name: 'Conversation' }).scrollTop).toBe(600);
    expect(screen.queryByRole('button', { name: 'Scroll to latest message' })).not.toBeInTheDocument();
  });

  it('resets to the latest message when reopened before its exit animation finishes', () => {
    render(<ChatWidget />);
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
    fireEvent.scroll(screen.getByRole('region', { name: 'Conversation' }), { target: { scrollTop: 0 } });

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    fireEvent.click(screen.getByRole('button', { name: 'Open chat' }));
    expect(screen.getByRole('region', { name: 'Conversation' }).scrollTop).toBe(600);
    expect(screen.queryByRole('button', { name: 'Scroll to latest message' })).not.toBeInTheDocument();
  });
});
