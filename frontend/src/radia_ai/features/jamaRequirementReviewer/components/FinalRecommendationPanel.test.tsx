import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { buildContribution, buildFinding, buildRecommendation } from '../test/recommendationFixtures';
import { FinalRecommendationPanel } from './FinalRecommendationPanel';

describe('FinalRecommendationPanel', () => {
  it('shows the single recommendation as the primary artifact with its Skillz status', () => {
    render(<FinalRecommendationPanel recommendation={buildRecommendation()} findings={[buildFinding()]} />);

    expect(screen.getByText('Final recommended requirement')).toBeInTheDocument();
    expect(screen.getByText('Ready to replace')).toBeInTheDocument();
    expect(screen.getByText('Skillz applied · Rev 5.5')).toBeInTheDocument();
    expect(screen.getByText('The system shall respond fast.')).toBeInTheDocument();
    // Highlighting shows removed words struck through alongside the added ones.
    expect(screen.getByTestId('recommended-description')).toHaveTextContent(
      'The system shall respond fast. within 2 s.'
    );
    fireEvent.click(screen.getByLabelText('Highlight changes'));
    expect(screen.getByTestId('recommended-description')).toHaveTextContent(/^The system shall respond within 2 s\.$/);
    expect(screen.getByText('Supporting evidence (1)')).toBeInTheDocument();
  });

  it('shows unresolved conflicts with every conflicting suggestion', () => {
    render(
      <FinalRecommendationPanel
        recommendation={buildRecommendation({
          status: 'needs_review',
          contributions: [
            buildContribution({ finding_id: 'F1', status: 'conflict_unresolved', conflict_id: 'K1' }),
            buildContribution({ finding_id: 'F2', status: 'conflict_unresolved', conflict_id: 'K1' }),
          ],
          conflicts: [
            {
              conflict_id: 'K1',
              finding_ids: ['F1', 'F2'],
              description: 'OAuth versus SAML.',
              resolution: 'unresolved',
              governing_rule_ids: [],
            },
          ],
        })}
        findings={[
          buildFinding({ finding_id: 'F1', suggested_rewrite: 'The system shall authenticate using OAuth.' }),
          buildFinding({ finding_id: 'F2', suggested_rewrite: 'The system shall authenticate using SAML.' }),
        ]}
      />
    );

    expect(screen.getByText('Needs review')).toBeInTheDocument();
    expect(screen.getByText('Review before replacing the original')).toBeInTheDocument();
    expect(screen.getByText('OAuth versus SAML.')).toBeInTheDocument();
    expect(screen.getAllByText('The system shall authenticate using OAuth.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('The system shall authenticate using SAML.').length).toBeGreaterThan(0);
  });

  it('opens the cited Skillz rule text', () => {
    render(
      <FinalRecommendationPanel
        recommendation={buildRecommendation({
          skillz_changes: [{ rule_id: 'C18', change: "Removed 'adequate'", reason: '' }],
          skillz_rules: [
            {
              rule_id: 'C18',
              title: 'Forbidden and controlled language',
              document: 'core-rules.md',
              text: 'Do not use vague language in a shall.',
              source_url: null,
              source_type: 'skillz_rule',
              authority_level: 1,
            },
          ],
        })}
        findings={[buildFinding()]}
      />
    );

    fireEvent.click(screen.getByText('Skillz C18'));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/Forbidden and controlled language/)).toBeInTheDocument();
    expect(within(dialog).getByText('Do not use vague language in a shall.')).toBeInTheDocument();
  });

  it('labels a standards-only recommendation when Skillz could not be loaded', () => {
    render(
      <FinalRecommendationPanel
        recommendation={buildRecommendation({
          skillz_status: 'unavailable',
          skillz_status_message: 'Skillz not applied: the Skillz rules could not be loaded.',
          skillz_revision: null,
        })}
        findings={[buildFinding()]}
      />
    );

    expect(screen.getByText('Skillz not applied')).toBeInTheDocument();
    expect(screen.getByText('Skillz not applied: the Skillz rules could not be loaded.')).toBeInTheDocument();
  });

  describe('writing to Jama', () => {
    const jamaTarget = { itemId: 101, documentKey: 'SYS-REQ-1', webUrl: null };

    it('confirms and writes the exact recommended text for Ready to replace', () => {
      const onApplyDecision = vi.fn();
      render(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={onApplyDecision}
          jamaTarget={jamaTarget}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Ready to replace', pressed: false }));
      fireEvent.click(screen.getByRole('button', { name: 'Save & write to Jama' }));

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText('Write to Jama SYS-REQ-1?')).toBeInTheDocument();
      expect(within(dialog).getByTestId('jama-write-preview')).toHaveTextContent(
        /^The system shall respond within 2 s\.$/
      );
      expect(onApplyDecision).not.toHaveBeenCalled();

      fireEvent.click(within(dialog).getByRole('button', { name: 'Write to Jama' }));

      expect(onApplyDecision).toHaveBeenCalledWith(
        'rev-1',
        { decision: 'ready_to_replace', reason: '', modified_description: null },
        { writeToJama: true }
      );
    });

    it('writes the reviewer-modified text for Accept, but modify', () => {
      const onApplyDecision = vi.fn();
      render(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={onApplyDecision}
          jamaTarget={jamaTarget}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Accept, but modify' }));
      fireEvent.change(screen.getByLabelText(/Modified description/), {
        target: { value: 'The system shall respond within 1 s.' },
      });
      fireEvent.click(screen.getByRole('button', { name: 'Save & write to Jama' }));

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByTestId('jama-write-preview')).toHaveTextContent(
        /^The system shall respond within 1 s\.$/
      );
      fireEvent.click(within(dialog).getByRole('button', { name: 'Write to Jama' }));

      expect(onApplyDecision).toHaveBeenCalledWith(
        'rev-1',
        {
          decision: 'accepted_with_modifications',
          reason: '',
          modified_description: 'The system shall respond within 1 s.',
        },
        { writeToJama: true }
      );
    });

    it('lets the Ready to replace status chip accept and open the Jama confirmation', () => {
      const onApplyDecision = vi.fn();
      render(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={onApplyDecision}
          jamaTarget={jamaTarget}
        />
      );

      fireEvent.click(screen.getByTestId('quick-accept-chip'));

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByTestId('jama-write-preview')).toHaveTextContent(
        /^The system shall respond within 2 s\.$/
      );
      expect(
        screen.getByRole('button', { name: 'Ready to replace', pressed: true, hidden: true })
      ).toBeInTheDocument();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Write to Jama' }));

      expect(onApplyDecision).toHaveBeenCalledWith(
        'rev-1',
        { decision: 'ready_to_replace', reason: '', modified_description: null },
        { writeToJama: true }
      );
    });

    it('keeps the status chip a plain label when no decision can be made', () => {
      render(
        <FinalRecommendationPanel recommendation={buildRecommendation()} findings={[buildFinding()]} readOnly />
      );
      expect(screen.queryByTestId('quick-accept-chip')).not.toBeInTheDocument();
    });

    it('never offers a Jama write for a rejection or a review not pulled from Jama', () => {
      const onApplyDecision = vi.fn();
      const { rerender } = render(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={onApplyDecision}
          jamaTarget={jamaTarget}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: 'Reject with reason' }));
      expect(screen.getByRole('button', { name: 'Save decision' })).toBeInTheDocument();

      rerender(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={onApplyDecision}
        />
      );
      fireEvent.click(screen.getByRole('button', { name: 'Ready to replace', pressed: false }));
      fireEvent.click(screen.getByRole('button', { name: 'Save decision' }));

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(onApplyDecision).toHaveBeenCalledWith(
        'rev-1',
        { decision: 'ready_to_replace', reason: '', modified_description: null },
        { writeToJama: false }
      );
    });

    it('shows the write result and errors', () => {
      const { rerender } = render(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={vi.fn()}
          jamaTarget={jamaTarget}
          jamaWriteError="This Jama item was changed after it was reviewed."
        />
      );
      expect(screen.getByText('Not written to Jama')).toBeInTheDocument();
      expect(screen.getByText('This Jama item was changed after it was reviewed.')).toBeInTheDocument();

      rerender(
        <FinalRecommendationPanel
          recommendation={buildRecommendation()}
          findings={[buildFinding()]}
          reviewId="rev-1"
          onApplyDecision={vi.fn()}
          jamaTarget={jamaTarget}
          jamaWrite={{
            item_id: 101,
            document_key: 'SYS-REQ-1',
            decision: 'ready_to_replace',
            description: 'The system shall respond within 2 s.',
            written_by: 'engineer@example.com',
            written_at: '2026-01-01T00:00:00Z',
            web_url: null,
          }}
        />
      );
      expect(screen.getByText('Written to Jama')).toBeInTheDocument();
    });
  });

  it('falls back to the individual suggestions when synthesis failed', () => {
    render(
      <FinalRecommendationPanel
        recommendation={buildRecommendation({
          status: 'failed',
          recommended_description: null,
          failure_message: 'The AI synthesis call did not complete.',
        })}
        findings={[buildFinding()]}
      />
    );

    expect(screen.getByText('Final recommendation not generated')).toBeInTheDocument();
    expect(screen.getByText('Individual suggestions')).toBeInTheDocument();
  });
});
