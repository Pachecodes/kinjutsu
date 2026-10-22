import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  ExternalLink,
  FolderOpen,
  HardDrive,
  Loader2,
  MonitorSmartphone,
  Play,
  RefreshCw,
  Search,
  Server,
} from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { useConfig } from '../../hooks/queries'
import { t, useT } from '../../i18n'
import {
  useFeatures,
  useModelStatus,
  useWorkstationActions,
  useWorkstationDiscovery,
  useWorkstationStatus,
} from '../../hooks/features'
import { ApiError } from '../../lib/api'
import { cn } from '../../lib/cn'
import { HELP, type HelpEntry } from '../../lib/help'
import { isActiveDownload } from '../../lib/models'
import type { RootCandidate, RuntimeCandidate, WorkstationStatus } from '../../lib/types'
import {
  BINDING_COPY,
  FOLDER_KINDS,
  FOLDER_LABEL,
  STATE_COPY,
  generatesHere,
  isLocalContext,
  type Tone,
} from '../../lib/workstation'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'
import { InfoTip } from '../ui/info-tip'
import { ErrorState } from '../ui/states'
import { useToast } from '../ui/toast'

const TONE: Record<Tone, string> = {
  ok: 'border-accent/35 bg-accent/[0.07] text-accent',
  busy: 'border-accent/30 bg-accent/[0.05] text-accent',
  idle: 'border-white/10 bg-white/[0.03] text-muted',
  warn: 'border-warn/40 bg-warn-soft/40 text-warn',
  error: 'border-danger/40 bg-danger-soft/40 text-danger',
}

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof Error ? error.message : fallback
}

function Section({
  title,
  icon: Icon,
  children,
  note,
  help,
}: {
  title: string
  icon: typeof Cpu
  children: ReactNode
  note?: ReactNode
  help?: HelpEntry
}) {
  return (
    <section aria-label={title} className="space-y-2.5 rounded-2xl border border-white/[0.06] bg-ink-850 p-3.5">
      <div className="flex items-center gap-1.5">
        <h3 className="flex items-center gap-1.5 text-[13px] font-semibold text-fg">
          <Icon className="size-4 text-accent" aria-hidden />
          {title}
        </h3>
        {help ? <InfoTip help={help} label={title} /> : null}
      </div>
      {note ? <div className="text-[11px] leading-snug text-faint">{note}</div> : null}
      {children}
    </section>
  )
}

/** Studio · engine · files, so nobody confuses opening a tab with starting a GPU process. */
function HowItFits() {
  useT()
  const items = [
    { title: 'Studio', body: t('Esta app. Prepara tomas, guarda historial y manda el trabajo al motor.') },
    { title: t('Motor ComfyUI'), body: t('El proceso que renderiza en la GPU. Puede estar detenido aunque Studio funcione.') },
    { title: t('Modelos y LoRAs'), body: t('Archivos en disco que el motor carga en VRAM al generar. Espacio en disco no es VRAM.') },
  ]
  return (
    <ol className="grid gap-2 sm:grid-cols-3" aria-label={t('Cómo encaja todo')}>
      {items.map((item, index) => (
        <li key={item.title} className="rounded-xl border border-white/[0.06] bg-ink-950/50 p-2.5">
          <p className="text-[11px] font-bold uppercase tracking-caps text-muted">
            {index + 1}. {item.title}
          </p>
          <p className="mt-1 text-[11px] leading-snug text-faint">{item.body}</p>
        </li>
      ))}
    </ol>
  )
}

function EngineSection({ status, comfyOnline }: { status: WorkstationStatus; comfyOnline: boolean }) {
  useT()
  const { start, open } = useWorkstationActions()
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const copy = STATE_COPY[status.state]
  const binding = BINDING_COPY[status.generation_binding]

  const doStart = async () => {
    setError(null)
    setNote(null)
    try {
      const result = await start.mutateAsync()
      setNote(
        result.state === 'online'
          ? t('Ya estaba en marcha: se reutilizó sin tocar sus trabajos.')
          : t('Arranque pedido. Arrancado aún no es listo: el estado se actualiza solo hasta «en línea».'),
      )
    } catch (cause) {
      setError(message(cause, t('No se pudo iniciar el motor.')))
    }
  }

  const doOpen = async () => {
    setError(null)
    setNote(null)
    try {
      await open.mutateAsync()
      setNote(t('Se pidió abrir ComfyUI en el navegador del equipo servidor. Si no ves la ventana, mírala en ese escritorio.'))
    } catch (cause) {
      setError(message(cause, t('No se pudo abrir ComfyUI.')))
    }
  }

  return (
    <Section title={t('Motor ComfyUI')} icon={Cpu} help={HELP.engine}>
      <div role="status" aria-live="polite" className={cn('rounded-xl border px-3 py-2.5', TONE[copy.tone])}>
        <p className="flex items-center gap-1.5 text-[13px] font-semibold">
          {status.state === 'starting' ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {status.state === 'online' ? <CheckCircle2 className="size-4" aria-hidden /> : null}
          {copy.label}
        </p>
        <p className="mt-1 text-[12px] leading-snug text-fg/90">{copy.body}</p>
        <p className="mt-1 text-[11px] leading-snug opacity-90">{copy.next}</p>
      </div>

      {status.label ? (
        <p className="text-[12px] text-muted">
          {t('Instalación elegida:')} <span className="font-semibold text-fg">{status.label}</span>
          {status.url ? <span className="font-mono text-[11px] text-faint"> · {status.url}</span> : null}
        </p>
      ) : null}

      <p
        className={cn(
          'rounded-xl border px-3 py-2 text-[11px] leading-snug',
          // A matching URL is only good news once the engine actually answers.
          TONE[generatesHere(status, comfyOnline) ? 'ok' : status.generation_binding === 'matches' ? 'idle' : binding.tone],
        )}
      >
        {generatesHere(status, comfyOnline)
          ? t('Esta instalación es la que genera tus tomas en Studio.')
          : binding.text}
      </p>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <Button variant="primary" size="sm" className="w-full" disabled={!status.capabilities.start} loading={start.isPending} onClick={() => void doStart()}>
            <Play aria-hidden />
            {t('Iniciar motor')}
          </Button>
          <p className="text-[10px] leading-snug text-faint">
            {status.capabilities.start
              ? t('Arranca el proceso ComfyUI aprobado en el equipo. Solo con el puerto libre; nunca detiene ni reinicia otro.')
              : t('Solo disponible con una instalación elegida, el motor detenido y su puerto libre.')}
          </p>
        </div>
        <div className="space-y-1">
          <Button variant="outline" size="sm" className="w-full" disabled={!status.capabilities.open_comfy} loading={open.isPending} onClick={() => void doOpen()}>
            <ExternalLink aria-hidden />
            {t('Abrir ComfyUI')}
          </Button>
          <p className="text-[10px] leading-snug text-faint">
            {t('Abre la interfaz de ComfyUI en el navegador del servidor. No arranca el motor: debe estar en línea.')}
          </p>
        </div>
      </div>
      {note ? <p role="status" className="text-[11px] text-accent">{note}</p> : null}
      {error ? (
        <p role="alert" className="flex items-start gap-1.5 text-[11px] text-danger">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
      <p className="text-[10px] text-faint">{t('No hay botón de detener ni reiniciar: este panel nunca interrumpe renders.')}</p>
    </Section>
  )
}

function FoldersSection({ status }: { status: WorkstationStatus }) {
  useT()
  const { folder } = useWorkstationActions()
  const { toast } = useToast()
  const [error, setError] = useState<string | null>(null)
  const anyFolder = FOLDER_KINDS.some((kind) => status.capabilities.folders[kind])

  const openFolder = async (kind: (typeof FOLDER_KINDS)[number]) => {
    setError(null)
    try {
      await folder.mutateAsync(kind)
      toast({
        title: t('Carpeta {folder} pedida', { folder: FOLDER_LABEL[kind] }),
        description: t('Se abre en el Explorador del equipo servidor.'),
        tone: 'info',
      })
    } catch (cause) {
      setError(message(cause, t('No se pudo abrir la carpeta.')))
    }
  }

  return (
    <Section
      title={t('Carpetas')}
      icon={FolderOpen}
      note={t('Abren el Explorador de Windows en el equipo servidor, no en tu teléfono. Solo las carpetas que el administrador aprobó para la instalación elegida.')}
    >
      <div className="flex flex-wrap gap-2">
        {FOLDER_KINDS.map((kind) => (
          <Button
            key={kind}
            variant="outline"
            size="sm"
            disabled={!status.capabilities.folders[kind] || folder.isPending}
            onClick={() => void openFolder(kind)}
          >
            <FolderOpen aria-hidden />
            {FOLDER_LABEL[kind]}
          </Button>
        ))}
      </div>
      {!anyFolder ? <p className="text-[11px] text-faint">{t('Elige una instalación aprobada para habilitar sus carpetas.')}</p> : null}
      {error ? <p role="alert" className="text-[11px] text-danger">{error}</p> : null}
    </Section>
  )
}

function Consent({ label, children, onConfirm, onCancel, busy, confirmLabel }: {
  label: string
  children: ReactNode
  onConfirm: () => void
  onCancel: () => void
  busy: boolean
  confirmLabel: string
}) {
  useT()
  const [accepted, setAccepted] = useState(false)
  const id = useId()
  return (
    <div role="group" aria-label={label} className="mt-2 space-y-2 rounded-xl border border-white/10 bg-ink-950/60 p-3 text-[11px] leading-snug text-muted">
      {children}
      <label htmlFor={id} className="flex items-start gap-2 text-[12px] text-fg">
        <input id={id} type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} className="mt-0.5 size-4 accent-[hsl(var(--accent))]" />
        {t('Lo entiendo y quiero continuar.')}
      </label>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          {t('Cancelar')}
        </Button>
        <Button variant="primary" size="sm" disabled={!accepted} loading={busy} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </div>
  )
}

function RuntimeRow({ runtime, selected }: { runtime: RuntimeCandidate; selected: boolean }) {
  useT()
  const { selectRuntime } = useWorkstationActions()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const confirm = async () => {
    setError(null)
    try {
      await selectRuntime.mutateAsync(runtime.id)
      setDone(true)
      setAsking(false)
    } catch (cause) {
      setError(message(cause, t('No se pudo elegir esta instalación.')))
    }
  }

  return (
    <li className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-fg">{runtime.label}</p>
          <p className="truncate font-mono text-[10px] text-faint" title={runtime.location}>{runtime.location}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {selected ? <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-semibold', TONE.ok)}>{t('Elegida')}</span> : null}
          <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-semibold', runtime.approved ? TONE.ok : TONE.idle)}>
            {runtime.approved ? t('Aprobada') : t('Solo detectada')}
          </span>
          <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-semibold', runtime.online ? TONE.busy : TONE.idle)}>
            {runtime.online ? t('Respondió ahora') : t('Sin respuesta')}
          </span>
        </div>
      </div>
      {!runtime.approved ? (
        <p className="mt-2 text-[11px] leading-snug text-faint">
          {t('Detectada no es aprobada: el administrador debe autorizarla en la configuración local del equipo antes de poder elegirla o arrancarla.')}
        </p>
      ) : null}
      {runtime.approved && !selected && !done && !asking ? (
        <Button variant="outline" size="sm" className="mt-2" onClick={() => setAsking(true)}>
          {t('Usar esta instalación…')}
        </Button>
      ) : null}
      {asking ? (
        <Consent
          label={t('Usar {name}', { name: runtime.label })}
          busy={selectRuntime.isPending}
          confirmLabel={t('Usar esta instalación')}
          onCancel={() => setAsking(false)}
          onConfirm={() => void confirm()}
        >
          <p>{t('Studio usará este ComfyUI y sus carpetas tal como están: no copia ni mueve modelos.')}</p>
          <p>{t('No arranca el motor ni cambia con qué genera Studio ahora mismo; eso lo ajusta el administrador sin renders en curso.')}</p>
        </Consent>
      ) : null}
      {done ? (
        <p role="status" className="mt-2 text-[11px] text-accent">
          {t('Elegida. La generación no se ha redirigido; revisa el estado del motor arriba.')}
        </p>
      ) : null}
      {error ? <p role="alert" className="mt-2 text-[11px] text-danger">{error}</p> : null}
    </li>
  )
}

function RootRow({ root, selectedId, downloading }: { root: RootCandidate; selectedId: string | null; downloading: boolean }) {
  useT()
  const { selectRoot } = useWorkstationActions()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)
  const already = root.runtime_id === null
  const adoptable = root.approved && !already && root.runtime_id === selectedId

  const confirm = async () => {
    setError(null)
    try {
      const outcome = await selectRoot.mutateAsync(root.id)
      setAsking(false)
      setResult(
        (outcome.verified_models === 1
          ? t('1 modelo verificado por SHA256 y reutilizados sin copiar.')
          : t('{n} modelos verificados por SHA256 y reutilizados sin copiar.', { n: outcome.verified_models })) +
          (outcome.restart_required ? ' ' + t('Reinicia Comfy (DETENER/INICIAR) en un momento sin renders para que los vea.') : ''),
      )
    } catch (cause) {
      setError(message(cause, t('No se pudo verificar esta carpeta.')))
    }
  }

  return (
    <li className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-fg">{root.label}</p>
          <p className="truncate font-mono text-[10px] text-faint" title={root.location}>{root.location}</p>
        </div>
        <span className={cn('rounded-full border px-2 py-0.5 text-[10px] font-semibold', already ? TONE.ok : root.approved ? TONE.busy : TONE.idle)}>
          {already ? t('Ya autorizada para Modelos') : root.approved ? t('Aprobada · sin verificar') : t('Solo detectada')}
        </span>
      </div>
      {adoptable && !asking && !result ? (
        <Button variant="outline" size="sm" className="mt-2" disabled={downloading} onClick={() => setAsking(true)}>
          <HardDrive aria-hidden />
          {t('Verificar y reutilizar…')}
        </Button>
      ) : null}
      {adoptable && downloading ? (
        <p className="mt-1 text-[11px] text-warn">{t('Espera a que termine la descarga de modelos en curso.')}</p>
      ) : null}
      {root.approved && !already && root.runtime_id !== selectedId ? (
        <p className="mt-2 text-[11px] text-faint">{t('Pertenece a otra instalación: elige esa instalación primero.')}</p>
      ) : null}
      {asking ? (
        <Consent
          label={t('Reutilizar {name}', { name: root.label })}
          busy={selectRoot.isPending}
          confirmLabel={t('Verificar y reutilizar')}
          onCancel={() => setAsking(false)}
          onConfirm={() => void confirm()}
        >
          <p>{t('Comprueba el SHA256 completo de los modelos del manifiesto que haya en esta carpeta. Puede tardar varios minutos; no cierres Studio.')}</p>
          <p>{t('No copia, mueve ni descarga pesos, y no modifica la configuración de otro ComfyUI. Los que falten seguirán faltando.')}</p>
        </Consent>
      ) : null}
      {selectRoot.isPending ? (
        <p role="status" className="mt-2 flex items-center gap-1.5 text-[11px] text-accent">
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {t('Verificando SHA256… puede tardar varios minutos.')}
        </p>
      ) : null}
      {result ? <p role="status" className="mt-2 text-[11px] text-accent">{result}</p> : null}
      {error ? <p role="alert" className="mt-2 text-[11px] text-danger">{error}</p> : null}
    </li>
  )
}

function DiscoverySection({ selectedId, modelsEnabled }: { selectedId: string | null; modelsEnabled: boolean }) {
  useT()
  const [searching, setSearching] = useState(false)
  const discovery = useWorkstationDiscovery(searching)
  const modelStatus = useModelStatus(modelsEnabled)
  const downloading = (modelStatus.data?.downloads ?? []).some((job) => isActiveDownload(job))

  return (
    <Section
      title={t('Instalaciones de ComfyUI')}
      icon={Search}
      help={HELP.installation}
      note={t('Busca solo en ubicaciones conocidas y carpetas que el administrador autorizó, durante unos 2 s, sin recorrer el disco ni descargar nada. Encontrar una instalación no la aprueba.')}
    >
      <div className="flex flex-wrap gap-2">
        <Button
          variant={searching ? 'ghost' : 'primary'}
          size="sm"
          loading={discovery.isFetching}
          onClick={() => (searching ? void discovery.refetch() : setSearching(true))}
        >
          <Search aria-hidden />
          {searching ? t('Buscar otra vez') : t('Buscar instalaciones')}
        </Button>
      </div>
      {discovery.isError ? (
        <ErrorState title={t('No se pudo buscar')} message={message(discovery.error, t('Error desconocido.'))} onRetry={() => void discovery.refetch()} />
      ) : null}
      {discovery.data ? (
        <div className="space-y-3">
          {discovery.data.runtimes.length === 0 ? (
            <p className="text-[12px] text-muted">
              {t('No se encontró ningún ComfyUI en las ubicaciones conocidas. Configura uno en este equipo y vuelve a buscar.')}
            </p>
          ) : (
            <ul className="space-y-2" aria-label={t('Instalaciones encontradas')}>
              {discovery.data.runtimes.map((runtime) => (
                <RuntimeRow key={runtime.id} runtime={runtime} selected={runtime.id === selectedId} />
              ))}
            </ul>
          )}
          {discovery.data.roots.length > 0 ? (
            <div className="space-y-2">
              <h4 className="eyebrow">{t('Carpetas de modelos')}</h4>
              <ul className="space-y-2" aria-label={t('Carpetas de modelos encontradas')}>
                {discovery.data.roots.map((root) => (
                  <RootRow key={root.id} root={root} selectedId={selectedId} downloading={downloading} />
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </Section>
  )
}

function RemoteNotice() {
  useT()
  return (
    <div role="note" className="space-y-2 rounded-2xl border border-white/10 bg-ink-850 p-4">
      <p className="flex items-center gap-2 text-[14px] font-semibold text-fg">
        <MonitorSmartphone className="size-4 text-accent" aria-hidden />
        {t('Solo desde el propio equipo')}
      </p>
      <p className="text-[12px] leading-relaxed text-muted">
        {t('Estos controles arrancan el motor y abren carpetas o el navegador')}{' '}
        <strong className="text-fg">{t('en el Windows del servidor')}</strong>
        {t('. Por seguridad solo responden cuando Studio se abre en ese equipo (localhost); desde la red o el teléfono quedan desactivados a propósito.')}
      </p>
      <p className="text-[12px] leading-relaxed text-muted">
        {t('Para usarlos, abre Studio en el navegador del propio servidor. Generar, Modelos y Plantilla siguen funcionando aquí.')}
      </p>
    </div>
  )
}

/** Installation · ComfyUI engine · folders. Every action is an explicit button. */
export function WorkstationPanel({ local = isLocalContext() }: { local?: boolean } = {}) {
  useT()
  const features = useFeatures()
  const config = useConfig()
  const status = useWorkstationStatus(local)
  const forbidden = status.error instanceof ApiError && status.error.status === 403

  if (!local || forbidden) return <RemoteNotice />

  return (
    <div className="space-y-3">
      <HowItFits />
      {status.isLoading ? (
        <p role="status" className="flex items-center gap-2 text-[12px] text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {t('Leyendo el estado del equipo…')}
        </p>
      ) : status.isError ? (
        <ErrorState title={t('No se pudo leer el estado')} message={message(status.error, t('Error desconocido.'))} onRetry={() => void status.refetch()} retrying={status.isFetching} />
      ) : status.data ? (
        <>
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" loading={status.isFetching} onClick={() => void status.refetch()}>
              <RefreshCw aria-hidden />
              {t('Actualizar estado')}
            </Button>
          </div>
          <EngineSection status={status.data} comfyOnline={config.data?.capabilities.comfy_online ?? false} />
          <FoldersSection status={status.data} />
          <DiscoverySection selectedId={status.data.selected_id} modelsEnabled={features.models} />
        </>
      ) : null}
    </div>
  )
}

/** Header entry point; present only when this backend serves the workstation API. */
export function WorkstationButton() {
  useT()
  const features = useFeatures()
  if (!features.workstation) return null
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={t('Instalación: motor ComfyUI y carpetas')} data-tour="workstation">
          <Server aria-hidden />
          <span className="hidden md:inline">{t('Instalación')}</span>
        </Button>
      </DialogTrigger>
      <DialogPanel
        title={t('Instalación · ComfyUI · Carpetas')}
        description={t('Estado del motor que renderiza, qué instalación usa este equipo y sus carpetas. Nada se arranca, descarga ni copia sin que lo pidas.')}
        className="w-[min(46rem,calc(100vw-1.5rem))]"
      >
        <WorkstationPanel />
      </DialogPanel>
    </Dialog>
  )
}
