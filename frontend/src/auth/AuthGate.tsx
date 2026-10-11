import { Fragment, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { MsalProvider, useAccount, useIsAuthenticated, useMsal } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LoginIcon from '@mui/icons-material/Login';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import { msalInstance, signIn, signOut } from './msal';

/** Provides MSAL context when Entra sign-in is configured. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => (
    new QueryClient({
      defaultOptions: {
        queries: { retry: 1, staleTime: 30_000 },
        mutations: { retry: 0 },
      },
    })
  ));
  const content = msalInstance
    ? <MsalProvider instance={msalInstance}>{children}</MsalProvider>
    : children;

  return <QueryClientProvider client={client}>{content}</QueryClientProvider>;
}

/** Renders the app only for signed-in users; everyone else sees the sign-in screen. */
export function AuthGate({ children }: { children: ReactNode }) {
  if (!msalInstance) return <AccountSession>{children}</AccountSession>;
  return <MsalGate>{children}</MsalGate>;
}

function MsalGate({ children }: { children: ReactNode }) {
  const { inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = useAccount();

  if (isAuthenticated && account) {
    return (
      <AccountSession key={`${account.tenantId}:${account.localAccountId}`}>
        {children}
      </AccountSession>
    );
  }
  if (inProgress !== InteractionStatus.None) {
    return <LoadingSpinner fullScreen message="Signing you in…" />;
  }
  return <SignInScreen />;
}

function AccountSession({ children }: { children: ReactNode }) {
  const [client] = useState(() => (
    new QueryClient({
      defaultOptions: {
        queries: { retry: 1, staleTime: 30_000 },
        mutations: { retry: 0 },
      },
    })
  ));

  return (
    <QueryClientProvider client={client}>
      <VerifiedUserGate>{children}</VerifiedUserGate>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}

function VerifiedUserGate({ children }: { children: ReactNode }) {
  const { data: user, isPending, error, refetch } = useCurrentUser();
  if (isPending) return <LoadingSpinner fullScreen message="Loading your account..." />;
  if (error) {
    return (
      <Stack spacing={2} sx={{ p: 3 }}>
        <Alert severity="error">{getApiErrorMessage(error)}</Alert>
        <Button onClick={() => void refetch()}>Retry</Button>
        {msalInstance && <Button onClick={() => void signOut()}>Sign out</Button>}
      </Stack>
    );
  }
  if (!user) return <Alert severity="error">Unable to load your account.</Alert>;
  return <Fragment key={`${user.tenant_id}:${user.user_id}`}>{children}</Fragment>;
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
