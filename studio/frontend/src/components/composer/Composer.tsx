import { Info, Sparkles } from 'lucide-react'

import { useComposerRequest } from '../../hooks/useComposerRequest'
import { generateGate, useGenerate } from '../../hooks/useGenerate'
import { useValidation } from '../../hooks/queries'
import { useIsDesktop } from '../../hooks/useMediaQuery'
import { t, useT } from '../../i18n'
import { BRAND } from '../../lib/brand'
import { formatSeconds } from '../../lib/format'
import { issuesIn, visibleIssues } from '../../lib/issues'
import type { CapabilityResponse, Issue, StudioConfig } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { GuideSync } from '../references/GuideSync'
import { Button } from '../ui/button'
import { InfoTip } from '../ui/info-tip'
import { AdvancedChip, DurationChip, FrameChip, MethodChip, RecipeChip, SeedChip } from './ComposerChips'
import { IssueList } from './IssueList'
import { PromptComposer } from './PromptComposer'
import { RecipeChecklist } from './RecipeChecklist'
import { ReferenceTray } from './ReferenceTray'

interface ComposerProps {
  config: StudioConfig
  capabilities: CapabilityResponse
}

/**
 * The creator's one object: references on top, the prompt in the middle, the
 * settings that matter as chips, and the single Generate action. Everything
 * technical is one tap away in Advanced, never in the way.
 */
export function Composer({ config, capabilities }: ComposerProps) {
  useT()
  const request = useComposerRequest()
  const notice = useComposer((state) => state.notice)
  const isDesktop = useIsDesktop()
  const setNotice = useComposer((state) => state.setNotice)

  // Validation is pure server-side math, so it stays useful even when the lab
  // instance is down — the creator can keep shaping a take offline.
  const validation = useValidation(request, true)
  const { generate, pending } = useGenerate()

  const issues: Issue[] = validation.data?.issues ?? []
  const { blockedReason } = generateGate(request, capabilities, issues)
  const estimate = validation.data?.estimate_seconds ?? null
  const shown = visibleIssues(issues)
  const referenceIssues = issuesIn(shown, 'references')
  const promptIssues = issuesIn(shown, 'prompt')
  const settingIssues = issuesIn(shown, 'duration', 'frame', 'method', 'advanced', 'general').filter(
    // The continuity plan is shown as its own note below.
    (issue) => issue.code !== 'continuity_auto_split',
  )

  return (
    <section aria-label={t('Compositor')} className="shell flex min-w-0 flex-col gap-3 p-2.5 md:p-3">
      <RecipeChecklist />

      {notice ? (
        <div
          role="status"
          className="flex items-start gap-2 rounded-xl border border-warn/35 bg-warn-soft/35 px-2.5 py-2 text-[11px] text-warn"
        >
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span className="flex-1">{notice}</span>
          <button type="button" className="font-semibold underline underline-offset-2" onClick={() => setNotice(null)}>
            {t('Entendido')}
          </button>
        </div>
      ) : null}

      <ReferenceTray />
      <GuideSync />
      {referenceIssues.length ? <IssueList issues={referenceIssues} /> : null}

      <PromptComposer issues={promptIssues} />

      {validation.data?.continuity_plan?.split ? (
        <p className="rounded-xl border border-accent/30 bg-accent/[0.07] px-3 py-2 text-[11px] leading-snug text-accent">
          <span className="font-semibold">{t('Plan de continuidad · ')}</span>
          {validation.data.continuity_plan.summary}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5 border-t border-white/[0.05] pt-3" data-tour="settings-chips">
        {/* Phones show the recipe as a full-width picker above the task switch. */}
        {isDesktop ? <RecipeChip presets={config.presets} comfyOnline={capabilities.comfy_online} /> : null}
        <DurationChip capabilities={capabilities} />
        <FrameChip />
        <MethodChip capabilities={capabilities} />
        <SeedChip />
        <AdvancedChip />
      </div>

      {settingIssues.length ? <IssueList issues={settingIssues} /> : null}

      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2" data-tour="generate">
        <span className="tabular mr-auto flex items-center gap-1 text-[11px] text-faint">
          {validation.isFetching && !validation.data
            ? t('Comprobando…')
            : estimate !== null
              ? t('≈ {time} estimado', { time: formatSeconds(estimate) })
              : t('Sin estimación')}
          <InfoTip
            label={t('Estimación')}
            help={{
              what: t('Estimación a partir de tiempos medidos en {machine}. No es un compromiso.', { machine: BRAND.machine }),
              cost: t('Preparar referencias, renderizar y decodificar pueden durar muy distinto según la toma.'),
              when: config.estimate_basis,
            }}
          />
        </span>
        <Button
          variant="cta"
          size="lg"
          loading={pending}
          disabled={blockedReason !== null}
          onClick={() => void generate(request)}
          aria-describedby={blockedReason ? 'generate-blocked' : undefined}
          aria-label={
            pending
              ? t('Enviando la toma')
              : estimate !== null
                ? t('Generar toma, unos {time} estimados', { time: formatSeconds(estimate) })
                : t('Generar toma')
          }
          className="min-w-[10rem] rounded-[13px]"
        >
          {pending ? (
            t('Enviando…')
          ) : (
            <>
              {t('Generar')}
              <Sparkles className="fill-current" aria-hidden />
            </>
          )}
        </Button>
      </div>

      {blockedReason ? (
        <p id="generate-blocked" role="status" className="-mt-1 text-right text-[11px] text-faint">
          {blockedReason}
        </p>
      ) : null}
    </section>
  )
}
