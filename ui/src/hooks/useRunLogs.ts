import { useEffect, useState } from 'react';

import { createLogsSse, type LogLine } from '../lib/runSseClient';

const BUFFER_MAX = 500;

/**
 * F6.i — consumer SSE de `/api/runs/{id}/logs?service=<name>`.
 *
 * Buffer ring fixo (`BUFFER_MAX = 500` linhas) pra não vazar memória em
 * runs longas. Quando `runId` ou `service` mudam, fecha o EventSource
 * anterior e abre novo.
 */
export function useRunLogs(runId: string | null, service: string | null): LogLine[] {
  const [lines, setLines] = useState<LogLine[]>([]);

  useEffect(() => {
    if (!runId || !service) {
      setLines([]);
      return undefined;
    }
    setLines([]);
    const conn = createLogsSse(runId, service, (line) => {
      setLines((prev) => {
        const next = [...prev, line];
        if (next.length > BUFFER_MAX) {
          return next.slice(next.length - BUFFER_MAX);
        }
        return next;
      });
    });
    return () => conn.close();
  }, [runId, service]);

  return lines;
}
