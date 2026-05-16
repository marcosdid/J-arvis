import { useCallback, useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

import { MasterHeader } from './MasterHeader';
import { MasterFooter } from './MasterFooter';
import { QuickCommands } from './QuickCommands';
import * as MasterAPI from '../../wailsjs/go/api/MasterAPI';
import { EventsOn, EventsOff } from '../../wailsjs/runtime/runtime';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
type SystemMsg = { level: 'warn' | 'error'; message: string } | null;

export function MasterSidebar() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const [systemMsg, setSystemMsg] = useState<SystemMsg>(null);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [pid, setPid] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string>('');

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const term = new Terminal({
      fontSize: 13,
      fontFamily: 'monospace',
      theme: { background: '#030503', foreground: '#d4e4d0', cursor: '#ff10f0' },
    });
    termRef.current = term;
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(container);

    let disposed = false;
    const safeFit = (): void => {
      if (disposed) return;
      if (container.offsetWidth === 0) return;
      fit.fit();
      const dims = (fit as unknown as { proposeDimensions?: () => { rows: number; cols: number } | undefined }).proposeDimensions?.();
      if (dims) {
        MasterAPI.Resize(dims.rows, dims.cols).catch(() => undefined);
      }
    };

    requestAnimationFrame(safeFit);
    const resizeObserver = new ResizeObserver(safeFit);
    resizeObserver.observe(container);

    if (import.meta.env.MODE !== 'production') {
      (window as unknown as { __masterTerm?: Terminal }).__masterTerm = term;
    }

    EventsOn('master.output', (chunk: unknown) => {
      if (typeof chunk === 'string') {
        term.write(chunk);
      }
    });
    EventsOn('master.status', (s: unknown) => {
      const obj = s as { running?: boolean; pid?: number; session_id?: string };
      if (obj?.session_id) setSessionId(obj.session_id);
      if (obj?.running) {
        setStatus('connected');
        setPid(typeof obj.pid === 'number' ? obj.pid : null);
      } else {
        setStatus('disconnected');
        setPid(null);
      }
    });
    EventsOn('master.exit', (payload: unknown) => {
      const obj = payload as {
        early_exit?: boolean;
        elapsed_ms?: number;
        error?: string;
        session_id?: string;
      };
      if (obj?.early_exit) {
        setSystemMsg({
          level: 'warn',
          message: `master crashed after ${obj.elapsed_ms ?? '?'}ms — recovering...`,
        });
        MasterAPI.Start()
          .then((st) => {
            setSessionId(st.session_id);
            setStatus('connected');
            setPid(st.pid);
            term.write('\x1b[2m-- recovered with new session --\x1b[0m\r\n');
          })
          .catch((e: unknown) => {
            const msg = e instanceof Error ? e.message : String(e);
            setSystemMsg({ level: 'error', message: `recovery failed: ${msg}` });
          });
      } else {
        const ms = obj?.elapsed_ms !== undefined ? `${obj.elapsed_ms}ms` : '?';
        const err = obj?.error ? `: ${obj.error}` : '';
        setSystemMsg({ level: 'error', message: `master exited (${ms})${err}` });
        setStatus('disconnected');
        setPid(null);
      }
    });

    MasterAPI.Start()
      .then((st) => {
        setSessionId(st.session_id);
        setStatus(st.running ? 'connected' : 'disconnected');
        setPid(st.running ? st.pid : null);
        if (st.running) {
          term.write('\x1b[2m-- claude session started --\x1b[0m\r\n');
        }
      })
      .catch((err: unknown) => {
        setStatus('error');
        const msg = err instanceof Error ? err.message : String(err);
        setSystemMsg({ level: 'error', message: `start failed: ${msg}` });
        term.write(`\x1b[31m-- failed to start claude: ${msg} --\x1b[0m\r\n`);
      });

    term.onData((data: string) => {
      MasterAPI.Send(data).catch(() => undefined);
    });

    return () => {
      disposed = true;
      resizeObserver.disconnect();
      EventsOff('master.output');
      EventsOff('master.status');
      EventsOff('master.exit');
      MasterAPI.Stop().catch(() => undefined);
      term.dispose();
      termRef.current = null;
    };
  }, []);

  const handleInject = useCallback((command: string) => {
    MasterAPI.Send(command + '\n').catch(() => undefined);
  }, []);

  const handleClear = useCallback(() => {
    termRef.current?.clear();
  }, []);

  const handleCopyId = useCallback(() => {
    navigator.clipboard?.writeText(sessionId).catch(() => undefined);
  }, [sessionId]);

  return (
    <aside className="flex flex-col h-full bg-bg-void border-l border-border-subtle" aria-label="master-session">
      <MasterHeader
        pid={pid}
        sessionId={sessionId}
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
        pid={pid}
        rtt={null}
        live={status === 'connected'}
      />
    </aside>
  );
}
