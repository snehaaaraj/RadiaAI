import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppProvider } from './AppContext';
import { NavigationGuardProvider } from './NavigationGuardContext';
import { useAppContext } from './useAppContext';
import { useNavigationGuardContext } from './useNavigationGuardContext';

function PreferencesProbe() {
  const { themePreference, setThemePreference } = useAppContext();
  return (
    <button onClick={() => setThemePreference('dark')}>
      {themePreference}
    </button>
  );
}

function NavigationProbe() {
  const { setDirty, guardedNavigate, dialogOpen, handleConfirm, handleCancel } =
    useNavigationGuardContext();
  const { pathname } = useLocation();
  return (
    <>
      <span>{pathname}</span>
      <button onClick={() => setDirty(true)}>Mark dirty</button>
      <button onClick={() => guardedNavigate('/next')}>Navigate</button>
      {dialogOpen && (
        <div role="dialog">
          <button onClick={handleConfirm}>Confirm</button>
          <button onClick={handleCancel}>Cancel</button>
        </div>
      )}
    </>
  );
}

describe('context providers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('shares and persists preferences through the application hook', () => {
    render(<AppProvider><PreferencesProbe /></AppProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'system' }));
    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem('radia-ui-preferences') ?? '{}'))
      .toHaveProperty('themePreference', 'dark');
  });

  it('shares navigation guard state and requires confirmation for dirty pages', () => {
    render(
      <MemoryRouter initialEntries={['/current']}>
        <NavigationGuardProvider><NavigationProbe /></NavigationGuardProvider>
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Mark dirty' }));
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('/current')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText('/current')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText('/next')).toBeInTheDocument();
  });
});
