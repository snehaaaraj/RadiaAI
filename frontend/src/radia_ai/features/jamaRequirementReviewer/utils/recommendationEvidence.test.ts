import { describe, expect, it } from 'vitest';
import { buildContribution, buildFinding, buildRecommendation } from '../test/recommendationFixtures';
import { findingSourceLabel, groupEvidence, needsReviewReasons } from './recommendationEvidence';

describe('groupEvidence', () => {
  it('groups contributions by treatment in display order and links each to its finding', () => {
    const findings = [
      buildFinding({ finding_id: 'F1' }),
      buildFinding({ finding_id: 'F2' }),
      buildFinding({ finding_id: 'F3' }),
      buildFinding({ finding_id: 'F4' }),
    ];
    const recommendation = buildRecommendation({
      contributions: [
        buildContribution({ finding_id: 'F3', status: 'overridden', overridden_by_rule_ids: ['C17'] }),
        buildContribution({ finding_id: 'F1', status: 'applied' }),
        buildContribution({ finding_id: 'F4', status: 'out_of_scope' }),
        buildContribution({ finding_id: 'F2', status: 'merged_duplicate', duplicate_of: 'F1' }),
      ],
    });

    const groups = groupEvidence(recommendation, findings);

    expect(groups.map((g) => g.key)).toEqual(['applied', 'merged', 'overridden', 'not_incorporated']);
    expect(groups[2].items[0].finding?.finding_id).toBe('F3');
    expect(groups[2].items[0].findingIndex).toBe(2);
  });

  it('keeps contributions whose finding is missing', () => {
    const groups = groupEvidence(
      buildRecommendation({ contributions: [buildContribution({ finding_id: 'F9' })] }),
      [buildFinding()]
    );

    expect(groups[0].items[0].finding).toBeNull();
    expect(groups[0].items[0].findingIndex).toBe(-1);
  });

  it('falls back to positional IDs for findings stored without an ID', () => {
    const groups = groupEvidence(buildRecommendation(), [buildFinding({ finding_id: null })]);

    expect(groups[0].items[0].findingIndex).toBe(0);
  });
});

describe('needsReviewReasons', () => {
  it('is empty for a ready recommendation', () => {
    expect(needsReviewReasons(buildRecommendation())).toEqual([]);
  });

  it('explains unresolved conflicts, unaddressed suggestions and Skillz check issues', () => {
    const reasons = needsReviewReasons(
      buildRecommendation({
        status: 'needs_review',
        contributions: [buildContribution({ status: 'not_addressed' })],
        conflicts: [
          {
            conflict_id: 'K1',
            finding_ids: ['F2', 'F3'],
            description: 'OAuth versus SAML',
            resolution: 'unresolved',
            governing_rule_ids: [],
          },
        ],
        skillz_check_issues: [{ rule_id: 'C18', term: 'adequate', message: 'Forbidden.' }],
      })
    );

    expect(reasons).toHaveLength(3);
    expect(reasons[0]).toContain('could not be resolved safely');
  });
});

describe('findingSourceLabel', () => {
  it('prefers page, then section', () => {
    expect(findingSourceLabel(buildFinding())).toBe('INCOSE Guide, p.12');
    expect(findingSourceLabel(buildFinding({ source_page: null, source_section: '4.2' }))).toBe('INCOSE Guide, 4.2');
    expect(findingSourceLabel(null)).toBe('Source unavailable');
  });
});
