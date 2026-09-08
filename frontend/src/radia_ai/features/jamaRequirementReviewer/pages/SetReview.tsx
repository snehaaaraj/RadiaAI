import { useCallback, useMemo, useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import LinearProgress from '@mui/material/LinearProgress';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import PendingOutlinedIcon from '@mui/icons-material/PendingOutlined';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import ReplayIcon from '@mui/icons-material/Replay';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { CategoryScoreGrid } from '@/radia_ai/features/jamaRequirementReviewer/components/CategoryScoreGrid';
import { ReviewResultHero } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewResultHero';
import { ReviewChangeSet } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewChangeSet';
import { ReviewIncompleteNotice } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewIncompleteNotice';
import {
  SET_REVIEW_CONCURRENCY,
  formatSetReviewError,
  useSetReviewQueue,
  type SetReviewItemStatus,
  type SetReviewItemError,
  type SetReviewQueueItem,
} from '@/radia_ai/features/jamaRequirementReviewer/hooks/useSetReviewQueue';
import { ErrorDisplay } from '@/components/ErrorDisplay';
import { getReviewQualityScore } from '@/utils/reviewQuality';
import { isReviewFailed } from '@/utils/reviewCompletion';
import {
  parseRequirementsFromPdf,
  type ParsedRequirement,
} from '@/radia_ai/features/jamaRequirementReviewer/utils/pdfRequirementParser';
import {
  exportReviewSetToPdf,
  exportReviewToPdf,
  type ReviewPdfSection,
} from '@/radia_ai/features/jamaRequirementReviewer/utils/reviewPdfExport';
import type { RequirementReviewResponse } from '@/types/api';
import { normalizeRequirementText, prepareFlatTextForNormalization } from '@/radia_ai/features/jamaRequirementReviewer/utils/requirementNormalization';
import { useNavigationGuard } from '@/hooks/useNavigationGuard';
import { requirementReviewStyles } from './RequirementReview.styles';

const IDLE_STATUS: SetReviewItemStatus = { state: 'pending' };

/** Stable per-item key; requirement IDs can repeat across PDF sections. */
function itemKey(req: ParsedRequirement, index: number): string {
  return `${index}:${req.id}`;
}

function StatusIcon({ state }: { state: SetReviewItemStatus['state'] }) {
  if (state === 'done') return <CheckCircleIcon color="success" fontSize="small" />;
  if (state === 'reviewing') return <CircularProgress size={18} color="primary" />;
  if (state === 'error') return <ErrorOutlineIcon color="error" fontSize="small" />;
  if (state === 'queued') return <PendingOutlinedIcon color="warning" fontSize="small" />;
  return <RadioButtonUncheckedIcon color="disabled" fontSize="small" />;
}

export default function SetReview() {
  const [requirements, setRequirements] = useState<ParsedRequirement[]>([]);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState('');
  const [showSummary, setShowSummary] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const resultRef = useRef<HTMLDivElement | null>(null);

  const { statuses, isRunning, runQueue, runSingle, reset: resetQueue } = useSetReviewQueue();

  const buildQueueItem = useCallback(
    (req: ParsedRequirement, index: number): SetReviewQueueItem => ({
      key: itemKey(req, index),
      payload: {
        requirement_id: req.id,
        text: normalizeRequirementText(prepareFlatTextForNormalization(req.rawText)),
        requirement_level: 'Aircraft',
      },
    }),
    []
  );

  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsParsing(true);
    setParseError(null);
    setRequirements([]);
    setActiveIndex(-1);
    setShowSummary(false);
    setUploadedFilename(file.name);
    resetQueue();

    try {
      const parsed = await parseRequirementsFromPdf(file);
      if (parsed.length === 0) {
        setParseError('No requirements found in the PDF. Expected format: WR-ACR-XXX or WR-TXT-XXXX requirement IDs.');
        setIsParsing(false);
        return;
      }
      setRequirements(parsed);
      setActiveIndex(0);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to parse PDF');
    } finally {
      setIsParsing(false);
    }
  }, [resetQueue]);

  /** Kicks off (or resumes) reviews for every requirement that has no result yet. */
  const runAll = useCallback(() => {
    const items = requirements
      .map((req, index) => ({ req, index }))
      .filter(({ req, index }) => (statuses[itemKey(req, index)] ?? IDLE_STATUS).state !== 'done')
      .map(({ req, index }) => buildQueueItem(req, index));
    void runQueue(items);
  }, [requirements, statuses, buildQueueItem, runQueue]);

  const retryOne = useCallback(
    (index: number) => {
      const req = requirements[index];
      if (!req) return;
      void runSingle(buildQueueItem(req, index));
    },
    [requirements, buildQueueItem, runSingle]
  );

  const goToRequirement = useCallback((index: number) => {
    setActiveIndex(index);
    setShowSummary(false);
  }, []);

  const goNext = useCallback(() => {
    if (activeIndex < requirements.length - 1) {
      goToRequirement(activeIndex + 1);
    } else {
      setShowSummary(true);
    }
  }, [activeIndex, requirements.length, goToRequirement]);

  const goPrev = useCallback(() => {
    if (activeIndex > 0) {
      goToRequirement(activeIndex - 1);
    }
  }, [activeIndex, goToRequirement]);

  const activeReq = activeIndex >= 0 ? requirements[activeIndex] : null;
  const activeStatus = activeReq ? statuses[itemKey(activeReq, activeIndex)] ?? IDLE_STATUS : IDLE_STATUS;
  const activeResult = activeStatus.result ?? null;
  const reviewFailed = activeResult ? isReviewFailed(activeResult.completion) : false;

  const counts = useMemo(() => {
    let done = 0;
    let errored = 0;
    let inFlight = 0;
    requirements.forEach((req, index) => {
      const state = (statuses[itemKey(req, index)] ?? IDLE_STATUS).state;
      if (state === 'done') done += 1;
      else if (state === 'error') errored += 1;
      else if (state === 'reviewing' || state === 'queued') inFlight += 1;
    });
    return { done, errored, inFlight, settled: done + errored };
  }, [requirements, statuses]);

  const progress = requirements.length > 0 ? (counts.settled / requirements.length) * 100 : 0;
  const allSettled = requirements.length > 0 && counts.settled === requirements.length;
  const hasStarted = counts.settled > 0 || counts.inFlight > 0;

  const failedItems = useMemo(() => {
    const failures: Array<{ req: ParsedRequirement; index: number; error: SetReviewItemError }> = [];
    requirements.forEach((req, index) => {
      const status = statuses[itemKey(req, index)] ?? IDLE_STATUS;
      if (status.state === 'error' && status.error) {
        failures.push({ req, index, error: status.error });
      }
    });
    return failures;
  }, [requirements, statuses]);

  const reviewedSections = useMemo<ReviewPdfSection[]>(
    () =>
      requirements
        .map((req, index) => ({ req, status: statuses[itemKey(req, index)] ?? IDLE_STATUS }))
        .filter(
          (
            entry
          ): entry is {
            req: ParsedRequirement;
            status: SetReviewItemStatus & { result: RequirementReviewResponse };
          } => !!entry.status.result
        )
        .map(({ req, status }) => ({
          requirementId: req.id,
          requirementTitle: req.title,
          result: status.result,
          metadata: [
            { label: 'Requirement ID', value: req.id },
            { label: 'Title', value: req.title },
            ...(req.section ? [{ label: 'Section', value: req.section }] : []),
          ],
        })),
    [requirements, statuses]
  );

  const handleExportActivePdf = () => {
    if (!activeReq || !activeResult) return;
    exportReviewToPdf({
      requirementId: activeReq.id,
      requirementTitle: activeReq.title,
      result: activeResult,
      metadata: [
        { label: 'Requirement ID', value: activeReq.id },
        { label: 'Title', value: activeReq.title },
        ...(activeReq.section ? [{ label: 'Section', value: activeReq.section }] : []),
      ],
    });
  };

  const handleExportConsolidatedPdf = () => {
    exportReviewSetToPdf(
      reviewedSections,
      uploadedFilename ? `set-review-${uploadedFilename.replace(/\.pdf$/i, '')}` : 'set-review'
    );
  };

  // Guard navigation: dirty while a set is loaded/parsing/reviewing.
  const isDirty = requirements.length > 0 || isParsing || isRunning;
  useNavigationGuard(isDirty);

  const handleClearAll = () => {
    setRequirements([]);
    setActiveIndex(-1);
    setParseError(null);
    setUploadedFilename('');
    setShowSummary(false);
    resetQueue();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={400} gutterBottom>
          Set Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Upload a PDF containing multiple requirements.
          One click reviews the whole set - up to{' '}
          {SET_REVIEW_CONCURRENCY} requirements are processed at a time while you read results.
        </Typography>
      </Box>

      {/* Upload Section */}
      <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
        <Stack spacing={2}>
          <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
            <Button
              variant="contained"
              startIcon={isParsing ? <CircularProgress size={16} color="inherit" /> : <UploadFileIcon />}
              component="label"
              disabled={isParsing}
            >
              {isParsing ? 'Parsing PDF...' : 'Upload PDF'}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                hidden
                onChange={handleFileUpload}
              />
            </Button>
            {uploadedFilename && (
              <Chip label={uploadedFilename} onDelete={handleClearAll} size="small" />
            )}
            {requirements.length > 0 && (
              <>
                <Typography variant="body2" color="text.secondary">
                  {requirements.length} requirement{requirements.length !== 1 ? 's' : ''} found
                </Typography>
                <Button variant="outlined" color="inherit" size="small" onClick={handleClearAll}>
                  Clear Review
                </Button>
                {counts.done > 0 && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<FileDownloadIcon />}
                    onClick={handleExportConsolidatedPdf}
                  >
                    Export consolidated PDF ({counts.done})
                  </Button>
                )}
              </>
            )}
          </Box>

          {parseError && <Alert severity="error">{parseError}</Alert>}

          {requirements.length > 0 && (
            <>
              <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
                <Button
                  variant="contained"
                  startIcon={isRunning ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                  onClick={runAll}
                  disabled={isRunning || (allSettled && counts.errored === 0)}
                >
                  {isRunning
                    ? `Reviewing set... (${counts.settled}/${requirements.length})`
                    : hasStarted
                      ? 'Resume AI Review of set'
                      : 'Run AI Review on all requirements'}
                </Button>
                {isRunning && (
                  <Typography variant="caption" color="text.secondary">
                    {counts.inFlight} in progress or queued - results appear as each requirement finishes.
                  </Typography>
                )}
              </Box>

              <Box>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                  <Typography variant="caption" color="text.secondary">
                    Review progress
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {counts.done} reviewed
                    {counts.errored > 0 ? ` · ${counts.errored} failed` : ''} / {requirements.length}
                  </Typography>
                </Box>
                <LinearProgress variant="determinate" value={progress} sx={{ borderRadius: 1, height: 6 }} />
              </Box>

              <Divider />

              {/* Requirements List */}
              <Box sx={{ maxHeight: 360, overflow: 'auto' }}>
                <List dense disablePadding>
                  {requirements.map((req, index) => {
                    const isActive = index === activeIndex;
                    const status = statuses[itemKey(req, index)] ?? IDLE_STATUS;
                    return (
                      <ListItem key={itemKey(req, index)} disablePadding>
                        <ListItemButton
                          selected={isActive}
                          onClick={() => goToRequirement(index)}
                          sx={{ borderRadius: 1 }}
                        >
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            <StatusIcon state={status.state} />
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              <Typography variant="body2" fontWeight={isActive ? 700 : 400}>
                                {req.id} - {req.title}
                              </Typography>
                            }
                            secondary={
                              status.state === 'error' && status.error
                                ? formatSetReviewError(status.error)
                                : req.section || undefined
                            }
                            secondaryTypographyProps={
                              status.state === 'error' ? { color: 'error' } : undefined
                            }
                          />
                        </ListItemButton>
                      </ListItem>
                    );
                  })}
                </List>
              </Box>
            </>
          )}
        </Stack>
      </Paper>

      {/* Review Complete summary */}
      {showSummary && requirements.length > 0 && (
        <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
          <Stack spacing={2} alignItems="flex-start">
            <Box display="flex" alignItems="center" gap={1}>
              <CheckCircleIcon color="success" />
              <Typography variant="h6" fontWeight={700}>
                Review Complete
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              {counts.done} of {requirements.length} requirement{requirements.length !== 1 ? 's' : ''} reviewed
              successfully{counts.errored > 0 ? `, ${counts.errored} failed` : ''}.
            </Typography>
            {failedItems.length > 0 && (
              <Alert severity="warning" sx={{ width: '100%' }}>
                <Typography variant="body2" fontWeight={600} gutterBottom>
                  {failedItems.length} requirement{failedItems.length !== 1 ? 's' : ''} failed to review
                </Typography>
                <Stack spacing={0.5}>
                  {failedItems.map(({ req, index, error }) => (
                    <Box key={itemKey(req, index)} display="flex" alignItems="center" gap={1}>
                      <Typography variant="caption" sx={{ flex: 1 }}>
                        <strong>{req.id}</strong> - {formatSetReviewError(error)}
                      </Typography>
                      <Button size="small" startIcon={<ReplayIcon />} onClick={() => retryOne(index)}>
                        Retry
                      </Button>
                    </Box>
                  ))}
                </Stack>
              </Alert>
            )}
            {!allSettled && (
              <Alert severity="info" sx={{ width: '100%' }}>
                {counts.inFlight} requirement{counts.inFlight !== 1 ? 's are' : ' is'} still being reviewed. The
                export will include everything finished so far.
              </Alert>
            )}
            <Box display="flex" gap={1}>
              <Button
                variant="contained"
                startIcon={<FileDownloadIcon />}
                onClick={handleExportConsolidatedPdf}
                disabled={reviewedSections.length === 0}
              >
                Export Review Findings ({reviewedSections.length})
              </Button>
              <Button
                variant="outlined"
                startIcon={<NavigateBeforeIcon />}
                onClick={() => goToRequirement(requirements.length - 1)}
              >
                Back to results
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}

      {/* Active Requirement Details */}
      {!showSummary && activeReq && (
        <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
          <Stack spacing={2}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography variant="h6" fontWeight={400}>
                  {activeReq.id} - {activeReq.title}
                </Typography>
                {activeReq.section && (
                  <Typography variant="caption" color="text.secondary">
                    Section: {activeReq.section}
                  </Typography>
                )}
              </Box>
              <Chip label={`${activeIndex + 1} of ${requirements.length}`} size="small" variant="outlined" />
            </Box>

            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover', maxHeight: 200, overflow: 'auto' }}>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {normalizeRequirementText(prepareFlatTextForNormalization(activeReq.rawText))}
              </Typography>
            </Paper>

            {activeStatus.state === 'queued' && (
              <Alert severity="info" icon={<PendingOutlinedIcon fontSize="small" />}>
                Waiting in queue - this requirement starts as soon as a review slot frees up.
              </Alert>
            )}
            {activeStatus.state === 'reviewing' && (
              <Alert severity="info" icon={<CircularProgress size={16} />}>
                AI review in progress...
              </Alert>
            )}
            {activeStatus.state === 'error' && activeStatus.error && (
              <ErrorDisplay
                error={activeStatus.error.raw}
                context={`Set Review · ${activeReq.id}`}
                onRetry={() => retryOne(activeIndex)}
              />
            )}

            <Box display="flex" gap={1} justifyContent="space-between" alignItems="center">
              <Box display="flex" gap={1}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<NavigateBeforeIcon />}
                  disabled={activeIndex <= 0}
                  onClick={goPrev}
                >
                  Previous
                </Button>
                <Button variant="outlined" size="small" endIcon={<NavigateNextIcon />} onClick={goNext}>
                  {activeIndex >= requirements.length - 1 ? 'Finish' : 'Next'}
                </Button>
              </Box>
              {(activeStatus.state === 'done' || activeStatus.state === 'error') && (
                <Button variant="outlined" startIcon={<ReplayIcon />} onClick={() => retryOne(activeIndex)}>
                  Re-run this review
                </Button>
              )}
            </Box>
          </Stack>
        </Paper>
      )}

      {/* Review Results */}
      {!showSummary && activeResult && reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewIncompleteNotice
            completion={activeResult.completion}
            onRetry={() => retryOne(activeIndex)}
            isRetrying={activeStatus.state === 'reviewing'}
          />
        </Stack>
      )}

      {!showSummary && activeResult && !reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <Box display="flex" justifyContent="flex-end">
            <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={handleExportActivePdf}>
              Export PDF
            </Button>
          </Box>
          <ReviewResultHero
            title="Requirement score"
            score={getReviewQualityScore(activeResult.category_results)}
            status={activeResult.overall}
            findings={activeResult.findings}
            reviewId={activeResult.review_id}
            metadata={[
              { label: 'Requirement ID', value: activeReq?.id ?? 'N/A' },
              { label: 'Title', value: activeReq?.title ?? 'N/A' },
            ]}
          />
          <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
            <Stack spacing={2}>
              <Box>
                <Typography variant="h6" fontWeight={800} gutterBottom>
                  Category scoring
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Individual sub-category quality scoring helps you spot where the requirement is weakest.
                </Typography>
              </Box>
              <CategoryScoreGrid categories={activeResult.category_results} />
              <Divider />
              <ReviewChangeSet findings={activeResult.findings} reviewId={activeResult.review_id} />
            </Stack>
          </Paper>

          {/* Navigation after reviewing */}
          <Box display="flex" justifyContent="flex-end" gap={1}>
            <Button variant="contained" endIcon={<NavigateNextIcon />} onClick={goNext}>
              {activeIndex >= requirements.length - 1 ? 'Finish Review' : 'Next Requirement'}
            </Button>
          </Box>
        </Stack>
      )}
    </Stack>
  );
}
