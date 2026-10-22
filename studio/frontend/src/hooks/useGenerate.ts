import { useCallback } from 'react'

import { ApiError } from '../lib/api'
import { BRAND } from '../lib/brand'
import { blockingSentence } from '../lib/issues'
import type { CapabilityResponse, GenerationRequest, Issue } from '../lib/types'
import { useComposer } from '../state/composer'
import { useUi } from '../state/ui'
import { useToast } from '../components/ui/toast'
import { useJobMutations } from './queries'
import { t } from '../i18n'

export interface GenerateGate {
  /** null when the take can be submitted. */
  blockedReason: string | null
}

/** Everything that can stop a render, checked in the order the creator hits it. */
export function generateGate(
  request: GenerationRequest,
  capabilities: CapabilityResponse | undefined,
  issues: Issue[],
): GenerateGate {
  if (!request.prompt.trim()) return { blockedReason: t('Escribe un prompt primero.') }
  const omni = request.method === 'fast_h3_omni_8step'
  if (omni && request.mode !== 'ref2va') return { blockedReason: t('Omni solo admite escenas en Referencias (Ref2VA).') }
  if (omni && !capabilities?.methods.some((entry) => entry.id === request.method)) return { blockedReason: t('Omni aún no tiene disponibilidad confirmada. Revisa Instalar o configurar Omni.') }
  if (!omni && capabilities && !capabilities.comfy_online) {
    return { blockedReason: `H3 Lab (ComfyUI en ${capabilities.comfy_url}) no responde. Puedes seguir preparando la toma.` }
  }
  const mode = capabilities?.modes.find((entry) => entry.id === request.mode)
  if (!omni && mode && !mode.available) {
    return { blockedReason: mode.unavailable_reason ?? t('Esta tarea no está disponible ahora mismo.') }
  }
  const method = capabilities?.methods.find((entry) => entry.id === request.method)
  if (method && !method.available) {
    return { blockedReason: method.unavailable_reason ?? t('Este método no está disponible ahora mismo.') }
  }
  const error = issues.find((issue) => issue.severity === 'error')
  if (error) return { blockedReason: blockingSentence(error) }
  return { blockedReason: null }
}

export function useGenerate() {
  const { create } = useJobMutations()
  const setActiveJob = useUi((state) => state.setActiveJob)
  const setMobileView = useUi((state) => state.setMobileView)
  const setNotice = useComposer((state) => state.setNotice)
  const { toast } = useToast()

  const generate = useCallback(
    async (request: GenerationRequest) => {
      try {
        const { job } = await create.mutateAsync(request)
        setActiveJob(job.id)
        setMobileView('stage')
        if (job.status === 'failed') {
          toast({ title: t('ComfyUI rechazó la toma'), description: job.error ?? undefined, tone: 'error' })
        } else {
          toast({ title: t('Toma en cola'), description: job.title ?? t('Generando en {machine}. Sigue el progreso en el escenario.', { machine: BRAND.machine }), tone: 'success' })
        }
        return job
      } catch (error) {
        const message = error instanceof ApiError ? error.message : t('No se pudo poner la toma en cola.')
        setNotice(message)
        toast({ title: t('No se pudo poner en cola'), description: message, tone: 'error' })
        return null
      }
    },
    [create, setActiveJob, setMobileView, setNotice, toast],
  )

  return { generate, pending: create.isPending }
}
