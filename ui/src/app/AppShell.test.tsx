import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AppShell } from './AppShell';

vi.mock('@/components/hud/HudTopBar', () => ({
  HudTopBar: ({ wsRtt }: { wsRtt: number | null }) => (
    <div data-testid="mock-hud-top-bar">{wsRtt ?? 'null'}</div>
  ),
}));

vi.mock('@/components/header/AppHeader', () => ({
  AppHeader: ({
    projectsCount,
    tasksCount,
    activeCount,
  }: {
    projectsCount: number;
    tasksCount: number;
    activeCount: number;
  }) => (
    <div data-testid="mock-app-header">
      {projectsCount}/{tasksCount}/{activeCount}
    </div>
  ),
}));

vi.mock('@/components/status/StatusBar', () => ({
  StatusBar: () => <div data-testid="mock-status-bar" />,
}));

vi.mock('@/components/status/ErrorBanner', () => ({
  ErrorBanner: () => <div data-testid="mock-error-banner" />,
}));

const defaultProps = {
  projectsCount: 3,
  tasksCount: 10,
  activeCount: 2,
  wsRtt: null,
};

describe('AppShell', () => {
  it('renders HudTopBar', () => {
    render(<AppShell {...defaultProps}>content</AppShell>);
    expect(screen.getByTestId('mock-hud-top-bar')).toBeInTheDocument();
  });

  it('renders AppHeader', () => {
    render(<AppShell {...defaultProps}>content</AppShell>);
    expect(screen.getByTestId('mock-app-header')).toBeInTheDocument();
  });

  it('renders children inside main', () => {
    render(
      <AppShell {...defaultProps}>
        <span data-testid="child-node">hello</span>
      </AppShell>,
    );
    const main = screen.getByRole('main');
    expect(main).toContainElement(screen.getByTestId('child-node'));
  });

  it('renders StatusBar at the bottom of the kanban column', () => {
    render(<AppShell {...defaultProps}>content</AppShell>);
    expect(screen.getByTestId('mock-status-bar')).toBeInTheDocument();
  });

  it('passes wsRtt to HudTopBar', () => {
    render(<AppShell {...defaultProps} wsRtt={42}>content</AppShell>);
    expect(screen.getByTestId('mock-hud-top-bar')).toHaveTextContent('42');
  });

  it('passes projectsCount/tasksCount/activeCount to AppHeader', () => {
    render(
      <AppShell {...defaultProps} projectsCount={5} tasksCount={20} activeCount={7}>
        content
      </AppShell>,
    );
    expect(screen.getByTestId('mock-app-header')).toHaveTextContent('5/20/7');
  });

  it('renders null wsRtt as fallback text in HudTopBar', () => {
    render(<AppShell {...defaultProps} wsRtt={null}>content</AppShell>);
    expect(screen.getByTestId('mock-hud-top-bar')).toHaveTextContent('null');
  });

  it('renders ErrorBanner between HudTopBar and AppHeader', () => {
    render(<AppShell {...defaultProps}>content</AppShell>);
    expect(screen.getByTestId('mock-error-banner')).toBeInTheDocument();
  });

  it('uses h-screen on its root so its grid rows (including StatusBar) anchor to the viewport', () => {
    // AppShell sits in App.tsx's grid-cols-[1fr_360px] alongside MasterSidebar.
    // Both columns are 100vh tall, but `h-full` on a grid item with min-h-0
    // can collapse below the track in WebKit. Explicit h-screen forces 100vh
    // so the StatusBar (the last grid row) sticks to the bottom of the viewport.
    const { container } = render(<AppShell {...defaultProps}>content</AppShell>);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/\bh-screen\b/);
  });
});
