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
