import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { BootstrapModal } from './BootstrapModal';

vi.mock('../../lib/api', () => ({
  api: { bootstrapManifest: vi.fn() },
}));

import { api } from '../../lib/api';

function wrap(onClose = vi.fn()) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <BootstrapModal taskId="t1" onClose={onClose} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.clearAllMocks());

describe('BootstrapModal', () => {
  it('renders title + explanation + 2 buttons', () => {
    wrap();
    expect(screen.getByText(/Manifesto faltando/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Iniciar bootstrap/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /Cancelar/i })).toBeDefined();
  });

  it('calls bootstrapManifest on "Iniciar bootstrap" then onClose on success', async () => {
    (api.bootstrapManifest as ReturnType<typeof vi.fn>).mockResolvedValue({
      session_id: 'abc', cwd: '/p',
    });
    const onClose = vi.fn();
    wrap(onClose);
    fireEvent.click(screen.getByRole('button', { name: /Iniciar bootstrap/i }));
    await waitFor(() => expect(api.bootstrapManifest).toHaveBeenCalledWith('t1'));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('shows error alert when bootstrap fails', async () => {
    (api.bootstrapManifest as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 500: server boom'),
    );
    wrap();
    fireEvent.click(screen.getByRole('button', { name: /Iniciar bootstrap/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeDefined());
    expect(screen.getByRole('alert').textContent).toContain('server boom');
  });

  it('Cancelar invokes onClose immediately', () => {
    const onClose = vi.fn();
    wrap(onClose);
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
