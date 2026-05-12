interface MasterFooterProps {
  pid: number | null;
  rtt: number | null;
  rows?: number;
  cols?: number;
  live: boolean;
}

export function MasterFooter({ pid, rtt, rows = 24, cols = 80, live }: MasterFooterProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1 text-[0.6rem] text-text-faint border-t border-border-subtle bg-bg-deep">
      <span>pty {cols}x{rows}</span>
      <span className="text-border-subtle">·</span>
      <span>pid {pid ?? '—'}</span>
      <span className="text-border-subtle">·</span>
      <span
        data-testid="live-indicator"
        className={live ? 'text-accent-primary' : 'text-text-faint'}
      >
        ● live
      </span>
      <span className="text-border-subtle">·</span>
      <span>{rtt ?? '—'}ms</span>
    </div>
  );
}
