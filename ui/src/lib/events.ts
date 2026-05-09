export type WsEvent =
  | { type: 'session.status';   session_id: string; payload: { status: string; previous: string }; at: string }
  | { type: 'session.tool_use'; session_id: string; payload: { tool: string };                     at: string }
  | { type: 'session.stopped';  session_id: string; payload: Record<string, never>;               at: string };

export type WsHandlers = {
  [K in WsEvent['type']]?: (event: Extract<WsEvent, { type: K }>) => void;
};

export function dispatch(event: WsEvent, handlers: WsHandlers): void {
  const handler = handlers[event.type];
  if (handler) {
    (handler as (e: WsEvent) => void)(event);
  }
}
