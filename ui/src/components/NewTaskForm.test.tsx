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

  it('calls createTask on submit (no branch → undefined)', async () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        project_id: 'p1', title: 'A', description: '', branch: undefined,
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

  it('Avançado <details> is collapsed by default', () => {
    wrap(<NewTaskForm projects={projects} />);
    const details = screen.getByText('Avançado').closest('details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
  });

  it('branch placeholder reflects slug preview from title', () => {
    wrap(<NewTaskForm projects={projects} />);
    const titleInput = screen.getByLabelText(/título/i);
    fireEvent.change(titleInput, { target: { value: 'Refactor Login Flow' } });
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    expect(branchInput.placeholder).toBe('refactor-login-flow');
  });

  it('branch placeholder falls back to "auto-slug do título" when title empty', () => {
    wrap(<NewTaskForm projects={projects} />);
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    expect(branchInput.placeholder).toBe('auto-slug do título');
  });

  it('branch placeholder falls back when title only punctuation', () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: '!!!' } });
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    expect(branchInput.placeholder).toBe('auto-slug do título');
  });

  it('submitting with non-empty branch passes it to mutation', async () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText(/task-branch/i), {
      target: { value: 'feature/jira-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        project_id: 'p1', title: 'A', description: '',
        branch: 'feature/jira-123',
      });
    });
  });

  it('submitting without touching branch omits the field from the payload', async () => {
    // The branch input is optional; not touching it (empty string default)
    // should send a payload without a `branch` key. (Whitespace values are
    // blocked at the HTML5 pattern layer, so we cover the realistic flow:
    // user types title + project, leaves Avançado collapsed, clicks Criar.)
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        project_id: 'p1', title: 'A', description: '',
      });
    });
  });

  it('submitting with valid branch sends branch in the payload', async () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    fireEvent.change(screen.getByLabelText(/task-branch/i), {
      target: { value: 'feature/jira-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        project_id: 'p1', title: 'A', description: '',
        branch: 'feature/jira-123',
      });
    });
  });

  it('branch input has pattern attribute for browser-level validation', () => {
    wrap(<NewTaskForm projects={projects} />);
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    expect(branchInput.pattern).toBe('^[a-z0-9][a-z0-9._/-]*$');
    expect(branchInput.maxLength).toBe(200);
  });

  it('branch input pattern rejects invalid input ("Bad Branch")', () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    fireEvent.change(branchInput, { target: { value: 'Bad Branch' } });
    expect(branchInput.validity.valid).toBe(false);
  });

  it('branch input pattern accepts valid slug', () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    fireEvent.change(branchInput, { target: { value: 'feature/jira-123' } });
    expect(branchInput.validity.valid).toBe(true);
  });

  it('clears branch field after successful create', async () => {
    wrap(<NewTaskForm projects={projects} />);
    fireEvent.change(screen.getByLabelText(/título/i), { target: { value: 'A' } });
    const branchInput = screen.getByLabelText(/task-branch/i) as HTMLInputElement;
    fireEvent.change(branchInput, { target: { value: 'my-branch' } });
    fireEvent.click(screen.getByRole('button', { name: /criar/i }));
    await waitFor(() => expect(branchInput.value).toBe(''));
  });
});
