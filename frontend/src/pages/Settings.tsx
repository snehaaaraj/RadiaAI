import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Divider from '@mui/material/Divider';

export default function Settings() {
  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Settings
      </Typography>
      <Paper variant="outlined" sx={{ p: 3, maxWidth: 600 }}>
        <Typography variant="h6" gutterBottom>
          Application Settings
        </Typography>
        <Divider sx={{ my: 2 }} />
        <Typography color="text.secondary">
          Settings configuration will be implemented in Phase 2. This page will include:
          retrieval parameters, model selection, ingestion configuration, and theme preferences.
        </Typography>
      </Paper>
    </Box>
  );
}
