import { useEffect, useRef, useState } from 'react';

import { useBootstrapManifest, useCancelBootstrap, useStartRun } from '../../hooks/useRun';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

type Phase = 'idle' | 'starting' | 'waiting' | 'preview-valid' | 'preview-invalid';

export type BootstrapProposed = {
  manifest_text: string;
  valid: boolean;
  errors: string[];
};

type Props = {
  taskId: string;
  onClose: () => void;
  // External signal: parent subscribes to bootstrap.proposed via
  // useSessionEvents/store and forwards the filtered-by-taskId payload here.
  // The parent MUST pass a fresh object reference on each emit so this
  // component's useEffect re-fires.
  proposed?: BootstrapProposed | null;
};

const AUTO_FIRE_MS = 10_000;
const TICK_MS = 100;

/**
 * F6.j / F10.6 — bootstrap UX state machine.
 *
 * idle → starting → waiting → preview-valid → (auto-fire Run) → close
 *                             ↘ preview-invalid → (Claude fixes it) → preview-valid
 *
 * The parent wires the `proposed` prop from useBootstrapProposedStore.
 */
export function BootstrapModal({ taskId, onClose, proposed }: Props) {
  const bootstrap = useBootstrapManifest(taskId);
  const cancel = useCancelBootstrap(taskId);
  const startRun = useStartRun(taskId);
  const [phase, setPhase] = useState<Phase>('idle');
  const [countdownMs, setCountdownMs] = useState(AUTO_FIRE_MS);
  const timerRef = useRef<number | null>(null);

  // Reflect external `proposed` prop into phase. The store's setLast wraps
  // each emit in a fresh object, so this effect re-fires on every emit.
  useEffect(() => {
    if (proposed == null) return;
    setPhase(proposed.valid ? 'preview-valid' : 'preview-invalid');
  }, [proposed]);

  // Countdown effect: while in preview-valid, count down to AUTO_FIRE_MS then
  // fire startRun. Re-entered if the user transitions back from invalid.
  useEffect(() => {
    if (phase !== 'preview-valid') return;
    setCountdownMs(AUTO_FIRE_MS);
    const start = Date.now();
    timerRef.current = window.setInterval(() => {
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, AUTO_FIRE_MS - elapsed);
      setCountdownMs(remaining);
      if (remaining === 0) {
        if (timerRef.current) window.clearInterval(timerRef.current);
        startRun.mutate(undefined, {
          onSuccess: () => onClose(),
        });
      }
    }, TICK_MS);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const onStart = () => {
    setPhase('starting');
    bootstrap.mutate(undefined, {
      onSuccess: () => setPhase('waiting'),
      onError: () => setPhase('idle'),
    });
  };

  const onCancelAll = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    // No bootstrap session yet → don't bother the backend, just close.
    if (phase === 'idle') {
      onClose();
      return;
    }
    cancel.mutate(undefined, {
      onSettled: () => onClose(),
    });
  };

  const onRunNow = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    startRun.mutate(undefined, {
      onSuccess: () => onClose(),
    });
  };

  const title =
    phase === 'idle' || phase === 'starting' ? 'Manifesto faltando'
    : phase === 'waiting' ? 'Aguardando o Claude propor o manifesto'
    : phase === 'preview-valid' ? 'Manifesto pronto'
    : 'Manifesto inválido';

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onCancelAll(); }}>
      <DialogContent
        className="bg-bg-surface border-border-subtle max-w-3xl"
        aria-label="bootstrap-manifest-modal"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-text-emphasis">{title}</DialogTitle>
          {(phase === 'idle' || phase === 'starting') && (
            <DialogDescription className="text-text-subtle">
              Esse projeto ainda não tem <code>.orchestrator/run.yml</code>. Clique em{' '}
              <strong>Iniciar bootstrap</strong> pra abrir uma sessão Claude efêmera
              que vai propor o manifesto.
            </DialogDescription>
          )}
        </DialogHeader>

        {(phase === 'idle' || phase === 'starting') && (
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onStart} disabled={bootstrap.isPending}>
              Iniciar bootstrap
            </button>
            <button type="button" onClick={onClose}>Cancelar</button>
          </div>
        )}

        {phase === 'waiting' && (
          <div className="flex gap-2 pt-2 items-center">
            <p className="text-text-subtle">
              Claude está lendo o repo. Quando salvar o manifesto, ele aparece aqui automaticamente.
            </p>
            <button type="button" onClick={onCancelAll}>Cancelar</button>
          </div>
        )}

        {(phase === 'preview-valid' || phase === 'preview-invalid') && proposed && (
          <>
            <pre className="bg-bg-elevated border border-border-subtle rounded p-2 overflow-auto max-h-96 text-xs">
              <code>{proposed.manifest_text}</code>
            </pre>
            {phase === 'preview-invalid' && (
              <ul className="text-status-error">
                {proposed.errors.map((e, i) => (<li key={i}>{e}</li>))}
              </ul>
            )}
            <div className="flex gap-2 pt-2 items-center">
              {phase === 'preview-valid' && (
                <button type="button" onClick={onRunNow}>
                  Run agora ({Math.ceil(countdownMs / 1000)}s)
                </button>
              )}
              <button type="button" onClick={onCancelAll}>Cancelar</button>
            </div>
          </>
        )}

        {bootstrap.isError && (
          <p role="alert">
            Falha ao iniciar bootstrap: {(bootstrap.error as Error).message}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
