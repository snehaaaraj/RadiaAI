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
import { useTheme } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import BugReportIcon from '@mui/icons-material/BugReport';
import type { KeyboardEvent, MouseEvent } from 'react';
import { useMemo, useState } from 'react';
import { RadiaMark } from './RadiaMark';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { ROUTES } from '@/utils/constants';

type HeaderSearchOption = {
  label: string;
  path: string;
  keywords: string[];
};

const HEADER_SEARCH_OPTIONS: HeaderSearchOption[] = [
  { label: 'Launchpad', path: ROUTES.LANDING, keywords: ['launchpad', 'landing', 'start', 'radia ai 2.0'] },
  { label: 'Home', path: ROUTES.HOME, keywords: ['home', 'workspace'] },
  { label: 'Single Review', path: ROUTES.REVIEW_REQUIREMENT, keywords: ['single review', 'requirement'] },
  { label: 'Delta Review', path: ROUTES.REVIEW_DELTA, keywords: ['delta review', 'delta'] },
  { label: 'Review History', path: ROUTES.REVIEW_HISTORY, keywords: ['history', 'review history'] },
  { label: 'Standards', path: ROUTES.STANDARDS, keywords: ['standards', 'library'] },
  { label: 'Settings', path: ROUTES.SETTINGS, keywords: ['settings', 'preferences'] },
];

const SUPPORT_EMAIL = 'sneha.nagaraju@radia.com';
const BUG_REPORT_EMAIL = 'sneha.nagaraju@radia.com';

export function TopBar() {
  const theme = useTheme();
  const headerForegroundColor = theme.palette.mode === 'dark' ? '#FFFFFF' : '#2F4659';
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
      <Toolbar sx={{ gap: 1.5, color: headerForegroundColor }}>
        <RadiaMark size={32} />
        <Link
          href="https://radia.com/"
          target="_blank"
          rel="noopener noreferrer"
          underline="none"
          color={headerForegroundColor}
          variant="h6"
          fontWeight={800}
          sx={{ '&:hover': { textDecoration: 'underline' } }}
        >
          RADIA
        </Link>
        <Box sx={{ width: 3, height: 24, bgcolor: headerForegroundColor, borderRadius: 1 }} />
        <Link
          component="button"
          type="button"
          underline="none"
          color={headerForegroundColor}
          variant="h6"
          fontWeight={800}
          onClick={() => guardedNavigate(ROUTES.LANDING)}
          sx={{ '&:hover': { textDecoration: 'underline' } }}
        >
          Radia AI 2.0
        </Link>
        <Box sx={{ flexGrow: 1 }} />

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

        <Button
          color="inherit"
          onClick={openSupport}
          sx={{ textTransform: 'none', minWidth: 'auto', fontWeight: 600, color: headerForegroundColor }}
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
