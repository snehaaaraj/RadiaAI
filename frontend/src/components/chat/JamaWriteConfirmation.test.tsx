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

  it('shows exact values and writes only after clicking confirmation', async () => {
    const onComplete = vi.fn();
    mocks.confirm.mockResolvedValue({ answer: 'Written' });
    render(<JamaWriteConfirmation preview={preview} disabled={false}
      onComplete={onComplete} onCancel={vi.fn()} />);
    expect(screen.getByText('"Old"')).toBeInTheDocument();
    expect(screen.getByText('"<p>New</p>"')).toBeInTheDocument();
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
