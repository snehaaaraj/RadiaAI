import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { AuthProvider } from '@/auth/AuthGate';
import { initializeAuth } from '@/auth/msal';
import '@fontsource/roboto/300.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found');

// Complete any Microsoft sign-in redirect before rendering so the first API
// calls already carry the user's access token.
void initializeAuth()
  .catch((error: unknown) => {
    console.error('Microsoft sign-in initialisation failed', error);
  })
  .finally(() => {
    createRoot(root).render(
      <StrictMode>
        <AuthProvider>
          <App />
        </AuthProvider>
      </StrictMode>
    );
  });
