import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LogsTab } from './LogsTab';

describe('LogsTab', () => {
  it('renders placeholder text', () => {
    render(<LogsTab taskId="task-123" />);
    expect(screen.getByText(/logs streaming coming soon/i)).toBeDefined();
  });

  it('shows taskId', () => {
    render(<LogsTab taskId="task-123" />);
    expect(screen.getByText(/task-123/)).toBeDefined();
  });
});
