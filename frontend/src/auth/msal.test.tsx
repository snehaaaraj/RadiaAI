import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { usePersistentState } from '@/hooks/usePersistentState';
import { REQUIREMENT_REVIEW_FORM_KEY } from '@/radia_ai/features/jamaRequirementReviewer/persistedReviewKeys';
import { signOut } from './msal';

const mocks = vi.hoisted(() => ({
  logoutRedirect: vi.fn(),
  getActiveAccount: vi.fn(),
}));

vi.mock('./authConfig', () => ({
  isAuthEnabled: true,
  authSettings: {
    clientId: 'client',
    tenantId: 'tenant',
    redirectUri: 'http://localhost',
  },
  apiTokenRequest: { scopes: ['api'] },
}));

vi.mock('@azure/msal-browser', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@azure/msal-browser')>();
  return {
    ...actual,
    PublicClientApplication: class {
      logoutRedirect = mocks.logoutRedirect;
      getActiveAccount = mocks.getActiveAccount;
    },
  };
});

function RequirementNameProbe() {
  const { state, setState } = usePersistentState({
    key: REQUIREMENT_REVIEW_FORM_KEY,
    initialValue: { jamaPicker: { inputValue: '' } },
  });
  return (
    <input
      aria-label="Requirement name"
      value={state.jamaPicker.inputValue}
      onChange={(event) => setState({ jamaPicker: { inputValue: event.target.value } })}
    />
  );
}

describe('signing out with a retained requirement form', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    mocks.getActiveAccount.mockReturnValue(null);
    mocks.logoutRedirect.mockResolvedValue(undefined);
  });

  it('retains the input across remounts but starts empty after sign-out and sign-in', async () => {
    const first = render(<RequirementNameProbe />);
    fireEvent.change(screen.getByLabelText('Requirement name'), {
      target: { value: 'Operational Requirements' },
    });
    first.unmount();

    const returning = render(<RequirementNameProbe />);
    expect(screen.getByLabelText('Requirement name')).toHaveValue('Operational Requirements');
    await act(async () => { await signOut(); });
    returning.unmount();

    render(<RequirementNameProbe />);
    expect(screen.getByLabelText('Requirement name')).toHaveValue('');
    expect(mocks.logoutRedirect).toHaveBeenCalledWith({ account: undefined });
  });

  it('removes previously saved form data before redirecting without clearing unrelated preferences', async () => {
    localStorage.setItem(REQUIREMENT_REVIEW_FORM_KEY, JSON.stringify({
      jamaPicker: { inputValue: 'Operational Requirements', projectId: 7 },
    }));
    localStorage.setItem('theme', 'dark');
    const account = { homeAccountId: 'account' };
    mocks.getActiveAccount.mockReturnValue(account);
    mocks.logoutRedirect.mockImplementation(async () => {
      expect(localStorage.getItem(REQUIREMENT_REVIEW_FORM_KEY)).toBeNull();
    });

    await signOut();

    expect(mocks.logoutRedirect).toHaveBeenCalledWith({ account });
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
