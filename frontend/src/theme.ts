/**
 * MUI theme configuration — Radia AI brand colours and typography.
 *
 * Components import useTheme() or the ThemeProvider from here.
 * Override individual component styles in the 'components' section to keep
 * global styles centralised rather than scattered in sx props.
 */

import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1B4FD8',       // Radia blue
      light: '#4F78E3',
      dark: '#1239A5',
    },
    secondary: {
      main: '#6B21A8',       // Deep purple accent
      light: '#9B4DD1',
      dark: '#4A1577',
    },
    background: {
      default: '#F8FAFC',
      paper: '#FFFFFF',
    },
    error: { main: '#DC2626' },
    warning: { main: '#D97706' },
    success: { main: '#16A34A' },
    text: {
      primary: '#0F172A',
      secondary: '#64748B',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontWeight: 700 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 600 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    body1: { lineHeight: 1.7 },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        },
      },
    },
  },
});

export default theme;
