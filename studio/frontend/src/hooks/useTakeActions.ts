import { useCallback } from 'react'

import { useToast } from '../components/ui/toast'
import { ApiError, api } from '../lib/api'
import type { JobOut } from '../lib/types'
import { useComposer } from '../state/composer'
import { useUi } from '../state/ui'
import { useAssetIndex, useJobMutations } from './queries'
import { copyText } from './useCopy'

/**
 * The five take actions the product promises, in one place so the stage and the
 * gallery cannot drift apart: Reuse, Copy prompt, Download, Hide/Unhide, Delete.
 */
export function useTakeActions() {
  const { cancel, setHidden, remove, reuse } = useJobMutations()
  const loadRequest = useComposer((state) => state.loadRequest)
  const selectJob = useUi((state) => state.selectJob)
  const setMobileView = useUi((state) => state.setMobileView)
  const assets = useAssetIndex()
  const { toast } = useToast()

  const reuseTake = useCallback(
    async (job: JobOut, keepSeed: boolean) => {
      try {
        const request = await reuse.mutateAsync({ jobId: job.id, keepSeed })
        const { missing } = loadRequest(request, assets)
        setMobileView('compose')
        toast({
          title: keepSeed ? 'Receta y semilla cargadas' : 'Receta cargada con semilla nueva',
          description:
            missing > 0
              ? `${missing === 1 ? 'No se pudo restaurar 1 referencia' : `No se pudieron restaurar ${missing} referencias`}: ya no están en la biblioteca.`
              : undefined,
          tone: missing > 0 ? 'info' : 'success',
        })
      } catch (error) {
        toast({
          title: 'No se pudo reutilizar esta toma',
          description: error instanceof ApiError ? error.message : undefined,
          tone: 'error',
        })
      }
    },
    [assets, loadRequest, reuse, setMobileView, toast],
  )

  const copyPrompt = useCallback(
    async (job: JobOut) => {
      const ok = await copyText(job.prompt)
      toast({
        title: ok ? 'Prompt copiado' : 'No se pudo copiar el prompt',
        description: ok ? undefined : 'El navegador bloqueó el portapapeles en esta dirección.',
        tone: ok ? 'success' : 'error',
      })
    },
    [toast],
  )

  const download = useCallback((outputId: string) => {
    // Same-origin file route; the backend sets the attachment disposition.
    window.location.href = api.downloadUrl(outputId)
  }, [])

  const toggleHidden = useCallback(
    async (job: JobOut) => {
      try {
        await setHidden.mutateAsync({ jobId: job.id, hidden: !job.hidden })
        toast({ title: job.hidden ? 'Toma visible de nuevo' : 'Toma oculta', tone: 'info' })
      } catch (error) {
        toast({
          title: 'No se pudo actualizar esta toma',
          description: error instanceof ApiError ? error.message : undefined,
          tone: 'error',
        })
      }
    },
    [setHidden, toast],
  )

  const deleteTake = useCallback(
    async (job: JobOut) => {
      try {
        await remove.mutateAsync(job.id)
        selectJob(null)
        toast({ title: 'Toma eliminada', description: 'Se borraron el render y sus archivos.', tone: 'info' })
        return true
      } catch (error) {
        toast({
          title: 'No se pudo eliminar esta toma',
          description: error instanceof ApiError ? error.message : undefined,
          tone: 'error',
        })
        return false
      }
    },
    [remove, selectJob, toast],
  )

  const cancelTake = useCallback(
    async (job: JobOut) => {
      try {
        await cancel.mutateAsync(job.id)
        toast({ title: 'Cancelación enviada', description: 'Mira el escenario para saber si el cálculo llegó a detenerse.', tone: 'info' })
      } catch (error) {
        toast({
          title: 'No se pudo cancelar esta toma',
          description: error instanceof ApiError ? error.message : undefined,
          tone: 'error',
        })
      }
    },
    [cancel, toast],
  )

  return {
    reuseTake,
    copyPrompt,
    download,
    toggleHidden,
    deleteTake,
    cancelTake,
    pending: {
      reuse: reuse.isPending,
      hidden: setHidden.isPending,
      remove: remove.isPending,
      cancel: cancel.isPending,
    },
  }
}
