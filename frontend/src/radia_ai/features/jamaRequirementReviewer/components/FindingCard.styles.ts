import type { ChipProps } from '@mui/material/Chip';
import type { SxProps, Theme } from '@mui/material/styles';
import type { StackProps } from '@mui/material/Stack';
import type { FindingDispositionStatus, FindingSeverity } from '@/types/api';

export const findingCardStyles = {
  paper: (severity: FindingSeverity): SxProps<Theme> => ({
    p: 1.5,
    borderRadius: 3,
    borderLeft: '5px solid',
    borderLeftColor: getSeverityBorderColor(severity),
  }),
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 1,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  headerMetaRow: {
    direction: 'row' as const,
    gap: 1,
    flexWrap: 'wrap' as const,
    alignItems: 'center' as const,
  } satisfies StackProps,
  statusRow: {
    direction: 'row' as const,
    spacing: 1,
    alignItems: 'center' as const,
    flexWrap: 'wrap' as const,
  } satisfies StackProps,
  recommendationBox: {
    p: 1.25,
    borderRadius: 2,
    bgcolor: 'action.hover',
  } satisfies SxProps<Theme>,
  detailBodyText: {
    mt: 0.5,
  } satisfies SxProps<Theme>,
  sourceBox: {
    p: 1.25,
    borderRadius: 2,
    border: '1px solid',
    borderColor: 'divider',
  } satisfies SxProps<Theme>,
  accordion: {
    boxShadow: 'none',
    border: '1px solid',
    borderColor: 'divider',
    borderRadius: 2,
    '&:before': { display: 'none' },
    overflow: 'hidden',
  } satisfies SxProps<Theme>,
  changesetHeaderRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    mb: 0.75,
  } satisfies SxProps<Theme>,
  copyButton: {
    minWidth: 0,
    py: 0.25,
    px: 1,
  } satisfies SxProps<Theme>,
  changesetBox: {
    p: 1.25,
    borderRadius: 2,
    border: '1px solid',
    borderColor: 'primary.main',
    bgcolor: 'primary.50',
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  } satisfies SxProps<Theme>,
  preWrapText: {
    whiteSpace: 'pre-wrap',
  } satisfies SxProps<Theme>,
  changesetCaption: {
    mt: 0.5,
    display: 'block',
  } satisfies SxProps<Theme>,
  dispositionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 1.5,
    flexWrap: 'wrap',
  } satisfies SxProps<Theme>,
  reviewerCommentBox: {
    p: 1.25,
    borderRadius: 2,
    border: '1px solid',
    borderColor: 'divider',
    bgcolor: 'action.hover',
  } satisfies SxProps<Theme>,
  actionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 1.5,
  } satisfies SxProps<Theme>,
  savedIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: 0.5,
    color: 'success.main',
  } satisfies SxProps<Theme>,
};

function getSeverityBorderColor(severity: FindingSeverity) {
  if (severity === 'Critical' || severity === 'High') {
    return 'error.main';
  }
  if (severity === 'Medium') {
    return 'warning.main';
  }
  return 'info.main';
}

export function getDispositionChipColor(
  disposition: FindingDispositionStatus
): ChipProps['color'] {
  if (disposition === 'Accepted') {
    return 'success';
  }
  if (disposition === 'Rejected') {
    return 'error';
  }
  return 'warning';
}
