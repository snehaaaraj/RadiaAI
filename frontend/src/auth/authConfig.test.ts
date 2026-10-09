import { describe, expect, it } from 'vitest';
import { isLocalViewingEnvironment } from './authConfig';

describe('isLocalViewingEnvironment', () => {
  it.each(['localhost', '127.0.0.1', '::1'])('allows local viewing on %s', (hostname) => {
    expect(isLocalViewingEnvironment('local-preview', true, hostname)).toBe(true);
  });

  it.each([
    ['development', true, 'localhost'],
    ['local-preview', false, 'localhost'],
    ['local-preview', true, 'radia.example.com'],
  ])('does not allow local viewing for mode=%s, dev=%s, host=%s', (mode, isDev, hostname) => {
    expect(isLocalViewingEnvironment(mode, isDev, hostname)).toBe(false);
  });
});
