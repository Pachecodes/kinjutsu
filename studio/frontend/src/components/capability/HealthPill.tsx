import { RefreshCw } from 'lucide-react'

import { useHealth, useRefreshCapabilities } from '../../hooks/queries'
import { cn } from '../../lib/cn'
import { Button } from '../ui/button'
import { Tooltip } from '../ui/tooltip'

/**
 * Honest, low-noise status: whether the H3 lab Comfy instance answered, and how
 * many takes the Studio is currently watching. No invented metrics.
 */
export function HealthPill() {
  const health = useHealth()
  const refresh = useRefreshCapabilities()

  const online = health.data?.comfy_online ?? false
  const unreachable = health.isError
  const tone = unreachable ? 'offline' : online ? 'online' : 'degraded'

  const label =
    tone === 'offline' ? 'Studio sin respuesta' : tone === 'online' ? 'H3 Lab en línea' : 'H3 Lab desconectado'

  const detail = unreachable
    ? 'El backend del Studio no respondió. Arráncalo en esta máquina y reintenta.'
    : `ComfyUI ${health.data?.comfy_url ?? ''} · ${health.data?.active_jobs ?? 0} toma(s) activas · Studio v${health.data?.version ?? '—'}`

  return (
    <div className="flex min-w-0 items-center gap-1">
      <Tooltip content={detail} side="bottom" align="end">
        <span
          className={cn(
            'inline-flex min-h-8 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold',
            tone === 'online' && 'border-accent/35 bg-accent/10 text-accent',
            tone === 'degraded' && 'border-warn/40 bg-warn-soft/50 text-warn',
            tone === 'offline' && 'border-danger/40 bg-danger-soft/50 text-danger',
          )}
        >
          <span
            className={cn(
              'size-1.5 rounded-full',
              tone === 'online' && 'bg-accent',
              tone === 'degraded' && 'bg-warn',
              tone === 'offline' && 'bg-danger',
            )}
            aria-hidden
          />
          <span className="sm:hidden">{online ? 'En línea' : 'Sin conexión'}</span>
          <span className="hidden sm:inline">{label}</span>
        </span>
      </Tooltip>
      <Tooltip content="Volver a comprobar H3 Lab (ComfyUI)" side="bottom" align="end">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Comprobar H3 Lab de nuevo"
          loading={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? null : <RefreshCw aria-hidden />}
        </Button>
      </Tooltip>
    </div>
  )
}
