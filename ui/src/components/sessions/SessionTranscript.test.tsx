import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api');
  return { ...actual, api: { getTranscript: vi.fn() } };
});

import { api, type TranscriptMessage } from '@/lib/api';

import { SessionTranscript } from './SessionTranscript';

function wrap(node: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  vi.mocked(api.getTranscript).mockReset();
});

describe('SessionTranscript', () => {
  it('shows the loading placeholder before data resolves', () => {
    vi.mocked(api.getTranscript).mockReturnValue(new Promise(() => {}));
    wrap(<SessionTranscript sessionId="sess-1" />);
    expect(screen.getByText('Carregando transcript…')).toBeInTheDocument();
  });

  it('shows the empty placeholder when there are no messages', async () => {
    vi.mocked(api.getTranscript).mockResolvedValue([]);
    wrap(<SessionTranscript sessionId="sess-1" />);
    expect(await screen.findByText('Sem transcript ainda.')).toBeInTheDocument();
  });

  it('renders role, tool name and content for each message', async () => {
    const messages: TranscriptMessage[] = [
      {
        role: 'assistant',
        content: 'rodando build',
        tool_name: 'Bash',
        timestamp: '2026-01-01T00:00:00Z',
        source_file: 'a.jsonl',
      },
      {
        role: 'user',
        content: 'oi',
        tool_name: null,
        timestamp: '2026-01-01T00:00:01Z',
        source_file: 'a.jsonl',
      },
    ];
    vi.mocked(api.getTranscript).mockResolvedValue(messages);
    wrap(<SessionTranscript sessionId="sess-1" />);
    expect(await screen.findByText('[Bash]')).toBeInTheDocument();
    expect(screen.getByText('rodando build')).toBeInTheDocument();
    expect(screen.getByText('oi')).toBeInTheDocument();
  });
});
