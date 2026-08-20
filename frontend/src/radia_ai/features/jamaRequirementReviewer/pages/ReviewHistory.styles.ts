import type { SxProps, Theme } from '@mui/material/styles';

export const reviewHistoryStyles = {
  filterRow: {
    display: 'flex',
    gap: 2,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  filterSelect: {
    minWidth: 200,
  } satisfies SxProps<Theme>,
  resultCount: {
    alignSelf: 'center',
  } satisfies SxProps<Theme>,
  entryPaper: {
    p: 2.5,
  } satisfies SxProps<Theme>,
  entryHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 1,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  categoryRow: {
    display: 'flex',
    gap: 1,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  paginationRow: {
    display: 'flex',
    justifyContent: 'center',
    pt: 1,
  } satisfies SxProps<Theme>,
};
