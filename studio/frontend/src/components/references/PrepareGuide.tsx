import { QueryClientContext } from '@tanstack/react-query'
import { useContext, useRef, useState } from 'react'

import { FPS, FRAME_BASE, FRAME_STEP, FRAME_MAX, TRAINED_FRAME_MAX, TRAINED_FRAME_MIN } from '../../lib/frames'
import { api } from '../../lib/api'
import type { ReferenceSlot } from '../../lib/references'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'

interface PrepareGuideProps {
  slot: ReferenceSlot
  /** Visible trigger text; the dialog itself never changes. */
  triggerLabel?: string
  triggerVariant?: 'outline' | 'primary' | 'ghost'
}

export function PrepareGuide({ slot, triggerLabel = 'Preparar guía', triggerVariant = 'outline' }: PrepareGuideProps) {
  const width = useComposer(s => s.width)
  const height = useComposer(s => s.height)
  const length = useComposer(s => s.length)
  const [open, setOpen] = useState(false)
  const [fit, setFit] = useState<'pad' | 'crop'>('pad')
  const [start, setStart] = useState('0')
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  // Cards can also render outside the library; cache refresh is optional there.
  const queryClient = useContext(QueryClientContext)
  const [seconds, setSeconds] = useState<string | null>(null)
  const requested = seconds === null ? length / FPS : Number(seconds)
  // Round UP, not nearest: never silently shorten the user's requested duration.
  const targetLength = FRAME_BASE + FRAME_STEP * Math.max(0, Math.ceil((requested * FPS - FRAME_BASE - 1e-9) / FRAME_STEP))
  const maxLength = FRAME_BASE + FRAME_STEP * Math.floor((FRAME_MAX - FRAME_BASE) / FRAME_STEP)
  const invalidDuration = !Number.isFinite(requested) || requested <= 0 || targetLength > FRAME_MAX
  const duration = targetLength / FPS
  const provenance = slot.asset.guide_provenance
  const sourceDuration = provenance?.source_duration_seconds ?? slot.asset.duration_seconds
  const offset = Number(start)
  const invalidOffset = start.trim() === '' || !Number.isFinite(offset) || offset < 0 || offset > 3600
  const short = !invalidOffset && !invalidDuration && sourceDuration !== null && sourceDuration - offset + 0.000001 < duration

  async function prepare() {
    if (inFlight.current || invalidOffset || invalidDuration || short) return
    inFlight.current = true
    setBusy(true)
    setError(null)
    setSuccess(null)
    const sourceId = slot.asset.id
    const target = { width, height, length: targetLength, fit, start_seconds: offset }
    try {
      const result = await api.prepareGuide(sourceId, target)
      if (result.source_asset_id !== sourceId || result.verified.width !== width || result.verified.height !== height || result.verified.frame_count !== targetLength || result.verified.fps !== 24) {
        throw new Error('La guía recibida no coincide con el destino solicitado. No se ha cambiado la referencia.')
      }
      let swapped = false
      useComposer.setState(state => {
        // A removed/replaced slot or changed target must never be overwritten by a late response.
        if (state.mode !== 'ref2va' || state.width !== width || state.height !== height || state.length !== length) return state
        const references = state.references.map(current => {
          if (current.uid !== slot.uid || current.asset.id !== sourceId) return current
          swapped = true
          return { ...current, asset: result.asset, role: 'aligned_guide' as const, include_audio: false }
        })
        return swapped ? { references, length: targetLength } : state
      })
      void queryClient?.invalidateQueries({ queryKey: ['assets'] })
      setSuccess(swapped ? 'Guía preparada y verificada. El original sigue en la biblioteca. No se ha iniciado ningún render.' : 'Guía preparada en la biblioteca. La referencia o el destino cambiaron; no se sustituyó ninguna referencia.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo preparar la guía. Inténtalo otra vez.')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  return <Dialog open={open} onOpenChange={value => {
    if (value && !busy) {
      setSeconds(null)
      setFit(provenance?.fit ?? 'pad')
      setStart(String(provenance?.start_seconds ?? 0))
      setError(null)
      setSuccess(null)
    }
    setOpen(value)
  }}>
    <DialogTrigger asChild><Button variant={triggerVariant} size="sm">{triggerLabel}</Button></DialogTrigger>
    <DialogPanel title="Preparar guía" description="Crea un vídeo nuevo para Aligned guide, sin usar la GPU ni iniciar un render.">
      <div className="space-y-3 text-xs text-muted">
        <p>Origen: {slot.asset.original_name}</p>
        {provenance ? <p>Repreparación desde el original de la biblioteca: {provenance.source_asset_id} · {sourceDuration?.toFixed(3)} s. El inicio se mide sobre el original, no sobre esta guía.</p> : <p>Sin procedencia guardada. Si esta es una guía antigua, selecciona el vídeo original desde Library (biblioteca) para ampliar la duración; no se buscan coincidencias de archivos.</p>}
        <label className="block space-y-1">Duración deseada (segundos)
          <input aria-label="Duración deseada (segundos)" type="number" min="0.001" max={maxLength / FPS} step="any" value={seconds ?? String(length / FPS)} onChange={e => setSeconds(e.target.value)} disabled={busy} className="block w-full rounded border border-line bg-ink-850 p-2 text-fg" />
        </label>
        <p>Solicitada: {seconds ?? String(length / FPS)} s. Se redondea hacia arriba a 17k+5; máximo {maxLength} fotogramas ({(maxLength / FPS).toFixed(3)} s), dentro del límite de esquema {FRAME_MAX}.</p>
        {!invalidDuration ? <p className="font-mono text-fg">{width} × {height} · {targetLength} fotogramas · {duration.toFixed(3)} s · 24 FPS CFR</p> : <p role="alert">Introduce una duración positiva hasta {(maxLength / FPS).toFixed(3)} s; no se recorta al máximo automáticamente.</p>}
        {!invalidDuration && (targetLength < TRAINED_FRAME_MIN || targetLength > TRAINED_FRAME_MAX) ? <p>Fuera de la ventana entrenada de {TRAINED_FRAME_MIN}–{TRAINED_FRAME_MAX} fotogramas. La preparación es válida, pero la generación a esta duración es experimental.</p> : null}
        {!invalidDuration && !invalidOffset && !short ? <p>Cobertura del original: {offset.toFixed(3)}–{(offset + duration).toFixed(3)} s de {sourceDuration === null ? 'duración desconocida' : `${sourceDuration.toFixed(3)} s`}. {sourceDuration !== null && sourceDuration - offset - duration > 0.000001 ? `Se excluyen ${(sourceDuration - offset - duration).toFixed(3)} s del final.` : ''} Solo se usa este tramo; sin estirar, congelar ni repetir.</p> : null}
        <p>El original se conserva en la biblioteca. Al crear con éxito, se actualizan esta referencia y la duración de salida a {targetLength} fotogramas; identidad y demás ajustes no cambian. La guía se guarda sin audio.</p>
        <label className="block space-y-1">Encuadre
          <select aria-label="Encuadre" value={fit} onChange={e => setFit(e.target.value as 'pad' | 'crop')} disabled={busy} className="block w-full rounded border border-line bg-ink-850 p-2 text-fg">
            <option value="pad">Encajar + bandas negras — conserva todo el encuadre</option>
            <option value="crop">Recortar al centro — elimina los bordes sobrantes</option>
          </select>
        </label>
        <p>{fit === 'pad' ? 'Bandas negras si la proporción no coincide; sin recortar ni deformar.' : 'Recorte centrado: se perderá parte de la imagen para llenar el destino.'} Se mantiene la velocidad original.</p>
        <label className="block space-y-1">Inicio (segundos)
          <input aria-label="Inicio (segundos)" type="number" min="0" max="3600" step="0.001" value={start} onChange={e => setStart(e.target.value)} disabled={busy} className="block w-full rounded border border-line bg-ink-850 p-2 text-fg" />
        </label>
        {invalidOffset ? <p role="alert">El inicio debe estar entre 0 y 3600 segundos.</p> : null}
        {short ? <p role="alert">Vídeo demasiado corto: necesitas {duration.toFixed(3)} s desde el inicio indicado. Reduce la duración de salida, adelanta el inicio o usa un vídeo más largo. No se congela ni se repite el final.</p> : null}
        {error ? <p role="alert" className="text-warn">{error}</p> : null}
        {success ? <p role="status" className="text-accent">{success}</p> : null}
        <Button disabled={busy || invalidOffset || invalidDuration || short} onClick={() => void prepare()}>{busy ? 'Preparando guía…' : 'Crear guía 24 FPS'}</Button>
        {busy ? <p role="status">Preparando y verificando con CPU… Puedes cerrar este panel; no se inicia ningún render.</p> : null}
      </div>
    </DialogPanel>
  </Dialog>
}
