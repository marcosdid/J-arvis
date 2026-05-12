import { describe, it, expect } from 'vitest';
import { deriveCardState } from './taskCardState';

describe('deriveCardState', () => {
  it('returns idle for new task with no run', () => {
    expect(deriveCardState({ state: 'idea' })).toEqual({ kind: 'idle' });
  });
  it('returns running when task is in_progress', () => {
    expect(deriveCardState({ state: 'in_progress' })).toEqual({ kind: 'running' });
  });
  it('returns running when runStatus is running', () => {
    expect(deriveCardState({ state: 'ready' }, 'running')).toEqual({ kind: 'running' });
  });
  it('returns awaiting when runStatus is awaiting_response (overrides task state)', () => {
    expect(deriveCardState({ state: 'in_progress' }, 'awaiting_response')).toEqual({ kind: 'awaiting' });
  });
  it('returns done when task state is done', () => {
    expect(deriveCardState({ state: 'done' })).toEqual({ kind: 'done' });
  });
  it('returns error when task state is error', () => {
    expect(deriveCardState({ state: 'error' })).toEqual({ kind: 'error' });
  });
  it('error in run with running state still returns idle (run errors handled elsewhere)', () => {
    expect(deriveCardState({ state: 'ready' }, 'error')).toEqual({ kind: 'idle' });
  });
});
