import type { Session, SessionStatus } from '@/lib/api';

const COLORS: Record<SessionStatus, string> = {
  executing: 'bg-blue-500 animate-pulse',
  awaiting_response: 'bg-yellow-500',
  idle: 'bg-green-500',
  error: 'bg-red-500',
  done: 'bg-zinc-500',
};

export function SessionStatusChip({ session }: { session: Session }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs"
      data-testid="session-status-chip"
    >
      <span
        className={`w-2 h-2 rounded-full ${COLORS[session.status]}`}
        aria-label={session.status}
      />
      <span>{session.status}</span>
    </span>
  );
}
