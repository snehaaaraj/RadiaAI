import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AccountInfo } from '@azure/msal-browser';
import type { CurrentUser, JamaAccountStatus } from '@/types/api';
import { signOut } from '@/auth/msal';
import { UserMenu } from './UserMenu';

const auth = vi.hoisted(() => ({
  user: undefined as CurrentUser | undefined,
  account: null as AccountInfo | null,
  error: null as unknown,
  enabled: true,
  jama: {
    data: undefined as JamaAccountStatus | undefined,
    isPending: true,
    isError: false,
    error: null as unknown,
  },
}));
vi.mock('@/radia_ai/features/jamaRequirementReviewer/hooks/useJama', () => ({
  useJamaAccount: () => auth.jama,
}));
vi.mock('@/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: auth.user, error: auth.error }),
}));
vi.mock('@/auth/msal', () => ({
  signOut: vi.fn(),
  getActiveAccount: () => auth.account,
}));
vi.mock('@/auth/authConfig', () => ({ get isAuthEnabled() { return auth.enabled; } }));

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = undefined;
  auth.account = null;
  auth.error = null;
  auth.enabled = true;
  auth.jama = { data: undefined, isPending: true, isError: false, error: null };
});

describe('Jama account status', () => {
  const unlinked: JamaAccountStatus = {
    linking_enabled: true,
    linked: false,
    relink_required: false,
    jama_base_url: 'https://jama.example',
    jama_user_id: null,
    jama_username: null,
    jama_email: null,
    jama_display_name: null,
    linked_at: null,
  };

  beforeEach(() => {
    auth.user = {
      tenant_id: 'tenant', user_id: 'alice', display_name: 'Alice',
      email: 'alice@example.test', auth_method: 'entra',
      roles: ['Radia.User'], is_admin: false, can_manage_documents: false,
    };
  });

  it('shows loading rather than an unlinked warning before status is known', () => {
    render(<UserMenu onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByRole('progressbar', { name: 'Checking Jama account status' })).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it.each([
    { status: unlinked, label: 'Jama account not linked' },
    { status: { ...unlinked, linked: true }, label: 'Jama account linked' },
    { status: { ...unlinked, linked: true, relink_required: true }, label: 'Jama account needs to be re-linked' },
    { status: { ...unlinked, linking_enabled: false }, label: 'Jama account linking is not enabled' },
  ])('shows the icon for $label and preserves settings navigation', ({ status, label }) => {
    auth.jama = { data: status, isPending: false, isError: false, error: null };
    const navigate = vi.fn();
    render(<UserMenu onNavigate={navigate} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByRole('img', { name: label })).toHaveAttribute(
      'data-testid', label === 'Jama account linked' ? 'CheckCircleIcon' : 'WarningAmberIcon',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Jama account' }));
    expect(navigate).toHaveBeenCalledWith('/settings#jama-account');
  });

  it('replaces the warning with a tick after linking, and restores it after unlinking', () => {
    auth.jama = { data: unlinked, isPending: false, isError: false, error: null };
    const { rerender } = render(<UserMenu onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByRole('img', { name: 'Jama account not linked' })).toBeVisible();
    auth.jama.data = { ...unlinked, linked: true };
    rerender(<UserMenu onNavigate={vi.fn()} />);
    expect(screen.getByRole('img', { name: 'Jama account linked' })).toBeVisible();
    auth.jama.data = unlinked;
    rerender(<UserMenu onNavigate={vi.fn()} />);
    expect(screen.getByRole('img', { name: 'Jama account not linked' })).toBeVisible();
  });

  it('shows a status error instead of a stale linked tick when the lookup fails', () => {
    auth.jama = {
      data: { ...unlinked, linked: true },
      isPending: false,
      isError: true,
      error: { error: { code: 'HTTP_ERROR', message: 'Status unavailable', detail: {} } },
    };
    render(<UserMenu onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByRole('img', {
      name: 'Could not load Jama account status: Status unavailable',
    })).toBeVisible();
    expect(screen.queryByRole('img', { name: 'Jama account linked' })).not.toBeInTheDocument();
  });
});

describe('profile allocation tag', () => {
  it.each([false, true])('shows one role tag when is_admin=%s', (isAdmin) => {
    auth.user = {
      tenant_id: 'tenant',
      user_id: 'user',
      email: 'alice@example.test',
      display_name: 'Alice',
      auth_method: 'entra',
      roles: isAdmin
        ? ['Radia.Admin', 'Radia.User']
        : ['Radia.User'],
      is_admin: isAdmin,
      can_manage_documents: isAdmin,
    };
    render(<UserMenu onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Account' }));
    expect(screen.getByText(isAdmin ? 'Admin' : 'User')).toBeInTheDocument();
    expect(screen.queryByText(isAdmin ? 'User' : 'Admin')).not.toBeInTheDocument();
  });

  describe('sign-out availability', () => {
    const account: AccountInfo = {
      homeAccountId: 'home',
      localAccountId: 'alice',
      tenantId: 'tenant',
      environment: 'login.microsoftonline.com',
      username: 'alice@example.test',
      name: 'Alice',
    };

    it('keeps sign-out available while API identity is loading', () => {
      auth.account = account;
      render(<UserMenu onNavigate={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: 'Account' }));

      expect(screen.getByText('Loading your Radia account...')).toBeInTheDocument();
      expect(screen.queryByText('User')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Jama account' })).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
      expect(signOut).toHaveBeenCalledOnce();
    });

    it('keeps sign-out available when the API fails and recovers', () => {
      auth.account = account;
      auth.error = {
        error: { code: 'HTTP_ERROR', message: 'Unable to load account details.', detail: {} },
      };
      const { rerender } = render(<UserMenu onNavigate={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: 'Account' }));
      expect(screen.getByRole('alert')).toHaveTextContent('Unable to load account details.');
      expect(screen.getByRole('button', { name: 'Sign out' })).toBeVisible();

      auth.error = null;
      auth.user = {
        tenant_id: 'tenant',
        user_id: 'alice',
        email: 'alice@example.test',
        display_name: 'Alice',
        auth_method: 'entra',
        roles: ['Radia.User'],
        is_admin: false,
        can_manage_documents: false,
      };
      rerender(<UserMenu onNavigate={vi.fn()} />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.getByText('User')).toBeVisible();
      expect(screen.getByRole('button', { name: 'Sign out' })).toBeVisible();
      expect(screen.getByRole('button', { name: 'Jama account' })).toBeVisible();
    });

    it('hides the account menu when signed out', () => {
      render(<UserMenu onNavigate={vi.fn()} />);
      expect(screen.queryByRole('button', { name: 'Account' })).not.toBeInTheDocument();
    });

    it('does not offer Microsoft sign-out in unauthenticated local development', () => {
      auth.enabled = false;
      auth.user = {
        tenant_id: 'local',
        user_id: 'local',
        display_name: 'Developer',
        email: 'dev@example.test',
        auth_method: 'local',
        roles: ['Radia.User'],
        is_admin: false,
        can_manage_documents: false,
      };
      render(<UserMenu onNavigate={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', { name: 'Account' }));
      expect(screen.getByText('Local dev')).toBeVisible();
      expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
    });
  });
});
