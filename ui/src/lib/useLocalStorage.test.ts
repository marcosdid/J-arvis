import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLocalStorage } from './useLocalStorage';

describe('useLocalStorage', () => {
  const KEY = 'test-key';

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('returns initial value when nothing stored', () => {
    const { result } = renderHook(() => useLocalStorage<number>(KEY, 42));
    expect(result.current[0]).toBe(42);
  });

  it('returns stored value when present', () => {
    window.localStorage.setItem(KEY, JSON.stringify('stored'));
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'initial'));
    expect(result.current[0]).toBe('stored');
  });

  it('persists set value to localStorage', () => {
    const { result } = renderHook(() => useLocalStorage<string>(KEY, ''));
    act(() => result.current[1]('updated'));
    expect(result.current[0]).toBe('updated');
    expect(window.localStorage.getItem(KEY)).toBe(JSON.stringify('updated'));
  });

  it('falls back to initial when stored value is corrupt JSON', () => {
    window.localStorage.setItem(KEY, '{not valid json');
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'fallback'));
    expect(result.current[0]).toBe('fallback');
  });

  it('handles object values', () => {
    const { result } = renderHook(() =>
      useLocalStorage<{ a: number; b: string }>(KEY, { a: 1, b: 'x' }),
    );
    act(() => result.current[1]({ a: 2, b: 'y' }));
    expect(result.current[0]).toEqual({ a: 2, b: 'y' });
  });

  it('silently ignores write errors (e.g. quota exceeded)', () => {
    const { result } = renderHook(() => useLocalStorage<string>(KEY, ''));
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    try {
      act(() => result.current[1]('value'));
      expect(result.current[0]).toBe('value');
      expect(spy).toHaveBeenCalledWith(KEY, JSON.stringify('value'));
    } finally {
      spy.mockRestore();
    }
  });
});
