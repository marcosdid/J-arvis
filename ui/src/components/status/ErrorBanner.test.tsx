import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WsState } from '@/stores/wsConnection';
import { ErrorBanner } from './ErrorBanner';

vi.mock('@/stores/wsConnection');

import { useWsConnectionStore } from '@/stores/wsConnection';

function mockWs(state: WsState) {
  vi.mocked(useWsConnectionStore).mockImplementation(
    (selector: (s: { state: WsState; setState: () => void }) => unknown) =>
      selector({ state, setState: vi.fn() }),
  );
}

beforeEach(() => {
  mockWs('connected');
});

describe('ErrorBanner', () => {
  it('renders nothing when state is connected', () => {
    mockWs('connected');
    const { container } = render(<ErrorBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders reconnecting message with warn tone when state is reconnecting', () => {
    mockWs('reconnecting');
    render(<ErrorBanner />);
    const banner = screen.getByTestId('error-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent('Connection lost — reconnecting...');
    expect(banner.className).toContain('semantic-warn');
  });

  it('renders offline message with error tone when state is offline', () => {
    mockWs('offline');
    render(<ErrorBanner />);
    const banner = screen.getByTestId('error-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent('Offline — backend unreachable');
    expect(banner.className).toContain('sem-error');
  });

  it('renders connecting message when state is connecting', () => {
    mockWs('connecting');
    render(<ErrorBanner />);
    const banner = screen.getByTestId('error-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent('Connecting...');
  });

  it('has role=alert for accessibility', () => {
    mockWs('offline');
    render(<ErrorBanner />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
