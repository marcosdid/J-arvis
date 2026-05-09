import type { WsEvent } from './events';

export type WsConnection = { disconnect: () => void };

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function connectWs(onEvent: (event: WsEvent) => void): WsConnection {
  let stopped = false;
  let socket: WebSocket | null = null;
  let attempts = 0;

  function open(): void {
    if (stopped) return;
    const url = `${location.protocol.replace('http', 'ws')}//${location.host}/ws`;
    socket = new WebSocket(url);
    socket.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WsEvent;
        onEvent(data);
      } catch {
        // non-JSON or malformed; drop silently
      }
    };
    socket.onclose = () => {
      if (stopped) return;
      attempts += 1;
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attempts - 1), MAX_DELAY_MS);
      setTimeout(open, delay);
    };
    socket.onopen = () => { attempts = 0; };
  }

  open();

  return {
    disconnect: () => {
      stopped = true;
      socket?.close();
    },
  };
}
