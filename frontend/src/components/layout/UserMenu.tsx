import { useState, type MouseEvent } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Popover from '@mui/material/Popover';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { SxProps, Theme } from '@mui/material/styles';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import LinkIcon from '@mui/icons-material/Link';
import LogoutIcon from '@mui/icons-material/Logout';
import { getActiveAccount, signOut } from '@/auth/msal';
import { isAuthEnabled } from '@/auth/authConfig';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { ROUTES } from '@/utils/constants';
import { SETTINGS_SECTION_IDS } from '@/utils/settingsSections';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';

interface UserMenuProps {
  buttonSx?: SxProps<Theme>;
  onNavigate: (path: string) => void;
}

/** Signed-in user, their Radia roles, Jama account shortcut, and sign-out. */
export function UserMenu({ buttonSx, onNavigate }: UserMenuProps) {
  const { data: user, error } = useCurrentUser();
  const account = getActiveAccount();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  if (!user && !account) return null;

  const displayName = user?.display_name || account?.name || '';
  const email = user?.email || account?.username || '';
  const firstName = (displayName || email).split(/[\s@]/)[0] || 'Account';
  const close = () => setAnchor(null);

  return (
    <>
      <Button
        color="inherit"
        startIcon={<AccountCircleIcon />}
        onClick={(event: MouseEvent<HTMLElement>) => setAnchor(event.currentTarget)}
        sx={buttonSx}
        aria-label="Account"
      >
        {firstName}
      </Button>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Stack spacing={1.5} sx={{ p: 2.25, minWidth: 280 }}>
          <Stack spacing={0.25}>
            <Typography variant="subtitle2" fontWeight={700}>
              {displayName}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {email}
            </Typography>
          </Stack>
          {error ? (
            <Alert severity="error">{getApiErrorMessage(error)}</Alert>
          ) : !user ? (
            <Typography variant="body2" color="text.secondary">
              Loading your Radia account...
            </Typography>
          ) : null}
          {user && (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              <Chip label={user.is_admin ? 'Admin' : 'User'} size="small" />
              {user.auth_method === 'local' && (
                <Chip label="Local dev" size="small" color="warning" variant="outlined" />
              )}
            </Stack>
          )}
          <Divider />
          {user && (
            <Button
              startIcon={<LinkIcon />}
              sx={{ justifyContent: 'flex-start', textTransform: 'none' }}
              onClick={() => {
                close();
                onNavigate(`${ROUTES.SETTINGS}#${SETTINGS_SECTION_IDS.JAMA_ACCOUNT}`);
              }}
            >
              Jama account
            </Button>
          )}
          {isAuthEnabled && (
            <Button
              color="inherit"
              startIcon={<LogoutIcon />}
              sx={{ justifyContent: 'flex-start', textTransform: 'none' }}
              onClick={() => void signOut()}
            >
              Sign out
            </Button>
          )}
        </Stack>
      </Popover>
    </>
  );
}
