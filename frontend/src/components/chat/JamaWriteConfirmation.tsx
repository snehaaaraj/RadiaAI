import { useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { confirmJamaWrite } from '@/api/chat';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import type { ChatData, JamaWritePreview } from '@/types/api';

function previewText(value: unknown): string {
  if (typeof value !== 'string') return JSON.stringify(value, null, 2) ?? '';
  if (!/<\/?[a-z][^>]*>/i.test(value)) return value;

  const template = document.createElement('template');
  template.innerHTML = value;
  template.content.querySelectorAll('script, style').forEach((element) => element.remove());
  template.content.querySelectorAll('br').forEach((element) => {
    element.replaceWith(document.createTextNode('\n'));
  });
  template.content.querySelectorAll('p, div, li, h1, h2, h3, h4, h5, h6, tr').forEach((element) => {
    element.appendChild(document.createTextNode('\n'));
  });
  return (template.content.textContent ?? '').trim();
}

export function JamaWriteConfirmation({
  preview, disabled, onComplete, onCancel, onError,
}: {
  preview: JamaWritePreview;
  disabled: boolean;
  onComplete: (data: ChatData) => void;
  onCancel: () => void;
  onError?: (message: string) => void;
}) {
  const { data: user } = useCurrentUser();
  const owner = user ? `${user.tenant_id}:${user.user_id}` : null;
  const [originalOwner] = useState(owner);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState('');
  const submitted = useRef(false);
  const activeOwner = useRef(owner);
  activeOwner.current = owner;

  if (!owner || owner !== originalOwner) return null;

  const confirm = async () => {
    if (submitted.current || disabled) return;
    submitted.current = true;
    setWriting(true);
    try {
      const result = await confirmJamaWrite(preview.confirmation_token);
      if (activeOwner.current === originalOwner) onComplete(result);
    } catch (failure) {
      if (activeOwner.current === originalOwner) {
        const message = getApiErrorMessage(failure) +
          ' Check the item in Jama before preparing another write.';
        setError(message);
        onError?.(message);
      }
    } finally {
      setWriting(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack spacing={1}>
        <Typography fontWeight={700}>
          Confirm Jama update: {preview.document_key ?? preview.item_id} (ID {preview.item_id})
        </Typography>
        <Typography variant="body2">{preview.name}</Typography>
        <Alert severity="warning">
          Nothing has been written. Only the fields below will change. Preview expires in 10 minutes.
        </Alert>
        {!!preview.preserved_fields?.length && (
          <Alert severity="info">
            Existing required field values will also be resubmitted unchanged.
            Unchecked checkboxes remain No (false); missing values are not filled automatically.
          </Alert>
        )}
        {preview.changes.map((change) => (
          <Box key={change.field}>
            <Typography fontWeight={700}>{change.label} ({change.field})</Typography>
            <Typography variant="caption">Before</Typography>
            <Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', m: 0 }}>
              {previewText(change.before)}
            </Box>
            <Typography variant="caption">After</Typography>
            <Box component="pre" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', m: 0 }}>
              {previewText(change.after)}
            </Box>
          </Box>
        ))}
        {error && <Alert severity="error">{error}</Alert>}
        <Stack direction="row" spacing={1}>
          <Button variant="contained" disabled={disabled || writing || submitted.current}
            onClick={() => void confirm()}>
            {writing ? 'Writing to Jama…' : 'Confirm & write to Jama'}
          </Button>
          <Button disabled={writing} onClick={onCancel}>Cancel</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}
