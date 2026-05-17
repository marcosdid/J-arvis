import { useMemo, useState } from 'react';

import { useRun, useStartRun, useStopRun } from '../hooks/useRun';
import { useBootstrapProposedStore } from '../stores/bootstrapProposed';
import { BootstrapModal } from './dialogs/BootstrapModal';

type Props = { taskId: string };

/**
 * F6.j / F10.6 — rodapé do TaskCard mostrando estado da Run.
 *
 * Estados:
 * - `useRun.data === null` (sem run ativa): botão `▶ Run`.
 * - status pending/building/seeding/stopping: spinner-text com status.
 * - status ready: chips clicáveis (1 por service exposto) + `⏹ Stop`.
 * - status failed: `✗ Falha` + botão pra abrir logs/modal.
 *
 * Quando `startRun` retorna `{run:null, bootstrap:{reason:'manifest_missing'}}`,
 * abre `BootstrapModal`. Erros de verdade caem em `onError` (não abrem modal).
 */
export function RunStatus({ taskId }: Props) {
  const run = useRun(taskId);
  const startRun = useStartRun(taskId);
  const stopRun = useStopRun(taskId);
  const [bootstrapOpen, setBootstrapOpen] = useState(false);
  const lastProposed = useBootstrapProposedStore((s) => s.last);
  // Memoized by lastProposed reference. The store wraps each emit in a
  // fresh object, so this changes identity once per emit (not per render),
  // which is exactly what BootstrapModal's useEffect on `proposed` expects.
  const proposedForTask = useMemo(() => {
    if (!lastProposed || lastProposed.task_id !== taskId) return null;
    return {
      manifest_text: lastProposed.manifest_text,
      valid: lastProposed.valid,
      errors: lastProposed.errors,
    };
  }, [lastProposed, taskId]);

  const onStart = () => {
    startRun.mutate(undefined, {
      onSuccess: (result) => {
        if (result.bootstrap?.reason === 'manifest_missing') {
          setBootstrapOpen(true);
        }
        // result.run != null → normal flow; the useRun query will refetch
        // (already wired in useStartRun.onSuccess).
      },
    });
  };

  if (run.isLoading || !run.isFetched) {
    return <div className="run-status" data-loading="true">…</div>;
  }
  const data = run.data;
  if (!data) {
    return (
      <div className="run-status" data-status="idle">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onStart(); }}
          disabled={startRun.isPending}
          aria-label={`run-start-${taskId}`}
        >
          ▶ Run
        </button>
        {bootstrapOpen && (
          <BootstrapModal
            taskId={taskId}
            onClose={() => setBootstrapOpen(false)}
            proposed={proposedForTask}
          />
        )}
      </div>
    );
  }

  const isActive = !['stopped', 'failed'].includes(data.status);
  const exposed = data.services.filter((s) => s.port_host !== null);

  return (
    <div className="run-status" data-status={data.status}>
      {data.status === 'ready' ? (
        <>
          <span className="run-label">● ready</span>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); stopRun.mutate(data.id); }}
            disabled={stopRun.isPending}
            aria-label={`run-stop-${taskId}`}
          >
            ⏹ Stop
          </button>
          {exposed.map((s) => (
            <a
              key={s.name}
              className="run-url"
              href={`http://localhost:${s.port_host}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              🌐 {s.name} :{s.port_host}
            </a>
          ))}
        </>
      ) : data.status === 'failed' ? (
        <span className="run-label run-failed">
          ✗ {data.error_message ?? 'falha'}
        </span>
      ) : isActive ? (
        <span className="run-label run-busy">
          {data.status === 'building' ? '◐ building'
            : data.status === 'seeding' ? '◑ seeding'
              : data.status === 'stopping' ? '◯ stopping'
                : '· pending'}
        </span>
      ) : (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onStart(); }}
          disabled={startRun.isPending}
          aria-label={`run-restart-${taskId}`}
        >
          ▶ Run
        </button>
      )}
    </div>
  );
}
