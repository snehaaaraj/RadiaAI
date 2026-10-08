import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MergeTypeIcon from '@mui/icons-material/MergeType';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import GavelIcon from '@mui/icons-material/Gavel';
import type {
  ApplyFindingDispositionRequest,
  FinalRecommendation,
  FindingDisposition,
  ReviewFinding,
} from '@/types/api';
import {
  CONTRIBUTION_STATUS_LABEL,
  findingSourceLabel,
  groupEvidence,
  type EvidenceGroupKey,
  type EvidenceItem,
} from '../utils/recommendationEvidence';
import { FindingCard } from './FindingCard';
import { finalRecommendationStyles as styles } from './FinalRecommendationPanel.styles';

const GROUP_ICON: Record<EvidenceGroupKey, JSX.Element> = {
  applied: <CheckCircleIcon fontSize="small" color="success" />,
  merged: <MergeTypeIcon fontSize="small" color="info" />,
  overridden: <GavelIcon fontSize="small" color="secondary" />,
  unresolved: <WarningAmberIcon fontSize="small" color="warning" />,
  not_incorporated: <RemoveCircleOutlineIcon fontSize="small" color="disabled" />,
};

interface RecommendationEvidenceProps {
  recommendation: FinalRecommendation;
  findings: ReviewFinding[];
  onViewRule: (ruleId: string) => void;
  reviewId?: string | null;
  dispositions?: FindingDisposition[];
  onApplyDisposition?: (reviewId: string, payload: ApplyFindingDispositionRequest) => void;
  isApplyingDisposition?: boolean;
  readOnly?: boolean;
}

/** Supporting evidence: every individual suggestion and how it shaped the final recommendation. */
export function RecommendationEvidence({
  recommendation,
  findings,
  onViewRule,
  reviewId,
  dispositions = [],
  onApplyDisposition,
  isApplyingDisposition = false,
  readOnly = false,
}: RecommendationEvidenceProps) {
  const groups = groupEvidence(recommendation, findings);
  const total = recommendation.contributions.length;

  return (
    <Accordion disableGutters sx={styles.accordion}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Typography variant="subtitle1" fontWeight={800}>
            Supporting evidence ({total})
          </Typography>
          {groups.map((group) => (
            <Chip
              key={group.key}
              size="small"
              variant="outlined"
              icon={GROUP_ICON[group.key]}
              label={`${group.label}: ${group.items.length}`}
            />
          ))}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          <Typography variant="body2" color="text.secondary">
            Each individual suggestion from the standards review, and how it was used in the final
            recommendation. Expand a suggestion to see its source passage and rationale.
          </Typography>
          {groups.map((group) => (
            <Stack key={group.key} spacing={1}>
              <Typography variant="overline" color="text.secondary" fontWeight={700}>
                {group.label}
              </Typography>
              {group.items.map((item) => (
                <EvidenceEntry
                  key={item.contribution.finding_id}
                  item={item}
                  icon={GROUP_ICON[group.key]}
                  onViewRule={onViewRule}
                  reviewId={reviewId}
                  disposition={dispositions.find((d) => d.finding_index === item.findingIndex)}
                  onApplyDisposition={onApplyDisposition}
                  isApplyingDisposition={isApplyingDisposition}
                  readOnly={readOnly}
                />
              ))}
            </Stack>
          ))}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

interface EvidenceEntryProps {
  item: EvidenceItem;
  icon: JSX.Element;
  onViewRule: (ruleId: string) => void;
  reviewId?: string | null;
  disposition?: FindingDisposition;
  onApplyDisposition?: (reviewId: string, payload: ApplyFindingDispositionRequest) => void;
  isApplyingDisposition: boolean;
  readOnly: boolean;
}

function EvidenceEntry({
  item,
  icon,
  onViewRule,
  reviewId,
  disposition,
  onApplyDisposition,
  isApplyingDisposition,
  readOnly,
}: EvidenceEntryProps) {
  const { contribution, finding, findingIndex } = item;
  const headline = contribution.contribution || finding?.recommendation || contribution.finding_id;

  return (
    <Accordion disableGutters sx={styles.accordion}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={styles.evidenceRow}>
          <Box pt={0.25}>{icon}</Box>
          <Stack spacing={0.25} flex={1} minWidth={0}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Typography variant="body2" fontWeight={700}>
                {headline}
              </Typography>
              <Chip size="small" label={CONTRIBUTION_STATUS_LABEL[contribution.status]} variant="outlined" />
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {contribution.finding_id} · {findingSourceLabel(finding)}
              {contribution.duplicate_of ? ` · same change as ${contribution.duplicate_of}` : ''}
            </Typography>
            {contribution.reason && (
              <Typography variant="caption">Reason: {contribution.reason}</Typography>
            )}
            {contribution.overridden_by_rule_ids.length > 0 && (
              <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
                <Typography variant="caption">Overridden by:</Typography>
                {contribution.overridden_by_rule_ids.map((ruleId) => (
                  <Chip
                    key={ruleId}
                    size="small"
                    color="secondary"
                    label={`Skillz ${ruleId}`}
                    sx={styles.ruleChip}
                    onClick={(event) => {
                      event.stopPropagation();
                      onViewRule(ruleId);
                    }}
                  />
                ))}
              </Stack>
            )}
          </Stack>
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        {finding ? (
          <FindingCard
            finding={finding}
            index={findingIndex}
            reviewId={reviewId}
            disposition={disposition}
            onApplyDisposition={onApplyDisposition}
            isApplyingDisposition={isApplyingDisposition}
            readOnly={readOnly}
            evidenceMode
          />
        ) : (
          <Typography variant="body2" color="text.secondary">
            The original suggestion for {contribution.finding_id} is not available.
          </Typography>
        )}
      </AccordionDetails>
    </Accordion>
  );
}
