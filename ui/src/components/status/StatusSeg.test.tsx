import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { StatusSeg } from './StatusSeg';

describe('StatusSeg', () => {
  it('renders label and value', () => {
    render(<StatusSeg label="branch" value="main" />);
    expect(screen.getByText('branch')).toBeDefined();
    expect(screen.getByText('main')).toBeDefined();
  });

  it('derives data-testid from label', () => {
    render(<StatusSeg label="env" value="prod" />);
    expect(screen.getByTestId('status-seg-env')).toBeDefined();
  });

  it('default tone applies text-accent-primary to value span', () => {
    const { container } = render(<StatusSeg label="mode" value="dark" />);
    const valueSpan = container.querySelector('.text-accent-primary');
    expect(valueSpan).not.toBeNull();
    expect(valueSpan?.textContent).toBe('dark');
  });

  it('warn tone applies text-semantic-warn to value span', () => {
    const { container } = render(<StatusSeg label="cpu" value="92%" tone="warn" />);
    const valueSpan = container.querySelector('.text-semantic-warn');
    expect(valueSpan).not.toBeNull();
    expect(valueSpan?.textContent).toBe('92%');
  });

  it('error tone applies text-accent-attn to value span', () => {
    const { container } = render(<StatusSeg label="status" value="down" tone="error" />);
    const valueSpan = container.querySelector('.text-accent-attn');
    expect(valueSpan).not.toBeNull();
    expect(valueSpan?.textContent).toBe('down');
  });

  it('all tones share text-text-subtle on the label span', () => {
    const tones = ['default', 'warn', 'error'] as const;
    for (const tone of tones) {
      const { container, unmount } = render(
        <StatusSeg label="lbl" value="val" tone={tone} />,
      );
      const labelSpan = container.querySelector('.text-text-subtle');
      expect(labelSpan).not.toBeNull();
      expect(labelSpan?.textContent).toBe('lbl');
      unmount();
    }
  });

  it('renders as an inline-flex span wrapper', () => {
    const { container } = render(<StatusSeg label="x" value="y" />);
    const wrapper = container.querySelector('.inline-flex');
    expect(wrapper?.tagName.toLowerCase()).toBe('span');
  });
});
