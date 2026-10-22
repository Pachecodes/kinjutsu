import { AlertTriangle, Boxes, CheckCircle2, Download, HardDrive, Loader2, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { useId, useState } from 'react'

import { t, useT } from '../../i18n'
import { useFeatures, useLicenseText, useModelCatalog, useModelMutations, useModelStatus } from '../../hooks/features'
import { useCachedConfig } from '../../hooks/queries'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/cn'
import { HELP } from '../../lib/help'
import {
  CATEGORY_LABEL,
  STATE_LABEL,
  describeModel,
  fitsOnDisk,
  formatGiB,
  isActiveDownload,
  licenseName,
  missingBytes,
  modelState,
  partialInfo,
  type ModelState,
} from '../../lib/models'
import type { ManagedModel, ModelDownload } from '../../lib/types'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'
import { InfoTip } from '../ui/info-tip'
import { ProgressBar } from '../ui/progress'
import { EmptyState, ErrorState } from '../ui/states'
import { useToast } from '../ui/toast'

const STATE_TONE: Record<ModelState, string> = {
  verified: 'border-accent/35 bg-accent/10 text-accent',
  reused: 'border-accent/35 bg-accent/10 text-accent',
  installed_now: 'border-warn/40 bg-warn-soft/50 text-warn',
  missing: 'border-white/15 text-muted',
  queued: 'border-white/15 text-muted',
  downloading: 'border-accent/35 text-accent',
  verifying: 'border-accent/35 text-accent',
  cancelling: 'border-warn/40 text-warn',
  cancelled: 'border-warn/40 text-warn',
  error: 'border-danger/40 bg-danger-soft/40 text-danger',
}

function LicenseLine({ path, readable }: { path: string; readable: boolean }) {
  useT()
  const [open, setOpen] = useState(false)
  const name = licenseName(path)
  const text = useLicenseText(open ? name : null)
  return (
    <li className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px]">{path}</span>
        {readable ? (
          <button
            type="button"
            aria-expanded={open}
            aria-label={open ? t('Ocultar {name}', { name }) : t('Leer {name}', { name })}
            onClick={() => setOpen(!open)}
            className="rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] font-semibold text-fg hover:bg-white/[0.06]"
          >
            {open ? t('Ocultar') : t('Leer')}
          </button>
        ) : null}
      </div>
      {open ? (
        text.isLoading ? (
          <p className="text-[10px] text-faint">{t('Cargando licencia…')}</p>
        ) : text.isError ? (
          <p role="alert" className="text-[10px] text-danger">{t('No se pudo cargar esta licencia.')}</p>
        ) : (
          // Plain text only: React escapes it; never rendered as HTML or Markdown.
          <pre aria-label={t('Texto de {name}', { name })} className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-white/[0.06] bg-ink-950 p-2 text-[10px] leading-relaxed text-muted">
            {text.data}
          </pre>
        )
      ) : null}
    </li>
  )
}

function LicenseConsent({
  model,
  licenses,
  resume,
  onConfirm,
  onCancel,
  busy,
  readable,
}: {
  model: ManagedModel
  licenses: string[]
  resume: boolean
  readable: boolean
  onConfirm: () => void
  onCancel: () => void
  busy: boolean
}) {
  useT()
  const [accepted, setAccepted] = useState(false)
  const checkId = useId()
  const info = describeModel(model)
  return (
    <div role="group" aria-label={t('Licencia y descarga de {name}', { name: info.label })} className="mt-3 space-y-3 rounded-xl border border-white/10 bg-ink-950/60 p-3">
      <p className="text-[12px] font-semibold text-fg">
        {resume
          ? t('Reanudar {name} · {size}', { name: info.label, size: formatGiB(model.size) })
          : t('Descargar {name} · {size}', { name: info.label, size: formatGiB(model.size) })}
      </p>
      <ul className="space-y-1 text-[11px] leading-snug text-muted">
        <li>
          {t('Origen fijado:')} <span className="font-mono text-fg">huggingface.co/{model.repo}</span> · {t('revisión')}{' '}
          <span className="font-mono">{model.revision.slice(0, 7)}</span>. {t('No se aceptan otras URLs.')}
        </li>
        <li>
          {t('Destino:')} <span className="font-mono">models/{model.target}</span>.{' '}
          {t('Si ya hay un parcial, se reanuda; al final se comprueba el SHA256 antes de usarlo. Nunca se sobrescribe un archivo final.')}
        </li>
        <li>{t('Necesita espacio libre para lo que falte más 1 GB de margen; el backend lo comprueba antes de empezar.')}</li>
        <li>{t('No inicia ningún render. Al terminar hay que reiniciar Comfy (DETENER/INICIAR) cuando no haya renders.')}</li>
      </ul>
      <div className="text-[11px] text-muted">
        <p className="font-semibold text-fg">{readable ? t('Licencias:') : t('Licencias (en la carpeta del paquete):')}</p>
        <ul className="mt-1 space-y-1">
          {licenses.map((path) => (
            <LicenseLine key={path} path={path} readable={readable} />
          ))}
        </ul>
      </div>
      <label htmlFor={checkId} className="flex items-start gap-2 text-[12px] text-fg">
        <input
          id={checkId}
          type="checkbox"
          checked={accepted}
          onChange={(event) => setAccepted(event.target.checked)}
          className="mt-0.5 size-4 accent-[hsl(var(--accent))]"
        />
        {t('He leído las licencias y las acepto para este uso privado.')}
      </label>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          {t('No descargar')}
        </Button>
        <Button variant="primary" size="sm" disabled={!accepted} loading={busy} onClick={onConfirm}>
          <Download aria-hidden />
          {resume ? t('Reanudar {size}', { size: formatGiB(model.size) }) : t('Descargar {size}', { size: formatGiB(model.size) })}
        </Button>
      </div>
    </div>
  )
}

function ModelCard({
  model,
  job,
  licenses,
  freeBytes,
  readableLicenses,
}: {
  model: ManagedModel
  job: ModelDownload | undefined
  licenses: string[]
  freeBytes: number | undefined
  readableLicenses: boolean
}) {
  useT()
  const cachedConfig = useCachedConfig()
  const recipes = (model.required_by ?? []).map(
    (id) => cachedConfig()?.presets.find((preset) => preset.id === id)?.label ?? id,
  )
  const partial = partialInfo(model)
  const fits = fitsOnDisk(model, freeBytes)
  const { install, cancel } = useModelMutations()
  const { toast } = useToast()
  const [consenting, setConsenting] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const info = describeModel(model)
  const active = isActiveDownload(job)
  const state = modelState(model, job, cancelRequested && active)
  const badPartial = partial !== null && !partial.valid && !job
  const canInstall = (state === 'missing' || state === 'cancelled' || state === 'error') && !badPartial && fits !== false
  const resume =
    state === 'cancelled' || state === 'error' || (job !== undefined && job.bytes > 0 && !model.verified) || (partial?.valid ?? false)

  const confirm = async () => {
    setError(null)
    try {
      const result = await install.mutateAsync(model.id)
      setConsenting(false)
      setCancelRequested(false)
      if (result.status === 'installed' && result.reused) {
        toast({
          title: t('{name} ya estaba verificado', { name: info.label }),
          description: t('Se usa en su carpeta autorizada; no se descargó ni copió nada.'),
          tone: 'success',
        })
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t('No se pudo iniciar la descarga.'))
    }
  }

  const requestCancel = async () => {
    setError(null)
    try {
      await cancel.mutateAsync(model.id)
      setCancelRequested(true)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t('No se pudo pedir la cancelación.'))
    }
  }

  return (
    <li className="rounded-2xl border border-white/[0.06] bg-ink-850 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-1.5">
            <span className="text-[13px] font-semibold text-fg">{info.label}</span>
            <span className="rounded-md bg-white/[0.06] px-1.5 text-[10px] font-bold uppercase tracking-caps text-faint">
              {CATEGORY_LABEL[info.category]}
            </span>
            {model.included ? (
              <span className="rounded-md bg-white/[0.06] px-1.5 text-[10px] text-faint">{t('incluido en el paquete')}</span>
            ) : null}
          </p>
          <p className="mt-0.5 text-[11px] leading-snug text-muted">{info.purpose}</p>
          <p className="tabular mt-1 truncate font-mono text-[10px] text-faint" title={model.target}>
            {info.file} · {formatGiB(model.size)}
          </p>
        </div>
        <span className={cn('inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold', STATE_TONE[state])}>
          {state === 'verified' || state === 'reused' ? <CheckCircle2 className="size-3" aria-hidden /> : null}
          {active ? <Loader2 className="size-3 animate-spin" aria-hidden /> : null}
          {STATE_LABEL[state]}
        </span>
      </div>

      {recipes.length > 0 ? (
        <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[10px] text-faint">
          {t('Lo usa:')}
          {recipes.map((label) => (
            <span key={label} className="rounded-md border border-white/10 px-1.5 py-0.5 text-muted">
              {label}
            </span>
          ))}
        </p>
      ) : null}

      {partial && !job ? (
        partial.valid ? (
          <p className="mt-2 text-[11px] text-muted">
            {t('Hay una descarga parcial guardada: {done} de {total}. «Reanudar» continúa desde ahí y verifica el SHA256 al final.', {
              done: formatGiB(partial.bytes),
              total: formatGiB(model.size),
            })}
          </p>
        ) : (
          <p role="alert" className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {t('El parcial guardado es mayor que el tamaño fijado. No se reanuda: el administrador debe revisarlo en el equipo.')}
          </p>
        )
      ) : null}

      {fits === false && !model.verified && !active ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-[11px] text-warn">
          <HardDrive className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {t('No cabe en el disco: faltan {missing} más 1 GB de margen y hay {free} libres. Libera espacio en disco (no es VRAM).', {
            missing: formatGiB(model.size - (partial?.valid ? partial.bytes : 0)),
            free: formatGiB(freeBytes ?? 0),
          })}
        </p>
      ) : null}

      {state === 'reused' ? (
        <p className="mt-2 text-[11px] text-faint">{t('Encontrado y verificado en una carpeta autorizada: se usa ahí, sin copiarlo.')}</p>
      ) : null}

      {job && (active || state === 'cancelled' || state === 'error') ? (
        <div className="mt-2 space-y-1">
          <ProgressBar
            value={job.total > 0 ? job.bytes / job.total : null}
            label={t('Descarga de {name}', { name: info.label })}
          />
          <p className="tabular text-[10px] text-faint">
            {t('{done} de {total}', { done: formatGiB(job.bytes), total: formatGiB(job.total) })}
            {state === 'verifying' ? ` · ${t('comprobando SHA256, puede tardar')}` : ''}
            {state === 'cancelling' ? ` · ${t('la conexión puede tardar hasta 30 s en detenerse; el parcial se conserva')}` : ''}
          </p>
        </div>
      ) : null}

      {job?.error ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {job.error}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap justify-end gap-2">
        {canInstall && !consenting ? (
          <Button variant="outline" size="sm" onClick={() => setConsenting(true)}>
            <Download aria-hidden />
            {resume ? t('Reanudar…') : t('Instalar…')}
          </Button>
        ) : null}
        {active && state !== 'cancelling' ? (
          <Button variant="ghost" size="sm" loading={cancel.isPending} onClick={() => void requestCancel()}>
            <X aria-hidden />
            {t('Cancelar descarga')}
          </Button>
        ) : null}
      </div>

      {consenting ? (
        <LicenseConsent
          model={model}
          licenses={licenses}
          readable={readableLicenses}
          resume={resume}
          busy={install.isPending}
          onCancel={() => setConsenting(false)}
          onConfirm={() => void confirm()}
        />
      ) : null}
    </li>
  )
}

/** The pinned catalog: what is verified, reused, missing or downloading. */
export function ModelsPanel() {
  useT()
  const features = useFeatures()
  const [checking, setChecking] = useState(false)
  const catalog = useModelCatalog(checking)
  const status = useModelStatus(true)
  const jobs = new Map((status.data?.downloads ?? []).map((job) => [job.id, job]))
  const models = catalog.data?.models ?? []
  const verified = models.filter((model) => model.verified).length
  const installedThisSession = (status.data?.downloads ?? []).some((job) => job.status === 'installed' && !job.reused)
  const anyActive = (status.data?.downloads ?? []).some((job) => isActiveDownload(job))

  return (
    <div className="space-y-4">
      <p className="text-[12px] leading-relaxed text-muted">
        {t('Catálogo fijado del paquete: cada archivo tiene origen, revisión, tamaño y SHA256 fijos. Solo se buscan las carpetas autorizadas por el operador')}{' '}
        (<span className="font-mono text-[11px]">runtime/model-roots.json</span>),{' '}
        {t('nunca el disco entero, y lo ya verificado se reutiliza sin copiarlo.')}
      </p>

      {installedThisSession ? (
        <p role="status" className="flex items-start gap-2 rounded-xl border border-warn/40 bg-warn-soft/40 px-3 py-2 text-[12px] text-warn">
          <RefreshCw className="mt-0.5 size-4 shrink-0" aria-hidden />
          {t('Hay modelos nuevos. Reinicia Comfy con DETENER/INICIAR cuando no haya renders; hasta entonces no estarán disponibles para generar.')}
        </p>
      ) : null}

      {!checking ? (
        <EmptyState
          icon={HardDrive}
          title={t('Comprobar los modelos')}
          body={t('Verifica el SHA256 completo de cada archivo (decenas de GB). Puede tardar varios minutos y no descarga nada.')}
          action={
            <Button variant="primary" size="sm" onClick={() => setChecking(true)}>
              <ShieldCheck aria-hidden />
              {t('Comprobar ahora')}
            </Button>
          }
        />
      ) : catalog.isLoading ? (
        <div role="status" className="flex flex-col items-center gap-2 py-10 text-center">
          <Loader2 className="size-5 animate-spin text-accent" aria-hidden />
          <p className="text-[13px] font-semibold text-fg">{t('Verificando hashes…')}</p>
          <p className="max-w-sm text-[11px] text-faint">
            {t('Lee cada archivo completo para comprobar su SHA256. Puedes cerrar este panel; el resultado se guarda para esta sesión.')}
          </p>
        </div>
      ) : catalog.isError ? (
        <ErrorState
          title={t('No se pudo comprobar el catálogo')}
          message={catalog.error instanceof Error ? catalog.error.message : t('Error desconocido.')}
          onRetry={() => void catalog.refetch()}
          retrying={catalog.isFetching}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[12px] text-fg">
              <span className="font-semibold">
                {t('{verified} de {total} verificados', { verified, total: models.length })}
              </span>
              {catalog.data?.free_bytes !== undefined ? (
                <span className="text-muted"> · {t('{size} libres en disco (no VRAM)', { size: formatGiB(catalog.data.free_bytes) })}</span>
              ) : null}
              {missingBytes(models) > 0 ? (
                <span className="text-muted"> · {t('faltan {size}', { size: formatGiB(missingBytes(models)) })}</span>
              ) : (
                <span className="text-accent"> · {t('todo listo')}</span>
              )}
            </p>
            {catalog.data?.free_bytes !== undefined ? <InfoTip help={HELP.diskVsVram} label={t('Disco y VRAM')} /> : null}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto"
              disabled={anyActive}
              loading={catalog.isFetching}
              onClick={() => void catalog.refetch()}
            >
              <RefreshCw aria-hidden />
              {t('Volver a comprobar')}
            </Button>
          </div>
          <ul className="space-y-2">
            {models.map((model) => (
              <ModelCard
                key={model.id}
                model={model}
                job={jobs.get(model.id)}
                licenses={catalog.data?.license_documents ?? []}
                freeBytes={catalog.data?.free_bytes}
                readableLicenses={features.licenses}
              />
            ))}
          </ul>
          <p className="text-[11px] leading-snug text-faint">
            {t('Una sola descarga a la vez. Tener los modelos no garantiza que una receta funcione: también hacen falta los nodos y el runtime de Comfy. La disponibilidad real aparece en cada receta.')}
          </p>
        </>
      )}
    </div>
  )
}

/** Header entry point; it exists only when this backend serves the model manager. */
export function ModelsButton() {
  useT()
  const features = useFeatures()
  if (!features.models) return null
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={t('Modelos: comprobar e instalar')} data-tour="models-button">
          <Boxes aria-hidden />
          <span className="hidden sm:inline">{t('Modelos')}</span>
        </Button>
      </DialogTrigger>
      <DialogPanel
        title={t('Modelos')}
        description={t('Instalado, verificado, faltante o descargando. Nada se descarga sin tu consentimiento.')}
        className="w-[min(44rem,calc(100vw-1.5rem))]"
      >
        <ModelsPanel />
      </DialogPanel>
    </Dialog>
  )
}
