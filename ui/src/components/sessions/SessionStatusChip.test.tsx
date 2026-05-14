import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Session, SessionStatus } from '@/lib/api';

import { SessionStatusChip } from './SessionStatusChip';

function makeSession(status: SessionStatus): Session {
  return {
    id: 'sess-1',
    task_id: 't1',
    status,
    pid: 123,
    cwd: '/tmp/wt',
    last_hook_at: null,
    started_at: '2026-01-01T00:00:00Z',
    ended_at: null,
  };
}

describe('SessionStatusChip', () => {
  it('renders the status label', () => {
    render(<SessionStatusChip session={makeSession('awaiting_response')} />);
    expect(screen.getByText('awaiting_response')).toBeInTheDocument();
  });

  it('applies the executing color class and pulse animation', () => {
    render(<SessionStatusChip session={makeSession('executing')} />);
    const dot = screen.getByLabelText('executing');
    expect(dot.className).toContain('bg-blue-500');
    expect(dot.className).toContain('animate-pulse');
  });

  it('uses a distinct color per status', () => {
    render(<SessionStatusChip session={makeSession('error')} />);
    expect(screen.getByLabelText('error').className).toContain('bg-red-500');
  });
});
