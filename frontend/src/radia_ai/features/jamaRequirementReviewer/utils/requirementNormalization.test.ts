import { describe, expect, it } from 'vitest';
import { normalizeRequirementText } from './requirementNormalization';

describe('normalizeRequirementText', () => {
  it('preserves wrapped field lines in structured Jama text', () => {
    const rawText = [
      'Title: Lubrication, Movable Pin Arrangements',
      '',
      'Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin',
      'arrangements on the aircraft shall have a means to lubricate the joints with grease fittings',
      'or other materials that prevent corrosion or damage of the movable pin arrangement.',
      '',
      'Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of',
      'Permanent Sealing & Servicing.',
    ].join('\n');

    expect(normalizeRequirementText(rawText)).toBe(
      'Title: Lubrication, Movable Pin Arrangements\n\n'
        + 'Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin arrangements on the aircraft shall have a means to lubricate the joints with grease fittings or other materials that prevent corrosion or damage of the movable pin arrangement.\n\n'
        + 'Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing.'
    );
  });
});
