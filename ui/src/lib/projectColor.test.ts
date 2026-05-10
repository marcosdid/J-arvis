import { describe, expect, it } from 'vitest';
import { projectColor, PALETTE } from './projectColor';

describe('projectColor', () => {
  it('returns one of the 8 palette colors', () => {
    expect(PALETTE).toHaveLength(8);
    const c = projectColor('any-uuid-here');
    expect(PALETTE).toContain(c);
  });
  it('is deterministic for the same id', () => {
    expect(projectColor('xyz')).toBe(projectColor('xyz'));
  });
  it('distributes different ids across colors', () => {
    const colors = new Set(
      Array.from({ length: 32 }, (_, i) => projectColor(`id-${i}`))
    );
    expect(colors.size).toBeGreaterThanOrEqual(4);
  });
});
