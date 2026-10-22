import { PlugZap } from 'lucide-react'

import { useRefreshCapabilities } from '../../hooks/queries'
import type { CapabilityResponse } from '../../lib/types'
import { Button } from '../ui/button'
import { t, useT } from '../../i18n'

/**
 * When the H3 lab instance is unreachable the whole product still renders — it
 * just says exactly what is wrong and what it is falling back to, instead of
 * pretending every mode vanished.
 */
export function CapabilityNotice({ capabilities }: { capabilities: CapabilityResponse }) {
  useT()
  const refresh = useRefreshCapabilities()
  if (capabilities.comfy_online) return null

  return (
    <div
      role="status"
      className="flex items-center gap-3 border-b border-warn/25 bg-warn-soft/40 px-4 py-2 text-xs"
    >
      <PlugZap className="size-4 shrink-0 text-warn" aria-hidden />
      <p className="min-w-0 flex-1 leading-snug text-fg">
        <span className="font-semibold">{t('H3 Lab no responde.')}</span>{' '}
        <span className="text-muted">
          {t('Puedes preparar tomas; nada se genera hasta que vuelva.')}
          <span className="hidden sm:inline">
            {' '}
            {t('Tareas y recetas vienen del contrato instalado, sin confirmar (ComfyUI en {url}).', { url: capabilities.comfy_url })}
          </span>
        </span>
        {capabilities.error ? (
          <span className="mt-0.5 hidden truncate text-[11px] text-faint lg:block">{capabilities.error}</span>
        ) : null}
      </p>
      <Button variant="outline" size="sm" loading={refresh.isPending} onClick={() => refresh.mutate()} className="shrink-0">
        <span className="sm:hidden">{t('Comprobar')}</span>
        <span className="hidden sm:inline">{t('Comprobar de nuevo')}</span>
      </Button>
    </div>
  )
}
