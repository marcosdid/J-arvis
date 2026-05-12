import { cn } from '@/lib/utils';

type Tone = 'default' | 'warn' | 'error';

type Props = {
  label: string;
  value: string;
  tone?: Tone;
};

const toneClass: Record<Tone, string> = {
  default: 'text-accent-primary',
  warn: 'text-semantic-warn',
  error: 'text-accent-attn',
};

export function StatusSeg({ label, value, tone = 'default' }: Props) {
  return (
    <span className="inline-flex gap-1 items-center" data-testid={`status-seg-${label}`}>
      <span className="text-text-subtle">{label}</span>
      <span className={cn('font-semibold', toneClass[tone])}>{value}</span>
    </span>
  );
}
