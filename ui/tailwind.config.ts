import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          void: 'var(--bg-void)',
          deep: 'var(--bg-deep)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          muted: 'var(--bg-muted)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          mid: 'var(--border-mid)',
          strong: 'var(--border-strong)',
        },
        text: {
          faint: 'var(--text-faint)',
          subtle: 'var(--text-subtle)',
          body: 'var(--text-body)',
          emphasis: 'var(--text-emphasis)',
          title: 'var(--text-title)',
        },
        accent: {
          primary: 'var(--accent-primary)',
          attn: 'var(--accent-attn)',
          info: 'var(--accent-info)',
        },
        sem: {
          error: 'var(--semantic-error)',
          warn: 'var(--semantic-warn)',
          frontend: 'var(--semantic-frontend)',
          backend: 'var(--semantic-backend)',
          bugfix: 'var(--semantic-bugfix)',
          refactor: 'var(--semantic-refactor)',
          review: 'var(--semantic-review)',
        },
      },
      fontFamily: {
        mono: 'var(--font-mono)',
        display: 'var(--font-display)',
      },
    },
  },
} satisfies Config;
