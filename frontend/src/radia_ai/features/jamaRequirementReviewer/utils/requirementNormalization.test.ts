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

  it('drops trailing metadata glued to the rationale line', () => {
    const rawText = [
      'Title: Lubrication, Movable Pin Arrangements',
      '',
      'Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin arrangements on the aircraft shall have a means to lubricate the joints with grease fittings or other materials that prevent corrosion or damage of the movable pin arrangement. Note: design solution will be system and case specific.',
      '',
      'Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing. Requirement Volatility Low Derived Requirement No Safety Requirement No Security Effectiveness Requirement No Validation Method Engineering Review,Traceability Verification Method Undetermined,Inspection,Review',
    ].join('\n');

    expect(normalizeRequirementText(rawText)).toBe(
      'Title: Lubrication, Movable Pin Arrangements\n\n'
        + 'Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin arrangements on the aircraft shall have a means to lubricate the joints with grease fittings or other materials that prevent corrosion or damage of the movable pin arrangement. Note: design solution will be system and case specific.\n\n'
        + 'Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing.'
    );
  });

  it('drops the requirement heading from the description body', () => {
    const rawText = [
      '1 WR-ACR-732 Semi-Prepared Runway Operations (SPRO)',
      'The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on',
      'semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR)',
      'of 9 or greater, without requiring ground support equipment for maneuvering.',
      '',
      'Project ID WR-ACR-732',
      'Title Semi-Prepared Runway Operations (SPRO)',
      'Rationale Ensures mission compatibility with SPRO sites',
      'Requirement Volatility Low',
    ].join('\n');

    expect(normalizeRequirementText(rawText)).toBe(
      'Title: Semi-Prepared Runway Operations (SPRO)\n\n'
        + 'Description: The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR) of 9 or greater, without requiring ground support equipment for maneuvering.\n\n'
        + 'Rationale: Ensures mission compatibility with SPRO sites'
    );
  });
});
