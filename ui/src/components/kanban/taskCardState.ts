import type { Task } from '@/lib/api';

export type CardKind = 'idle' | 'running' | 'awaiting' | 'error' | 'done';
export type CardState = { kind: CardKind; meta?: string };

// runStatus: free-form string from RunStatus query, OR a derived enum from the run subscription.
// Pass it as optional — TaskCard can resolve internally if not yet known.
export function deriveCardState(
  task: Pick<Task, 'state'>,
  runStatus?: string | null,
): CardState {
  // Awaiting beats running
  if (runStatus === 'awaiting_response') return { kind: 'awaiting' };
  if (task.state === 'done') return { kind: 'done' };
  if (task.state === 'error') return { kind: 'error' };
  if (runStatus === 'running' || task.state === 'in_progress') return { kind: 'running' };
  return { kind: 'idle' };
}
