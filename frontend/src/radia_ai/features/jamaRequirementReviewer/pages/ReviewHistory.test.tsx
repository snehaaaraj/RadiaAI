import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReviewHistoryEntry, ReviewWorkflow } from '@/types/api';
import ReviewHistory from './ReviewHistory';

const mocks = vi.hoisted(() => ({
  user: { is_admin: true } as { is_admin: boolean } | undefined,
  entries: [] as ReviewHistoryEntry[],
}));

vi.mock('@/hooks/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: mocks.user }),
}));
vi.mock('@/radia_ai/features/jamaRequirementReviewer/hooks/useReviewHistory', () => ({
  useReviewHistory: () => ({
    data: { entries: mocks.entries },
    isLoading: false,
    isError: false,
  }),
}));

function entry(reviewId: string, name: string | null, workflow: ReviewWorkflow = 'requirement'): ReviewHistoryEntry {
  return {
    review_id: reviewId,
    workflow,
    subject_id: 'REQ-1',
    created_at: '2026-10-10T12:00:00Z',
    owner_name: name,
    overall: 'Acceptable',
    completion: { status: 'complete', reason: null, message: '' },
    category_results: [],
    findings: [],
    dispositions: [],
    finding_to_requirement_map: {},
    determinism: {
      reviewer_bundle_version: 'test',
      prompt_versions: {},
      standards_versions: {},
      config_hash: 'test',
      config_snapshot: { temperature: 0, max_tokens: 100, retrieval_top_k: 5 },
    },
  };
}

describe('review runner visibility', () => {
  beforeEach(() => {
    mocks.user = { is_admin: true };
    mocks.entries = [entry('alice-review', 'Alice Engineer'), entry('bob-review', 'Bob Engineer', 'delta')];
  });

  it('shows the correct runner on each requirement and delta review for Admin', () => {
    render(<ReviewHistory />);
    const aliceCard = screen.getByText('alice-review').closest('.MuiPaper-root');
    const bobCard = screen.getByText('bob-review').closest('.MuiPaper-root');
    expect(aliceCard).not.toBeNull();
    expect(bobCard).not.toBeNull();
    if (!(aliceCard instanceof HTMLElement) || !(bobCard instanceof HTMLElement)) {
      throw new Error('Review cards were not rendered');
    }
    expect(within(aliceCard).getByText('Run by: Alice Engineer')).toBeInTheDocument();
    expect(within(bobCard).getByText('Run by: Bob Engineer')).toBeInTheDocument();
    expect(within(aliceCard).queryByText('Run by: Bob Engineer')).not.toBeInTheDocument();
  });

  it.each([null, '', '   ', undefined])('shows Unknown user for an unavailable runner name (%s)', (name) => {
    mocks.entries = [{ ...entry('legacy-review', null), owner_name: name }];
    render(<ReviewHistory />);
    expect(screen.getByText('Run by: Unknown user')).toBeInTheDocument();
  });

  it('does not show runner labels to a User', () => {
    mocks.user = { is_admin: false };
    render(<ReviewHistory />);
    expect(screen.getByText('alice-review')).toBeInTheDocument();
    expect(screen.queryByText(/Run by:/)).not.toBeInTheDocument();
  });

  it('does not show runner labels before the role is known', () => {
    mocks.user = undefined;
    render(<ReviewHistory />);
    expect(screen.queryByText(/Run by:/)).not.toBeInTheDocument();
  });
});
