import type { SxProps, Theme } from '@mui/material/styles';
import radiaLogo from '@/assets/radia-circle-white background.png?inline';

const processingCursor = `url("data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="white" stroke="#cbd5e1" stroke-width="2"/><image href="${radiaLogo}" x="8" y="8" width="24" height="24"/><path d="M20 2a18 18 0 0 1 18 18" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round"/></svg>`,
)}") 20 20, progress`;

export const requirementReviewStyles = {
  processingWorkspace: {
    '@media (hover: hover) and (pointer: fine)': {
      '&, & *': {
        cursor: `${processingCursor} !important`,
      },
    },
  } satisfies SxProps<Theme>,
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
