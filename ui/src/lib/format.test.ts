import { describe, expect, it } from 'vitest';

import { formatStatus } from './format';

describe('formatStatus', () => {
  it('translates executing to "Em execução"', () => {
    expect(formatStatus('executing')).toBe('Em execução');
  });
});
