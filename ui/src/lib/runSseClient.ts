/**
 * F6.i — SSE client pra `GET /api/runs/{id}/logs?service=<name>`.
 *
 * O endpoint streama `data: {service,stream,text}\n\n` por linha de log.
 * Cliente faz EventSource (auto-reconnect on browser side); cancela com
 * `close()` quando o consumer (RunLogsPanel) desmonta.
 */

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
  const url = `/api/runs/${encodeURIComponent(runId)}/logs?service=${encodeURIComponent(service)}`;
  const es = new EventSource(url);
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
  return { close: () => es.close() };
}
