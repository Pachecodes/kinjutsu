import { localizedList, t } from '../i18n'
/**
 * Deterministic prompt template.
 *
 * It only arranges what the creator typed and the shot vocabulary they picked
 * into a predictable order. It never looks at references, never rewrites the
 * creator's words, and is never presented as analysis or "smart" enhancement.
 */

export interface ShotOption {
  id: string
  /** What the creator reads. */
  label: string
  /** What H3 reads; the presets and model card are written in English. */
  text: string
}

export const CAMERA_OPTIONS: ShotOption[] = localizedList(() => [
  { id: 'static', label: t('Plano fijo'), text: 'static locked-off camera' },
  { id: 'push', label: t('Acercamiento lento'), text: 'slow push-in' },
  { id: 'pull', label: t('Alejamiento lento'), text: 'slow pull-back' },
  { id: 'tracking', label: t('Travelling lateral'), text: 'smooth lateral tracking shot' },
  { id: 'handheld', label: t('Cámara en mano'), text: 'subtle handheld camera movement' },
  { id: 'orbit', label: t('Órbita'), text: 'slow orbit around the subject' },
  { id: 'closeup', label: t('Primer plano'), text: 'close-up framing' },
  { id: 'medium', label: t('Plano medio'), text: 'medium shot' },
  { id: 'wide', label: t('Plano general'), text: 'wide establishing shot' },
  { id: 'low', label: t('Contrapicado'), text: 'low-angle shot' },
])

export const LIGHT_OPTIONS: ShotOption[] = localizedList(() => [
  { id: 'golden', label: t('Hora dorada'), text: 'warm golden-hour sunlight' },
  { id: 'daylight', label: t('Luz de día suave'), text: 'soft natural daylight' },
  { id: 'overcast', label: t('Nublado'), text: 'diffused overcast light' },
  { id: 'night', label: t('Noche con neones'), text: 'night scene lit by neon signs' },
  { id: 'lowkey', label: t('Contraste dramático'), text: 'moody low-key lighting with deep shadows' },
  { id: 'practical', label: t('Luces cálidas de interior'), text: 'warm practical interior lights' },
  { id: 'studio', label: t('Estudio'), text: 'clean studio softbox lighting' },
  { id: 'film', label: t('Look de cine'), text: 'cinematic film look, natural grain' },
])

export interface PromptFields {
  subject: string
  action: string
  scene: string
  camera: string[]
  light: string[]
  sound: string
}

export const EMPTY_FIELDS: PromptFields = {
  subject: '',
  action: '',
  scene: '',
  camera: [],
  light: [],
  sound: '',
}

function sentence(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ')
  if (!trimmed) return ''
  return /[.!?…]$/.test(trimmed) ? trimmed : `${trimmed}.`
}

function phrases(ids: string[], options: ShotOption[]): string {
  return options
    .filter((option) => ids.includes(option.id))
    .map((option) => option.text)
    .join(', ')
}

/** Subject → action → setting → camera → light → sound, skipping what is empty. */
export function buildPrompt(fields: PromptFields): string {
  const camera = phrases(fields.camera, CAMERA_OPTIONS)
  const light = phrases(fields.light, LIGHT_OPTIONS)
  return [
    sentence(fields.subject),
    sentence(fields.action),
    fields.scene.trim() ? sentence(`Setting: ${fields.scene}`) : '',
    camera ? sentence(`Camera: ${camera}`) : '',
    light ? sentence(`Lighting and mood: ${light}`) : '',
    fields.sound.trim() ? sentence(`Sound: ${fields.sound}`) : '',
  ]
    .filter(Boolean)
    .join(' ')
}

/**
 * Guide-driven swaps: the aligned guide already owns scene, pose and camera, so
 * the template only adds direction after the recipe's own text and never
 * touches the `body_swap:` trigger.
 */
export function buildSwapDirection(fields: Pick<PromptFields, 'subject' | 'light' | 'sound'>): string {
  const light = phrases(fields.light, LIGHT_OPTIONS)
  const parts = [
    fields.subject.trim() ? sentence(`Character details for <Picture 1>: ${fields.subject}`) : '',
    light ? sentence(`Lighting and mood: ${light}`) : '',
    fields.sound.trim() ? sentence(`Sound: ${fields.sound}`) : '',
  ].filter(Boolean)
  return parts.join(' ')
}

export function appendToPrompt(current: string, addition: string): string {
  const base = current.trimEnd()
  const extra = addition.trim()
  if (!extra) return current
  return base ? `${base} ${extra}` : extra
}

/** What the approved swap needs from the prompt, mirrored from the validator. */
export function swapPromptReady(prompt: string): boolean {
  return prompt.trimStart().startsWith('body_swap:') && prompt.includes('<Picture 1>')
}
