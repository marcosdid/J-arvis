import { afterEach, describe, expect, it } from 'vitest';
import { loadFilters, saveFilters } from './kanbanFilters';

afterEach(() => localStorage.clear());

describe('kanbanFilters', () => {
  it('load returns empty when nothing saved', () => {
    expect(loadFilters()).toEqual([]);
  });
  it('saves and loads array of project ids', () => {
    saveFilters(['a', 'b']);
    expect(loadFilters()).toEqual(['a', 'b']);
  });
  it('filters out ids not in the known set on read', () => {
    saveFilters(['a', 'gone']);
    expect(loadFilters(new Set(['a']))).toEqual(['a']);
  });
  it('ignores corrupted JSON gracefully', () => {
    localStorage.setItem('jarvis.kanban.filters', '{not json}');
    expect(loadFilters()).toEqual([]);
  });
  it('ignores non-array JSON gracefully', () => {
    localStorage.setItem('jarvis.kanban.filters', '"hello"');
    expect(loadFilters()).toEqual([]);
  });
});
