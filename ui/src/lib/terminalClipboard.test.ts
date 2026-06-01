import { describe, expect, it, vi } from 'vitest';

import { handleTerminalKeyEvent, type ClipboardCtx } from './terminalClipboard';

function makeCtx(over: Partial<ClipboardCtx> = {}): ClipboardCtx {
  return {
    hasSelection: () => false,
    getSelection: () => '',
    clearSelection: vi.fn(),
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
    paste: vi.fn(),
    ...over,
  };
}

describe('handleTerminalKeyEvent', () => {
  it('Ctrl+C with selection copies, clears selection, returns false', () => {
    const ctx = makeCtx({
      hasSelection: () => true,
      getSelection: () => 'hello world',
    });
    const ev = new KeyboardEvent('keydown', { key: 'c', ctrlKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(false);
    expect(ctx.writeText).toHaveBeenCalledWith('hello world');
    expect(ctx.clearSelection).toHaveBeenCalled();
  });

  it('Ctrl+C without selection lets SIGINT through (returns true)', () => {
    const ctx = makeCtx({ hasSelection: () => false });
    const ev = new KeyboardEvent('keydown', { key: 'c', ctrlKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(true);
    expect(ctx.writeText).not.toHaveBeenCalled();
  });

  it('Ctrl+Shift+C copies selection and suppresses default', () => {
    const ctx = makeCtx({
      hasSelection: () => true,
      getSelection: () => 'foo',
    });
    const ev = new KeyboardEvent('keydown', { key: 'C', ctrlKey: true, shiftKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(false);
    expect(ctx.writeText).toHaveBeenCalledWith('foo');
  });

  it('Ctrl+Shift+C with empty selection still suppresses default', () => {
    const ctx = makeCtx({ hasSelection: () => false });
    const ev = new KeyboardEvent('keydown', { key: 'C', ctrlKey: true, shiftKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(false);
    expect(ctx.writeText).not.toHaveBeenCalled();
  });

  it('Ctrl+Shift+V reads clipboard, pastes, suppresses default', async () => {
    const readText = vi.fn().mockResolvedValue('pasted text');
    const paste = vi.fn();
    const ctx = makeCtx({ readText, paste });
    const ev = new KeyboardEvent('keydown', { key: 'V', ctrlKey: true, shiftKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(false);
    await new Promise((r) => setTimeout(r, 0));
    expect(paste).toHaveBeenCalledWith('pasted text');
  });

  it('Ctrl+Shift+V with empty clipboard does not paste empty', async () => {
    const readText = vi.fn().mockResolvedValue('');
    const paste = vi.fn();
    const ctx = makeCtx({ readText, paste });
    const ev = new KeyboardEvent('keydown', { key: 'V', ctrlKey: true, shiftKey: true });
    handleTerminalKeyEvent(ev, ctx);
    await new Promise((r) => setTimeout(r, 0));
    expect(paste).not.toHaveBeenCalled();
  });

  it('keyup events always pass through (only keydown is handled)', () => {
    const ctx = makeCtx({ hasSelection: () => true, getSelection: () => 'x' });
    const ev = new KeyboardEvent('keyup', { key: 'c', ctrlKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(true);
    expect(ctx.writeText).not.toHaveBeenCalled();
  });

  it('regular character keys pass through unchanged', () => {
    const ctx = makeCtx();
    const ev = new KeyboardEvent('keydown', { key: 'a' });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(true);
  });

  it('Ctrl+V alone (no Shift) passes through — terminal owns paste mode', () => {
    const ctx = makeCtx();
    const ev = new KeyboardEvent('keydown', { key: 'v', ctrlKey: true });
    expect(handleTerminalKeyEvent(ev, ctx)).toBe(true);
    expect(ctx.paste).not.toHaveBeenCalled();
  });
});
