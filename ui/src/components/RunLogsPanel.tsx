import { useState } from 'react';

import { useRunLogs } from '../hooks/useRunLogs';
import type { ServiceStatus } from '../lib/api';

type Props = {
  runId: string;
  services: ServiceStatus[];
};

/**
 * F6.j — painel de logs do `RunTab`.
 *
 * Dropdown filtra por serviço (default = primeiro). `useRunLogs` mantém
 * buffer ring 500 linhas. UI mostra cada linha com prefix `[stdout]`/`[stderr]`.
 */
export function RunLogsPanel({ runId, services }: Props) {
  const [service, setService] = useState<string>(services[0]?.name ?? '');
  const lines = useRunLogs(runId, service || null);

  return (
    <div className="run-logs-panel">
      <label>
        Service:
        <select
          aria-label="run-logs-service"
          value={service}
          onChange={(e) => setService(e.target.value)}
        >
          {services.map((s) => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>
      </label>
      <pre className="run-logs-output" data-service={service}>
        {lines.length === 0 ? (
          <em>(sem logs ainda)</em>
        ) : lines.map((l, idx) => (
          <div key={idx} className={`log-line log-line-${l.stream}`}>
            [{l.stream}] {l.text}
          </div>
        ))}
      </pre>
    </div>
  );
}
