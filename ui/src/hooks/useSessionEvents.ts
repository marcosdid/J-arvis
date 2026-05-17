import type { QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { dispatch } from '../lib/events';
import { queryKeys } from '../lib/query-keys';
import { connectWs } from '../lib/ws';
import { useWsConnectionStore } from '../stores/wsConnection';

export type WorktreeOrphanedToastEmitter = (msg: string) => void;

export type BootstrapProposedEmitter = (payload: {
  task_id: string;
  manifest_text: string;
  valid: boolean;
  errors: string[];
}) => void;

export function useSessionEvents(
  queryClient: QueryClient,
  emitToast?: WorktreeOrphanedToastEmitter,
  emitBootstrapProposed?: BootstrapProposedEmitter,
): void {
  useEffect(() => {
    const setWsState = useWsConnectionStore.getState().setState;
    const conn = connectWs((event) => {
      dispatch(event, {
        'session.started': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'session.status_changed': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'session.stopped': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'session.tool_use': (e) => {
          queryClient.invalidateQueries({
            queryKey: queryKeys.transcript(e.session_id),
          });
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
        'bootstrap.proposed': (e) => {
          if (emitBootstrapProposed) {
            emitBootstrapProposed({
              task_id: e.task_id,
              manifest_text: e.payload.manifest_text,
              valid: e.payload.valid,
              errors: e.payload.errors,
            });
          } else if (emitToast) {
            // Fallback for callers (tests, e2e) that don't wire the modal store
            emitToast('Manifesto pronto. Abra o painel da tarefa.');
          }
        },
      });
    }, setWsState);
    return () => conn.disconnect();
  }, [queryClient, emitToast, emitBootstrapProposed]);
}
