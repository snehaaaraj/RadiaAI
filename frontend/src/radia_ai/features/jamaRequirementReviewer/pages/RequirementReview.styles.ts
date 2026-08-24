import type { SxProps, Theme } from '@mui/material/styles';

export const requirementReviewStyles = {
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
