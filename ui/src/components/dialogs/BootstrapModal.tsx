import { useEffect, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, FileQuestion, Loader2, Play, X } from 'lucide-react';

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
  proposed?: BootstrapProposed | null;
};

const AUTO_FIRE_MS = 10_000;
const TICK_MS = 100;

const HEADER_META: Record<Phase, { icon: React.ElementType; tint: string; title: string }> = {
  'idle': { icon: FileQuestion, tint: 'text-accent-info', title: 'Manifesto faltando' },
  'starting': { icon: Loader2, tint: 'text-accent-info', title: 'Manifesto faltando' },
  'waiting': { icon: Loader2, tint: 'text-accent-info', title: 'Aguardando o Claude propor o manifesto' },
  'preview-valid': { icon: CheckCircle2, tint: 'text-accent-primary', title: 'Manifesto pronto' },
  'preview-invalid': { icon: AlertCircle, tint: 'text-sem-error', title: 'Manifesto inválido' },
};

export function BootstrapModal({ taskId, onClose, proposed }: Props) {
  const bootstrap = useBootstrapManifest(taskId);
  const cancel = useCancelBootstrap(taskId);
  const startRun = useStartRun(taskId);
  const [phase, setPhase] = useState<Phase>('idle');
  const [countdownMs, setCountdownMs] = useState(AUTO_FIRE_MS);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (proposed == null) return;
    setPhase(proposed.valid ? 'preview-valid' : 'preview-invalid');
  }, [proposed]);

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

  const meta = HEADER_META[phase];
  const Icon = meta.icon;
  const animate = phase === 'starting' || phase === 'waiting';

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onCancelAll(); }}>
      <DialogContent
        className="bg-bg-surface border border-border-subtle rounded-lg p-0 max-w-3xl gap-0 overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.4),0_0_0_1px_rgba(74,222,128,0.05)]"
        aria-label="bootstrap-manifest-modal"
      >
        <DialogHeader className="flex flex-row items-center gap-3 border-b border-border-subtle px-6 py-4 space-y-0">
          <Icon
            size={20}
            className={`${meta.tint} shrink-0 ${animate ? 'animate-spin' : ''}`}
            aria-hidden
          />
          <DialogTitle className="font-display text-lg tracking-[0.04em] text-text-title">
            {meta.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Fluxo de bootstrap do manifesto .orchestrator/run.yml
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 py-5 space-y-5">
          {(phase === 'idle' || phase === 'starting') && (
            <p className="text-[15px] leading-relaxed text-text-emphasis">
              Esse projeto ainda não tem{' '}
              <code className="font-mono text-sm px-1.5 py-0.5 rounded bg-bg-deep border border-border-subtle text-accent-primary">
                .orchestrator/run.yml
              </code>
              . Ao iniciar o bootstrap, uma sessão Claude efêmera abre e propõe o manifesto.
            </p>
          )}

          {phase === 'waiting' && (
            <p className="text-[15px] leading-relaxed text-text-emphasis">
              Claude está lendo o repositório. Quando ele salvar o manifesto, ele aparece aqui automaticamente.
            </p>
          )}

          {(phase === 'preview-valid' || phase === 'preview-invalid') && proposed && (
            <>
              <pre className="bg-bg-deep border border-border-subtle rounded-md p-4 overflow-auto max-h-96 text-xs font-mono leading-relaxed text-text-emphasis">
                <code>{proposed.manifest_text}</code>
              </pre>
              {phase === 'preview-invalid' && (
                <div className="rounded-md border border-sem-error/30 bg-sem-error/5 p-4">
                  <div className="flex items-center gap-2 mb-2 text-sem-error font-display text-sm uppercase tracking-[0.08em]">
                    <AlertCircle size={14} aria-hidden />
                    Erros de validação
                  </div>
                  <ul className="space-y-1 text-sm text-sem-error font-mono">
                    {proposed.errors.map((e, i) => (
                      <li key={i} className="flex gap-2">
                        <span aria-hidden className="text-sem-error/60">›</span>
                        <span>{e}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {bootstrap.isError && (
            <div
              role="alert"
              className="rounded-md border border-sem-error/30 bg-sem-error/5 p-3 flex items-start gap-2 text-sm text-sem-error"
            >
              <AlertCircle size={14} aria-hidden className="mt-0.5 shrink-0" />
              <span className="font-mono break-all">
                Falha ao iniciar bootstrap: {(bootstrap.error as Error).message}
              </span>
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-3 border-t border-border-subtle bg-bg-elevated/40 px-6 py-4">
          {(phase === 'idle' || phase === 'starting') && (
            <>
              <SecondaryButton onClick={onClose}>
                <X size={16} aria-hidden />
                <span>Cancelar</span>
              </SecondaryButton>
              <PrimaryButton onClick={onStart} disabled={bootstrap.isPending}>
                {bootstrap.isPending ? (
                  <Loader2 size={16} className="animate-spin" aria-hidden />
                ) : (
                  <Play size={16} aria-hidden />
                )}
                <span>Iniciar bootstrap</span>
              </PrimaryButton>
            </>
          )}

          {phase === 'waiting' && (
            <SecondaryButton onClick={onCancelAll}>
              <X size={16} aria-hidden />
              <span>Cancelar</span>
            </SecondaryButton>
          )}

          {(phase === 'preview-valid' || phase === 'preview-invalid') && (
            <>
              <SecondaryButton onClick={onCancelAll}>
                <X size={16} aria-hidden />
                <span>Cancelar</span>
              </SecondaryButton>
              {phase === 'preview-valid' && (
                <PrimaryButton onClick={onRunNow}>
                  <Play size={16} aria-hidden />
                  <span>Run agora ({Math.ceil(countdownMs / 1000)}s)</span>
                </PrimaryButton>
              )}
            </>
          )}
        </footer>
      </DialogContent>
    </Dialog>
  );
}

function PrimaryButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-2 rounded-md border border-accent-primary/70 bg-accent-primary/10 px-4 py-2.5 font-display text-sm uppercase tracking-[0.06em] text-accent-primary transition-all hover:bg-accent-primary/20 hover:border-accent-primary focus:outline-none focus:bg-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}

function SecondaryButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-md border border-border-subtle bg-transparent px-4 py-2.5 font-display text-sm uppercase tracking-[0.06em] text-text-subtle transition-colors hover:border-border-mid hover:text-text-emphasis focus:outline-none focus:border-border-mid focus:text-text-emphasis"
    >
      {children}
    </button>
  );
}
