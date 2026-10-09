import type { FinalRecommendation, FindingContribution, ReviewFinding } from '@/types/api';

export function buildFinding(overrides: Partial<ReviewFinding> = {}): ReviewFinding {
  return {
    finding_id: 'F1',
    source_type: 'standard',
    authority_level: 2,
    category: 'Ambiguous Wording',
    reviewer: 'language',
    severity: 'Medium',
    pass_fail: 'Fail',
    status: 'Revision Recommended',
    rule: 'Avoid vague terms.',
    explanation: "'fast' is not verifiable.",
    evidence: 'fast',
    recommendation: 'Bound the response time.',
    reference: 'INCOSE',
    reference_title: 'INCOSE Guide',
    reference_url: null,
    suggested_rewrite: 'The system shall respond within 2 s.',
    source_page: 12,
    source_section: null,
    source_excerpt: 'Requirements shall be verifiable.',
    source_chunk_id: null,
    ...overrides,
  };
}

export function buildContribution(overrides: Partial<FindingContribution> = {}): FindingContribution {
  return {
    finding_id: 'F1',
    status: 'applied',
    contribution: 'Bounded the response time',
    reason: '',
    overridden_by_rule_ids: [],
    duplicate_of: null,
    conflict_id: null,
    ...overrides,
  };
}

export function buildRecommendation(overrides: Partial<FinalRecommendation> = {}): FinalRecommendation {
  return {
    status: 'ready',
    original_description: 'The system shall respond fast.',
    recommended_description: 'The system shall respond within 2 s.',
    summary: 'Bounded the response time.',
    skillz_status: 'applied',
    skillz_status_message: 'Skillz applied: acr-generator Revision 5.5.',
    skillz_package: 'acr-generator',
    skillz_revision: '5.5',
    skillz_content_hash: 'abc',
    skillz_source_url: 'https://sharepoint/skillz.zip',
    contributions: [buildContribution()],
    skillz_changes: [],
    conflicts: [],
    open_items: [],
    skillz_rules: [],
    skillz_check_issues: [],
    failure_message: '',
    prompt_version: 'synthesis.v1',
    ...overrides,
  };
}
