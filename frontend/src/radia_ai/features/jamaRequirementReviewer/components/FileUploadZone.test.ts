import { describe, expect, it } from 'vitest';
import { cleanExtractedText } from './fileUploadTextCleaner';

describe('cleanExtractedText', () => {
  it('drops Jama metadata after the rationale section', () => {
    const raw = [
      'Radia Production Page 3 of 3',
      '1 SAND-ACR-1164 Lubrication, Movable Pin Arrangements',
      'Unless permanently sealed by design, all movable pin arrangements on the aircraft shall',
      'have a means to lubricate the joints with grease fittings or other materials that prevent',
      'corrosion or damage of the movable pin arrangement.',
      'Note: design solution will be system and case specific.',
      'Project ID SAND-ACR-1164',
      'Status Draft',
      'Title Lubrication, Movable Pin Arrangements',
      'Rationale Prevention against corrosion. See WR-ACR-241 for conditions of',
      'Permanent Sealing & Servicing.',
      'Requirement Volatility Low',
      'Derived Requirement No',
      'Safety Requirement No',
      'Security Effectiveness Requirement No',
    ].join('\n');

    expect(cleanExtractedText(raw)).toContain('Rationale Prevention against corrosion. See WR-ACR-241 for conditions of');
    expect(cleanExtractedText(raw)).not.toContain('Requirement Volatility Low');
    expect(cleanExtractedText(raw)).not.toContain('Derived Requirement No');
  });
});
