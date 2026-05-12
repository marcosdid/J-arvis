import { useEffect } from 'react';

type Opts = { meta?: boolean; ctrl?: boolean; shift?: boolean; alt?: boolean };

export function useKeyboardShortcut(
  key: string,
  handler: (e: KeyboardEvent) => void,
  opts: Opts = {},
) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target;
      if (target instanceof Element && target.matches('input, textarea, [contenteditable=true]')) return;
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      if (!!opts.meta !== e.metaKey) return;
      if (!!opts.ctrl !== e.ctrlKey) return;
      if (!!opts.shift !== e.shiftKey) return;
      if (!!opts.alt !== e.altKey) return;
      e.preventDefault();
      handler(e);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [key, handler, opts.meta, opts.ctrl, opts.shift, opts.alt]);
}
