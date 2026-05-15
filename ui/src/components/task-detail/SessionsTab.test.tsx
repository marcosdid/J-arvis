import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SessionsTab } from './SessionsTab';

describe('SessionsTab', () => {
  it('renders placeholder text', () => {
    render(<SessionsTab taskId="task-abc" />);
    expect(screen.getByText(/sessions list coming/i)).toBeDefined();
  });

  it('shows taskId', () => {
    render(<SessionsTab taskId="task-abc" />);
    expect(screen.getByText(/task-abc/)).toBeDefined();
  });
});
