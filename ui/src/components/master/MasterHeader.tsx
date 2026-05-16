type Status = 'connecting' | 'connected' | 'disconnected' | 'error';

interface MasterHeaderProps {
  pid: number | null;
  sessionId: string;
  status: Status;
  onClear?: () => void;
  onCopyId?: () => void;
  onRestart?: () => void;
  onMinimize?: () => void;
}

const dotColor: Record<Status, string> = {
  connecting: 'bg-semantic-warn',
  connected: 'bg-accent-primary',
  disconnected: 'bg-border-subtle',
  error: 'bg-semantic-error',
};

export function MasterHeader({
  pid,
  sessionId,
  status,
  onClear,
  onCopyId,
  onRestart,
  onMinimize,
}: MasterHeaderProps) {
  const displaySessionId = sessionId.length > 8 ? `${sessionId.slice(0, 8)}…` : sessionId;

  return (
    <div className="bg-bg-deep border-b border-border-subtle px-3 py-2 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            data-testid="status-dot"
            aria-label={`status-${status}`}
            className={`inline-block w-2 h-2 rounded-full ${dotColor[status]}`}
          />
          <span className="text-text-emphasis text-xs font-mono">{displaySessionId}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onClear}
            className="text-[0.6rem] px-1.5 py-0.5 text-text-subtle hover:text-text-emphasis border border-border-subtle hover:border-border-mid rounded-sm transition-colors"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onCopyId}
            className="text-[0.6rem] px-1.5 py-0.5 text-text-subtle hover:text-text-emphasis border border-border-subtle hover:border-border-mid rounded-sm transition-colors"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={onRestart}
            className="text-[0.6rem] px-1.5 py-0.5 text-text-subtle hover:text-text-emphasis border border-border-subtle hover:border-border-mid rounded-sm transition-colors"
          >
            Restart
          </button>
          <button
            type="button"
            onClick={onMinimize}
            className="text-[0.6rem] px-1.5 py-0.5 text-text-subtle hover:text-text-emphasis border border-border-subtle hover:border-border-mid rounded-sm transition-colors"
          >
            Min
          </button>
        </div>
      </div>
      <span className="text-text-faint text-xs font-mono">
        claude --resume {displaySessionId} · 80×24 · pid {pid ?? '—'}
      </span>
    </div>
  );
}
