import type { Session } from '@/lib/api';

import { SessionStatusChip } from './SessionStatusChip';

export function SessionHistoryItem({ session }: { session: Session }) {
  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <span className="font-mono">sid:{session.id.slice(0, 6)}</span>
      <SessionStatusChip session={session} />
      <span className="text-zinc-500">
        {new Date(session.started_at).toLocaleTimeString()}
      </span>
    </div>
  );
}
