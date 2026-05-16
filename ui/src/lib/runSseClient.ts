/**
 * F6.i / F10.6 — SSE client pra `GET /api/runs/{id}/logs?service=<name>`.
 *
 * O endpoint streama `data: {service,stream,text}\n\n` por linha de log.
 * No Wails a UI é servida via `wails://`, então URLs relativas não resolvem
 * pro localhttp server — a URL absoluta vem de `api.getRunLogsEventSourceURL`
 * (que internamente consulta `RunsAPI.LocalHTTPBase()`). Resolução é async,
 * mas mantemos a API síncrona pra não vazar `Promise<SseConnection>` pros
 * consumers (useRunLogs/RunLogsPanel) — o EventSource é construído quando
 * a URL chega; `close()` é seguro chamar antes disso.
 */

import { api } from './api';

export type LogLine = {
  service: string;
  stream: 'stdout' | 'stderr';
  text: string;
};

export type SseConnection = {
  close: () => void;
};

export function createLogsSse(
  runId: string,
  service: string,
  onLine: (line: LogLine) => void,
  onError?: (e: Event) => void,
): SseConnection {
  let es: EventSource | null = null;
  let closed = false;

  void api.getRunLogsEventSourceURL(runId, service).then((url) => {
    if (closed) return;
    es = new EventSource(url);
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as {
          service: string;
          stream: 'stdout' | 'stderr';
          text: string;
        };
        onLine(data);
      } catch {
        // Linha malformada (servidor enviou algo não-JSON) — ignora.
      }
    };
    if (onError) {
      es.onerror = onError;
    }
  });

  return {
    close: () => {
      closed = true;
      es?.close();
    },
  };
}
