import { useEffect, useRef, useState } from 'react';

export function useWebSocketRTT(ws: WebSocket | null): number | null {
  const [rtt, setRtt] = useState<number | null>(null);
  const inflightRef = useRef<number | null>(null);

  useEffect(() => {
    if (!ws) return;

    const handler = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'pong' && typeof msg.ts === 'number' && msg.ts === inflightRef.current) {
          setRtt(Date.now() - msg.ts);
          inflightRef.current = null;
        }
      } catch { /* ignore */ }
    };
    ws.addEventListener('message', handler);

    const interval = setInterval(() => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const ts = Date.now();
      inflightRef.current = ts;
      ws.send(JSON.stringify({ type: 'ping', ts }));
    }, 1000);

    return () => {
      clearInterval(interval);
      ws.removeEventListener('message', handler);
    };
  }, [ws]);

  return rtt;
}
