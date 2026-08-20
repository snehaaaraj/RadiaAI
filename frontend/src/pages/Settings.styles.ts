import type { SxProps, Theme } from '@mui/material/styles';
import type { CSSProperties } from 'react';

export const settingsStyles = {
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 1.25,
    mb: 1.5,
  } satisfies SxProps<Theme>,
  themeOptionWrapper: {
    flex: 1,
  } satisfies CSSProperties,
  themeOptionCard: (selected: boolean): SxProps<Theme> => ({
    height: '100%',
    borderColor: selected ? 'primary.main' : 'divider',
    boxShadow: selected ? 3 : undefined,
  }),
  fullHeight: {
    height: '100%',
  } satisfies SxProps<Theme>,
  themeOptionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    mb: 1,
  } satisfies SxProps<Theme>,
  settingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 2,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  workspacePageSelect: {
    minWidth: 260,
  } satisfies SxProps<Theme>,
  resetDescription: {
    mb: 2,
  } satisfies SxProps<Theme>,
};

export const getSettingsSectionCardSx = (headerHeight: number): SxProps<Theme> => ({
  scrollMarginTop: `${headerHeight + 24}px`,
});
