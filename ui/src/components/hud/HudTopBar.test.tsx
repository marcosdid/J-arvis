import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HudTopBar } from './HudTopBar';

vi.mock('@/hooks/useSystemHealth', () => ({
  useSystemHealth: vi.fn(),
}));

import { useSystemHealth } from '@/hooks/useSystemHealth';
const useSystemHealthMock = vi.mocked(useSystemHealth);

const baseData = {
  cpu_pct: 12.4,
  mem_used_bytes: 2_147_483_648,
  mem_total_bytes: 34_359_738_368,
  uptime_seconds: 16_380,
  active_alerts_count: 0,
};

describe('HudTopBar', () => {
  beforeEach(() => {
    useSystemHealthMock.mockReturnValue({
      data: baseData,
    } as any);
  });

  it('renders OPER badge', () => {
    render(<HudTopBar wsRtt={null} />);
    expect(screen.getByText('OPER')).toBeInTheDocument();
  });

  it('renders J-ARVIS // OP_CTRL brand title', () => {
    render(<HudTopBar wsRtt={null} />);
    expect(screen.getByText(/J-ARVIS.*OP_CTRL/)).toBeInTheDocument();
  });

  it('always renders env metric', () => {
    render(<HudTopBar wsRtt={null} />);
    expect(screen.getByTestId('hud-metric-env')).toBeInTheDocument();
    expect(screen.getByText('linux/x86_64')).toBeInTheDocument();
  });

  it('renders rtt metric with em dash when wsRtt is null', () => {
    render(<HudTopBar wsRtt={null} />);
    const rttMetric = screen.getByTestId('hud-metric-rtt');
    expect(rttMetric).toBeInTheDocument();
    expect(rttMetric).toHaveTextContent('—');
  });

  it('renders rtt metric with value when wsRtt=42', () => {
    render(<HudTopBar wsRtt={42} />);
    const rttMetric = screen.getByTestId('hud-metric-rtt');
    expect(rttMetric).toHaveTextContent('42ms');
  });

  it('renders all 5 metrics when data is available', () => {
    render(<HudTopBar wsRtt={10} />);
    expect(screen.getByTestId('hud-metric-cpu')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-mem')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-rtt')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-uptime')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-alert')).toBeInTheDocument();
  });

  it('formats cpu correctly', () => {
    render(<HudTopBar wsRtt={null} />);
    expect(screen.getByTestId('hud-metric-cpu')).toHaveTextContent('12.4%');
  });

  it('formats mem bytes correctly', () => {
    render(<HudTopBar wsRtt={null} />);
    // 2147483648 / 1024^3 = 2.0G, 34359738368 / 1024^3 = 32.0G
    expect(screen.getByTestId('hud-metric-mem')).toHaveTextContent('2.0G/32.0G');
  });

  it('formats uptime correctly', () => {
    render(<HudTopBar wsRtt={null} />);
    // 16380s = 4h33m
    expect(screen.getByTestId('hud-metric-uptime')).toHaveTextContent('4h33m');
  });

  it('applies hot tone to alert metric when alerts > 0', () => {
    useSystemHealthMock.mockReturnValue({
      data: { ...baseData, active_alerts_count: 3 },
    } as any);
    render(<HudTopBar wsRtt={null} />);
    const alertMetric = screen.getByTestId('hud-metric-alert');
    const valueSpan = alertMetric.querySelector('span:last-child');
    expect(valueSpan).toHaveClass('text-accent-attn');
  });

  it('uses default tone for alert metric when alerts === 0', () => {
    render(<HudTopBar wsRtt={null} />);
    const alertMetric = screen.getByTestId('hud-metric-alert');
    const valueSpan = alertMetric.querySelector('span:last-child');
    expect(valueSpan).toHaveClass('text-accent-primary');
    expect(valueSpan).not.toHaveClass('text-accent-attn');
  });

  it('hides cpu/mem/uptime/alert when data is undefined (loading)', () => {
    useSystemHealthMock.mockReturnValue({ data: undefined } as any);
    render(<HudTopBar wsRtt={null} />);
    expect(screen.queryByTestId('hud-metric-cpu')).not.toBeInTheDocument();
    expect(screen.queryByTestId('hud-metric-mem')).not.toBeInTheDocument();
    expect(screen.queryByTestId('hud-metric-uptime')).not.toBeInTheDocument();
    expect(screen.queryByTestId('hud-metric-alert')).not.toBeInTheDocument();
    // OPER, title, env, and rtt should still be visible
    expect(screen.getByText('OPER')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-env')).toBeInTheDocument();
    expect(screen.getByTestId('hud-metric-rtt')).toBeInTheDocument();
  });
});
