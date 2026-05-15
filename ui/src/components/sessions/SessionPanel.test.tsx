import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api');
  return {
    ...actual,
    api: { listSessions: vi.fn(), stopSession: vi.fn(), getTranscript: vi.fn() },
  };
});

import { api, type Session } from '@/lib/api';

import { SessionPanel } from './SessionPanel';

function wrap(node: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

function makeSession(over: Partial<Session>): Session {
  return {
    id: 'sess-active',
    task_id: 't1',
    status: 'executing',
    pid: 100,
    cwd: '/tmp/wt',
    last_hook_at: null,
    started_at: '2026-01-01T00:00:00Z',
    ended_at: null,
    ...over,
  };
}

beforeEach(() => {
  vi.mocked(api.listSessions).mockReset();
  vi.mocked(api.getTranscript).mockResolvedValue([]);
});

describe('SessionPanel', () => {
  it('renders an active session card with status chip and Stop button', async () => {
    vi.mocked(api.listSessions).mockResolvedValue([makeSession({})]);
    wrap(<SessionPanel taskId="t1" open onOpenChange={() => {}} />);
    expect(await screen.findByText('sid:sess-a')).toBeInTheDocument();
    expect(screen.getByTestId('session-status-chip')).toBeInTheDocument();
    expect(screen.getByText('Stop')).toBeInTheDocument();
  });

  it('separates ended sessions into the Histórico section', async () => {
    vi.mocked(api.listSessions).mockResolvedValue([
      makeSession({ id: 'sess-old', status: 'done', ended_at: '2026-01-01T01:00:00Z' }),
    ]);
    wrap(<SessionPanel taskId="t1" open onOpenChange={() => {}} />);
    expect(await screen.findByText('Histórico')).toBeInTheDocument();
    expect(screen.getByText('sid:sess-o')).toBeInTheDocument();
    expect(screen.queryByText('Stop')).toBeNull();
  });

  it('does not query sessions while closed with a null task', () => {
    wrap(<SessionPanel taskId={null} open={false} onOpenChange={() => {}} />);
    expect(api.listSessions).not.toHaveBeenCalled();
  });
});
