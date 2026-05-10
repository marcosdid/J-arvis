import { describe, expect, it } from 'vitest';

import { queryKeys } from './query-keys';

describe('queryKeys', () => {
  it('projects is a stable tuple', () => {
    expect(queryKeys.projects).toEqual(['projects']);
  });

  it('worktrees encodes the project id in the key', () => {
    expect(queryKeys.worktrees('abc')).toEqual(['worktrees', 'abc']);
  });

  it('sessions is a stable tuple', () => {
    expect(queryKeys.sessions).toEqual(['sessions']);
  });

  it('tasks is a stable tuple', () => {
    expect(queryKeys.tasks).toEqual(['tasks']);
  });

  it('tasksForProject encodes the project ids in the key', () => {
    expect(queryKeys.tasksForProject('p1,p2')).toEqual(['tasks', { projectId: 'p1,p2' }]);
  });
});
