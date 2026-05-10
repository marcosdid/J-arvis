import { describe, expect, it } from 'vitest';
import { translateError } from './errorMessages';

describe('translateError', () => {
  it('maps "task already has active session" to pt-BR', () => {
    expect(translateError('task already has active session'))
      .toContain('sessão ativa');
  });
  it('maps "invalid transition: …" to pt-BR', () => {
    expect(translateError('invalid transition: idea → done'))
      .toContain('Transição');
  });
  it('maps "title cannot be empty" to pt-BR', () => {
    expect(translateError('title cannot be empty or whitespace-only'))
      .toContain('Título');
  });
  it('maps "project has N task" to pt-BR', () => {
    expect(translateError('project has 2 task(s); discard them before deleting'))
      .toContain('Descarte');
  });
  it('maps terminal state error to pt-BR', () => {
    expect(translateError("cannot start session: task is in terminal state 'done'"))
      .toContain('terminal');
  });
  it('returns raw message for unknown errors', () => {
    expect(translateError('mystery error')).toBe('mystery error');
  });
});
