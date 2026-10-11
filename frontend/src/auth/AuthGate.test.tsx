import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useQuery } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '@/types/api';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { AuthGate } from './AuthGate';

const mocks = vi.hoisted(() => ({
  account: { tenantId: 'tenant', localAccountId: 'alice' } as {
    tenantId: string; localAccountId: string;
  } | null,
  authenticated: true,
  get: vi.fn(),
  history: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock('@/api/client', () => ({ default: { get: mocks.get } }));
vi.mock('@/auth/msal', () => ({ msalInstance: {}, signIn: vi.fn(), signOut: mocks.signOut }));
vi.mock('@azure/msal-react', () => ({
  useAccount: () => mocks.account,
  useIsAuthenticated: () => mocks.authenticated,
  useMsal: () => ({
    inProgress: 'none',
    instance: { getActiveAccount: () => mocks.account },
  }),
}));
vi.mock('@tanstack/react-query-devtools', () => ({ ReactQueryDevtools: () => null }));

function user(userId: string): CurrentUser {
  return {
    tenant_id: 'tenant', user_id: userId, display_name: userId,
    email: `${userId}@example.test`, auth_method: 'entra',
    roles: ['Radia.User'], can_manage_documents: false, is_admin: false,
  };
}

function HistoryProbe() {
  const { data: currentUser } = useCurrentUser();
  const { data } = useQuery({ queryKey: ['review-history'], queryFn: mocks.history });
  return <div>{currentUser?.user_id}: {data}</div>;
}

describe('authenticated account boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.account = { tenantId: 'tenant', localAccountId: 'alice' };
    mocks.authenticated = true;
  });

  it('does not reuse identity or review-history cache after switching accounts', async () => {
    mocks.get.mockResolvedValue({ data: { data: user('alice') } });
    mocks.history.mockResolvedValue('Alice reviews');
    const { rerender } = render(<AuthGate><HistoryProbe /></AuthGate>);
    expect(await screen.findByText('alice: Alice reviews')).toBeInTheDocument();

    mocks.account = { tenantId: 'tenant', localAccountId: 'bob' };
    mocks.get.mockResolvedValue({ data: { data: user('bob') } });
    mocks.history.mockResolvedValue('Bob reviews');
    rerender(<AuthGate><HistoryProbe /></AuthGate>);
    expect(screen.queryByText(/Alice reviews/)).not.toBeInTheDocument();
    expect(await screen.findByText('bob: Bob reviews')).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledTimes(2);
    expect(mocks.history).toHaveBeenCalledTimes(2);
  });

  it('does not render protected content when API authorization fails', async () => {
    mocks.get.mockRejectedValue({
      success: false,
      error: {
        code: 'FORBIDDEN',
        message: 'Your account has not been granted access to Radia AI. Ask an administrator to assign you a Radia role.',
        detail: {},
      },
    });
    render(<AuthGate><HistoryProbe /></AuthGate>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Your account has not been granted access to Radia AI.');
    expect(mocks.history).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
  });

  it('waits for verified identity before mounting protected content', async () => {
    let resolveUser!: (value: { data: { data: CurrentUser } }) => void;
    mocks.get.mockReturnValue(new Promise((resolve) => { resolveUser = resolve; }));
    mocks.history.mockResolvedValue('Alice reviews');
    render(<AuthGate><HistoryProbe /></AuthGate>);
    expect(mocks.history).not.toHaveBeenCalled();
    await act(async () => resolveUser({ data: { data: user('alice') } }));
    expect(await screen.findByText('alice: Alice reviews')).toBeInTheDocument();
  });

  it('discards pending review results from a previous account', async () => {
    let resolveHistory!: (value: string) => void;
    mocks.get.mockResolvedValue({ data: { data: user('alice') } });
    mocks.history.mockReturnValueOnce(new Promise((resolve) => { resolveHistory = resolve; }));
    const { rerender } = render(<AuthGate><HistoryProbe /></AuthGate>);
    await waitFor(() => expect(mocks.history).toHaveBeenCalledTimes(1));

    mocks.account = { tenantId: 'tenant', localAccountId: 'bob' };
    mocks.get.mockResolvedValue({ data: { data: user('bob') } });
    mocks.history.mockResolvedValue('Bob reviews');
    rerender(<AuthGate><HistoryProbe /></AuthGate>);
    expect(await screen.findByText('bob: Bob reviews')).toBeInTheDocument();
    await act(async () => resolveHistory('Late Alice reviews'));
    expect(screen.queryByText(/Alice reviews/)).not.toBeInTheDocument();
    expect(screen.getByText('bob: Bob reviews')).toBeInTheDocument();
  });
});
