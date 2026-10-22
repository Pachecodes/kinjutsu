import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

/**
 * Graphite/black studio (PictureME family) with exactly one accent hue (lime). Every colour resolves
 * through a CSS variable defined in `src/index.css`, so there is a single place
 * that decides what the product looks like — and no second accent hue exists.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: 'hsl(var(--ink-950) / <alpha-value>)',
          900: 'hsl(var(--ink-900) / <alpha-value>)',
          850: 'hsl(var(--ink-850) / <alpha-value>)',
          800: 'hsl(var(--ink-800) / <alpha-value>)',
          700: 'hsl(var(--ink-700) / <alpha-value>)',
          600: 'hsl(var(--ink-600) / <alpha-value>)',
        },
        line: 'hsl(var(--line) / <alpha-value>)',
        'line-strong': 'hsl(var(--line-strong) / <alpha-value>)',
        fg: 'hsl(var(--fg) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        faint: 'hsl(var(--faint) / <alpha-value>)',
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          soft: 'hsl(var(--accent-soft) / <alpha-value>)',
          ink: 'hsl(var(--accent-ink) / <alpha-value>)',
        },
        danger: {
          DEFAULT: 'hsl(var(--danger) / <alpha-value>)',
          soft: 'hsl(var(--danger-soft) / <alpha-value>)',
        },
        warn: {
          DEFAULT: 'hsl(var(--warn) / <alpha-value>)',
          soft: 'hsl(var(--warn-soft) / <alpha-value>)',
        },
        // The Generate action only. Same lime hue as the accent, one notch louder.
        cta: {
          DEFAULT: 'hsl(var(--cta) / <alpha-value>)',
          hover: 'hsl(var(--cta-hover) / <alpha-value>)',
          base: 'hsl(var(--cta-base) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        display: ['var(--font-display)'],
        mono: ['var(--font-mono)'],
      },
      letterSpacing: {
        editorial: '-0.02em',
        caps: '0.14em',
        wide2: '0.18em',
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '8px',
        md: '10px',
        lg: '12px',
        xl: '14px',
        '2xl': '18px',
        '3xl': '28px',
      },
      boxShadow: {
        panel: '0 1px 0 0 hsl(var(--line) / 0.6), 0 18px 40px -28px rgb(0 0 0 / 0.9)',
        lift: '0 24px 60px -32px rgb(0 0 0 / 0.95)',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(320%)' },
        },
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 hsl(var(--accent) / 0.45)' },
          '100%': { boxShadow: '0 0 0 8px hsl(var(--accent) / 0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 160ms ease-out',
        'slide-up': 'slide-up 200ms cubic-bezier(0.22, 1, 0.36, 1)',
        sweep: 'sweep 1.8s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 1.6s ease-out infinite',
      },
    },
  },
  plugins: [animate],
} satisfies Config
