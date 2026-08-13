import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import Link from '@mui/material/Link';
import Popover from '@mui/material/Popover';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import Autocomplete from '@mui/material/Autocomplete';
import InputAdornment from '@mui/material/InputAdornment';
import { alpha, useTheme } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import BugReportIcon from '@mui/icons-material/BugReport';
import type { KeyboardEvent, MouseEvent } from 'react';
import { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { RadiaMark } from './RadiaMark';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';

type HeaderSearchOption = {
  label: string;
  path: string;
  keywords: string[];
};

type LandingNavItem = {
  label: string;
  path: string;
};

const HEADER_SEARCH_OPTIONS: HeaderSearchOption[] = [
  { label: 'Launchpad', path: ROUTES.LANDING, keywords: ['launchpad', 'landing', 'start', 'radia ai 2.0'] },
  {
    label: 'Radia AI Resources',
    path: ROUTES.RADIA_AI_RESOURCES,
    keywords: ['radia ai', 'resources', 'tools', 'jama requirement review', 'jama roundtrip'],
  },
  { label: 'Home', path: ROUTES.HOME, keywords: ['home', 'workspace'] },
  { label: 'Single Review', path: ROUTES.REVIEW_REQUIREMENT, keywords: ['single review', 'requirement'] },
  { label: 'Delta Review', path: ROUTES.REVIEW_DELTA, keywords: ['delta review', 'delta'] },
  { label: 'Review History', path: ROUTES.REVIEW_HISTORY, keywords: ['history', 'review history'] },
  { label: 'Standards', path: ROUTES.STANDARDS, keywords: ['standards', 'library'] },
  { label: 'Settings', path: ROUTES.SETTINGS, keywords: ['settings', 'preferences'] },
];

const SUPPORT_EMAIL = 'sneha.nagaraju@radia.com';
const BUG_REPORT_EMAIL = 'sneha.nagaraju@radia.com';
const LANDING_NAV_ITEMS: LandingNavItem[] = [
  { label: 'RADIA AI', path: ROUTES.RADIA_AI_RESOURCES },
  { label: 'Jama Requirement Review', path: ROUTES.HOME },
  { label: 'Jama Roundtrip', path: `${ROUTES.RADIA_AI_RESOURCES}?tool=jama-roundtrip` },
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
  showSearch?: boolean;
  mode?: TopBarMode;
}

export function TopBar({ showSearch = true, mode = 'workspace' }: TopBarProps) {
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
  const [searchValue, setSearchValue] = useState<HeaderSearchOption | null>(null);
  const [searchInputValue, setSearchInputValue] = useState('');
  const [supportAnchor, setSupportAnchor] = useState<HTMLButtonElement | null>(null);

  const uniqueSearchOptions = useMemo(
    () => HEADER_SEARCH_OPTIONS.filter((option, index, all) => all.findIndex((item) => item.path === option.path) === index),
    []
  );

  const navigateToSearchOption = (option: HeaderSearchOption | null, rawInput?: string) => {
    if (option) {
      guardedNavigate(option.path);
      return;
    }

    const normalized = (rawInput ?? '').trim().toLowerCase();
    if (!normalized) return;

    const matched = HEADER_SEARCH_OPTIONS.find((item) => {
      if (item.label.toLowerCase().includes(normalized)) return true;
      return item.keywords.some((keyword) => keyword.includes(normalized));
    });

    if (matched) guardedNavigate(matched.path);
  };

  const handleSearchEnter = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    navigateToSearchOption(searchValue, searchInputValue);
  };

  const openSupport = (event: MouseEvent<HTMLButtonElement>) => setSupportAnchor(event.currentTarget);
  const closeSupport = () => setSupportAnchor(null);
  const currentSubpageLabel = WORKSPACE_SUBPAGE_LABELS[location.pathname] ?? 'Workspace';

  return (
    <AppBar
      position="fixed"
      color="inherit"
      sx={{
        width: '100%',
        zIndex: (theme) => theme.zIndex.drawer + 1,
        borderBottom: '1px solid',
        borderColor: headerBorder,
        borderBottomLeftRadius: 16,
        borderBottomRightRadius: 16,
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
        <Link
          href="https://radia.com/"
          target="_blank"
          rel="noopener noreferrer"
          underline="none"
          sx={{
            px: 0.65,
            py: 0.25,
            borderRadius: 1,
            position: 'relative',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 1,
            overflow: 'visible',
            transition: 'transform 180ms ease',
            '&:hover': {
              textDecoration: 'none',
              transform: 'scale(1.05)',
            },
            '@keyframes radiaPlaneFly': {
              '0%': {
                opacity: 0,
                transform: 'translate(-18px, 12px) rotate(-18deg) scale(0.9)',
              },
              '20%': {
                opacity: 0.95,
              },
              '100%': {
                opacity: 0,
                transform: 'translate(26px, -14px) rotate(4deg) scale(1)',
              },
            },
            '& .radia-hover-flight': {
              position: 'absolute',
              left: 20,
              top: -8,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 20,
              opacity: 0,
              pointerEvents: 'none',
              willChange: 'transform, opacity',
            },
            '& .radia-hover-plane': {
              fontSize: 20,
              color: flightColor,
            },
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
          <Box className="radia-hover-flight" aria-hidden>
            <FlightTakeoffIcon className="radia-hover-plane" />
          </Box>
          <RadiaMark size={32} />
          <Typography
            component="span"
            variant={isLandingMode ? 'h4' : 'h5'}
            fontWeight={900}
            color={brandWordmarkColor}
            sx={{ letterSpacing: '-0.02em', lineHeight: 1.05 }}
          >
            RADIA
          </Typography>
        </Link>
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
              variant="subtitle1"
              sx={{ color: brandWordmarkColor, fontWeight: 600, fontSize: { xs: '0.84rem', md: '0.93rem' } }}
            >
              {currentSubpageLabel}
            </Typography>
          </Stack>
        )}
        <Box sx={{ flexGrow: 1 }} />

        {showSearch && (
          <Autocomplete
            value={searchValue}
            onChange={(_event, option) => {
              setSearchValue(option);
              navigateToSearchOption(option);
            }}
            inputValue={searchInputValue}
            onInputChange={(_event, value) => setSearchInputValue(value)}
            options={uniqueSearchOptions}
            getOptionLabel={(option) => option.label}
            size="small"
            sx={{
              width: 320,
              '& .MuiInputBase-root': {
                color: headerForegroundColor,
                transition: 'transform 160ms ease, background-color 160ms ease',
                '&:hover': {
                  backgroundColor: hoverHighlight,
                  transform: 'scale(1.01)',
                },
              },
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.35)' : 'rgba(47,70,89,0.35)',
              },
            }}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder="Search tabs..."
                onKeyDown={handleSearchEnter}
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" sx={{ color: headerForegroundColor }} />
                    </InputAdornment>
                  ),
                }}
              />
            )}
          />
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
