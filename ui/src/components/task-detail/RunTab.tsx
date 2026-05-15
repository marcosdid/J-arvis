import { useState } from 'react';

import { useRun, useStartRun, useStopRun } from '../../hooks/useRun';
import { BootstrapModal } from '../dialogs/BootstrapModal';
import { RunLogsPanel } from '../RunLogsPanel';
import { ServiceStatusBadge } from '../ServiceStatusBadge';

type Props = { taskId: string };

/**
 * F6.j — aba "Run" do TaskDetailSheet.
 *
 * Visão expandida da run da task: badge per-service + URLs clicáveis +
 * painel de logs streamados via SSE. Quando não há run ativa, expõe
 * botão `▶ Run` (idem ao card); 422 `manifest_missing` abre `BootstrapModal`.
 */
export function RunTab({ taskId }: Props) {
  const run = useRun(taskId);
  const startRun = useStartRun(taskId);
  const stopRun = useStopRun(taskId);
  const [bootstrapOpen, setBootstrapOpen] = useState(false);

  const onStart = () => {
    startRun.mutate(undefined, {
      onError: (err) => {
        const msg = (err as Error).message ?? '';
        if (msg.includes('manifest_missing')) {
          setBootstrapOpen(true);
        }
      },
    });
  };

  if (run.isLoading || !run.isFetched) {
    return <div className="run-tab" data-loading="true">Carregando…</div>;
  }
  const data = run.data;
  if (!data) {
    return (
      <div className="run-tab" data-status="idle">
        <p>Nenhuma run ativa.</p>
        <button
          type="button"
          onClick={onStart}
          disabled={startRun.isPending}
          aria-label="run-tab-start"
        >
          ▶ Run
        </button>
        {bootstrapOpen && (
          <BootstrapModal
            taskId={taskId}
            onClose={() => setBootstrapOpen(false)}
          />
        )}
      </div>
    );
  }

  const exposed = data.services.filter((s) => s.port_host !== null);

  return (
    <div className="run-tab" data-status={data.status}>
      <header className="run-tab-header">
        <strong>Status: {data.status}</strong>
        {data.status !== 'stopped' && data.status !== 'failed' && (
          <button
            type="button"
            onClick={() => stopRun.mutate(data.id)}
            disabled={stopRun.isPending}
            aria-label="run-tab-stop"
          >
            ⏹ Stop
          </button>
        )}
        {(data.status === 'stopped' || data.status === 'failed') && (
          <button
            type="button"
            onClick={onStart}
            disabled={startRun.isPending}
            aria-label="run-tab-restart"
          >
            ▶ Run
          </button>
        )}
      </header>

      {data.error_message && (
        <p role="alert" className="run-tab-error">{data.error_message}</p>
      )}

      <ul className="run-tab-services">
        {data.services.map((s) => (
          <li key={s.name}>
            <ServiceStatusBadge service={s} />
            {s.port_host !== null && (
              <a
                href={`http://localhost:${s.port_host}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                🌐 :{s.port_host}
              </a>
            )}
          </li>
        ))}
      </ul>

      {exposed.length > 0 && (
        <RunLogsPanel runId={data.id} services={data.services} />
      )}
    </div>
  );
}
