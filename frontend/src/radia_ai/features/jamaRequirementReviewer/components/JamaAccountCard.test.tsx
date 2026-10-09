import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { JamaAccountStatus } from '@/types/api';

const api = vi.hoisted(() => ({
  fetchJamaAccount: vi.fn(),
  linkJamaAccount: vi.fn(),
  unlinkJamaAccount: vi.fn(),
}));

vi.mock('@/radia_ai/features/jamaRequirementReviewer/api/jama', () => ({
  ...api,
  fetchJamaProjects: vi.fn(),
  fetchJamaRequirement: vi.fn(),
  searchJamaRequirements: vi.fn(),
}));

const { JamaAccountCard } = await import('./JamaAccountCard');

const unlinked: JamaAccountStatus = {
  linking_enabled: true,
  linked: false,
  using_shared_account: false,
  jama_base_url: 'https://jama.example',
  jama_user_id: null,
  jama_username: null,
  jama_email: null,
  jama_display_name: null,
  linked_at: null,
};

const linked: JamaAccountStatus = {
  ...unlinked,
  linked: true,
  jama_user_id: 10,
  jama_username: 'alice',
  jama_email: 'alice@radia.example',
  jama_display_name: 'Alice Engineer',
  linked_at: '2026-10-08T12:00:00Z',
};

function renderCard(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  render(<JamaAccountCard />, { wrapper });
}

describe('JamaAccountCard', () => {
  afterEach(() => vi.clearAllMocks());

  it('links the account with the entered credentials', async () => {
    api.fetchJamaAccount.mockResolvedValueOnce(unlinked).mockResolvedValue(linked);
    api.linkJamaAccount.mockResolvedValue(linked);
    renderCard();

    fireEvent.change(await screen.findByLabelText(/Jama client ID/), {
      target: { value: ' alice-client ' },
    });
    fireEvent.change(screen.getByLabelText(/Jama client secret/), {
      target: { value: 'alice-secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Link Jama account' }));

    await waitFor(() =>
      expect(api.linkJamaAccount.mock.calls[0][0]).toEqual({
        client_id: 'alice-client',
        client_secret: 'alice-secret',
      })
    );
    expect(await screen.findByText('Alice Engineer')).toBeInTheDocument();
  });

  it('shows the server reason when Jama rejects the credentials', async () => {
    api.fetchJamaAccount.mockResolvedValue(unlinked);
    api.linkJamaAccount.mockRejectedValue({
      success: false,
      error: {
        code: 'JAMA_ACCOUNT_MISMATCH',
        message: 'These Jama credentials belong to a different person.',
      },
    });
    renderCard();

    fireEvent.change(await screen.findByLabelText(/Jama client ID/), { target: { value: 'x' } });
    fireEvent.change(screen.getByLabelText(/Jama client secret/), { target: { value: 'y' } });
    fireEvent.click(screen.getByRole('button', { name: 'Link Jama account' }));

    expect(
      await screen.findByText('These Jama credentials belong to a different person.')
    ).toBeInTheDocument();
  });

  it('unlinks a linked account', async () => {
    api.fetchJamaAccount.mockResolvedValueOnce(linked).mockResolvedValue(unlinked);
    api.unlinkJamaAccount.mockResolvedValue(unlinked);
    renderCard();

    fireEvent.click(await screen.findByRole('button', { name: 'Unlink' }));

    await waitFor(() => expect(api.unlinkJamaAccount).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: 'Link Jama account' })).toBeInTheDocument();
  });

  it('explains when linking is not enabled on the server', async () => {
    api.fetchJamaAccount.mockResolvedValue({ ...unlinked, linking_enabled: false });
    renderCard();

    expect(await screen.findByText(/linking is not enabled/)).toBeInTheDocument();
  });
});
