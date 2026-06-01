export type ClipboardCtx = {
  hasSelection: () => boolean;
  getSelection: () => string;
  clearSelection: () => void;
  writeText: (s: string) => Promise<void>;
  readText: () => Promise<string>;
  paste: (s: string) => void;
};

export function handleTerminalKeyEvent(
  ev: KeyboardEvent,
  ctx: ClipboardCtx,
): boolean {
  if (ev.type !== 'keydown') return true;
  if (!ev.ctrlKey) return true;

  const key = ev.key.toLowerCase();

  if (key === 'c' && !ev.shiftKey) {
    if (!ctx.hasSelection()) return true;
    void ctx.writeText(ctx.getSelection());
    ctx.clearSelection();
    return false;
  }

  if (key === 'c' && ev.shiftKey) {
    if (ctx.hasSelection()) {
      void ctx.writeText(ctx.getSelection());
      ctx.clearSelection();
    }
    return false;
  }

  if (key === 'v' && ev.shiftKey) {
    ctx.readText().then((text) => {
      if (text) ctx.paste(text);
    });
    return false;
  }

  return true;
}
