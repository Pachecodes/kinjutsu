import { Copy, Download, Eye, EyeOff, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useTakeActions } from '../../hooks/useTakeActions'
import type { JobOut } from '../../lib/types'
import { ConfirmDialog } from '../ui/alert-dialog'
import { Button } from '../ui/button'
import { Tooltip } from '../ui/tooltip'
import { t, useT } from '../../i18n'

interface TakeActionsProps {
  job: JobOut
  size?: 'sm' | 'md'
  /** Compact cards drop the labels and keep icon-only affordances. */
  iconOnly?: boolean
}

/** Reutilizar · Copiar prompt · Descargar · Ocultar/Mostrar · Eliminar. */
export function TakeActions({ job, size = 'sm', iconOnly = false }: TakeActionsProps) {
  useT()
  const { reuseTake, copyPrompt, download, toggleHidden, deleteTake, pending } = useTakeActions()
  const [confirming, setConfirming] = useState(false)

  const primaryOutput = job.outputs.find((output) => output.kind === 'video') ?? job.outputs[0]
  const canDelete = job.status === 'completed' || job.status === 'failed' || job.status === 'canceled'

  const label = (text: string) => (iconOnly ? null : text)

  return (
    <>
      <div className="flex flex-wrap items-center gap-1">
        <Tooltip content={t('Carga la receta, referencias y semilla de esta toma en el compositor. No genera.')}>
          <Button
            variant="outline"
            size={size}
            loading={pending.reuse}
            onClick={() => void reuseTake(job, true)}
            aria-label={t('Reutilizar esta toma')}
          >
            <RotateCcw aria-hidden />
            {label(t('Reutilizar'))}
          </Button>
        </Tooltip>

        <Tooltip content={t('Copia el prompt al portapapeles')}>
          <Button variant="ghost" size={size} onClick={() => void copyPrompt(job)} aria-label={t('Copiar prompt')}>
            <Copy aria-hidden />
            {label(t('Copiar prompt'))}
          </Button>
        </Tooltip>

        <Tooltip content={primaryOutput ? t('Descarga el archivo renderizado') : t('Esta toma no produjo archivo')}>
          <span>
            <Button
              variant="ghost"
              size={size}
              disabled={!primaryOutput}
              onClick={() => primaryOutput && download(primaryOutput.id)}
              aria-label={t('Descargar toma')}
            >
              <Download aria-hidden />
              {label(t('Descargar'))}
            </Button>
          </span>
        </Tooltip>

        <Tooltip content={job.hidden ? t('Volver a mostrar en la galería') : t('Ocultar de la galería (no borra nada)')}>
          <Button
            variant="ghost"
            size={size}
            loading={pending.hidden}
            onClick={() => void toggleHidden(job)}
            aria-label={job.hidden ? t('Mostrar toma') : t('Ocultar toma')}
          >
            {job.hidden ? <Eye aria-hidden /> : <EyeOff aria-hidden />}
            {label(job.hidden ? t('Mostrar') : t('Ocultar'))}
          </Button>
        </Tooltip>

        <Tooltip content={canDelete ? t('Elimina la toma y sus archivos') : t('Cancela la toma antes de eliminarla')}>
          <span>
            <Button
              variant="ghost"
              size={size}
              disabled={!canDelete}
              onClick={() => setConfirming(true)}
              aria-label={t('Eliminar toma')}
              className="text-danger hover:bg-danger/10 hover:text-danger"
            >
              <Trash2 aria-hidden />
              {label(t('Eliminar'))}
            </Button>
          </span>
        </Tooltip>
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t('¿Eliminar esta toma?')}
        description={
          <>
            <span className="block">
              {job.outputs.length === 1
                ? t('{take} y 1 archivo renderizado se borrarán del disco. No se puede deshacer.', {
                    take: job.title ? t('«{title}»', { title: job.title }) : t('Esta toma'),
                  })
                : t('{take} y {n} archivos renderizados se borrarán del disco. No se puede deshacer.', {
                    take: job.title ? t('«{title}»', { title: job.title }) : t('Esta toma'),
                    n: job.outputs.length,
                  })}
            </span>
            <span className="mt-2 block text-xs text-faint">
              {t('La receta se va con ella: pulsa Reutilizar antes si quieres conservar los ajustes.')}
            </span>
          </>
        }
        confirmLabel={t('Eliminar para siempre')}
        cancelLabel={t('Conservarla')}
        busy={pending.remove}
        onConfirm={() => {
          void deleteTake(job).then((ok) => {
            if (ok) setConfirming(false)
          })
        }}
      />
    </>
  )
}
