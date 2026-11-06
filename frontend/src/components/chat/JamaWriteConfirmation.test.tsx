import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JamaWriteConfirmation } from './JamaWriteConfirmation';

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  user: { tenant_id: 'tenant', user_id: 'user' },
}));
vi.mock('@/api/chat', () => ({ confirmJamaWrite: mocks.confirm }));
vi.mock('@/hooks/useCurrentUser', () => ({ useCurrentUser: () => ({ data: mocks.user }) }));

const preview = {
  item_id: 1, document_key: 'SRS-1', name: 'Requirement',
  changes: [{ field: 'description', label: 'Description', before: 'Old', after: '<p>New</p>' }],
  confirmation_token: 'signed', expires_at: 2000000000,
};

describe('Jama write confirmation', () => {
  beforeEach(() => {
    mocks.confirm.mockReset();
    mocks.user.user_id = 'user';
  });

  it('shows readable text and writes only after clicking confirmation', async () => {
    const onComplete = vi.fn();
    mocks.confirm.mockResolvedValue({ answer: 'Written' });
    render(<JamaWriteConfirmation preview={preview} disabled={false}
      onComplete={onComplete} onCancel={vi.fn()} />);
    expect(screen.getByText('Old')).toBeInTheDocument();
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.queryByText(/<p>/)).not.toBeInTheDocument();
    expect(mocks.confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & write to Jama' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    expect(mocks.confirm).toHaveBeenCalledExactlyOnceWith('signed');
  });

  it('preserves line breaks and entities without rendering upstream HTML', () => {
    const richPreview = {
      ...preview,
      changes: [{
        field: 'description', label: 'Description',
        before: '<p>Stop &lt; 50 m &amp; hold.</p><p>Second paragraph</p>',
        after: '<p>Line one<br /><br />- Test</p><script>bad()</script><img src="https://example.com/image" />',
      }],
    };
    const { container } = render(<JamaWriteConfirmation preview={richPreview} disabled={false}
      onComplete={vi.fn()} onCancel={vi.fn()} />);
    const values = container.querySelectorAll('pre');
    expect(values[0].textContent).toBe('Stop < 50 m & hold.\nSecond paragraph');
    expect(values[1].textContent).toBe('Line one\n\n- Test');
    expect(container.querySelector('script, img')).toBeNull();
    expect(richPreview.changes[0].after).toContain('<p>');
  });

  it('keeps non-HTML strings and typed field values readable', () => {
    const typedPreview = {
      ...preview,
      changes: [
        { field: 'name', label: 'Name', before: 'Stop < 50 m', after: 'Go > 10 m' },
        { field: 'custom', label: 'Custom', before: false, after: [1, 2] },
      ],
    };
    const { container } = render(<JamaWriteConfirmation preview={typedPreview} disabled={false}
      onComplete={vi.fn()} onCancel={vi.fn()} />);
    expect(Array.from(container.querySelectorAll('pre'), (element) => element.textContent)).toEqual([
      'Stop < 50 m', 'Go > 10 m', 'false', '[\n  1,\n  2\n]',
    ]);
  });

  it('shows only requested changes while leaving preserved required values untouched', async () => {
    const preservedPreview = {
      ...preview,
      preserved_fields: [{
        field: 'safety_requirement$67', label: 'Safety Requirement', before: false, after: false,
      }],
    };
    mocks.confirm.mockResolvedValue({ answer: 'Written' });
    const onComplete = vi.fn();
    const { container } = render(<JamaWriteConfirmation preview={preservedPreview} disabled={false}
      onComplete={onComplete} onCancel={vi.fn()} />);
    expect(screen.getByText('Description (description)')).toBeInTheDocument();
    expect(Array.from(container.querySelectorAll('pre'), (element) => element.textContent))
      .toEqual(['Old', 'New']);
    expect(screen.queryByText('Required fields preserved unchanged')).not.toBeInTheDocument();
    expect(screen.queryByText(/Safety Requirement/)).not.toBeInTheDocument();
    expect(preservedPreview.preserved_fields[0].after).toBe(false);
    expect(mocks.confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & write to Jama' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    expect(mocks.confirm).toHaveBeenCalledExactlyOnceWith('signed');
  });

  it('cancels without making a write request', () => {
    const cancel = vi.fn();
    render(<JamaWriteConfirmation preview={preview} disabled={false}
      onComplete={vi.fn()} onCancel={cancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(cancel).toHaveBeenCalled();
    expect(mocks.confirm).not.toHaveBeenCalled();
  });

  it('shows errors and does not automatically retry a failed write', async () => {
    const onError = vi.fn();
    mocks.confirm.mockRejectedValue({ error: { message: 'Jama requires another field.' } });
    render(<JamaWriteConfirmation preview={preview} disabled={false}
      onComplete={vi.fn()} onCancel={vi.fn()} onError={onError} />);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & write to Jama' }));
    expect(await screen.findByText(/Jama requires another field/)).toBeInTheDocument();
    expect(mocks.confirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Confirm & write to Jama' })).toBeDisabled();
    expect(onError).toHaveBeenCalledExactlyOnceWith(
      'Jama requires another field. Check the item in Jama before preparing another write.'
    );
  });

  it('hides an earlier account preview after the current user changes', () => {
    const props = { preview, disabled: false, onComplete: vi.fn(), onCancel: vi.fn() };
    const { rerender } = render(<JamaWriteConfirmation {...props} />);
    mocks.user.user_id = 'other';
    rerender(<JamaWriteConfirmation {...props} />);
    expect(screen.queryByText(/Confirm Jama update/)).not.toBeInTheDocument();
  });
});
