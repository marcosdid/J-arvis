import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AppHeader } from './AppHeader';

function fireKey(key: string) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key }));
}

const defaultProps = {
  projectsCount: 3,
  tasksCount: 12,
  activeCount: 2,
};

describe('AppHeader', () => {
  it('renders BrandMark (j-arvis text)', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByText(/j-arvis/i)).toBeInTheDocument();
  });

  it('renders projectsCount', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders tasksCount', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('renders activeCount', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('renders filter button', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByRole('button', { name: /filter/i })).toBeInTheDocument();
  });

  it('renders projects button', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByRole('button', { name: /projects/i })).toBeInTheDocument();
  });

  it('renders run button', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
  });

  it('renders new task button', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByRole('button', { name: /new task/i })).toBeInTheDocument();
  });

  it('run button is disabled', () => {
    render(<AppHeader {...defaultProps} />);
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled();
  });

  it('keyboard / triggers onFilter', () => {
    const onFilter = vi.fn();
    render(<AppHeader {...defaultProps} onFilter={onFilter} />);
    fireKey('/');
    expect(onFilter).toHaveBeenCalledTimes(1);
  });

  it('keyboard p triggers onToggleProjects', () => {
    const onToggleProjects = vi.fn();
    render(<AppHeader {...defaultProps} onToggleProjects={onToggleProjects} />);
    fireKey('p');
    expect(onToggleProjects).toHaveBeenCalledTimes(1);
  });

  it('keyboard n triggers onNewTask', () => {
    const onNewTask = vi.fn();
    render(<AppHeader {...defaultProps} onNewTask={onNewTask} />);
    fireKey('n');
    expect(onNewTask).toHaveBeenCalledTimes(1);
  });

  it('keyboard r does not crash (registered as no-op)', () => {
    render(<AppHeader {...defaultProps} />);
    expect(() => fireKey('r')).not.toThrow();
  });

  it('click filter button triggers onFilter', async () => {
    const onFilter = vi.fn();
    render(<AppHeader {...defaultProps} onFilter={onFilter} />);
    await userEvent.click(screen.getByRole('button', { name: /filter/i }));
    expect(onFilter).toHaveBeenCalledTimes(1);
  });

  it('click projects button triggers onToggleProjects', async () => {
    const onToggleProjects = vi.fn();
    render(<AppHeader {...defaultProps} onToggleProjects={onToggleProjects} />);
    await userEvent.click(screen.getByRole('button', { name: /projects/i }));
    expect(onToggleProjects).toHaveBeenCalledTimes(1);
  });

  it('click new task button triggers onNewTask', async () => {
    const onNewTask = vi.fn();
    render(<AppHeader {...defaultProps} onNewTask={onNewTask} />);
    await userEvent.click(screen.getByRole('button', { name: /new task/i }));
    expect(onNewTask).toHaveBeenCalledTimes(1);
  });

  it('click run button does not trigger any handler (disabled)', async () => {
    const onFilter = vi.fn();
    render(<AppHeader {...defaultProps} onFilter={onFilter} />);
    const runBtn = screen.getByRole('button', { name: /run/i });
    await userEvent.click(runBtn);
    expect(onFilter).not.toHaveBeenCalled();
  });
});
