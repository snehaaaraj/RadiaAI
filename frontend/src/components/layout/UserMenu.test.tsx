import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AccountInfo } from '@azure/msal-browser';
import type { CurrentUser } from '@/types/api';
import { signOut } from '@/auth/msal';
import { UserMenu } from './UserMenu';

const auth = vi.hoisted(() => ({
  user: undefined as CurrentUser | undefined,
  account: null as AccountInfo | null,
  error: null as unknown,
  enabled: true,
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
