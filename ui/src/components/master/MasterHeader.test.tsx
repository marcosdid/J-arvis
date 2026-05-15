import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MasterHeader } from './MasterHeader';

describe('MasterHeader', () => {
  it('renders the session id as title', () => {
    render(
      <MasterHeader pid={null} sessionId="master_001" status="connected" />,
    );
    expect(screen.getByText('master_001')).toBeInTheDocument();
  });

  it('renders a green dot when status is connected', () => {
    render(
      <MasterHeader pid={null} sessionId="master_001" status="connected" />,
    );
    const dot = screen.getByTestId('status-dot');
    expect(dot.className).toContain('bg-accent-primary');
  });

  it('renders a yellow dot when status is connecting', () => {
    render(
      <MasterHeader pid={null} sessionId="master_001" status="connecting" />,
    );
    const dot = screen.getByTestId('status-dot');
    expect(dot.className).toContain('bg-semantic-warn');
  });

  it('renders a red dot when status is error', () => {
    render(
      <MasterHeader pid={null} sessionId="master_001" status="error" />,
    );
    const dot = screen.getByTestId('status-dot');
    expect(dot.className).toContain('bg-semantic-error');
  });

  it('fires onClear when Clear button is clicked', () => {
    const onClear = vi.fn();
    render(
      <MasterHeader
        pid={null}
        sessionId="master_001"
        status="connected"
        onClear={onClear}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it('fires onCopyId when Copy button is clicked', () => {
    const onCopyId = vi.fn();
    render(
      <MasterHeader
        pid={null}
        sessionId="master_001"
        status="connected"
        onCopyId={onCopyId}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /copy/i }));
    expect(onCopyId).toHaveBeenCalledOnce();
  });

  it('fires onRestart when Restart button is clicked', () => {
    const onRestart = vi.fn();
    render(
      <MasterHeader
        pid={null}
        sessionId="master_001"
        status="connected"
        onRestart={onRestart}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /restart/i }));
    expect(onRestart).toHaveBeenCalledOnce();
  });

  it('fires onMinimize when Min button is clicked', () => {
    const onMinimize = vi.fn();
    render(
      <MasterHeader
        pid={null}
        sessionId="master_001"
        status="connected"
        onMinimize={onMinimize}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /min/i }));
    expect(onMinimize).toHaveBeenCalledOnce();
  });

  it('renders meta line with pid when pid is provided', () => {
    render(
      <MasterHeader pid={1234} sessionId="master_001" status="connected" />,
    );
    expect(screen.getByText(/pid 1234/)).toBeInTheDocument();
  });

  it('renders meta line with em-dash when pid is null', () => {
    render(
      <MasterHeader pid={null} sessionId="master_001" status="connected" />,
    );
    expect(screen.getByText(/pid —/)).toBeInTheDocument();
  });
});
