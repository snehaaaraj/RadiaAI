import { useState, type FormEvent } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import LinkIcon from '@mui/icons-material/Link';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import {
  useJamaAccount,
  useJamaAccountMutations,
} from '@/radia_ai/features/jamaRequirementReviewer/hooks/useJama';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';

/**
 * Lets the signed-in user link their own Jama account.
 *
 * Jama has no "Sign in with Jama" (OAuth authorization-code) flow, so users paste
 * personal API credentials once. Radia verifies them with Jama, checks they belong
 * to the signed-in Microsoft user, and stores them encrypted. Every Jama request
 * then runs as that user, so Jama enforces their own project permissions.
 */
export function JamaAccountCard() {
  const accountQuery = useJamaAccount();
  const { link, unlink } = useJamaAccountMutations();
  const [editing, setEditing] = useState(false);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  const account = accountQuery.data;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    link.mutate(
      { client_id: clientId.trim(), client_secret: clientSecret.trim() },
      {
        onSuccess: () => {
          setClientSecret('');
          setClientId('');
          setEditing(false);
        },
      }
    );
  };

  if (accountQuery.isLoading) {
    return <CircularProgress size={24} />;
  }
  if (accountQuery.isError || !account) {
    return (
      <Alert severity="warning" variant="outlined">
        Could not load your Jama account status: {getApiErrorMessage(accountQuery.error)}
      </Alert>
    );
  }

  if (!account.linking_enabled) {
    return account.using_shared_account ? (
      <Alert severity="info" variant="outlined">
        Local development: Jama requests use the shared service account configured on the server.
      </Alert>
    ) : (
      <Alert severity="info" variant="outlined">
        Jama account linking is not enabled on this server. Ask an administrator to configure Jama.
      </Alert>
    );
  }

  const jamaHome = account.jama_base_url ?? undefined;

  if (account.linked && !editing) {
    return (
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} alignItems="center">
          <VerifiedUserIcon color="success" fontSize="small" />
          <Typography variant="body1">
            Linked as <strong>{account.jama_display_name || account.jama_username}</strong>
            {account.jama_email ? ` (${account.jama_email})` : ''}
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Radia only shows and edits the Jama projects your own Jama account can access.
          {account.linked_at
            ? ` Linked ${new Date(account.linked_at).toLocaleDateString()}.`
            : ''}
        </Typography>
        {unlink.isError && (
          <Alert severity="error" variant="outlined">
            {getApiErrorMessage(unlink.error)}
          </Alert>
        )}
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<LinkIcon />} onClick={() => setEditing(true)}>
            Replace credentials
          </Button>
          <Button
            color="error"
            startIcon={unlink.isPending ? <CircularProgress size={16} /> : <LinkOffIcon />}
            onClick={() => unlink.mutate()}
            disabled={unlink.isPending}
          >
            Unlink
          </Button>
        </Stack>
      </Stack>
    );
  }

  return (
    <Box component="form" onSubmit={submit}>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          Link your Jama account so Radia can read and write Jama as you, limited to the projects
          you can access in Jama. Jama does not support Microsoft sign-in for its API, so this is
          a one-time step:
        </Typography>
        <Box component="ol" sx={{ m: 0, pl: 3, '& li': { mb: 0.5 } }}>
          <li>
            <Typography variant="body2">
              Open{' '}
              {jamaHome ? (
                <Link href={jamaHome} target="_blank" rel="noopener noreferrer">
                  Jama
                </Link>
              ) : (
                'Jama'
              )}
              , click your profile picture, and choose <strong>Set API Credentials</strong>.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              Enter a name such as <em>Radia AI</em> and select <strong>Create credentials</strong>.
            </Typography>
          </li>
          <li>
            <Typography variant="body2">
              Copy the client ID and secret below. The secret is encrypted and never shown again.
            </Typography>
          </li>
        </Box>
        <TextField
          label="Jama client ID"
          size="small"
          value={clientId}
          onChange={(event) => setClientId(event.target.value)}
          autoComplete="off"
          required
          fullWidth
        />
        <TextField
          label="Jama client secret"
          size="small"
          type="password"
          value={clientSecret}
          onChange={(event) => setClientSecret(event.target.value)}
          autoComplete="new-password"
          required
          fullWidth
        />
        {link.isError && (
          <Alert severity="error" variant="outlined">
            {getApiErrorMessage(link.error)}
          </Alert>
        )}
        <Stack direction="row" spacing={1}>
          <Button
            type="submit"
            variant="contained"
            startIcon={link.isPending ? <CircularProgress size={16} color="inherit" /> : <LinkIcon />}
            disabled={link.isPending || !clientId.trim() || !clientSecret.trim()}
          >
            {link.isPending ? 'Verifying with Jama…' : 'Link Jama account'}
          </Button>
          {account.linked && (
            <Button onClick={() => setEditing(false)} disabled={link.isPending}>
              Cancel
            </Button>
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
