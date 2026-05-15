import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { NewTaskInline } from './NewTaskInline';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
  return {
    ...actual,
    api: {
      createTask: vi.fn(),
      listTasks: vi.fn(),
      getCatalog: vi.fn(),
    },
  };
});

import { api, type Catalog } from '../../lib/api';

const emptyCatalog: Catalog = {
  version: '1',
  fallback_permission_profile: 'default',
  permission_profiles: [],
  templates: [],
};

const fullCatalog: Catalog = {
  version: '1',
  fallback_permission_profile: 'yolo',
  permission_profiles: [
    { name: 'yolo', description: 'Y', claude_args: ['--dangerously-skip-permissions'] },
    { name: 'default', description: 'D', claude_args: [] },
  ],
  templates: [
    { name: 'frontend', description: 'F', default_permission_profile: 'yolo', branch_prefix: 'feat-ui/' },
    { name: 'backend', description: 'B', default_permission_profile: 'default', branch_prefix: 'feat-be/' },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.createTask).mockResolvedValue({} as never);
  // Default: empty catalog so existing tests (which don't care about the
  // dropdown) see no <select> rendered.
  vi.mocked(api.getCatalog).mockResolvedValue(emptyCatalog);
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('NewTaskInline', () => {
  it('renders "+ add task" button initially', () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    expect(screen.getByRole('button', { name: /\+ add task/i })).toBeInTheDocument();
  });

  it('click expands into text input', async () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    expect(screen.getByPlaceholderText(/task title/i)).toBeInTheDocument();
  });

  it('typing populates input value', async () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    const input = screen.getByPlaceholderText(/task title/i) as HTMLInputElement;
    await userEvent.type(input, 'My new task');
    expect(input.value).toBe('My new task');
  });

  it('Enter submits with correct project and defaults', async () => {
    wrap(<NewTaskInline columnState="in_progress" projectId="proj-42" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    const input = screen.getByPlaceholderText(/task title/i);
    await userEvent.type(input, 'Ship it{Enter}');
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        title: 'Ship it',
        project_id: 'proj-42',
      });
    });
  });

  it('ESC collapses back to button', async () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    const input = screen.getByPlaceholderText(/task title/i);
    await userEvent.type(input, 'hello');
    fireEvent.keyDown(input, { key: 'Escape', code: 'Escape' });
    expect(screen.getByRole('button', { name: /\+ add task/i })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/task title/i)).not.toBeInTheDocument();
  });

  it('empty title does not submit', async () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    const input = screen.getByPlaceholderText(/task title/i);
    fireEvent.submit(input.closest('form')!);
    expect(api.createTask).not.toHaveBeenCalled();
  });

  it('collapses back to button after successful create', async () => {
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    const input = screen.getByPlaceholderText(/task title/i);
    await userEvent.type(input, 'A task{Enter}');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ add task/i })).toBeInTheDocument();
    });
  });

  it('renders template dropdown populated from catalog', async () => {
    vi.mocked(api.getCatalog).mockResolvedValue(fullCatalog);
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /task-template/i })).toBeInTheDocument();
    });
    const select = screen.getByRole('combobox', { name: /task-template/i });
    expect(select).toHaveDisplayValue('no template');
    // 1 placeholder + 2 catalog templates
    expect(select.querySelectorAll('option')).toHaveLength(3);
  });

  it('submits selected template along with title', async () => {
    vi.mocked(api.getCatalog).mockResolvedValue(fullCatalog);
    wrap(<NewTaskInline columnState="idea" projectId="proj-9" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /task-template/i })).toBeInTheDocument();
    });
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /task-template/i }), 'frontend');
    const input = screen.getByPlaceholderText(/task title/i);
    await userEvent.type(input, 'Build form{Enter}');
    await waitFor(() => {
      expect(api.createTask).toHaveBeenCalledWith({
        title: 'Build form',
        project_id: 'proj-9',
        template: 'frontend',
      });
    });
  });

  it('no dropdown when catalog has no templates', async () => {
    // Default mock returns emptyCatalog; nothing to render.
    wrap(<NewTaskInline columnState="idea" projectId="p1" />);
    await userEvent.click(screen.getByRole('button', { name: /\+ add task/i }));
    // Give useQuery a tick to resolve, then assert no select.
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/task title/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole('combobox', { name: /task-template/i })).not.toBeInTheDocument();
  });
});
