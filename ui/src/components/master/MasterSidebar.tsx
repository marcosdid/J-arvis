import { useCallback, useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

import { useWebSocketRTT } from '../../hooks/useWebSocketRTT';
import { MasterHeader } from './MasterHeader';
import { MasterFooter } from './MasterFooter';
import { QuickCommands } from './QuickCommands';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
type SystemMsg = { level: 'warn' | 'error'; message: string } | null;

const SESSION_ID = 'master_001';

export function MasterSidebar() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [wsForRtt, setWsForRtt] = useState<WebSocket | null>(null);
  const [systemMsg, setSystemMsg] = useState<SystemMsg>(null);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');

  const rtt = useWebSocketRTT(wsForRtt);

  useEffect(() => {
    const term = new Terminal({
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#030503', foreground: '#d4e4d0', cursor: '#ff10f0' },
    });
    termRef.current = term;
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
    wsRef.current = ws;
    setWsForRtt(ws);

    ws.onopen = () => setStatus('connected');
    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      setWsForRtt(null);
    };
    ws.onerror = () => setStatus('error');

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
      termRef.current = null;
      wsRef.current = null;
      setWsForRtt(null);
    };
  }, []);

  const handleInject = useCallback((command: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data: command + '\n' }));
    }
  }, []);

  const handleClear = useCallback(() => {
    termRef.current?.clear();
  }, []);

  const handleCopyId = useCallback(() => {
    navigator.clipboard?.writeText(SESSION_ID).catch(() => undefined);
  }, []);

  return (
    <aside className="flex flex-col h-full bg-bg-void border-l border-border-subtle" aria-label="master-session">
      <MasterHeader
        pid={null}
        sessionId={SESSION_ID}
        status={status}
        onClear={handleClear}
        onCopyId={handleCopyId}
      />
      <QuickCommands onInject={handleInject} />
      {systemMsg && (
        <div
          className={`px-3 py-1 text-xs ${systemMsg.level === 'error' ? 'text-semantic-error bg-semantic-error/10 error' : 'text-semantic-warn bg-semantic-warn/10 warn'}`}
          aria-label="system-msg"
        >
          {systemMsg.message}
        </div>
      )}
      <div ref={containerRef} className="flex-1 overflow-hidden" />
      <MasterFooter
        pid={null}
        rtt={rtt}
        live={status === 'connected'}
      />
    </aside>
  );
}
