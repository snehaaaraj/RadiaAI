import { describe, expect, it } from 'vitest';
import { diffWords } from './wordDiff';

describe('diffWords', () => {
  it('returns a single unchanged part for identical text', () => {
    expect(diffWords('The system shall run.', 'The system shall run.')).toEqual([
      { type: 'same', text: 'The system shall run.' },
    ]);
  });

  it('marks replaced words as removed then added', () => {
    expect(diffWords('shall respond fast to the pilot', 'shall respond to the flightcrew')).toEqual([
      { type: 'same', text: 'shall respond' },
      { type: 'removed', text: 'fast' },
      { type: 'same', text: 'to the' },
      { type: 'removed', text: 'pilot' },
      { type: 'added', text: 'flightcrew' },
    ]);
  });

  it('handles empty inputs', () => {
    expect(diffWords('', 'new text')).toEqual([{ type: 'added', text: 'new text' }]);
    expect(diffWords('old text', '')).toEqual([{ type: 'removed', text: 'old text' }]);
  });
});
