import { describe, expect, it } from 'vitest';
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
