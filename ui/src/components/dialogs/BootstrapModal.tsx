import { useBootstrapManifest } from '../../hooks/useRun';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

type Props = {
  taskId: string;
  onClose: () => void;
};

/**
 * F6.j — modal disparado por 422 `manifest_missing` em `startRun`.
 *
 * Botão "Iniciar bootstrap" chama `api.bootstrapManifest(taskId)` que
 * spawna sessão Claude efêmera no projeto. O daemon assiste o filesystem;
 * quando `.orchestrator/run.yml` aparece, broadcasta `bootstrap.proposed`
 * que `useSessionEvents` converte em toast.
 */
export function BootstrapModal({ taskId, onClose }: Props) {
  const bootstrap = useBootstrapManifest(taskId);

  const onStart = () => {
    bootstrap.mutate(undefined, {
      onSuccess: () => onClose(),
    });
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent
        className="bg-bg-surface border-border-subtle"
        aria-label="bootstrap-manifest-modal"
        aria-labelledby=""
      >
        <DialogHeader>
          <DialogTitle className="font-display text-text-emphasis">
            Manifesto faltando
          </DialogTitle>
          <DialogDescription className="text-text-subtle">
            Esse projeto ainda não tem <code>.orchestrator/run.yml</code>. Clique
            em <strong>Iniciar bootstrap</strong> pra abrir uma sessão Claude
            efêmera que vai propor o manifesto. Quando o Claude salvar o arquivo,
            você recebe um toast e pode clicar <strong>▶ Run</strong> de novo.
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-2 pt-2">
          <button
            type="button"
            onClick={onStart}
            disabled={bootstrap.isPending}
          >
            Iniciar bootstrap
          </button>
          <button type="button" onClick={onClose}>Cancelar</button>
        </div>
        {bootstrap.isError && (
          <p role="alert">
            Falha ao iniciar bootstrap: {(bootstrap.error as Error).message}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
