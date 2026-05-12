import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useKeyboardShortcut } from './useKeyboardShortcut';

function fireKey(key: string, opts: Partial<KeyboardEventInit> = {}, target?: HTMLElement) {
  const ev = new KeyboardEvent('keydown', { key, ...opts });
  if (target) {
    Object.defineProperty(ev, 'target', { value: target });
  }
  window.dispatchEvent(ev);
}

describe('useKeyboardShortcut', () => {
  it('fires handler on key match (case-insensitive)', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('N', handler));
    fireKey('n');
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not fire on wrong key', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('n', handler));
    fireKey('x');
    expect(handler).not.toHaveBeenCalled();
  });

  it('skips when target is input', () => {
    const handler = vi.fn();
    const input = document.createElement('input');
    document.body.appendChild(input);
    renderHook(() => useKeyboardShortcut('n', handler));
    fireKey('n', {}, input);
    expect(handler).not.toHaveBeenCalled();
    input.remove();
  });

  it('skips when target is textarea', () => {
    const handler = vi.fn();
    const textarea = document.createElement('textarea');
    document.body.appendChild(textarea);
    renderHook(() => useKeyboardShortcut('n', handler));
    fireKey('n', {}, textarea);
    expect(handler).not.toHaveBeenCalled();
    textarea.remove();
  });

  it('skips when target is contenteditable', () => {
    const handler = vi.fn();
    const div = document.createElement('div');
    div.setAttribute('contenteditable', 'true');
    document.body.appendChild(div);
    renderHook(() => useKeyboardShortcut('n', handler));
    fireKey('n', {}, div);
    expect(handler).not.toHaveBeenCalled();
    div.remove();
  });

  it('respects meta modifier requirement', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { meta: true }));
    fireKey('k'); // no meta
    expect(handler).not.toHaveBeenCalled();
    fireKey('k', { metaKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('respects ctrl modifier', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { ctrl: true }));
    fireKey('k');
    expect(handler).not.toHaveBeenCalled();
    fireKey('k', { ctrlKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('respects shift modifier', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { shift: true }));
    fireKey('k', { shiftKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('respects alt modifier', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('k', handler, { alt: true }));
    fireKey('k'); // no alt — must not fire
    expect(handler).not.toHaveBeenCalled();
    fireKey('k', { altKey: true });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('rejects key when extra modifier accidentally pressed', () => {
    const handler = vi.fn();
    renderHook(() => useKeyboardShortcut('n', handler));
    fireKey('n', { shiftKey: true }); // shift pressed but not required
    expect(handler).not.toHaveBeenCalled();
  });

  it('removes listener on unmount', () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() => useKeyboardShortcut('n', handler));
    unmount();
    fireKey('n');
    expect(handler).not.toHaveBeenCalled();
  });
});
