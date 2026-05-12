import { cn } from '@/lib/utils';

type Props = {
  label: string;
  value: string | number;
  tone?: 'default' | 'hot';
};

export function HudMetric({ label, value, tone = 'default' }: Props) {
  return (
    <span className='inline-flex gap-1.5 items-center' data-testid={`hud-metric-${label}`}>
      <span className='text-text-faint'>{label}</span>
      <span
        className={cn(
          'font-semibold tabular-nums',
          tone === 'hot' ? 'text-accent-attn drop-shadow-[0_0_6px_rgba(255,16,240,0.6)]' : 'text-accent-primary',
        )}
      >
        {value}
      </span>
    </span>
  );
}
