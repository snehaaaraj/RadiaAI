import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MessageText } from './MessageText';

describe('MessageText', () => {
  it('renders Markdown bold text as strong text without the delimiters', () => {
    render(
      <p>
        <MessageText content="13. **Operational Requirements** - **Document Key**: ABC-123" />
      </p>,
    );

    expect(screen.getByText('Operational Requirements')).toBeInTheDocument();
    expect(screen.getByText('Operational Requirements').tagName).toBe('STRONG');
    expect(screen.getByText('Document Key').tagName).toBe('STRONG');
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  it('preserves ordinary text and safe Markdown links', () => {
    render(
      <p>
        <MessageText content="See **details** at [View in Jama](https://example.com/item/1)." />
      </p>,
    );

    expect(screen.getByText('details').tagName).toBe('STRONG');
    expect(screen.getByRole('link', { name: 'View in Jama' })).toHaveAttribute(
      'href',
      'https://example.com/item/1',
    );
    expect(screen.getByText('See')).toBeInTheDocument();
  });
});
