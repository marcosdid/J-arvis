import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuickCommands } from './QuickCommands';

describe('QuickCommands', () => {
  it('renders all 5 chip buttons', () => {
    render(<QuickCommands onInject={vi.fn()} />);
    expect(screen.getByRole('button', { name: /list tasks/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create task/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /update state/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /show doing/i })).toBeInTheDocument();
  });

  it('clicking "list tasks" fires onInject with j-arvis list_tasks', () => {
    const onInject = vi.fn();
    render(<QuickCommands onInject={onInject} />);
    fireEvent.click(screen.getByRole('button', { name: /list tasks/i }));
    expect(onInject).toHaveBeenCalledWith('j-arvis list_tasks');
  });

  it('clicking "create task" fires onInject with j-arvis create_task ', () => {
    const onInject = vi.fn();
    render(<QuickCommands onInject={onInject} />);
    fireEvent.click(screen.getByRole('button', { name: /create task/i }));
    expect(onInject).toHaveBeenCalledWith('j-arvis create_task ');
  });

  it('clicking "update state" fires onInject with j-arvis update_state ', () => {
    const onInject = vi.fn();
    render(<QuickCommands onInject={onInject} />);
    fireEvent.click(screen.getByRole('button', { name: /update state/i }));
    expect(onInject).toHaveBeenCalledWith('j-arvis update_state ');
  });

  it('clicking "discard" fires onInject with j-arvis discard ', () => {
    const onInject = vi.fn();
    render(<QuickCommands onInject={onInject} />);
    fireEvent.click(screen.getByRole('button', { name: /discard/i }));
    expect(onInject).toHaveBeenCalledWith('j-arvis discard ');
  });

  it('clicking "show doing" fires onInject with j-arvis list_tasks state=in_progress', () => {
    const onInject = vi.fn();
    render(<QuickCommands onInject={onInject} />);
    fireEvent.click(screen.getByRole('button', { name: /show doing/i }));
    expect(onInject).toHaveBeenCalledWith('j-arvis list_tasks state=in_progress');
  });

  it('renders exactly 5 buttons', () => {
    render(<QuickCommands onInject={vi.fn()} />);
    expect(screen.getAllByRole('button')).toHaveLength(5);
  });
});
