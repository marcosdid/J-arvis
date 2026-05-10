import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { NewTaskForm } from './NewTaskForm';

const projects = [{ id: 'p1', name: 'projA', path: '/p', created_at: '', repositories: [] }];

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      createTask: vi.fn(),
    },
  };
});

import { api } from '../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.createTask).mockResolvedValue({} as never);
});

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe('NewTaskForm', () => {
  it('disables submit when title is blank', () => {
    wrap(<NewTaskForm projects={projects} />);
    expect(screen.getByRole('button', { name: /criar/i })).toBeDisabled();
  });

  it('calls createTask on submit', async () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        project_id: 'p1', title: 'A', description: '',
      });
    });
  });

  it('rejects whitespace-only title', () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: '   ' } });
    expect(screen.getByRole('button', { name: /criar/i })).toBeDisabled();
  });

  it('clears form after successful create', async () => {
    wrap(<NewTaskForm projects={projects} />);
    const titleInput = screen.getByLabelText(/título/i) as HTMLInputElement;
    fireEvent.change(titleInput, { target: { value: 'A' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => expect(titleInput.value).toBe(''));
  });
});
