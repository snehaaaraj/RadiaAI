import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Box from '@mui/material/Box';

interface NavigationConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function NavigationConfirmDialog({ open, onConfirm, onCancel }: NavigationConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="xs"
      fullWidth
      PaperProps={{ elevation: 8 }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <WarningAmberIcon color="warning" />
          Discard review in progress?
        </Box>
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          You have an ongoing review with unsaved input. Navigating away will discard all current
          data. This cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
        <Button variant="outlined" onClick={onCancel} autoFocus>
          Cancel
        </Button>
        <Button variant="contained" color="error" onClick={onConfirm}>
          Yes, discard
        </Button>
      </DialogActions>
    </Dialog>
  );
}
