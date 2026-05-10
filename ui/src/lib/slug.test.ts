import { describe, expect, it } from 'vitest';
import { slugifyForBranch, InvalidBranchSlugError } from './slug';

describe('slugifyForBranch', () => {
  it('simple kebab from spaces', () => {
    expect(slugifyForBranch('Add dark mode')).toBe('add-dark-mode');
  });

  it('collapses repeated separators', () => {
    expect(slugifyForBranch('Refactor:::HTTP/2 layer')).toBe('refactor-http-2-layer');
  });

  it('strips leading/trailing hyphens and whitespace', () => {
    expect(slugifyForBranch('  --  Fix bug  --  ')).toBe('fix-bug');
  });

  it('truncates at 60 chars', () => {
    expect(slugifyForBranch('a'.repeat(100)).length).toBe(60);
  });

  it('unicode accents become hyphens then collapse', () => {
    expect(slugifyForBranch('Café à la mode')).toBe('caf-la-mode');
  });

  it('throws InvalidBranchSlugError on empty result', () => {
    expect(() => slugifyForBranch('...')).toThrow(InvalidBranchSlugError);
  });

  it('throws on whitespace-only input', () => {
    expect(() => slugifyForBranch('   ')).toThrow(InvalidBranchSlugError);
  });
});
