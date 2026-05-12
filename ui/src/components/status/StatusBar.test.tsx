import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WsState } from '@/stores/wsConnection';
import type { SystemHealth } from '@/hooks/useSystemHealth';
import { StatusBar } from './StatusBar';

vi.mock('@/hooks/useSystemHealth');
vi.mock('@/stores/wsConnection');

import { useSystemHealth } from '@/hooks/useSystemHealth';
import { useWsConnectionStore } from '@/stores/wsConnection';

function mockWs(state: WsState) {
  vi.mocked(useWsConnectionStore).mockImplementation(
    (selector: (s: { state: WsState; setState: () => void }) => unknown) =>
      selector({ state, setState: vi.fn() }),
  );
}

function mockHealth(active_alerts_count: number) {
  vi.mocked(useSystemHealth).mockReturnValue({
    data: {
      cpu_pct: 0,
      mem_used_bytes: 0,
      mem_total_bytes: 0,
      uptime_seconds: 0,
      active_alerts_count,
    } satisfies SystemHealth,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any);
}

beforeEach(() => {
  mockWs('connected');
  mockHealth(0);
});

describe('StatusBar', () => {
  it('renders all 8 segments', () => {
    render(<StatusBar />);
    const ids = ['state', 'ws', 'mcp', 'alerts', 'mode', 'profile', 'git', 'v'];
    for (const id of ids) {
      expect(screen.getByTestId(`status-seg-${id}`)).toBeDefined();
    }
  });

  it('state segment shows "online" when ws is connected', () => {
    mockWs('connected');
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-state');
    expect(seg.textContent).toContain('online');
  });

  it('state segment shows "offline" when ws is offline', () => {
    mockWs('offline');
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-state');
    expect(seg.textContent).toContain('offline');
  });

  it('state segment shows "offline" when ws is reconnecting', () => {
    mockWs('reconnecting');
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-state');
    expect(seg.textContent).toContain('offline');
  });

  it('state tone is default (text-accent-primary) when connected', () => {
    mockWs('connected');
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-state"]');
    expect(seg?.querySelector('.text-accent-primary')).not.toBeNull();
  });

  it('state tone is error (text-accent-attn) when offline', () => {
    mockWs('offline');
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-state"]');
    expect(seg?.querySelector('.text-accent-attn')).not.toBeNull();
  });

  it('ws segment tone is warn when reconnecting', () => {
    mockWs('reconnecting');
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-ws"]');
    expect(seg?.querySelector('.text-semantic-warn')).not.toBeNull();
  });

  it('ws segment tone is error when offline', () => {
    mockWs('offline');
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-ws"]');
    expect(seg?.querySelector('.text-accent-attn')).not.toBeNull();
  });

  it('ws segment tone is default when connected', () => {
    mockWs('connected');
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-ws"]');
    expect(seg?.querySelector('.text-accent-primary')).not.toBeNull();
  });

  it('alerts segment reflects active_alerts_count', () => {
    mockHealth(3);
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-alerts');
    expect(seg.textContent).toContain('3');
  });

  it('alerts tone is error when count > 0', () => {
    mockHealth(2);
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-alerts"]');
    expect(seg?.querySelector('.text-accent-attn')).not.toBeNull();
  });

  it('alerts tone is default when count === 0', () => {
    mockHealth(0);
    const { container } = render(<StatusBar />);
    const seg = container.querySelector('[data-testid="status-seg-alerts"]');
    expect(seg?.querySelector('.text-accent-primary')).not.toBeNull();
  });

  it('v segment shows hardcoded v0.0.1', () => {
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-v');
    expect(seg.textContent).toContain('v0.0.1');
  });

  it('renders as a footer with role=status', () => {
    render(<StatusBar />);
    expect(screen.getByRole('status')).toBeDefined();
  });

  it('alerts defaults to 0 when health data is undefined', () => {
    vi.mocked(useSystemHealth).mockReturnValue({ data: undefined } as any);
    render(<StatusBar />);
    const seg = screen.getByTestId('status-seg-alerts');
    expect(seg.textContent).toContain('0');
  });
});
