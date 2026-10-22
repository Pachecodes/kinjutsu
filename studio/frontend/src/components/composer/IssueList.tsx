import { AlertCircle, AlertTriangle, Info, Wrench } from 'lucide-react'
import type { ComponentType } from 'react'

import { useCachedConfig } from '../../hooks/queries'
import { localized, t, useT } from '../../i18n'
import { cn } from '../../lib/cn'
import { issueGuidance, sortIssues, type IssueFix } from '../../lib/issues'
import { missingTags, withTagsAppended } from '../../lib/references'
import type { Issue, Severity } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { useUi } from '../../state/ui'

const ICON: Record<Severity, ComponentType<{ className?: string }>> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const TONE: Record<Severity, string> = {
  error: 'border-danger/40 bg-danger-soft/40 text-danger',
  warning: 'border-warn/35 bg-warn-soft/35 text-warn',
  info: 'border-white/[0.07] bg-ink-850 text-muted',
}

const SEVERITY_LABEL: Record<Severity, string> = localized(() => ({ error: t('Bloquea'), warning: t('Aviso'), info: t('Nota') }))

const FIX_LABEL: Record<IssueFix, string> = localized(() => ({
  disable_continuity: t('Apagar continuidad'),
  guide_recipe: t('Usar Quality + Default'),
  mute_guide: t('Quitar sonido de la guía'),
  restore_swap_prompt: t('Restaurar texto de la receta'),
  append_tags: t('Añadir etiquetas'),
  open_references: t('Ver referencias'),
  open_advanced: t('Abrir Avanzado'),
}))

/** Applies a fix that is one unambiguous state change; anything else only navigates. */
function useIssueFix() {
  const cachedConfig = useCachedConfig()
  const setInspectorTab = useUi((state) => state.setInspectorTab)
  const setMobileView = useUi((state) => state.setMobileView)

  return (fix: IssueFix) => {
    const store = useComposer.getState()
    switch (fix) {
      case 'disable_continuity':
        store.setContinuity({ auto_split: false })
        return
      case 'guide_recipe':
        store.setMethod('baseline')
        store.setWeights('int8')
        return
      case 'mute_guide':
        for (const slot of store.references) {
          if (slot.role === 'aligned_guide' && slot.include_audio) store.setIncludeAudio(slot.uid, false)
        }
        return
      case 'restore_swap_prompt': {
        const recipe = cachedConfig()?.presets.find((preset) => preset.id === store.presetId)?.patch.prompt
        if (recipe) store.setPrompt(recipe)
        return
      }
      case 'append_tags':
        store.setPrompt(withTagsAppended(store.prompt, missingTags(store.mode, store.references, store.prompt)))
        return
      case 'open_references':
        setInspectorTab('references')
        setMobileView('refs')
        return
      case 'open_advanced':
        setInspectorTab('settings')
        setMobileView('compose')
        return
    }
  }
}

/**
 * Backend issues, shown next to the control they concern. The backend message
 * is never rewritten; a known code adds a plain headline and, when safe, a fix.
 */
export function IssueList({ issues, className, id }: { issues: Issue[]; className?: string; id?: string }) {
  useT()
  const applyFix = useIssueFix()
  const presetId = useComposer((state) => state.presetId)
  if (issues.length === 0) return null

  return (
    <ul id={id} className={cn('space-y-1.5', className)}>
      {sortIssues(issues).map((issue) => {
        const Icon = ICON[issue.severity]
        const guidance = issueGuidance(issue)
        const fix =
          guidance?.fix === 'restore_swap_prompt' && !presetId ? undefined : guidance?.fix
        return (
          <li
            key={`${issue.code}-${issue.field ?? ''}-${issue.message}`}
            className={cn('flex items-start gap-2 rounded-xl border px-2.5 py-2', TONE[issue.severity])}
          >
            <Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1 text-[11px] leading-snug">
              <span className="sr-only">{SEVERITY_LABEL[issue.severity]}: </span>
              {guidance ? <p className="font-semibold text-fg">{guidance.headline}</p> : null}
              <p className={guidance ? 'mt-0.5 opacity-80' : undefined}>{issue.message}</p>
            </div>
            {fix ? (
              <button
                type="button"
                onClick={() => applyFix(fix)}
                className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-lg border border-white/15 px-2 text-[10px] font-bold uppercase tracking-caps hover:bg-white/[0.06]"
              >
                <Wrench className="size-3" aria-hidden />
                {FIX_LABEL[fix]}
              </button>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
