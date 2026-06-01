import { describe, expect, it } from 'vitest';

import { formatRelativeTime } from './relativeTime';

const NOW = new Date('2026-05-18T22:00:00Z').getTime();

describe('formatRelativeTime', () => {
  it('returns "agora" for times within the last minute', () => {
    expect(formatRelativeTime('2026-05-18T21:59:30Z', NOW)).toBe('agora');
  });

  it('returns minutes with "m" suffix under 1 hour', () => {
    expect(formatRelativeTime('2026-05-18T21:55:00Z', NOW)).toBe('5m');
    expect(formatRelativeTime('2026-05-18T21:01:00Z', NOW)).toBe('59m');
  });

  it('returns hours with "h" suffix under 24h', () => {
    expect(formatRelativeTime('2026-05-18T20:00:00Z', NOW)).toBe('2h');
    expect(formatRelativeTime('2026-05-17T23:00:00Z', NOW)).toBe('23h');
  });

  it('returns days with "d" suffix under 30d', () => {
    expect(formatRelativeTime('2026-05-15T22:00:00Z', NOW)).toBe('3d');
    expect(formatRelativeTime('2026-04-19T22:00:00Z', NOW)).toBe('29d');
  });

  it('returns months with "mo" suffix beyond 30d', () => {
    expect(formatRelativeTime('2026-04-01T00:00:00Z', NOW)).toBe('1mo');
    expect(formatRelativeTime('2025-08-01T00:00:00Z', NOW)).toBe('9mo');
  });

  it('returns "—" for invalid input', () => {
    expect(formatRelativeTime('not-a-date', NOW)).toBe('—');
    expect(formatRelativeTime('', NOW)).toBe('—');
  });

  it('uses the current time when no reference provided', () => {
    expect(formatRelativeTime(new Date().toISOString())).toBe('agora');
  });
});
