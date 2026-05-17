import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Run } from '../../lib/api';
import { RunTab } from './RunTab';

vi.mock('../../lib/api', () => ({
  api: {
    getActiveRun: vi.fn(),
    startRun: vi.fn(),
    stopRun: vi.fn(),
    bootstrapManifest: vi.fn(),
  },
}));
vi.mock('../../lib/runSseClient', () => ({
  createLogsSse: vi.fn(() => ({ close: vi.fn() })),
}));

import { api } from '../../lib/api';

function wrap(taskId = 't1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RunTab taskId={taskId} />
    </QueryClientProvider>,
  );
}

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'r1', task_id: 't1', cwd: '/c', manifest_path: '/m',
    status: 'ready', services: [], network_name: 'net',
    started_at: '2026-01-01T00:00:00Z', ended_at: null, error_message: null,
    ...overrides,
  };
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.clearAllMocks());

describe('RunTab', () => {
  it('shows "Nenhuma run ativa" + Run button when no run', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    wrap();
    expect(await screen.findByText(/Nenhuma run ativa/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /run-tab-start/ })).toBeDefined();
  });

  it('shows status + Stop button when run is ready', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({
        status: 'ready',
        services: [{
          name: 'backend', state: 'ready', port_host: 31100,
          port_container: 8000, container_id: 'cid', error: null,
        }],
      }),
    );
    wrap();
    await waitFor(() => expect(screen.getByText(/Status: ready/)).toBeDefined());
    expect(screen.getByRole('button', { name: /run-tab-stop/ })).toBeDefined();
  });

  it('shows Run button (not Stop) when status is stopped', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'stopped', ended_at: '2026-01-01T01:00:00Z' }),
    );
    wrap();
    await waitFor(() => expect(screen.getByText(/Status: stopped/)).toBeDefined());
    expect(screen.getByRole('button', { name: /run-tab-restart/ })).toBeDefined();
    expect(screen.queryByRole('button', { name: /run-tab-stop/ })).toBeNull();
  });

  it('shows error_message in alert when run failed', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({ status: 'failed', error_message: 'build crashed' }),
    );
    wrap();
    await waitFor(() => expect(screen.getByRole('alert')).toBeDefined());
    expect(screen.getByRole('alert').textContent).toContain('build crashed');
  });

  it('lists services with badges', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRun({
        services: [
          {
            name: 'db', state: 'ready', port_host: null,
            port_container: 5432, container_id: 'c1', error: null,
          },
          {
            name: 'backend', state: 'ready', port_host: 31100,
            port_container: 8000, container_id: 'c2', error: null,
          },
        ],
      }),
    );
    const { container } = wrap();
    await waitFor(() => {
      const badges = container.querySelectorAll('.service-badge');
      expect(badges).toHaveLength(2);
    });
    // ServiceStatusBadge sets data-service-name; verify both rendered
    expect(container.querySelector('[data-service-name="db"]')).not.toBeNull();
    expect(container.querySelector('[data-service-name="backend"]')).not.toBeNull();
    // URL link só pro service com port_host
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0]!.getAttribute('href')).toBe('http://localhost:31100');
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
    const btn = await screen.findByRole('button', { name: /run-tab-start/ });
    fireEvent.click(btn);
    await waitFor(() =>
      expect(screen.getByRole('dialog', { name: /Manifesto faltando/ })).toBeDefined(),
    );
  });

  it('does NOT open BootstrapModal on a genuine startRun error', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    (api.startRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 500: docker daemon dead'),
    );
    wrap();
    const btn = await screen.findByRole('button', { name: /run-tab-start/ });
    fireEvent.click(btn);
    await waitFor(() => expect(api.startRun).toHaveBeenCalled());
    expect(
      screen.queryByRole('dialog', { name: /Manifesto faltando/ }),
    ).toBeNull();
  });
});
