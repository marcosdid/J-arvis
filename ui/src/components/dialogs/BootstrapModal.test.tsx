import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { BootstrapModal, type BootstrapProposed } from './BootstrapModal';

vi.mock('../../lib/api', () => ({
  api: {
    bootstrapManifest: vi.fn(),
    cancelBootstrap: vi.fn(),
    startRun: vi.fn(),
  },
}));

import { api } from '../../lib/api';

function makeWrapper(): { wrapper: ({ children }: { children: ReactNode }) => ReactElement } {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.clearAllMocks());

describe('BootstrapModal phase 1 (idle / starting / waiting)', () => {
  it('renders title + explanation + 2 buttons in idle phase', () => {
    const { wrapper } = makeWrapper();
    render(<BootstrapModal taskId="t1" onClose={vi.fn()} />, { wrapper });
    expect(screen.getByText(/Manifesto faltando/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Iniciar bootstrap/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Cancelar/i })).toBeDefined();
  });

  it('calls bootstrapManifest on "Iniciar bootstrap" then transitions to waiting phase', async () => {
    (api.bootstrapManifest as ReturnType<typeof vi.fn>).mockResolvedValue({
      session_id: 'abc',
      cwd: '/p',
      manifest_path: '/p/.orchestrator/run.yml',
      prompt_path: '/p/.orchestrator/bootstrap.prompt.md',
    });
    const onClose = vi.fn();
    const { wrapper } = makeWrapper();
    render(<BootstrapModal taskId="t1" onClose={onClose} />, { wrapper });
    fireEvent.click(screen.getByRole('button', { name: /Iniciar bootstrap/i }));
    await waitFor(() => expect(api.bootstrapManifest).toHaveBeenCalledWith('t1'));
    // After success the modal stays open and shows the waiting copy.
    await waitFor(() => {
      expect(screen.getByText(/Aguardando o Claude propor o manifesto/i)).toBeDefined();
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('shows error alert when bootstrap fails and stays open (returns to idle)', async () => {
    (api.bootstrapManifest as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 500: server boom'),
    );
    const { wrapper } = makeWrapper();
    render(<BootstrapModal taskId="t1" onClose={vi.fn()} />, { wrapper });
    fireEvent.click(screen.getByRole('button', { name: /Iniciar bootstrap/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeDefined());
    expect(screen.getByRole('alert').textContent).toContain('server boom');
    // Still in idle phase → button visible.
    expect(screen.getByRole('button', { name: /Iniciar bootstrap/i })).toBeDefined();
  });

  it('Cancelar in idle phase invokes onClose immediately without calling cancel', () => {
    const onClose = vi.fn();
    const { wrapper } = makeWrapper();
    render(<BootstrapModal taskId="t1" onClose={onClose} />, { wrapper });
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
    expect(onClose).toHaveBeenCalled();
    expect(api.cancelBootstrap).not.toHaveBeenCalled();
  });
});

describe('BootstrapModal phase 2 (preview-valid / preview-invalid)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows preview + countdown when proposed.valid=true', () => {
    const { wrapper } = makeWrapper();
    const proposed: BootstrapProposed = {
      manifest_text: 'version: "1"\nservices: {}\n',
      valid: true,
      errors: [],
    };
    render(
      <BootstrapModal taskId="t1" onClose={vi.fn()} proposed={proposed} />,
      { wrapper },
    );
    expect(screen.getByText(/Manifesto pronto/i)).toBeDefined();
    expect(screen.getByText(/version: "1"/)).toBeDefined();
    expect(screen.getByRole('button', { name: /Run agora/i })).toBeDefined();
  });

  it('auto-fires startRun after 10s in preview-valid and closes', async () => {
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      run: {
        id: 'r1', task_id: 't1', cwd: '/p',
        manifest_path: '/p/.orchestrator/run.yml',
        status: 'pending', services: [],
        network_name: 'net', started_at: '', ended_at: null, error_message: null,
      },
      bootstrap: null,
    });
    const onClose = vi.fn();
    const { wrapper } = makeWrapper();
    render(
      <BootstrapModal
        taskId="t1"
        onClose={onClose}
        proposed={{ manifest_text: 'version: "1"\n', valid: true, errors: [] }}
      />,
      { wrapper },
    );
    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });
    expect(api.startRun).toHaveBeenCalledWith('t1');
    // Flush the mutation resolution + onSuccess.
    await act(async () => {
      vi.useRealTimers();
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('preview-invalid shows manifest, errors, no Run-agora button, no countdown', () => {
    const { wrapper } = makeWrapper();
    const proposed: BootstrapProposed = {
      manifest_text: 'bad',
      valid: false,
      errors: ['missing version', 'unknown service'],
    };
    render(
      <BootstrapModal taskId="t1" onClose={vi.fn()} proposed={proposed} />,
      { wrapper },
    );
    expect(screen.getByText(/Manifesto inválido/i)).toBeDefined();
    expect(screen.getByText('missing version')).toBeDefined();
    expect(screen.getByText('unknown service')).toBeDefined();
    expect(screen.queryByRole('button', { name: /Run agora/i })).toBeNull();
    // Cancelar still present.
    expect(screen.getByRole('button', { name: /Cancelar/i })).toBeDefined();
  });

  it('Cancel in preview-valid calls cancelBootstrap then onClose', async () => {
    (api.cancelBootstrap as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const onClose = vi.fn();
    const { wrapper } = makeWrapper();
    render(
      <BootstrapModal
        taskId="t1"
        onClose={onClose}
        proposed={{ manifest_text: 'version: "1"\n', valid: true, errors: [] }}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
    await act(async () => {
      vi.useRealTimers();
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => expect(api.cancelBootstrap).toHaveBeenCalledWith('t1'));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('clicking "Run agora" before countdown ends fires startRun immediately', async () => {
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      run: {
        id: 'r1', task_id: 't1', cwd: '/p',
        manifest_path: '/p/.orchestrator/run.yml',
        status: 'pending', services: [],
        network_name: 'net', started_at: '', ended_at: null, error_message: null,
      },
      bootstrap: null,
    });
    const onClose = vi.fn();
    const { wrapper } = makeWrapper();
    render(
      <BootstrapModal
        taskId="t1"
        onClose={onClose}
        proposed={{ manifest_text: 'version: "1"\n', valid: true, errors: [] }}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByRole('button', { name: /Run agora/i }));
    // React Query schedules mutationFn on a microtask; flush before asserting.
    await act(async () => {
      vi.useRealTimers();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(api.startRun).toHaveBeenCalledWith('t1');
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
