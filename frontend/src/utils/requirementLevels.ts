export const REQUIREMENT_LEVELS = ['Aircraft', 'System', 'Subsystem', 'Component'] as const;

export type RequirementLevel = (typeof REQUIREMENT_LEVELS)[number];

const NORMALIZED_LEVEL_MAP: Record<string, RequirementLevel> = {
  aircraft: 'Aircraft',
  system: 'System',
  subsystem: 'Subsystem',
  component: 'Component',
};

export function normalizeRequirementLevel(level?: string | null): RequirementLevel {
  if (!level) return 'System';
  return NORMALIZED_LEVEL_MAP[level.trim().toLowerCase()] ?? 'System';
}
