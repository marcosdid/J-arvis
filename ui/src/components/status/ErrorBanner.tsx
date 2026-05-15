import { useWsConnectionStore } from '@/stores/wsConnection';

export function ErrorBanner() {
  const state = useWsConnectionStore((s) => s.state);
  if (state === 'connected') return null;

  const message =
    state === 'reconnecting' ? 'Connection lost — reconnecting...' :
    state === 'offline'      ? 'Offline — backend unreachable' :
                               'Connecting...';

  const isError = state === 'offline';

  return (
    <div
      role="alert"
      data-testid="error-banner"
      className={
        isError
          ? 'px-3 py-1 text-xs text-center bg-sem-error/20 text-sem-error border-b border-sem-error'
          : 'px-3 py-1 text-xs text-center bg-semantic-warn/20 text-semantic-warn border-b border-semantic-warn'
      }
    >
      {message}
    </div>
  );
}
