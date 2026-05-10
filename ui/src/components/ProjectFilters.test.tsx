import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectFilters } from './ProjectFilters';

const projects = [
  { id: 'p1', name: 'projA', path: '/a', created_at: '' },
  { id: 'p2', name: 'projB', path: '/b', created_at: '' },
];

describe('ProjectFilters', () => {
  it('renders all projects', () => {
    render(<ProjectFilters projects={projects} active={[]} onChange={() => {}} />);
    expect(screen.getByText('projA')).toBeInTheDocument();
    expect(screen.getByText('projB')).toBeInTheDocument();
  });
  it('toggles a project on click (add)', () => {
    const onChange = vi.fn();
    render(<ProjectFilters projects={projects} active={[]} onChange={onChange} />);
    fireEvent.click(screen.getByText('projA'));
    expect(onChange).toHaveBeenCalledWith(['p1']);
  });
  it('toggles a project on click (remove)', () => {
    const onChange = vi.fn();
    render(<ProjectFilters projects={projects} active={['p1']} onChange={onChange} />);
    fireEvent.click(screen.getByText('projA'));
    expect(onChange).toHaveBeenCalledWith([]);
  });
  it('renders active highlight via class', () => {
    render(<ProjectFilters projects={projects} active={['p1']} onChange={() => {}} />);
    expect(screen.getByText('projA').className).toMatch(/active/);
    expect(screen.getByText('projB').className).not.toMatch(/active/);
  });
});
