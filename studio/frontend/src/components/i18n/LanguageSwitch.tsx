import { LOCALE_NAME, LOCALES, t, useLocale } from '../../i18n'
import { cn } from '../../lib/cn'

/** Compact ES/EN switch for the header. The choice persists in this browser. */
export function LanguageSwitch({ className }: { className?: string }) {
  const locale = useLocale((state) => state.locale)
  const setLocale = useLocale((state) => state.setLocale)
  return (
    <div
      role="group"
      aria-label={t('Idioma de la interfaz')}
      className={cn('flex shrink-0 items-center rounded-lg border border-white/[0.07] bg-ink-850 p-0.5', className)}
    >
      {LOCALES.map((code) => {
        const active = code === locale
        return (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={active}
            aria-label={LOCALE_NAME[code]}
            title={LOCALE_NAME[code]}
            onClick={() => setLocale(code)}
            className={cn(
              'min-h-7 rounded-md px-2 text-[10px] font-black uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
              active ? 'bg-accent text-accent-ink' : 'text-faint hover:bg-ink-700 hover:text-fg',
            )}
          >
            {code}
          </button>
        )
      })}
    </div>
  )
}
