import { describe, expect, it } from 'vitest';

import { formatStatus } from './format';

describe('formatStatus', () => {
  it('translates executing', () => {
    expect(formatStatus('executing')).toBe('Em execução');
  });

  it('translates awaiting_response', () => {
    expect(formatStatus('awaiting_response')).toBe('Aguardando resposta');
  });

  it('translates idle', () => {
    expect(formatStatus('idle')).toBe('Ocioso');
  });

  it('translates error', () => {
    expect(formatStatus('error')).toBe('Erro');
  });

  it('translates done', () => {
    expect(formatStatus('done')).toBe('Concluído');
  });

  it('returns the raw value for unknown statuses', () => {
    expect(formatStatus('mystery')).toBe('mystery');
  });
});
