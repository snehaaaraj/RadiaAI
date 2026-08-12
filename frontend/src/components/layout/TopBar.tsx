import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import { RadiaMark } from './RadiaMark';
import { APP_NAME } from '@/utils/constants';

export function TopBar() {
  return (
    <AppBar
      position="fixed"
      color="inherit"
      sx={{
        width: '100%',
        zIndex: (theme) => theme.zIndex.drawer + 1,
        borderBottom: '1px solid',
        borderColor: 'divider',
        boxShadow: 'none',
      }}
    >
      <Toolbar sx={{ gap: 1.5 }}>
        <RadiaMark size={32} />
        <Typography variant="h6" fontWeight={800} color="text.primary" noWrap>
          {APP_NAME}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
      </Toolbar>
    </AppBar>
  );
}
