/**
 * Where a backend validation issue belongs on screen, and what a creator can do
 * about it.
 *
 * The backend message is always shown verbatim; this module only adds a plain
 * headline and, when the fix is a single unambiguous state change, a one-click
 * action. Unknown codes fall back to the raw message, never to a guess.
 */

import type { Issue, Severity } from './types'
import { localized, t } from '../i18n'

export type IssueArea = 'references' | 'prompt' | 'duration' | 'frame' | 'method' | 'advanced' | 'general'

const ADVANCED_FIELDS = [
  'weights',
  'encoder',
  'lora_chain',
  'sampler_name',
  'scheduler',
  'steps',
  'custom_sigmas',
  'ref_image_size',
  'seed',
  'continuity',
]

export function issueArea(issue: Issue): IssueArea {
  const field = issue.field ?? ''
  if (field.startsWith('references')) return 'references'
  if (field === 'prompt') return 'prompt'
  if (field === 'length') return 'duration'
  if (field === 'width' || field === 'height') return 'frame'
  if (field === 'method' || field.startsWith('easycache') || field.startsWith('sol')) return 'method'
  if (ADVANCED_FIELDS.some((name) => field.startsWith(name))) return 'advanced'
  return 'general'
}

export function issuesIn(issues: Issue[], ...areas: IssueArea[]): Issue[] {
  return issues.filter((issue) => areas.includes(issueArea(issue)))
}

const ORDER: Severity[] = ['error', 'warning', 'info']

export function sortIssues(issues: Issue[]): Issue[] {
  return [...issues].sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity))
}

/** One-click fixes the composer knows how to apply without guessing. */
export type IssueFix =
  | 'disable_continuity'
  | 'guide_recipe'
  | 'mute_guide'
  | 'restore_swap_prompt'
  | 'append_tags'
  | 'open_references'
  | 'open_advanced'

export interface IssueGuidance {
  headline: string
  fix?: IssueFix
  /**
   * A missing input the tray and recipe steps already show as an empty slot.
   * It still blocks Generate, but is not repeated as a red error.
   */
  pending?: boolean
}

const GUIDANCE: Record<string, IssueGuidance> = localized(() => ({
  // The guide card beside the tray already explains this with both numbers and both fixes.
  guide_alignment: { headline: t('La guía no coincide con la salida.'), pending: true },
  guide_metadata_missing: { headline: t('No se pudo certificar la guía (fps variables o metadatos ilegibles).') },
  guide_continuity: { headline: t('Una guía alineada necesita la continuidad automática apagada.'), fix: 'disable_continuity' },
  guide_recipe: { headline: t('La guía alineada solo funciona con Quality y el checkpoint Default (INT8).'), fix: 'guide_recipe' },
  guide_audio_unsupported: { headline: t('La guía alineada va sin sonido.'), fix: 'mute_guide' },
  guide_mode: { headline: t('Las guías alineadas requieren la tarea Referencias y una sola guía.'), fix: 'open_references' },
  guide_unavailable: { headline: t('El runtime de H3 no tiene los nodos de guía disponibles ahora mismo.') },
  character_swap_guide_required: { headline: t('Falta el vídeo guía: súbelo y márcalo como Guía alineada.'), fix: 'open_references', pending: true },
  character_swap_trigger: { headline: t('El prompt debe empezar por body_swap: y nombrar <Picture 1>.'), fix: 'restore_swap_prompt' },
  character_swap_identity: { headline: t('El retrato de identidad debe ser la primera imagen.'), fix: 'open_references', pending: true },
  character_swap_playground: { headline: t('Plantilla experimental: el vídeo es una referencia normal, no la guía aprobada.') },
  prompt_missing_reference_tags: { headline: t('Nombra cada referencia en el prompt.'), fix: 'append_tags' },
  references_required: { headline: t('Esta tarea necesita al menos una referencia.'), fix: 'open_references', pending: true },
  identity_image_required: { headline: t('Falta la imagen de identidad.'), fix: 'open_references', pending: true },
  motion_video_required: { headline: t('Falta el clip de movimiento.'), fix: 'open_references', pending: true },
  first_frame_required: { headline: t('Falta la imagen inicial.'), fix: 'open_references', pending: true },
  first_last_required: { headline: t('Faltan la imagen inicial y la final.'), fix: 'open_references', pending: true },
  unknown_asset: { headline: t('Una referencia ya no está en la biblioteca.'), fix: 'open_references' },
  custom_sigmas_invalid: { headline: t('Las sigmas manuales no son válidas.'), fix: 'open_advanced' },
  custom_sigmas_profile: { headline: t('Las sigmas manuales requieren Quality y continuidad apagada.'), fix: 'open_advanced' },
  lora_unavailable: { headline: t('Un LoRA de la cadena no está instalado.'), fix: 'open_advanced' },
  duplicate_lora: { headline: t('Hay un LoRA repetido en la cadena.'), fix: 'open_advanced' },
  checkpoint_missing: { headline: t('El checkpoint elegido no está instalado.'), fix: 'open_advanced' },
  ref_image_size_max_cost: { headline: t('Detalle máximo de referencias: el render puede tardar varias veces más.') },
  continuity_auto_split: { headline: t('La toma se dividirá en ventanas.') },
}))

export function issueGuidance(issue: Issue): IssueGuidance | null {
  return GUIDANCE[issue.code] ?? null
}

/** Issues worth showing inline: everything except inputs the tray already marks as missing. */
export function visibleIssues(issues: Issue[]): Issue[] {
  return issues.filter((issue) => !issueGuidance(issue)?.pending)
}

/** The one sentence Generate shows when it is blocked. */
export function blockingSentence(issue: Issue): string {
  return issueGuidance(issue)?.headline ?? issue.message
}
