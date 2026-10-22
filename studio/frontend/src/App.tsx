import { Compass, Images, Layers, PanelLeft, Play, ScrollText, SlidersHorizontal, Wand2 } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { CapabilityNotice } from './components/capability/CapabilityNotice'
import { HealthPill } from './components/capability/HealthPill'
import { Composer } from './components/composer/Composer'
import { RecipeChip } from './components/composer/ComposerChips'
import { ModeSwitch } from './components/composer/ModeSwitch'
import { Gallery } from './components/gallery/Gallery'
import { ModelsButton } from './components/models/ModelsDialog'
import { RecipeList } from './components/rail/RecipeRail'
import { ReferencesPanel } from './components/references/ReferencesPanel'
import { SettingsPanel } from './components/settings/SettingsPanel'
import { ActivityPanel } from './components/stage/ActivityPanel'
import { OutputStage } from './components/stage/OutputStage'
import { Tour, TourOffer } from './components/tour/Tour'
import { Button } from './components/ui/button'
import { EmptyState, ErrorState, Skeleton } from './components/ui/states'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs'
import { useConfig, useJob, useJobs } from './hooks/queries'
import { useIsDesktop } from './hooks/useMediaQuery'
import { BRAND } from './lib/brand'
import { cn } from './lib/cn'
import type { JobOut } from './lib/types'
import { useComposer } from './state/composer'
import { useUi, type MobileView } from './state/ui'

function Wordmark() {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <span aria-hidden className="flex size-7 items-center justify-center rounded-lg bg-accent text-[11px] font-black text-accent-ink">
        H3
      </span>
      <span className="display-title text-[15px] text-fg">{BRAND.product}</span>
      <span className="hidden text-[10px] font-bold uppercase tracking-caps text-faint sm:inline">{BRAND.tagline}</span>
    </div>
  )
}

/** The stage follows the newest take until the creator picks another one. */
function useStageJob(): { job: JobOut | null; loading: boolean; hasAnyTake: boolean } {
  const selectedJobId = useUi((state) => state.selectedJobId)
  const showHidden = useUi((state) => state.showHidden)
  const recent = useJobs({ includeHidden: showHidden, statuses: [] })
  const selected = useJob(selectedJobId)

  const newest = recent.data?.jobs[0] ?? null
  const job = selectedJobId ? (selected.data ?? null) : newest

  return {
    job,
    loading: selectedJobId ? selected.isLoading : recent.isLoading,
    hasAnyTake: (recent.data?.total ?? 0) > 0,
  }
}

const MOBILE_TABS: { id: MobileView; label: string; icon: typeof Play }[] = [
  { id: 'compose', label: 'Crear', icon: Wand2 },
  { id: 'stage', label: 'Escenario', icon: Play },
  { id: 'refs', label: 'Refs', icon: Layers },
  { id: 'gallery', label: 'Galería', icon: Images },
]

function GuideButton() {
  const openTour = useUi((state) => state.openTour)
  return (
    <Button variant="ghost" size="sm" onClick={() => openTour(0)} aria-label="Abrir la guía interactiva">
      <Compass aria-hidden />
      <span className="hidden sm:inline">Guía</span>
    </Button>
  )
}

export default function App() {
  const config = useConfig()
  const initialized = useRef(false)
  useEffect(() => {
    if (!config.data || initialized.current) return
    initialized.current = true
    const state = useComposer.getState()
    const preset = config.data.presets.find((item) => item.id === 'character-swap-hd-turbo8' && item.available)
    // Initialize only an empty composer; never replace a creator's existing draft.
    if (preset && !state.prompt && !state.title && !state.references.length && !state.presetId) state.applyPreset(preset)
  }, [config.data])
  const isDesktop = useIsDesktop()
  const inspectorTab = useUi((state) => state.inspectorTab)
  const setInspectorTab = useUi((state) => state.setInspectorTab)
  const mobileView = useUi((state) => state.mobileView)
  const setMobileView = useUi((state) => state.setMobileView)
  const referenceCount = useComposer((state) => state.references.length)
  const stage = useStageJob()
  const rendering = stage.job?.status === 'queued' || stage.job?.status === 'running'

  // Desktop shows every panel at once; the mobile tab state is meaningless there.
  useEffect(() => {
    if (isDesktop && mobileView !== 'compose') setMobileView('compose')
  }, [isDesktop, mobileView, setMobileView])

  if (config.isLoading) {
    return (
      <div className="flex h-full flex-col gap-3 p-4" aria-busy="true" aria-label={`Cargando ${BRAND.product}`}>
        <Skeleton className="h-12 w-full" />
        <div className="flex min-h-0 flex-1 gap-3">
          <Skeleton className="hidden w-72 lg:block" />
          <Skeleton className="flex-1" />
          <Skeleton className="hidden w-80 lg:block" />
        </div>
      </div>
    )
  }

  if (config.isError || !config.data) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-md space-y-4">
          <EmptyState
            icon={PanelLeft}
            title={`${BRAND.product} no encuentra su backend`}
            body="La API del Studio no respondió. Arranca el backend en esta máquina y vuelve a intentarlo."
          />
          <ErrorState
            title="Backend sin respuesta"
            message={config.error instanceof Error ? config.error.message : 'Error desconocido.'}
            onRetry={() => void config.refetch()}
            retrying={config.isFetching}
          />
        </div>
      </div>
    )
  }

  const { capabilities, presets } = config.data

  const inspector = (
    <Tabs
      value={inspectorTab}
      onValueChange={(value) => setInspectorTab(value as typeof inspectorTab)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <TabsList>
        <TabsTrigger value="references">
          <span className="flex items-center gap-1.5">
            <Layers className="size-3.5" aria-hidden />
            Referencias
          </span>
        </TabsTrigger>
        <TabsTrigger value="settings">
          <span className="flex items-center gap-1.5">
            <SlidersHorizontal className="size-3.5" aria-hidden />
            Avanzado
          </span>
        </TabsTrigger>
        <TabsTrigger value="activity">
          <span className="flex items-center gap-1.5">
            <ScrollText className="size-3.5" aria-hidden />
            Actividad
          </span>
        </TabsTrigger>
      </TabsList>
      <TabsContent value="references" className="relative min-h-0 flex-1 overflow-y-auto p-3">
        <ReferencesPanel config={config.data} />
      </TabsContent>
      <TabsContent value="settings" className="relative min-h-0 flex-1 overflow-y-auto p-3">
        <SettingsPanel capabilities={capabilities} />
      </TabsContent>
      <TabsContent value="activity" className="relative min-h-0 flex-1 overflow-y-auto p-3">
        <ActivityPanel job={stage.job} />
      </TabsContent>
    </Tabs>
  )

  return (
    <div className="flex h-full min-w-0 flex-col overflow-x-hidden bg-ink-950">
      <header className="safe-pt flex min-w-0 shrink-0 items-center gap-2 border-b border-white/[0.06] px-4 py-2 sm:gap-3">
        <Wordmark />
        <div className="ml-auto flex min-w-0 shrink-0 items-center gap-1">
          <ModelsButton />
          <GuideButton />
          <HealthPill />
        </div>
      </header>

      <CapabilityNotice capabilities={capabilities} />

      {isDesktop ? (
        <div className="flex min-h-0 flex-1">
          <aside aria-label="Recetas" className="relative w-[19rem] shrink-0 space-y-4 overflow-y-auto border-r border-white/[0.06] p-3">
            <TourOffer />
            <h2 className="eyebrow px-1 text-muted">Recetas</h2>
            <RecipeList presets={presets} comfyOnline={capabilities.comfy_online} />
          </aside>

          <main className="relative flex min-w-0 flex-1 flex-col overflow-y-auto">
            <div className="mx-auto flex w-full max-w-[72rem] flex-col gap-4 p-4">
              <OutputStage job={stage.job} loading={stage.loading} hasAnyTake={stage.hasAnyTake} />
              <div className="space-y-2.5">
                <ModeSwitch modes={capabilities.modes} comfyOnline={capabilities.comfy_online} className="w-fit" />
                <Composer config={config.data} capabilities={capabilities} />
              </div>
              <Gallery />
            </div>
          </main>

          <aside aria-label="Inspector" className="relative flex w-[23rem] shrink-0 flex-col overflow-hidden border-l border-white/[0.06]">
            {inspector}
          </aside>
        </div>
      ) : (
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden">
          <main className="safe-px relative min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto py-3">
            {mobileView === 'compose' ? (
              <div className="min-w-0 space-y-3">
                <TourOffer />
                <RecipeChip presets={presets} comfyOnline={capabilities.comfy_online} wide />
                <ModeSwitch modes={capabilities.modes} comfyOnline={capabilities.comfy_online} />
                <Composer config={config.data} capabilities={capabilities} />
                <section aria-label="Avanzado" className="panel p-3">
                  <h2 className="eyebrow mb-2 text-muted">Avanzado</h2>
                  <SettingsPanel capabilities={capabilities} />
                </section>
              </div>
            ) : mobileView === 'stage' ? (
              <div className="space-y-4">
                <OutputStage job={stage.job} loading={stage.loading} hasAnyTake={stage.hasAnyTake} />
                <section aria-label="Actividad" className="panel p-3">
                  <h2 className="eyebrow mb-2">Actividad</h2>
                  <ActivityPanel job={stage.job} />
                </section>
              </div>
            ) : mobileView === 'refs' ? (
              <div className="panel p-3">
                <ReferencesPanel config={config.data} />
              </div>
            ) : (
              <Gallery />
            )}
          </main>

          <nav
            aria-label="Secciones"
            className="safe-pb sticky bottom-0 grid shrink-0 grid-cols-4 border-t border-white/[0.06] bg-ink-900"
          >
            {MOBILE_TABS.map((tab) => {
              const Icon = tab.icon
              const active = mobileView === tab.id
              const badge = tab.id === 'refs' && referenceCount > 0 ? referenceCount : null
              return (
                <button
                  key={tab.id}
                  type="button"
                  aria-current={active ? 'page' : undefined}
                  onClick={() => setMobileView(tab.id)}
                  className={cn(
                    'relative flex min-h-14 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-colors',
                    active ? 'text-accent' : 'text-faint hover:text-muted',
                  )}
                >
                  <span className="relative">
                    <Icon className="size-5" aria-hidden />
                    {tab.id === 'stage' && rendering ? (
                      <span className="absolute -right-1 -top-0.5 size-2 rounded-full bg-accent animate-pulse-ring">
                        <span className="sr-only"> (generando)</span>
                      </span>
                    ) : null}
                    {badge !== null ? (
                      <span className="absolute -right-2.5 -top-1.5 min-w-4 rounded-full bg-accent px-1 text-center text-[9px] font-black leading-4 text-accent-ink">
                        {badge}
                        <span className="sr-only"> referencias</span>
                      </span>
                    ) : null}
                  </span>
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>
      )}

      <Tour />
    </div>
  )
}
