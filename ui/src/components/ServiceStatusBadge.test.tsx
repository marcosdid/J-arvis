import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ServiceStatus } from '../lib/api';
import { ServiceStatusBadge } from './ServiceStatusBadge';

function svc(overrides: Partial<ServiceStatus> = {}): ServiceStatus {
  return {
    name: 'backend',
    state: 'ready',
    port_host: null,
    port_container: null,
    container_id: null,
    error: null,
    ...overrides,
  };
}

describe('ServiceStatusBadge', () => {
  it('renders icon + name for ready state', () => {
    render(<ServiceStatusBadge service={svc({ state: 'ready' })} />);
    const el = screen.getByText(/backend/);
    expect(el).toHaveTextContent('●');
  });

  it('renders class with state suffix', () => {
    const { container } = render(
      <ServiceStatusBadge service={svc({ state: 'failed' })} />,
    );
    const el = container.querySelector('.service-badge');
    expect(el?.className).toContain('service-badge-failed');
  });

  it('exposes data attributes for testing/styling', () => {
    const { container } = render(
      <ServiceStatusBadge service={svc({ name: 'db', state: 'building' })} />,
    );
    const el = container.querySelector('.service-badge');
    expect(el?.getAttribute('data-service-name')).toBe('db');
    expect(el?.getAttribute('data-service-state')).toBe('building');
  });

  it('shows error as title tooltip when present', () => {
    const { container } = render(
      <ServiceStatusBadge
        service={svc({ state: 'failed', error: 'connection refused' })}
      />,
    );
    const el = container.querySelector('.service-badge');
    expect(el?.getAttribute('title')).toBe('connection refused');
  });

  it('renders distinct icons for each state', () => {
    const states: ServiceStatus['state'][] = [
      'pending', 'building', 'seeding', 'ready', 'failed', 'stopping', 'stopped',
    ];
    const icons = new Set<string>();
    for (const state of states) {
      const { container, unmount } = render(
        <ServiceStatusBadge service={svc({ state })} />,
      );
      const el = container.querySelector('.service-badge');
      icons.add((el?.textContent ?? '').trim().split(' ')[0]!);
      unmount();
    }
    // Cada state tem seu próprio icon (set has 7 distinct chars)
    expect(icons.size).toBe(7);
  });
});
