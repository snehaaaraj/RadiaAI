import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '@/types/api';
import { UserMenu } from './UserMenu';

const auth = vi.hoisted(() => ({ user: undefined as CurrentUser | undefined }));
vi.mock('@/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: auth.user }),
}));
vi.mock('@/auth/msal', () => ({ signOut: vi.fn() }));
vi.mock('@/auth/authConfig', () => ({ isAuthEnabled: true }));

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
});
