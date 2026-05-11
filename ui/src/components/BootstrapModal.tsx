import { useBootstrapManifest } from '../hooks/useRun';

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
    <div role="dialog" aria-label="bootstrap-manifest-modal" className="modal modal-bootstrap">
      <h3>Manifesto faltando</h3>
      <p>
        Esse projeto ainda não tem <code>.orchestrator/run.yml</code>. Clique
        em <strong>Iniciar bootstrap</strong> pra abrir uma sessão Claude
        efêmera que vai propor o manifesto. Quando o Claude salvar o arquivo,
        você recebe um toast e pode clicar <strong>▶ Run</strong> de novo.
      </p>
      <div className="modal-actions">
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
    </div>
  );
}
