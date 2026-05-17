import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Run } from '../lib/api';
import { RunStatus } from './RunStatus';

vi.mock('../lib/api', () => ({
  api: {
    getActiveRun: vi.fn(),
    startRun: vi.fn(),
    stopRun: vi.fn(),
    bootstrapManifest: vi.fn(),
  },
}));

import { api } from '../lib/api';

function wrap(taskId = 't1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunStatus taskId={taskId} />
    </QueryClientProvider>,
  );
}

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'r1',
    task_id: 't1',
    cwd: '/c',
    manifest_path: '/m',
    status: 'ready',
    services: [],
    network_name: 'jarvis-run-x',
    started_at: '2026-01-01T00:00:00Z',
    ended_at: null,
    error_message: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => vi.clearAllMocks());

describe('RunStatus', () => {
  it('shows ▶ Run button when no active run', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    wrap();
    expect(await screen.findByRole('button', { name: /run-start/ })).toBeDefined();
  });

  it('shows ● ready + Stop + URL chip when status ready and service has port_host', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({
        status: 'ready',
        services: [{
          name: 'backend', state: 'ready', port_host: 31101,
          port_container: 8000, container_id: 'cid', error: null,
        }],
      }),
    );
    wrap();
    await waitFor(() => expect(screen.getByText(/● ready/)).toBeDefined());
    expect(screen.getByRole('button', { name: /run-stop/ })).toBeDefined();
    const url = screen.getByRole('link', { name: /backend/ });
    expect(url.getAttribute('href')).toBe('http://localhost:31101');
  });

  it('shows building label when status building', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'building' }),
    );
    wrap();
    await waitFor(() => expect(screen.getByText(/building/)).toBeDefined());
  });

  it('shows failed label with error message', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'failed', error_message: 'build error: missing Dockerfile' }),
    );
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/build error: missing Dockerfile/)).toBeDefined(),
    );
  });

  it('shows ▶ Run button again when status stopped', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'stopped', ended_at: '2026-01-01T01:00:00Z' }),
    );
    wrap();
    expect(await screen.findByRole('button', { name: /run-restart/ })).toBeDefined();
  });

  it('opens BootstrapModal when startRun returns bootstrap hint', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      run: null,
      bootstrap: { reason: 'manifest_missing' },
    });
    wrap();
    const btn = await screen.findByRole('button', { name: /run-start/ });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(screen.getByRole('dialog', { name: /Manifesto faltando/ })).toBeDefined(),
    );
  });

  it('does NOT open bootstrap modal on a genuine startRun error', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    (api.startRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 500: docker daemon dead'),
    );
    wrap();
    const btn = await screen.findByRole('button', { name: /run-start/ });
    fireEvent.click(btn);
    await waitFor(() => expect(api.startRun).toHaveBeenCalled());
    expect(
      screen.queryByRole('dialog', { name: /Manifesto faltando/ }),
    ).toBeNull();
  });

  it('clicking ⏹ Stop calls stopRun with run id', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'ready' }),
    );
    (api.stopRun as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    wrap();
    const stop = await screen.findByRole('button', { name: /run-stop/ });
    fireEvent.click(stop);
    await waitFor(() => expect(api.stopRun).toHaveBeenCalledWith('r1'));
  });
});
