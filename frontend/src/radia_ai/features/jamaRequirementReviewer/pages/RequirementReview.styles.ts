import type { SxProps, Theme } from '@mui/material/styles';
import lightRadiaLogo from '@/assets/radia-circle-white background.png?inline';
import darkRadiaLogo from '@/assets/radia-circle-white lines.jpg?inline';

const processingWorkspace = (theme: Theme) => {
  const logo = theme.palette.mode === 'dark' ? darkRadiaLogo : lightRadiaLogo;
  const cursor = `url("data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="${theme.palette.background.paper}" stroke="${theme.palette.primary.main}" stroke-width="2"/><image href="${logo}" x="8" y="8" width="24" height="24"/></svg>`,
  )}") 17 17, progress`;

  return {
    '@media (hover: hover) and (pointer: fine)': {
      '&, & *': {
        cursor: `${cursor} !important`,
      },
    },
  };
};

export const requirementReviewStyles = {
  processingWorkspace,
  sectionPaper: {
    p: 2.5,
  } satisfies SxProps<Theme>,
  fieldLabel: {
    display: 'block',
    mb: 0.75,
  } satisfies SxProps<Theme>,
  inputModeRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 1,
    flexWrap: 'wrap',
    mb: 1.5,
  } satisfies SxProps<Theme>,
  uploadAlert: {
    py: 0.5,
  } satisfies SxProps<Theme>,
  actionRow: {
    display: 'flex',
    gap: 1,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
};
