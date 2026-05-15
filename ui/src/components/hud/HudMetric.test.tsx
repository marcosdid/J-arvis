import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HudMetric } from './HudMetric';

describe('HudMetric', () => {
  it('renders label + string value', () => {
    render(<HudMetric label='cpu' value='12.4%' />);
    expect(screen.getByText('cpu')).toBeInTheDocument();
    expect(screen.getByText('12.4%')).toBeInTheDocument();
  });

  it('renders numeric value', () => {
    render(<HudMetric label='alert' value={3} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('uses primary (green) accent for default tone', () => {
    render(<HudMetric label='cpu' value='0%' />);
    const valueEl = screen.getByText('0%');
    expect(valueEl).toHaveClass('text-accent-primary');
    expect(valueEl).not.toHaveClass('text-accent-attn');
  });

  it('uses attn (magenta) accent for hot tone', () => {
    render(<HudMetric label='alert' value={5} tone='hot' />);
    const valueEl = screen.getByText('5');
    expect(valueEl).toHaveClass('text-accent-attn');
    expect(valueEl.className).toContain('drop-shadow-[0_0_6px_rgba(255,16,240,0.6)]');
  });

  it('exposes data-testid derived from label', () => {
    render(<HudMetric label='mem' value='2G/32G' />);
    expect(screen.getByTestId('hud-metric-mem')).toBeInTheDocument();
  });
});
