import type { ReactNode } from 'react';
import { MsalProvider, useIsAuthenticated, useMsal } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LoginIcon from '@mui/icons-material/Login';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { msalInstance, signIn } from './msal';

/** Provides MSAL context when Entra sign-in is configured. */
export function AuthProvider({ children }: { children: ReactNode }) {
  if (!msalInstance) return <>{children}</>;
  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}

/** Renders the app only for signed-in users; everyone else sees the sign-in screen. */
export function AuthGate({ children }: { children: ReactNode }) {
  if (!msalInstance) return <>{children}</>;
  return <MsalGate>{children}</MsalGate>;
}

function MsalGate({ children }: { children: ReactNode }) {
  const { inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  if (isAuthenticated) return <>{children}</>;
  if (inProgress !== InteractionStatus.None) {
    return <LoadingSpinner fullScreen message="Signing you in…" />;
  }
  return <SignInScreen />;
}

function SignInScreen() {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Card sx={{ maxWidth: 420, width: '100%' }}>
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={2.5} alignItems="flex-start">
            <Typography variant="h5" fontWeight={800}>
              Radia AI
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Sign in with your company Microsoft account to continue.
            </Typography>
            <Button
              variant="contained"
              size="large"
              startIcon={<LoginIcon />}
              onClick={() => void signIn()}
              fullWidth
            >
              Sign in with Microsoft
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
