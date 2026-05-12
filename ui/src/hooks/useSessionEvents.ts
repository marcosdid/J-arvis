import type { QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { dispatch } from '../lib/events';
import { queryKeys } from '../lib/query-keys';
import { connectWs } from '../lib/ws';
import { useWsConnectionStore } from '../stores/wsConnection';

export type WorktreeOrphanedToastEmitter = (msg: string) => void;

export function useSessionEvents(
  queryClient: QueryClient,
  emitToast?: WorktreeOrphanedToastEmitter,
): void {
  useEffect(() => {
    const setWsState = useWsConnectionStore.getState().setState;
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
        'run.status': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.run(e.task_id),
          });
        },
        'run.failed': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.run(e.task_id),
          });
          if (emitToast) {
            const svc = e.payload.service ? ` (${e.payload.service})` : '';
            emitToast(`Run falhou${svc}: ${e.payload.error}`);
          }
        },
        'run.stopped': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.run(e.task_id),
          });
        },
        'bootstrap.proposed': () => {
          if (emitToast) {
            emitToast('Manifesto pronto. Tente Run de novo.');
          }
        },
      });
    }, setWsState);
    return () => conn.disconnect();
  }, [queryClient, emitToast]);
}
