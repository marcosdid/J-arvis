import { useSystemHealth } from '@/hooks/useSystemHealth';
import { HudMetric } from './HudMetric';

function formatBytes(b: number): string {
  if (b < 1024) return `${b}B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(0)}K`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(0)}M`;
  return `${(b / 1024 ** 3).toFixed(1)}G`;
}

function formatUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h${m.toString().padStart(2, '0')}m`;
}

export function HudTopBar({ wsRtt }: { wsRtt: number | null }) {
  const { data } = useSystemHealth();

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-between px-4 py-1.5 text-[0.62rem] tracking-wider border-b border-border-subtle bg-bg-deep text-text-subtle"
    >
      <div className="flex items-center gap-3.5">
        <span className="bg-accent-primary text-bg-void px-1.5 py-0.5 font-bold tracking-wider before:content-['●'] before:mr-1 before:animate-[cipher-blink_1.2s_steps(1)_infinite]">
          OPER
        </span>
        <span className="font-display font-bold tracking-[0.16em] text-accent-primary text-[0.65rem]">
          J-ARVIS // OP_CTRL
        </span>
        <span className="text-border-subtle">│</span>
        <HudMetric label="env" value="linux/x86_64" />
      </div>
      <div className="flex items-center gap-3.5">
        {data && (
          <>
            <HudMetric label="cpu" value={`${data.cpu_pct.toFixed(1)}%`} />
            <span className="text-border-subtle">│</span>
            <HudMetric label="mem" value={`${formatBytes(data.mem_used_bytes)}/${formatBytes(data.mem_total_bytes)}`} />
            <span className="text-border-subtle">│</span>
          </>
        )}
        <HudMetric label="rtt" value={wsRtt !== null ? `${wsRtt}ms` : '—'} />
        {data && (
          <>
            <span className="text-border-subtle">│</span>
            <HudMetric label="uptime" value={formatUptime(data.uptime_seconds)} />
            <span className="text-border-subtle">│</span>
            <HudMetric
              label="alert"
              value={data.active_alerts_count}
              tone={data.active_alerts_count > 0 ? 'hot' : 'default'}
            />
          </>
        )}
      </div>
    </div>
  );
}
