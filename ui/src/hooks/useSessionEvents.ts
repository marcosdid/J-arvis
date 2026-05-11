import type { QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { dispatch } from '../lib/events';
import { queryKeys } from '../lib/query-keys';
import { connectWs } from '../lib/ws';

export type WorktreeOrphanedToastEmitter = (msg: string) => void;

export function useSessionEvents(
  queryClient: QueryClient,
  emitToast?: WorktreeOrphanedToastEmitter,
): void {
  useEffect(() => {
    const conn = connectWs((event) => {
      dispatch(event, {
        'session.status': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'session.stopped': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'task.created': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'task.updated': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'worktree.created': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.worktrees(e.payload.project_id),
          });
        },
        'worktree.removed': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.worktrees(e.payload.project_id),
          });
        },
        'worktree.orphaned': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.worktrees(e.payload.project_id),
          });
          if (emitToast) {
            emitToast(`Worktree não pôde ser removida: ${e.payload.path}`);
          }
        },
      });
    });
    return () => conn.disconnect();
  }, [queryClient, emitToast]);
}
