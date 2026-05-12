import type { WsEvent } from './events';
import type { WsState } from '../stores/wsConnection';

export type WsConnection = { disconnect: () => void };

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function connectWs(
  onEvent: (event: WsEvent) => void,
  onStateChange?: (s: WsState) => void,
): WsConnection {
  let stopped = false;
  let socket: WebSocket | null = null;
  let attempts = 0;

  function open(): void {
    if (stopped) return;
    const url = `${location.protocol.replace('http', 'ws')}//${location.host}/ws`;
    onStateChange?.('connecting');
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
      if (stopped) {
        onStateChange?.('offline');
        return;
      }
      attempts += 1;
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attempts - 1), MAX_DELAY_MS);
      onStateChange?.('reconnecting');
      setTimeout(open, delay);
    };
    socket.onopen = () => {
      attempts = 0;
      onStateChange?.('connected');
    };
  }

  open();

  return {
    disconnect: () => {
      stopped = true;
      socket?.close();
    },
  };
}
