/**
 * MUI theme configuration — Radia AI brand colours and typography.
 */

import { createTheme, type PaletteMode } from '@mui/material/styles';
import type { AccentColor, UiDensity } from '@/context/AppContext';

const ACCENT_COLORS: Record<AccentColor, { light: string; dark: string }> = {
  indigo: { light: '#1B4FD8', dark: '#7C9CFF' },
  violet: { light: '#6B21A8', dark: '#C084FC' },
  teal: { light: '#0F766E', dark: '#2DD4BF' },
  rose: { light: '#BE185D', dark: '#FB7185' },
};

export function createAppTheme(mode: PaletteMode, accentColor: AccentColor, density: UiDensity) {
  const isDark = mode === 'dark';
  const primaryBase = ACCENT_COLORS[accentColor];
  const compact = density === 'compact';

  return createTheme({
    palette: {
      mode,
      primary: {
        main: isDark ? primaryBase.dark : primaryBase.light,
        light: isDark ? '#D2DFFF' : '#5B82F0',
        dark: isDark ? '#5C7EF5' : '#0F3BAE',
      },
      secondary: {
        main: isDark ? '#C084FC' : '#7E22CE',
        light: isDark ? '#E9D5FF' : '#A855F7',
        dark: isDark ? '#A855F7' : '#581C87',
      },
      background: {
        default: isDark ? '#0B1220' : '#F8FAFC',
        paper: isDark ? '#111827' : '#FFFFFF',
      },
      error: { main: '#DC2626' },
      warning: { main: '#D97706' },
      success: { main: '#16A34A' },
      text: {
        primary: isDark ? '#E5EEF9' : '#0F172A',
        secondary: isDark ? '#9CA3AF' : '#64748B',
      },
      divider: isDark ? 'rgba(255,255,255,0.10)' : 'rgba(15, 23, 42, 0.10)',
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontWeight: 800, letterSpacing: '-0.03em' },
      h2: { fontWeight: 800, letterSpacing: '-0.03em' },
      h3: { fontWeight: 700, letterSpacing: '-0.02em' },
      h4: { fontWeight: 700, letterSpacing: '-0.02em' },
      h5: { fontWeight: 700 },
      h6: { fontWeight: 700 },
      body1: { lineHeight: 1.7 },
      button: { fontWeight: 700 },
    },
    shape: {
      borderRadius: compact ? 12 : 14,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundImage: isDark
              ? 'radial-gradient(circle at top left, rgba(124,156,255,0.12), transparent 35%), radial-gradient(circle at top right, rgba(192,132,252,0.08), transparent 24%)'
              : 'radial-gradient(circle at top left, rgba(27,79,216,0.08), transparent 34%), radial-gradient(circle at top right, rgba(107,33,168,0.05), transparent 24%)',
            backgroundAttachment: 'fixed',
          },
        },
      },
      MuiButton: {
        defaultProps: {
          size: compact ? 'small' : 'medium',
        },
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: 999,
            paddingInline: compact ? 14 : 18,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            minHeight: compact ? 40 : 46,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: compact ? 16 : 20,
            transition: 'transform 160ms ease, box-shadow 160ms ease',
            '&:hover': {
              transform: 'translateY(-2px)',
            },
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 18,
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)'}`,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 700,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backdropFilter: 'blur(12px)',
            backgroundImage: 'none',
            boxShadow: isDark
              ? '0 10px 30px rgba(0,0,0,0.25)'
              : '0 10px 30px rgba(15,23,42,0.08)',
          },
        },
      },
    },
  });
}

export default createAppTheme;
