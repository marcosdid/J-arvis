export type WsEvent =
  | {
      type: 'session.status'; session_id: string; task_id: string | null;
      payload: { status: string; previous: string }; at: string;
    }
  | {
      type: 'session.tool_use'; session_id: string; task_id: string | null;
      payload: { tool: string }; at: string;
    }
  | {
      type: 'session.stopped'; session_id: string; task_id: string | null;
      payload: Record<string, never>; at: string;
    }
  | {
      type: 'task.created'; session_id: ''; task_id: string;
      payload: { project_id: string; title: string; state: string }; at: string;
    }
  | {
      type: 'task.updated'; session_id: ''; task_id: string;
      payload: {
        project_id: string; title: string;
        state: string; previous_state: string | null;
      }; at: string;
    }
  | {
      type: 'worktree.created'; session_id: ''; task_id: string | null;
      payload: {
        project_id: string; repository_id: string; worktree_id: string;
        path: string; branch: string | null;
      }; at: string;
    }
  | {
      type: 'worktree.removed'; session_id: ''; task_id: string | null;
      payload: {
        project_id: string; worktree_id: string; path: string;
      }; at: string;
    }
  | {
      type: 'worktree.orphaned'; session_id: ''; task_id: string | null;
      payload: {
        project_id: string; worktree_id: string; path: string; reason: string;
      }; at: string;
    }
  | {
      type: 'run.status'; session_id: ''; task_id: string;
      payload: {
        run_id: string;
        status:
          | 'pending' | 'building' | 'seeding' | 'ready'
          | 'failed' | 'stopping' | 'stopped';
        services: Array<{
          name: string;
          state: string;
          port_host: number | null;
          port_container: number | null;
          container_id: string | null;
          error: string | null;
        }>;
      }; at: string;
    }
  | {
      type: 'run.failed'; session_id: ''; task_id: string;
      payload: { run_id: string; service: string | null; error: string };
      at: string;
    }
  | {
      type: 'run.stopped'; session_id: ''; task_id: string;
      payload: {
        run_id: string;
        reason: 'manual' | 'session_stopped' | 'task_terminal';
      }; at: string;
    }
  | {
      type: 'bootstrap.proposed'; session_id: ''; task_id: null;
      payload: { manifest_text: string }; at: string;
    };

export type WsHandlers = {
  [K in WsEvent['type']]?: (event: Extract<WsEvent, { type: K }>) => void;
};

export function dispatch(event: WsEvent, handlers: WsHandlers): void {
  const handler = handlers[event.type];
  if (handler) {
    (handler as (e: WsEvent) => void)(event);
  }
}
