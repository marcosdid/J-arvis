import { useSystemHealth } from '@/hooks/useSystemHealth';
import { useWsConnectionStore } from '@/stores/wsConnection';
import { StatusSeg } from './StatusSeg';

const VERSION = 'v0.0.1';

export function StatusBar() {
  const wsState = useWsConnectionStore((s) => s.state);
  const { data } = useSystemHealth();

  const wsTone = wsState === 'connected' ? 'default' : wsState === 'reconnecting' ? 'warn' : 'error';
  const stateLabel = wsState === 'connected' ? 'online' : 'offline';
  const stateTone = wsState === 'connected' ? 'default' : 'error';
  const alertsCount = data?.active_alerts_count ?? 0;

  return (
    <footer
      role="status"
      aria-label="status bar"
      className="flex justify-between items-center px-3 py-1 text-[0.62rem] tracking-wider border-t border-border-subtle bg-bg-deep text-text-subtle"
    >
      <div className="flex items-center gap-2">
        <StatusSeg label="state" value={stateLabel} tone={stateTone} />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="ws" value={wsState} tone={wsTone} />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="mcp" value="ok" />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="alerts" value={String(alertsCount)} tone={alertsCount > 0 ? 'error' : 'default'} />
      </div>
      <div className="flex items-center gap-2">
        <StatusSeg label="mode" value="ops" />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="profile" value="—" />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="git" value="main" />
        <span className="text-border-subtle">│</span>
        <StatusSeg label="v" value={VERSION} />
      </div>
    </footer>
  );
}
