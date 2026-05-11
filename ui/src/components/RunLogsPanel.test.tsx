import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ServiceStatus } from '../lib/api';
import { RunLogsPanel } from './RunLogsPanel';

type Listener = (line: { service: string; stream: 'stdout'|'stderr'; text: string }) => void;

vi.mock('../lib/runSseClient', () => ({
  createLogsSse: vi.fn((_runId: string, _svc: string, _onLine: Listener) =>
    ({ close: vi.fn() }),
  ),
}));

import { createLogsSse } from '../lib/runSseClient';

function svc(name: string, port_host: number | null = null): ServiceStatus {
  return {
    name, state: 'ready' as const, port_host,
    port_container: 8000, container_id: 'cid', error: null,
  };
}

beforeEach(() => {
  (createLogsSse as ReturnType<typeof vi.fn>).mockClear();
});
afterEach(() => vi.clearAllMocks());

describe('RunLogsPanel', () => {
  it('renders empty placeholder when no log lines yet', () => {
    render(<RunLogsPanel runId="r1" services={[svc('backend')]} />);
    expect(screen.getByText(/sem logs/i)).toBeDefined();
  });

  it('renders dropdown with all services and defaults to first', () => {
    render(<RunLogsPanel runId="r1" services={[svc('db'), svc('backend')]} />);
    const select = screen.getByLabelText('run-logs-service') as HTMLSelectElement;
    expect(select.value).toBe('db');
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(['db', 'backend']);
  });

  it('subscribes to SSE on mount with first service', () => {
    render(<RunLogsPanel runId="r1" services={[svc('db')]} />);
    expect(createLogsSse).toHaveBeenCalledWith('r1', 'db', expect.any(Function));
  });

  it('re-subscribes when service dropdown changes', () => {
    render(<RunLogsPanel runId="r1" services={[svc('db'), svc('backend')]} />);
    const select = screen.getByLabelText('run-logs-service');
    fireEvent.change(select, { target: { value: 'backend' } });
    expect(createLogsSse).toHaveBeenCalledWith('r1', 'backend', expect.any(Function));
  });

  it('handles empty services array (no subscription)', () => {
    render(<RunLogsPanel runId="r1" services={[]} />);
    expect(createLogsSse).not.toHaveBeenCalled();
  });
});
