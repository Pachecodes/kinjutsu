import { Copy, Download, Eye, EyeOff, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useTakeActions } from '../../hooks/useTakeActions'
import type { JobOut } from '../../lib/types'
import { ConfirmDialog } from '../ui/alert-dialog'
import { Button } from '../ui/button'
import { Tooltip } from '../ui/tooltip'

interface TakeActionsProps {
  job: JobOut
  size?: 'sm' | 'md'
  /** Compact cards drop the labels and keep icon-only affordances. */
  iconOnly?: boolean
}

/** Reutilizar · Copiar prompt · Descargar · Ocultar/Mostrar · Eliminar. */
export function TakeActions({ job, size = 'sm', iconOnly = false }: TakeActionsProps) {
  const { reuseTake, copyPrompt, download, toggleHidden, deleteTake, pending } = useTakeActions()
  const [confirming, setConfirming] = useState(false)

  const primaryOutput = job.outputs.find((output) => output.kind === 'video') ?? job.outputs[0]
  const canDelete = job.status === 'completed' || job.status === 'failed' || job.status === 'canceled'

  const label = (text: string) => (iconOnly ? null : text)

  return (
    <>
      <div className="flex flex-wrap items-center gap-1">
        <Tooltip content="Carga la receta, referencias y semilla de esta toma en el compositor. No genera.">
          <Button
            variant="outline"
            size={size}
            loading={pending.reuse}
            onClick={() => void reuseTake(job, true)}
            aria-label="Reutilizar esta toma"
          >
            <RotateCcw aria-hidden />
            {label('Reutilizar')}
          </Button>
        </Tooltip>

        <Tooltip content="Copia el prompt al portapapeles">
          <Button variant="ghost" size={size} onClick={() => void copyPrompt(job)} aria-label="Copiar prompt">
            <Copy aria-hidden />
            {label('Copiar prompt')}
          </Button>
        </Tooltip>

        <Tooltip content={primaryOutput ? 'Descarga el archivo renderizado' : 'Esta toma no produjo archivo'}>
          <span>
            <Button
              variant="ghost"
              size={size}
              disabled={!primaryOutput}
              onClick={() => primaryOutput && download(primaryOutput.id)}
              aria-label="Descargar toma"
            >
              <Download aria-hidden />
              {label('Descargar')}
            </Button>
          </span>
        </Tooltip>

        <Tooltip content={job.hidden ? 'Volver a mostrar en la galería' : 'Ocultar de la galería (no borra nada)'}>
          <Button
            variant="ghost"
            size={size}
            loading={pending.hidden}
            onClick={() => void toggleHidden(job)}
            aria-label={job.hidden ? 'Mostrar toma' : 'Ocultar toma'}
          >
            {job.hidden ? <Eye aria-hidden /> : <EyeOff aria-hidden />}
            {label(job.hidden ? 'Mostrar' : 'Ocultar')}
          </Button>
        </Tooltip>

        <Tooltip content={canDelete ? 'Elimina la toma y sus archivos' : 'Cancela la toma antes de eliminarla'}>
          <span>
            <Button
              variant="ghost"
              size={size}
              disabled={!canDelete}
              onClick={() => setConfirming(true)}
              aria-label="Eliminar toma"
              className="text-danger hover:bg-danger/10 hover:text-danger"
            >
              <Trash2 aria-hidden />
              {label('Eliminar')}
            </Button>
          </span>
        </Tooltip>
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="¿Eliminar esta toma?"
        description={
          <>
            <span className="block">
              {job.title ? `«${job.title}»` : 'Esta toma'} y {job.outputs.length}{' '}
              {job.outputs.length === 1 ? 'archivo renderizado se borrarán' : 'archivos renderizados se borrarán'} del disco. No se puede deshacer.
            </span>
            <span className="mt-2 block text-xs text-faint">
              La receta se va con ella: pulsa Reutilizar antes si quieres conservar los ajustes.
            </span>
          </>
        }
        confirmLabel="Eliminar para siempre"
        cancelLabel="Conservarla"
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
