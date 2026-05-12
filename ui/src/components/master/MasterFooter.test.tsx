import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MasterFooter } from './MasterFooter';

describe('MasterFooter', () => {
  it('renders pty dimensions segment', () => {
    render(<MasterFooter pid={null} rtt={null} rows={24} cols={80} live={false} />);
    expect(screen.getByText('pty 80x24')).toBeInTheDocument();
  });

  it('renders pid when provided', () => {
    render(<MasterFooter pid={4242} rtt={null} rows={24} cols={80} live={false} />);
    expect(screen.getByText('pid 4242')).toBeInTheDocument();
  });

  it('renders em-dash for pid when pid is null', () => {
    render(<MasterFooter pid={null} rtt={null} rows={24} cols={80} live={false} />);
    expect(screen.getByText('pid —')).toBeInTheDocument();
  });

  it('renders rtt value in ms when provided', () => {
    render(<MasterFooter pid={null} rtt={42} rows={24} cols={80} live={true} />);
    expect(screen.getByText('42ms')).toBeInTheDocument();
  });

  it('renders em-dash ms when rtt is null', () => {
    render(<MasterFooter pid={null} rtt={null} rows={24} cols={80} live={false} />);
    expect(screen.getByText('—ms')).toBeInTheDocument();
  });

  it('live indicator is green (text-accent-primary) when live=true', () => {
    render(<MasterFooter pid={null} rtt={null} live={true} />);
    const indicator = screen.getByTestId('live-indicator');
    expect(indicator.className).toContain('text-accent-primary');
  });

  it('live indicator is dim (text-text-faint) when live=false', () => {
    render(<MasterFooter pid={null} rtt={null} live={false} />);
    const indicator = screen.getByTestId('live-indicator');
    expect(indicator.className).toContain('text-text-faint');
  });

  it('defaults to 80x24 when rows/cols not provided', () => {
    render(<MasterFooter pid={null} rtt={null} live={false} />);
    expect(screen.getByText('pty 80x24')).toBeInTheDocument();
  });
});
