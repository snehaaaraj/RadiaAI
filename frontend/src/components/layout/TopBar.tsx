import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import Popover from '@mui/material/Popover';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import { alpha, useTheme } from '@mui/material/styles';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import BugReportIcon from '@mui/icons-material/BugReport';
import type { MouseEvent } from 'react';
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { RadiaMark } from './RadiaMark';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';

type LandingNavItem = {
  label: string;
  path: string;
};

const SUPPORT_EMAIL = 'sneha.nagaraju@radia.com';
const BUG_REPORT_EMAIL = 'sneha.nagaraju@radia.com';
const LANDING_NAV_ITEMS: LandingNavItem[] = [
  { label: 'RADIA AI', path: ROUTES.RADIA_AI_RESOURCES },
  { label: 'Jama Requirement Reviewer', path: ROUTES.HOME },
  { label: 'Jama Roundtrip', path: ROUTES.JAMA_ROUNDTRIP },
];
const TOOL_RESOURCE_NAME = 'Jama Requirement Reviewer';
const TOOL_WORKSPACE_ROUTE = ROUTES.HOME;
const WORKSPACE_SUBPAGE_LABELS: Record<string, string> = {
  [ROUTES.HOME]: 'Home',
  [ROUTES.REVIEW_REQUIREMENT]: 'Single Review',
  [ROUTES.REVIEW_DELTA]: 'Delta Review',
  [ROUTES.REVIEW_HISTORY]: 'Review History',
  [ROUTES.STANDARDS]: 'Standards',
  [ROUTES.CHAT]: 'Chat',
  [ROUTES.SEARCH]: 'Search',
  [ROUTES.DOCUMENTS]: 'Documents',
  [ROUTES.SETTINGS]: 'Settings',
};

type TopBarMode = 'workspace' | 'landing';

interface TopBarProps {
  mode?: TopBarMode;
}

export function TopBar({ mode = 'workspace' }: TopBarProps) {
  const theme = useTheme();
  const location = useLocation();
  const isLandingMode = mode === 'landing';
  const flightColor = theme.palette.mode === 'dark' ? '#FFFFFF' : '#000000';
  const headerForegroundColor = theme.palette.mode === 'dark' ? '#FFFFFF' : '#2F4659';
  const brandWordmarkColor = theme.palette.mode === 'dark' ? '#FFFFFF' : '#0F172A';
  const hoverHighlight = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.12)' : 'rgba(47,70,89,0.10)';
  const headerSurface = theme.palette.mode === 'dark' ? alpha('#0E1728', 0.62) : alpha('#F7FAFD', 0.78);
  const headerBorder = theme.palette.mode === 'dark' ? alpha('#E2E8F0', 0.16) : alpha('#2F4659', 0.16);
  const { guardedNavigate } = useNavigationGuardContext();
  const [supportAnchor, setSupportAnchor] = useState<HTMLButtonElement | null>(null);

  const openSupport = (event: MouseEvent<HTMLButtonElement>) => setSupportAnchor(event.currentTarget);
  const closeSupport = () => setSupportAnchor(null);
  const isSettingsPage = location.pathname === ROUTES.SETTINGS;
  const currentSubpageLabel = WORKSPACE_SUBPAGE_LABELS[location.pathname] ?? 'Workspace';
  const showGlobalSettings = location.pathname !== ROUTES.LANDING && !isSettingsPage;

  return (
    <AppBar
      position="fixed"
      color="inherit"
      sx={{
        width: '100%',
        zIndex: (theme) => theme.zIndex.drawer + 1,
        borderBottom: '1px solid',
        borderColor: headerBorder,
        borderRadius: 0,
        overflow: 'hidden',
        backgroundColor: headerSurface,
        backdropFilter: 'blur(18px) saturate(150%)',
        WebkitBackdropFilter: 'blur(18px) saturate(150%)',
        boxShadow: theme.palette.mode === 'dark' ? '0 12px 34px rgba(2, 8, 20, 0.36)' : '0 10px 30px rgba(47, 70, 89, 0.18)',
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            theme.palette.mode === 'dark'
              ? 'linear-gradient(180deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.02) 62%)'
              : 'linear-gradient(180deg, rgba(255,255,255,0.82) 0%, rgba(255,255,255,0.15) 62%)',
        },
      }}
    >
      <Toolbar sx={{ gap: 1.5, color: headerForegroundColor, minHeight: `${HEADER_HEIGHT}px !important` }}>
        {/* Brand group — single hover zone: scales as unit, one plane animation */}
        <Box
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 1.5,                    // increased gap between logo and wordmark
            position: 'relative',
            overflow: 'visible',
            cursor: 'default',
            transition: 'transform 180ms ease',
            '&:hover': { transform: 'scale(1.04)' },
            '@keyframes radiaPlaneFly': {
              '0%':   { opacity: 0, transform: 'translate(-18px, 12px) rotate(-18deg) scale(0.9)' },
              '20%':  { opacity: 0.95 },
              '100%': { opacity: 0, transform: 'translate(26px, -14px) rotate(4deg) scale(1)' },
            },
            '& .radia-hover-flight': {
              position: 'absolute',
              left: 20,
              top: -10,
              display: 'inline-flex',
              alignItems: 'center',
              fontSize: 20,
              opacity: 0,
              pointerEvents: 'none',
              willChange: 'transform, opacity',
            },
            '& .radia-hover-plane': { fontSize: 20, color: flightColor },
            '&:hover .radia-hover-flight': {
              animation: 'radiaPlaneFly 2850ms cubic-bezier(0.22, 1, 0.36, 1)',
            },
            '@media (prefers-reduced-motion: reduce)': {
              transition: 'none',
              '&:hover': { transform: 'none' },
              '&:hover .radia-hover-flight': { animation: 'none', opacity: 0 },
            },
          }}
        >
          {/* Single plane — positioned over the logo, flies on parent hover */}
          <Box className="radia-hover-flight" aria-hidden>
            <FlightTakeoffIcon className="radia-hover-plane" />
          </Box>

          {/* Logo mark → opens radia.com in a new tab */}
          <Link
            href="https://radia.com/"
            target="_blank"
            rel="noopener noreferrer"
            underline="none"
            sx={{ display: 'inline-flex', alignItems: 'center' }}
          >
            <RadiaMark size={32} />
          </Link>

          {/* "RADIA" wordmark → navigates to the Launchpad */}
          <Link
            component="button"
            type="button"
            underline="none"
            onClick={() => guardedNavigate(ROUTES.LANDING)}
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              '&:hover': { textDecoration: 'none' },
            }}
          >
            <Typography
              component="span"
              variant="h4"
              fontWeight={900}
              color={brandWordmarkColor}
              sx={{ letterSpacing: '-0.02em', lineHeight: 1.05 }}
            >
              RADIA
            </Typography>
          </Link>
        </Box>
        <Typography component="span" sx={{ color: headerForegroundColor, opacity: 0.65, fontWeight: 700 }}>
          |
        </Typography>
        {isLandingMode ? (
          <Stack direction="row" alignItems="center" spacing={1.25}>
            {LANDING_NAV_ITEMS.map((item, index) => (
              <Stack key={item.label} direction="row" alignItems="center" spacing={1.25}>
                <Link
                  component="button"
                  type="button"
                  underline="none"
                  color={brandWordmarkColor}
                  variant="subtitle1"
                  fontWeight={700}
                  onClick={() => guardedNavigate(item.path)}
                  sx={{
                    px: 0.35,
                    py: 0.2,
                    borderRadius: 1,
                    fontSize: { xs: '0.86rem', md: '0.95rem' },
                    transition: 'transform 160ms ease, background-color 160ms ease',
                    '&:hover': {
                      textDecoration: 'none',
                      backgroundColor: hoverHighlight,
                      transform: 'scale(1.03)',
                    },
                  }}
                >
                  {item.label}
                </Link>
                {index < LANDING_NAV_ITEMS.length - 1 && (
                  <Typography component="span" sx={{ color: headerForegroundColor, opacity: 0.65, fontWeight: 700 }}>
                    |
                  </Typography>
                )}
              </Stack>
            ))}
          </Stack>
        ) : (
          <>
            {isSettingsPage ? (
              <Stack direction="row" alignItems="center" spacing={1.25}>
                <Link
                  component="button"
                  type="button"
                  underline="none"
                  color={brandWordmarkColor}
                  variant="subtitle1"
                  fontWeight={700}
                  onClick={() => guardedNavigate(ROUTES.RADIA_AI_RESOURCES)}
                  sx={{
                    px: 0.35,
                    py: 0.2,
                    borderRadius: 1,
                    fontSize: { xs: '0.86rem', md: '0.95rem' },
                    transition: 'transform 160ms ease, background-color 160ms ease',
                    '&:hover': {
                      textDecoration: 'none',
                      backgroundColor: hoverHighlight,
                      transform: 'scale(1.03)',
                    },
                  }}
                >
                  Radia AI
                </Link>
                <Typography component="span" sx={{ color: headerForegroundColor, opacity: 0.65, fontWeight: 700 }}>
                  |
                </Typography>
                <Typography component="span" variant="subtitle1" sx={{ color: brandWordmarkColor, fontWeight: 700 }}>
                  Settings
                </Typography>
              </Stack>
            ) : (
              <Stack direction="row" alignItems="center" spacing={1.25}>
                <Link
                  component="button"
                  type="button"
                  underline="none"
                  color={brandWordmarkColor}
                  variant="subtitle1"
                  fontWeight={700}
                  onClick={() => guardedNavigate(ROUTES.RADIA_AI_RESOURCES)}
                  sx={{
                    px: 0.35,
                    py: 0.2,
                    borderRadius: 1,
                    fontSize: { xs: '0.86rem', md: '0.95rem' },
                    transition: 'transform 160ms ease, background-color 160ms ease',
                    '&:hover': {
                      textDecoration: 'none',
                      backgroundColor: hoverHighlight,
                      transform: 'scale(1.03)',
                    },
                  }}
                >
                  Radia AI
                </Link>
                <Typography component="span" sx={{ color: headerForegroundColor, opacity: 0.65, fontWeight: 700 }}>
                  |
                </Typography>
                <Link
                  component="button"
                  type="button"
                  underline="none"
                  color={brandWordmarkColor}
                  variant="subtitle1"
                  fontWeight={700}
                  onClick={() => guardedNavigate(TOOL_WORKSPACE_ROUTE)}
                  sx={{
                    px: 0.35,
                    py: 0.2,
                    borderRadius: 1,
                    fontSize: { xs: '0.86rem', md: '0.95rem' },
                    transition: 'transform 160ms ease, background-color 160ms ease',
                    '&:hover': {
                      textDecoration: 'none',
                      backgroundColor: hoverHighlight,
                      transform: 'scale(1.03)',
                    },
                  }}
                >
                  {TOOL_RESOURCE_NAME}
                </Link>
                <Typography component="span" sx={{ color: headerForegroundColor, opacity: 0.65, fontWeight: 700 }}>
                  |
                </Typography>
                <Typography
                  component="span"
                  variant="body2"
                  sx={{
                    color: alpha(brandWordmarkColor, 0.88),
                    fontWeight: 500,
                    fontSize: { xs: '0.78rem', md: '0.84rem' },
                    fontStyle: 'italic',
                    letterSpacing: '0.01em',
                  }}
                >
                  {currentSubpageLabel}
                </Typography>
              </Stack>
            )}
          </>
        )}
        <Box sx={{ flexGrow: 1 }} />

        {showGlobalSettings && (
          <Button
            color="inherit"
            onClick={() => guardedNavigate(ROUTES.SETTINGS)}
            sx={{
              textTransform: 'none',
              minWidth: 'auto',
              fontWeight: 600,
              color: headerForegroundColor,
              px: 1,
              borderRadius: 1,
              transition: 'transform 160ms ease, background-color 160ms ease',
              '&:hover': {
                backgroundColor: hoverHighlight,
                transform: 'scale(1.04)',
              },
            }}
          >
            Settings
          </Button>
        )}
        <Button
          color="inherit"
          onClick={openSupport}
          sx={{
            textTransform: 'none',
            minWidth: 'auto',
            fontWeight: 600,
            color: headerForegroundColor,
            px: 1,
            borderRadius: 1,
            transition: 'transform 160ms ease, background-color 160ms ease',
            '&:hover': {
              backgroundColor: hoverHighlight,
              transform: 'scale(1.04)',
            },
          }}
        >
          Contact
        </Button>
        <Popover
          open={Boolean(supportAnchor)}
          anchorEl={supportAnchor}
          onClose={closeSupport}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <Stack spacing={1} sx={{ p: 2.25, minWidth: 280 }}>
            <Typography variant="subtitle2" fontWeight={700}>
              Contact support
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <SupportAgentIcon fontSize="small" color="action" />
              <Link href={`mailto:${SUPPORT_EMAIL}`} underline="hover">
                {SUPPORT_EMAIL}
              </Link>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center">
              <BugReportIcon fontSize="small" color="action" />
              <Link href={`mailto:${BUG_REPORT_EMAIL}?subject=Radia%20AI%202.0%20Bug%20Report`} underline="hover">
                Report a bug
              </Link>
            </Stack>
          </Stack>
        </Popover>
      </Toolbar>
    </AppBar>
  );
}
