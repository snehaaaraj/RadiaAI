import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid2';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import type { ChipProps } from '@mui/material/Chip';
import type {
  ApplyFindingDispositionRequest,
  ApplyRecommendationDecisionRequest,
  FinalRecommendation,
  FindingDisposition,
  RecommendationDecision,
  RecommendationDecisionStatus,
  RecommendationStatus,
  ReviewFinding,
  SkillzRuleReference,
  SkillzStatus,
} from '@/types/api';
import { diffWords } from '../utils/wordDiff';
import { findingSourceLabel, needsReviewReasons, unresolvedConflicts } from '../utils/recommendationEvidence';
import { RecommendationEvidence } from './RecommendationEvidence';
import { ReviewChangeSet } from './ReviewChangeSet';
import { finalRecommendationStyles as styles } from './FinalRecommendationPanel.styles';

const STATUS_CHIP: Record<RecommendationStatus, { label: string; color: ChipProps['color'] }> = {
  ready: { label: 'Ready to replace', color: 'success' },
  needs_review: { label: 'Needs review', color: 'warning' },
  no_change: { label: 'No change needed', color: 'default' },
  failed: { label: 'Not generated', color: 'error' },
};

const DECISION_OPTIONS: Array<{ value: RecommendationDecisionStatus; label: string }> = [
  { value: 'ready_to_replace', label: 'Ready to replace' },
  { value: 'rejected', label: 'Reject with reason' },
  { value: 'accepted_with_modifications', label: 'Accept, but modify' },
];

const DECISION_CHIP: Record<RecommendationDecisionStatus, { label: string; color: ChipProps['color'] }> = {
  ready_to_replace: { label: 'Ready to replace', color: 'success' },
  rejected: { label: 'Rejected', color: 'error' },
  accepted_with_modifications: { label: 'Accepted with modifications', color: 'warning' },
};

function skillzChip(recommendation: FinalRecommendation): { label: string; color: ChipProps['color'] } {
  const labels: Record<SkillzStatus, { label: string; color: ChipProps['color'] }> = {
    applied: {
      label: recommendation.skillz_revision
        ? `Skillz applied · Rev ${recommendation.skillz_revision}`
        : 'Skillz applied',
      color: 'secondary',
    },
    unavailable: { label: 'Skillz not applied', color: 'warning' },
    not_applicable: { label: 'Skillz not applicable', color: 'default' },
  };
  return labels[recommendation.skillz_status];
}

interface FinalRecommendationPanelProps {
  recommendation: FinalRecommendation;
  findings: ReviewFinding[];
  reviewId?: string | null;
  dispositions?: FindingDisposition[];
  onApplyDisposition?: (reviewId: string, payload: ApplyFindingDispositionRequest) => void;
  isApplyingDisposition?: boolean;
  decision?: RecommendationDecision | null;
  onApplyDecision?: (reviewId: string, payload: ApplyRecommendationDecisionRequest) => void;
  isApplyingDecision?: boolean;
  readOnly?: boolean;
}

/**
 * The primary review artifact: ONE recommended Description that can replace the
 * original in Jama, with every individual suggestion kept as supporting evidence.
 */
export function FinalRecommendationPanel({
  recommendation,
  findings,
  reviewId,
  dispositions,
  onApplyDisposition,
  isApplyingDisposition = false,
  decision,
  onApplyDecision,
  isApplyingDecision = false,
  readOnly = false,
}: FinalRecommendationPanelProps) {
  const [ruleId, setRuleId] = useState<string | null>(null);
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false);
  const viewRule = (id: string) => {
    setRuleId(id);
    setRuleDialogOpen(true);
  };
  const rulesById = useMemo(
    () => new Map(recommendation.skillz_rules.map((rule) => [rule.rule_id, rule])),
    [recommendation.skillz_rules]
  );
  const status = STATUS_CHIP[recommendation.status];
  const skillz = skillzChip(recommendation);

  if (recommendation.status === 'failed') {
    return (
      <Stack spacing={2}>
        <Alert severity="warning">
          <AlertTitle>Final recommendation not generated</AlertTitle>
          {recommendation.failure_message}
        </Alert>
        <ReviewChangeSet
          findings={findings}
          title="Individual suggestions"
          reviewId={reviewId}
          onApplyDisposition={onApplyDisposition}
          isApplyingDisposition={isApplyingDisposition}
          readOnly={readOnly}
        />
      </Stack>
    );
  }

  const reasons = needsReviewReasons(recommendation);
  const conflicts = unresolvedConflicts(recommendation);
  const findingById = new Map(findings.map((finding, index) => [finding.finding_id ?? `F${index + 1}`, finding]));
  const recommended = recommendation.recommended_description ?? recommendation.original_description;

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={styles.paper}>
        <Stack spacing={2}>
          <Box sx={styles.headerRow}>
            <Box>
              <Typography variant="h6" fontWeight={800}>
                Final recommended requirement
              </Typography>
              <Typography variant="body2" color="text.secondary">
                One Description that combines every valid suggestion and is ready to replace the original
                in Jama.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip label={status.label} color={status.color} />
              <Tooltip title={recommendation.skillz_status_message}>
                <Chip label={skillz.label} color={skillz.color} variant="outlined" />
              </Tooltip>
            </Stack>
          </Box>

          {recommendation.skillz_status === 'unavailable' && (
            <Alert severity="warning">{recommendation.skillz_status_message}</Alert>
          )}

          {reasons.length > 0 && (
            <Alert severity="warning">
              <AlertTitle>Review before replacing the original</AlertTitle>
              <Stack component="ul" sx={{ m: 0, pl: 2 }}>
                {reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </Stack>
            </Alert>
          )}

          <DescriptionComparison
            original={recommendation.original_description}
            recommended={recommended}
          />

          <RecommendationDecisionPanel
            reviewId={reviewId}
            decision={decision}
            recommendedDescription={recommended}
            onApplyDecision={onApplyDecision}
            isApplyingDecision={isApplyingDecision}
            readOnly={readOnly}
          />

          {recommendation.summary && (
            <Typography variant="body2" color="text.secondary">
              {recommendation.summary}
            </Typography>
          )}

          {conflicts.length > 0 && (
            <Stack spacing={1}>
              <Typography variant="subtitle1" fontWeight={800}>
                Unresolved conflicts
              </Typography>
              {conflicts.map((conflict) => (
                <Box key={conflict.conflict_id} sx={styles.conflictBox}>
                  <Stack spacing={1}>
                    <Typography variant="body2" fontWeight={700}>
                      {conflict.description || 'These suggestions conflict and could not be resolved safely.'}
                    </Typography>
                    {conflict.finding_ids.map((findingId) => {
                      const finding = findingById.get(findingId) ?? null;
                      return (
                        <Box key={findingId} sx={styles.conflictSuggestion}>
                          <Typography variant="caption" color="text.secondary">
                            {findingId} · {findingSourceLabel(finding)}
                          </Typography>
                          <Typography variant="body2">
                            {finding?.suggested_rewrite ?? finding?.recommendation ?? 'Suggestion unavailable.'}
                          </Typography>
                        </Box>
                      );
                    })}
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}

          {recommendation.skillz_changes.length > 0 && (
            <Box sx={styles.sectionBox}>
              <Typography variant="overline" color="text.secondary" fontWeight={700}>
                Changes required by Skillz rules
              </Typography>
              <Stack spacing={0.75}>
                {recommendation.skillz_changes.map((change, index) => (
                  <Stack key={`${change.rule_id}-${index}`} direction="row" spacing={1} alignItems="flex-start">
                    <RuleChip ruleId={change.rule_id} onClick={viewRule} />
                    <Box>
                      <Typography variant="body2" fontWeight={600}>
                        {change.change}
                      </Typography>
                      {change.reason && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          {change.reason}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                ))}
              </Stack>
            </Box>
          )}

          {recommendation.open_items.length > 0 && (
            <Box sx={styles.sectionBox}>
              <Typography variant="overline" color="text.secondary" fontWeight={700}>
                Follow-ups (information not available to the review)
              </Typography>
              <Stack spacing={0.75}>
                {recommendation.open_items.map((item, index) => (
                  <Stack key={`${item.rule_id ?? 'item'}-${index}`} direction="row" spacing={1} alignItems="flex-start">
                    {item.rule_id && <RuleChip ruleId={item.rule_id} onClick={viewRule} />}
                    <Typography variant="body2">{item.description}</Typography>
                  </Stack>
                ))}
              </Stack>
            </Box>
          )}

          {recommendation.skillz_check_issues.length > 0 && (
            <Alert severity="error">
              <AlertTitle>Skillz check issues in the recommended text</AlertTitle>
              <Stack spacing={0.5}>
                {recommendation.skillz_check_issues.map((issue) => (
                  <Stack key={`${issue.rule_id}-${issue.term}`} direction="row" spacing={1} alignItems="center">
                    <RuleChip ruleId={issue.rule_id} onClick={viewRule} />
                    <Typography variant="body2">{issue.message}</Typography>
                  </Stack>
                ))}
              </Stack>
            </Alert>
          )}
        </Stack>
      </Paper>

      {recommendation.contributions.length > 0 && (
        <RecommendationEvidence
          recommendation={recommendation}
          findings={findings}
          onViewRule={viewRule}
          reviewId={reviewId}
          dispositions={dispositions}
          onApplyDisposition={onApplyDisposition}
          isApplyingDisposition={isApplyingDisposition}
          readOnly={readOnly}
        />
      )}

      <SkillzRuleDialog
        open={ruleDialogOpen}
        rule={ruleId ? rulesById.get(ruleId) ?? null : null}
        ruleId={ruleId}
        recommendation={recommendation}
        onClose={() => setRuleDialogOpen(false)}
      />
    </Stack>
  );
}

interface RecommendationDecisionPanelProps {
  reviewId?: string | null;
  decision?: RecommendationDecision | null;
  recommendedDescription: string;
  onApplyDecision?: (reviewId: string, payload: ApplyRecommendationDecisionRequest) => void;
  isApplyingDecision?: boolean;
  readOnly?: boolean;
}

function RecommendationDecisionPanel({
  reviewId,
  decision,
  recommendedDescription,
  onApplyDecision,
  isApplyingDecision = false,
  readOnly = false,
}: RecommendationDecisionPanelProps) {
  const [selectedDecision, setSelectedDecision] = useState<RecommendationDecisionStatus | ''>(
    decision?.decision ?? ''
  );
  const [reason, setReason] = useState(decision?.reason ?? '');
  const [modifiedDescription, setModifiedDescription] = useState(
    decision?.modified_description ?? recommendedDescription
  );
  const [saved, setSaved] = useState(false);

  if (readOnly) {
    if (!decision) return null;
    const chip = DECISION_CHIP[decision.decision];
    return (
      <Box sx={styles.sectionBox}>
        <Stack spacing={1}>
          <Box sx={styles.decisionReadOnlyRow}>
            <Typography variant="subtitle2" fontWeight={700}>
              Reviewer decision
            </Typography>
            <Chip label={chip.label} color={chip.color} size="small" />
          </Box>
          {decision.decision === 'rejected' && decision.reason && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                Reason
              </Typography>
              <Typography variant="body2">{decision.reason}</Typography>
            </Box>
          )}
          {decision.decision === 'accepted_with_modifications' && decision.modified_description && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                Modified description
              </Typography>
              <Box sx={styles.decisionDetailBox}>
                <Typography variant="body2">{decision.modified_description}</Typography>
              </Box>
            </Box>
          )}
        </Stack>
      </Box>
    );
  }

  if (!onApplyDecision) return null;

  const canSubmit =
    Boolean(reviewId && selectedDecision) &&
    (selectedDecision !== 'rejected' || reason.trim().length > 0) &&
    (selectedDecision !== 'accepted_with_modifications' || modifiedDescription.trim().length > 0);

  return (
    <Box sx={styles.sectionBox}>
      <Stack spacing={1.5}>
        <Typography variant="subtitle2" fontWeight={700}>
          Reviewer decision
        </Typography>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={selectedDecision}
          onChange={(_, value: RecommendationDecisionStatus | null) => setSelectedDecision(value ?? '')}
        >
          {DECISION_OPTIONS.map((option) => (
            <ToggleButton key={option.value} value={option.value}>
              {option.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        {selectedDecision === 'rejected' && (
          <TextField
            multiline
            minRows={2}
            size="small"
            required
            label="Reason for rejecting"
            placeholder="Explain why this recommendation should not replace the original"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        )}

        {selectedDecision === 'accepted_with_modifications' && (
          <TextField
            multiline
            minRows={3}
            size="small"
            required
            label="Modified description"
            value={modifiedDescription}
            onChange={(event) => setModifiedDescription(event.target.value)}
          />
        )}

        <Box sx={styles.actionRow}>
          <Button
            variant="contained"
            size="small"
            disabled={!canSubmit || isApplyingDecision}
            onClick={() => {
              if (!reviewId || !selectedDecision) return;
              setSaved(false);
              onApplyDecision(reviewId, {
                decision: selectedDecision,
                reason: selectedDecision === 'rejected' ? reason : '',
                modified_description:
                  selectedDecision === 'accepted_with_modifications' ? modifiedDescription : null,
              });
              setSaved(true);
            }}
          >
            Save decision
          </Button>
          {saved && (
            <Box sx={styles.savedIndicator}>
              <CheckCircleIcon fontSize="small" />
              <Typography variant="caption" fontWeight={700} color="success.main">
                Saved
              </Typography>
            </Box>
          )}
        </Box>
      </Stack>
    </Box>
  );
}

function DescriptionComparison({ original, recommended }: { original: string; recommended: string }) {
  const [showChanges, setShowChanges] = useState(true);
  const [copied, setCopied] = useState(false);
  const parts = useMemo(() => diffWords(original, recommended), [original, recommended]);

  const handleCopy = () => {
    void navigator.clipboard.writeText(recommended).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Grid container spacing={1.5}>
      <Grid size={{ xs: 12, md: 6 }}>
        <Box sx={styles.textBox}>
          <Box sx={styles.textBoxHeader}>
            <Typography variant="overline" color="text.secondary" fontWeight={700}>
              Original Description
            </Typography>
          </Box>
          <Typography variant="body2">{original}</Typography>
        </Box>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <Box sx={styles.recommendedBox}>
          <Box sx={styles.textBoxHeader}>
            <Typography variant="overline" color="primary" fontWeight={700}>
              Recommended Description
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <FormControlLabel
                control={
                  <Switch size="small" checked={showChanges} onChange={(_, checked) => setShowChanges(checked)} />
                }
                label={<Typography variant="caption">Highlight changes</Typography>}
              />
              <Tooltip title={copied ? 'Copied!' : 'Copy to clipboard'}>
                <Button size="small" variant="outlined" startIcon={<ContentCopyIcon fontSize="small" />} onClick={handleCopy}>
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </Tooltip>
            </Stack>
          </Box>
          <Typography variant="body2" data-testid="recommended-description">
            {showChanges
              ? parts.map((part, index) => (
                  <Box component="span" key={index}>
                    {index > 0 ? ' ' : ''}
                    <Box
                      component="span"
                      sx={
                        part.type === 'added'
                          ? styles.diffAdded
                          : part.type === 'removed'
                            ? styles.diffRemoved
                            : undefined
                      }
                    >
                      {part.text}
                    </Box>
                  </Box>
                ))
              : recommended}
          </Typography>
        </Box>
      </Grid>
    </Grid>
  );
}

function RuleChip({ ruleId, onClick }: { ruleId: string; onClick: (ruleId: string) => void }) {
  return (
    <Chip
      size="small"
      color="secondary"
      variant="outlined"
      label={`Skillz ${ruleId}`}
      sx={styles.ruleChip}
      onClick={() => onClick(ruleId)}
    />
  );
}

interface SkillzRuleDialogProps {
  open: boolean;
  rule: SkillzRuleReference | null;
  ruleId: string | null;
  recommendation: FinalRecommendation;
  onClose: () => void;
}

function SkillzRuleDialog({ open, rule, ruleId, recommendation, onClose }: SkillzRuleDialogProps) {
  const sourceUrl = rule?.source_url ?? recommendation.skillz_source_url;
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Skillz rule {ruleId}
        {rule ? ` · ${rule.title}` : ''}
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={1.5}>
          <Typography variant="caption" color="text.secondary">
            {rule?.document ?? 'Skillz package'}
            {recommendation.skillz_package ? ` · ${recommendation.skillz_package}` : ''}
            {recommendation.skillz_revision ? ` Revision ${recommendation.skillz_revision}` : ''}
            {' · Authority level 1 (highest)'}
          </Typography>
          <Typography component="div" sx={styles.ruleText}>
            {rule?.text ?? 'The text of this rule was not recorded with the recommendation.'}
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        {sourceUrl && (
          <Link href={sourceUrl} target="_blank" rel="noopener noreferrer" underline="hover" sx={{ mr: 'auto', ml: 1 }}>
            Open Skillz package
          </Link>
        )}
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
