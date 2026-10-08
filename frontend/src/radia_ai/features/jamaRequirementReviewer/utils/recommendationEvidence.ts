import type {
  ContributionStatus,
  FinalRecommendation,
  FindingContribution,
  RecommendationConflict,
  ReviewFinding,
} from '@/types/api';

export type EvidenceGroupKey = 'applied' | 'merged' | 'overridden' | 'unresolved' | 'not_incorporated';

export interface EvidenceItem {
  contribution: FindingContribution;
  /** The finding this contribution traces back to, when it is still present. */
  finding: ReviewFinding | null;
  /** Position of the finding in the review's findings list (used for dispositions). */
  findingIndex: number;
}

export interface EvidenceGroup {
  key: EvidenceGroupKey;
  label: string;
  items: EvidenceItem[];
}

const GROUP_FOR_STATUS: Record<ContributionStatus, EvidenceGroupKey> = {
  applied: 'applied',
  merged_duplicate: 'merged',
  overridden: 'overridden',
  conflict_unresolved: 'unresolved',
  not_addressed: 'unresolved',
  rejected_unsupported: 'not_incorporated',
  out_of_scope: 'not_incorporated',
};

const GROUP_LABELS: Record<EvidenceGroupKey, string> = {
  applied: 'Applied',
  merged: 'Duplicates merged',
  overridden: 'Overridden by Skillz',
  unresolved: 'Unresolved',
  not_incorporated: 'Not incorporated',
};

const GROUP_ORDER: EvidenceGroupKey[] = ['applied', 'merged', 'overridden', 'unresolved', 'not_incorporated'];

export const CONTRIBUTION_STATUS_LABEL: Record<ContributionStatus, string> = {
  applied: 'Applied',
  merged_duplicate: 'Duplicate merged',
  overridden: 'Overridden by Skillz',
  conflict_unresolved: 'Unresolved conflict',
  not_addressed: 'Not addressed',
  rejected_unsupported: 'Not incorporated: unsupported',
  out_of_scope: 'Not incorporated: other field',
};

/** Groups every contribution by how it was treated, in a stable display order. */
export function groupEvidence(
  recommendation: FinalRecommendation,
  findings: ReviewFinding[]
): EvidenceGroup[] {
  const indexById = new Map<string, number>();
  findings.forEach((finding, index) => {
    indexById.set(finding.finding_id ?? `F${index + 1}`, index);
  });

  const byGroup = new Map<EvidenceGroupKey, EvidenceItem[]>();
  for (const contribution of recommendation.contributions) {
    const findingIndex = indexById.get(contribution.finding_id) ?? -1;
    const key = GROUP_FOR_STATUS[contribution.status];
    const items = byGroup.get(key) ?? [];
    items.push({
      contribution,
      finding: findingIndex >= 0 ? findings[findingIndex] : null,
      findingIndex,
    });
    byGroup.set(key, items);
  }

  return GROUP_ORDER.filter((key) => byGroup.has(key)).map((key) => ({
    key,
    label: GROUP_LABELS[key],
    items: byGroup.get(key) ?? [],
  }));
}

export function unresolvedConflicts(recommendation: FinalRecommendation): RecommendationConflict[] {
  return recommendation.conflicts.filter((conflict) => conflict.resolution === 'unresolved');
}

/** Human-readable reasons a recommendation needs review before it replaces the original. */
export function needsReviewReasons(recommendation: FinalRecommendation): string[] {
  const reasons: string[] = [];
  const conflicts = unresolvedConflicts(recommendation).length;
  const notAddressed = recommendation.contributions.filter((c) => c.status === 'not_addressed').length;
  const checkIssues = recommendation.skillz_check_issues.length;
  if (conflicts > 0) {
    reasons.push(
      `${conflicts} conflicting suggestion set${conflicts === 1 ? '' : 's'} could not be resolved safely; the original wording was kept for ${conflicts === 1 ? 'that aspect' : 'those aspects'}.`
    );
  }
  if (notAddressed > 0) {
    reasons.push(`${notAddressed} suggestion${notAddressed === 1 ? ' was' : 's were'} not addressed by the synthesis.`);
  }
  if (checkIssues > 0) {
    reasons.push(`${checkIssues} Skillz check issue${checkIssues === 1 ? ' remains' : 's remain'} in the recommended text.`);
  }
  return reasons;
}

/** Short source label such as "INCOSE Guide, p.12". */
export function findingSourceLabel(finding: ReviewFinding | null): string {
  if (!finding) return 'Source unavailable';
  const name = finding.reference_title ?? finding.reference;
  if (finding.source_page) return `${name}, p.${finding.source_page}`;
  if (finding.source_section) return `${name}, ${finding.source_section}`;
  return name;
}
