import { useCallback, useRef, useState } from 'react';
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
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import { CategoryScoreGrid } from '@/radia_ai/features/jamaRequirementReviewer/components/CategoryScoreGrid';
import { ReviewResultHero } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewResultHero';
import { ReviewChangeSet } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewChangeSet';
import { ReviewIncompleteNotice } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewIncompleteNotice';
import { useRequirementReview } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useRequirementReview';
import { ErrorDisplay } from '@/components/ErrorDisplay';
import { getReviewQualityScore } from '@/utils/reviewQuality';
import { isReviewFailed } from '@/utils/reviewCompletion';
import {
  parseRequirementsFromPdf,
  type ParsedRequirement,
} from '@/radia_ai/features/jamaRequirementReviewer/utils/pdfRequirementParser';
import type { RequirementReviewResponse } from '@/types/api';
import { normalizeRequirementText, prepareFlatTextForNormalization } from '@/radia_ai/features/jamaRequirementReviewer/utils/requirementNormalization';
import { useNavigationGuard } from '@/hooks/useNavigationGuard';
import { requirementReviewStyles } from './RequirementReview.styles';

type ReviewState = 'pending' | 'reviewing' | 'done' | 'error';

interface RequirementWithReview extends ParsedRequirement {
  reviewState: ReviewState;
  result?: RequirementReviewResponse;
}

export default function SetReview() {
  const [requirements, setRequirements] = useState<RequirementWithReview[]>([]);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const resultRef = useRef<HTMLDivElement | null>(null);

  const {
    mutate: runReview,
    isPending: isReviewing,
    isError,
    error,
    reset: resetReview,
  } = useRequirementReview();

  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsParsing(true);
    setParseError(null);
    setRequirements([]);
    setActiveIndex(-1);
    setUploadedFilename(file.name);
    resetReview();

    try {
      const parsed = await parseRequirementsFromPdf(file);
      if (parsed.length === 0) {
        setParseError('No requirements found in the PDF. Expected format: WR-ACR-XXX or WR-TXT-XXXX requirement IDs.');
        setIsParsing(false);
        return;
      }
      const withState: RequirementWithReview[] = parsed.map((r) => ({
        ...r,
        reviewState: 'pending' as ReviewState,
      }));
      setRequirements(withState);
      setActiveIndex(0);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Failed to parse PDF');
    } finally {
      setIsParsing(false);
    }
  }, [resetReview]);

  const reviewCurrent = useCallback(() => {
    if (activeIndex < 0 || activeIndex >= requirements.length) return;

    const req = requirements[activeIndex];

    // Mark as reviewing
    setRequirements((prev) =>
      prev.map((r, i) => (i === activeIndex ? { ...r, reviewState: 'reviewing' } : r))
    );

    runReview(
      {
        requirement_id: req.id,
        text: normalizeRequirementText(prepareFlatTextForNormalization(req.rawText)),
        requirement_level: 'Aircraft',
      },
      {
        onSuccess: (response) => {
          setRequirements((prev) =>
            prev.map((r, i) =>
              i === activeIndex ? { ...r, reviewState: 'done', result: response } : r
            )
          );
          setTimeout(() => {
            resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 100);
        },
        onError: () => {
          setRequirements((prev) =>
            prev.map((r, i) =>
              i === activeIndex ? { ...r, reviewState: 'error' } : r
            )
          );
        },
      }
    );
  }, [activeIndex, requirements, runReview]);

  const goToRequirement = useCallback((index: number) => {
    setActiveIndex(index);
    resetReview();
  }, [resetReview]);

  const goNext = useCallback(() => {
    if (activeIndex < requirements.length - 1) {
      goToRequirement(activeIndex + 1);
    }
  }, [activeIndex, requirements.length, goToRequirement]);

  const goPrev = useCallback(() => {
    if (activeIndex > 0) {
      goToRequirement(activeIndex - 1);
    }
  }, [activeIndex, goToRequirement]);

  const activeReq = activeIndex >= 0 ? requirements[activeIndex] : null;
  const activeResult = activeReq?.result ?? null;
  const reviewFailed = activeResult ? isReviewFailed(activeResult.completion) : false;
  const reviewedCount = requirements.filter((r) => r.reviewState === 'done').length;
  const progress = requirements.length > 0 ? (reviewedCount / requirements.length) * 100 : 0;

  // Guard navigation: dirty while a set is loaded/parsing/reviewing.
  const isDirty = requirements.length > 0 || isParsing || isReviewing;
  useNavigationGuard(isDirty);

  const handleClearAll = () => {
    setRequirements([]);
    setActiveIndex(-1);
    setParseError(null);
    setUploadedFilename('');
    resetReview();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Set Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Upload a PDF containing multiple requirements. Parse, review one at a time, and step through results.
        </Typography>
      </Box>

      {/* Upload Section */}
      <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
        <Stack spacing={2}>
          <Box display="flex" alignItems="center" gap={2}>
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
              </>
            )}
          </Box>

          {parseError && (
            <Alert severity="error">{parseError}</Alert>
          )}

          {requirements.length > 0 && (
            <>
              <Box>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                  <Typography variant="caption" color="text.secondary">
                    Review progress
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {reviewedCount} / {requirements.length}
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
                    return (
                      <ListItem key={req.id} disablePadding>
                        <ListItemButton
                          selected={isActive}
                          onClick={() => goToRequirement(index)}
                          sx={{ borderRadius: 1 }}
                        >
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            {req.reviewState === 'done' ? (
                              <CheckCircleIcon color="success" fontSize="small" />
                            ) : req.reviewState === 'reviewing' ? (
                              <HourglassEmptyIcon color="warning" fontSize="small" />
                            ) : req.reviewState === 'error' ? (
                              <RadioButtonUncheckedIcon color="error" fontSize="small" />
                            ) : (
                              <RadioButtonUncheckedIcon color="disabled" fontSize="small" />
                            )}
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              <Typography variant="body2" fontWeight={isActive ? 700 : 400}>
                                {req.id} — {req.title}
                              </Typography>
                            }
                            secondary={req.section || undefined}
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

      {/* Active Requirement Details */}
      {activeReq && (
        <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
          <Stack spacing={2}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography variant="h6" fontWeight={400}>
                  {activeReq.id} — {activeReq.title}
                </Typography>
                {activeReq.section && (
                  <Typography variant="caption" color="text.secondary">
                    Section: {activeReq.section}
                  </Typography>
                )}
              </Box>
              <Chip
                label={`${activeIndex + 1} of ${requirements.length}`}
                size="small"
                variant="outlined"
              />
            </Box>

            <Paper
              variant="outlined"
              sx={{ p: 2, bgcolor: 'action.hover', maxHeight: 200, overflow: 'auto' }}
            >
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {normalizeRequirementText(prepareFlatTextForNormalization(activeReq.rawText))}
              </Typography>
            </Paper>

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
                <Button
                  variant="outlined"
                  size="small"
                  endIcon={<NavigateNextIcon />}
                  disabled={activeIndex >= requirements.length - 1}
                  onClick={goNext}
                >
                  Next
                </Button>
              </Box>
              <Button
                variant="contained"
                onClick={reviewCurrent}
                disabled={isReviewing}
                startIcon={isReviewing ? <CircularProgress size={16} color="inherit" /> : undefined}
              >
                {activeReq.reviewState === 'done' ? 'Re-run Review' : isReviewing ? 'Reviewing...' : 'Run AI Review'}
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}

      {/* Review Results */}
      {isError && (
        <ErrorDisplay error={error} context="Set Review" onRetry={reviewCurrent} />
      )}

      {activeResult && reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewIncompleteNotice
            completion={activeResult.completion}
            onRetry={reviewCurrent}
            isRetrying={isReviewing}
          />
        </Stack>
      )}

      {activeResult && !reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewResultHero
            title="Requirement score"
            score={getReviewQualityScore(activeResult.overall, activeResult.findings)}
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
              <CategoryScoreGrid categories={activeResult.category_results} reviewCompleted />
              <Divider />
              <ReviewChangeSet
                findings={activeResult.findings}
                reviewId={activeResult.review_id}
              />
            </Stack>
          </Paper>

          {/* Navigation after reviewing */}
          <Box display="flex" justifyContent="flex-end" gap={1}>
            {activeIndex < requirements.length - 1 && (
              <Button
                variant="contained"
                endIcon={<NavigateNextIcon />}
                onClick={goNext}
              >
                Next Requirement
              </Button>
            )}
            {activeIndex === requirements.length - 1 && reviewedCount === requirements.length && (
              <Alert severity="success" sx={{ flex: 1 }}>
                All {requirements.length} requirements have been reviewed!
              </Alert>
            )}
          </Box>
        </Stack>
      )}
    </Stack>
  );
}
