import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

type SystemMsg = { level: 'warn' | 'error'; message: string } | null;

export function MasterSidebar() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [systemMsg, setSystemMsg] = useState<SystemMsg>(null);

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#1e293b', foreground: '#e2e8f0' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    if (containerRef.current) {
      term.open(containerRef.current);
      fit.fit();
    }

    if (import.meta.env.MODE !== 'production') {
      (window as unknown as { __masterTerm?: Terminal }).__masterTerm = term;
    }

    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${window.location.host}/ws/master`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'output') {
          term.write(msg.data);
        } else if (msg.type === 'system') {
          const level = msg.level === 'warn' || msg.level === 'error' ? msg.level : 'error';
          const message = typeof msg.message === 'string' ? msg.message : 'unknown system message';
          setSystemMsg({ level, message });
        }
      } catch {
        // ignore parse errors — server is the trusted source
      }
    };

    term.onData((data: string) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });
    term.onResize(({ rows, cols }: { rows: number; cols: number }) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'resize', rows, cols }));
      }
    });

    return () => {
      ws.close();
      term.dispose();
    };
  }, []);

  return (
    <aside className="master-sidebar" aria-label="master-session">
      <header>
        <h3>Claude master</h3>
        <span className="hint">compartilhado entre abas</span>
      </header>
      {systemMsg && (
        <div className={`system-msg ${systemMsg.level}`} aria-label="system-msg">
          {systemMsg.message}
        </div>
      )}
      <div ref={containerRef} className="master-term" />
    </aside>
  );
}
