import { describe, expect, it } from 'vitest';
import { splitMessageLinks } from './messageLinks';

describe('splitMessageLinks', () => {
  it('turns a Markdown link into a link segment', () => {
    expect(
      splitMessageLinks(
        'View it [here in Jama](https://radia.jamacloud.com/perspective.req#/items/778871?projectId=66).',
      ),
    ).toEqual([
      { type: 'text', text: 'View it ' },
      {
        type: 'link',
        text: 'here in Jama',
        href: 'https://radia.jamacloud.com/perspective.req#/items/778871?projectId=66',
      },
      { type: 'text', text: '.' },
    ]);
  });

  it('leaves plain text untouched', () => {
    expect(splitMessageLinks('No links here')).toEqual([{ type: 'text', text: 'No links here' }]);
  });

  it('never links a non-http(s) URL', () => {
    expect(splitMessageLinks('[click](javascript:alert(1))')).toEqual([
      { type: 'text', text: '[click](javascript:alert(1))' },
    ]);
    expect(splitMessageLinks('[x](data:text/html,hi)')).toEqual([
      { type: 'text', text: '[x](data:text/html,hi)' },
    ]);
  });

  it('handles several links', () => {
    const segments = splitMessageLinks('[A](https://a.example/1) and [B](https://a.example/2)');
    expect(segments.filter((s) => s.type === 'link').map((s) => s.text)).toEqual(['A', 'B']);
  });
});
