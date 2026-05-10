import { describe, expect, it } from 'vitest';
import { isValidTransition, resolveColumnState } from './transitions';

const VALID: Array<[string, string]> = [
  ['idea', 'ready'], ['idea', 'discarded'],
  ['ready', 'idea'], ['ready', 'in_progress'], ['ready', 'discarded'],
  ['in_progress', 'review'], ['in_progress', 'discarded'],
  ['review', 'in_progress'], ['review', 'done'], ['review', 'discarded'],
  ['discarded', 'idea'],
];
const STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

describe('isValidTransition', () => {
  for (const [f, t] of VALID) {
    it(`allows ${f} → ${t}`, () => {
      expect(isValidTransition(f, t)).toBe(true);
    });
  }
  for (const f of STATES) {
    it(`allows ${f} → ${f} (idempotent)`, () => {
      expect(isValidTransition(f, f)).toBe(true);
    });
  }
  it('rejects done → ready', () => {
    expect(isValidTransition('done', 'ready')).toBe(false);
  });
  it('rejects in_progress → idea', () => {
    expect(isValidTransition('in_progress', 'idea')).toBe(false);
  });
});

describe('resolveColumnState', () => {
  it.each([
    ['Backlog', 'ready'],
    ['In Progress', 'in_progress'],
    ['Review', 'review'],
    ['Done', 'done'],
    ['Discarded', 'discarded'],
  ])('column %s → %s', (col, expected) => {
    expect(resolveColumnState(col)).toBe(expected);
  });
  it('throws on unknown column', () => {
    expect(() => resolveColumnState('Foo')).toThrow();
  });
});
