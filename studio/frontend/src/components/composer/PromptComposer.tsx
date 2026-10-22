import { Loader2, MessageSquareText, RotateCcw, Sparkles, Tag, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { ApiError, api } from '../../lib/api'
import { cn } from '../../lib/cn'
import {
  isReferenceMode,
  missingTags,
  referenceTags,
  toReferenceInputs,
  withTagsAppended,
} from '../../lib/references'
import { HELP } from '../../lib/help'
import type { DirectorResponse, Issue } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { Button } from '../ui/button'
import { Dialog, DialogPanel } from '../ui/dialog'
import { Input, Textarea } from '../ui/field'
import { InfoTip } from '../ui/info-tip'
import { IssueList } from './IssueList'
import { PromptBuilder } from './PromptBuilder'
import { PromptChatDialog } from './PromptChatDialog'

/** Prompt authoring, exact reference tokens, and non-destructive local AI direction. */
export function PromptComposer({ issues = [] }: { issues?: Issue[] } = {}) {
  const mode = useComposer((state) => state.mode)
  const prompt = useComposer((state) => state.prompt)
  const title = useComposer((state) => state.title)
  const length = useComposer((state) => state.length)
  const references = useComposer((state) => state.references)
  const setPrompt = useComposer((state) => state.setPrompt)
  const setTitle = useComposer((state) => state.setTitle)

  const textarea = useRef<HTMLTextAreaElement>(null)
  const [directing, setDirecting] = useState(false)
  const [preview, setPreview] = useState<DirectorResponse | null>(null)
  const [directorError, setDirectorError] = useState<string | null>(null)
  const [previousPrompt, setPreviousPrompt] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)

  const tags = referenceTags(mode, references).filter((tag): tag is string => tag !== null)
  const missing = missingTags(mode, references, prompt)
  const hasGuide = references.some((slot) => slot.role === 'aligned_guide')

  const insertTag = (tag: string) => {
    const node = textarea.current
    if (!node) {
      setPrompt(withTagsAppended(prompt, [tag]))
      return
    }
    const start = node.selectionStart ?? prompt.length
    const end = node.selectionEnd ?? prompt.length
    const before = prompt.slice(0, start)
    const after = prompt.slice(end)
    const spacer = before && !before.endsWith(' ') ? ' ' : ''
    const next = `${before}${spacer}${tag}${after.startsWith(' ') || !after ? '' : ' '}${after}`
    setPrompt(next)
    requestAnimationFrame(() => {
      const caret = before.length + spacer.length + tag.length
      node.focus()
      node.setSelectionRange(caret, caret)
    })
  }

  const directPrompt = async () => {
    if (!prompt.trim() || directing) return
    setDirectorError(null)
    setDirecting(true)
    try {
      setPreview(
        await api.enhancePrompt({
          mode,
          prompt,
          length,
          references: toReferenceInputs(references),
        }),
      )
    } catch (error) {
      setDirectorError(error instanceof ApiError ? error.message : 'AI Director no pudo preparar una propuesta.')
    } finally {
      setDirecting(false)
    }
  }

  const applyPreview = () => {
    if (!preview) return
    setPreviousPrompt(prompt)
    setPrompt(preview.enhanced_prompt)
    setPreview(null)
  }

  const applyChatPrompt = (nextPrompt: string) => {
    setPreviousPrompt(prompt)
    setPrompt(nextPrompt)
    setChatOpen(false)
  }

  return (
    <div className="space-y-2" data-tour="prompt">
      <div className="flex items-center gap-2 px-1">
        <Input
          value={title}
          maxLength={120}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Toma sin título"
          aria-label="Título de la toma"
          className="h-8 flex-1 border-transparent bg-transparent px-0 text-[13px] font-semibold text-fg placeholder:text-faint hover:border-transparent focus:border-transparent"
        />
        {prompt ? (
          <Button variant="ghost" size="icon-sm" aria-label="Borrar prompt" onClick={() => setPrompt('')} title="Borrar prompt">
            <Trash2 aria-hidden />
          </Button>
        ) : null}
      </div>

      <div className="relative">
        <Textarea
          ref={textarea}
          value={prompt}
          rows={4}
          maxLength={20000}
          aria-label="Prompt"
          aria-describedby={issues.length ? 'prompt-issues' : undefined}
          data-focus="prompt"
          onChange={(event) => setPrompt(event.target.value)}
          placeholder={
            hasGuide
              ? 'body_swap: describe al personaje de <Picture 1>. La guía ya aporta escena, pose y cámara.'
              : isReferenceMode(mode)
                ? 'Describe la toma y nombra cada referencia: «<Picture 1> entra en cuadro mientras <Video 1> panea a la izquierda…»'
                : 'Describe la toma: sujeto, acción, cámara, luz y el sonido que quieres que H3 escriba.'
          }
          className="min-h-[7rem] border-transparent bg-transparent px-1 pb-6 text-[16px] leading-relaxed hover:border-transparent focus:border-transparent md:text-[15px]"
        />
        <span className="pointer-events-none absolute bottom-1 right-1 tabular text-[10px] text-faint">
          {prompt.length.toLocaleString('es')} / 20.000
        </span>
      </div>

      {issues.length ? <IssueList id="prompt-issues" issues={issues} /> : null}

      <div className="flex flex-wrap items-center gap-1.5">
        <PromptBuilder />
        {tags.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1" aria-label="Etiquetas de referencias">
            <Tag className="ml-1 size-3 text-faint" aria-hidden />
            {tags.map((tag) => {
              const present = prompt.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => insertTag(tag)}
                  title={present ? `${tag} ya está en el prompt` : `Insertar ${tag} en el cursor`}
                  aria-label={present ? `${tag} ya está en el prompt; insertar otra vez` : `Insertar ${tag}`}
                  className={cn(
                    'min-h-8 rounded-lg border px-1.5 py-0.5 font-mono text-[10px] transition-colors',
                    present
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : 'border-white/10 bg-white/[0.03] text-faint hover:border-white/25 hover:text-fg',
                  )}
                >
                  {tag}
                </button>
              )
            })}
            {missing.length > 0 ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-[11px]"
                onClick={() => setPrompt(withTagsAppended(prompt, missing))}
              >
                Añadir {missing.length} {missing.length === 1 ? 'etiqueta' : 'etiquetas'}
              </Button>
            ) : null}
            <InfoTip help={HELP.promptTags} label="Etiquetas de referencias" />
          </div>
        ) : null}

        <div className="ml-auto flex flex-wrap items-center gap-1">
          <span className="eyebrow mr-0.5 hidden sm:inline">IA opcional</span>
          <Button variant="ghost" size="sm" disabled={hasGuide} onClick={() => setChatOpen(true)} aria-label="GPU Prompt Chat">
            <MessageSquareText aria-hidden />
            Chat
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={!prompt.trim() || directing || hasGuide}
            onClick={() => void directPrompt()}
            aria-label="AI Director"
          >
            {directing ? <Loader2 className="animate-spin" aria-hidden /> : <Sparkles aria-hidden />}
            {directing ? 'Dirigiendo…' : 'Director'}
          </Button>
          {previousPrompt !== null ? (
            <Button
              variant="ghost"
              size="sm"
              aria-label="Undo AI Director"
              onClick={() => {
                setPrompt(previousPrompt)
                setPreviousPrompt(null)
              }}
            >
              <RotateCcw aria-hidden />
              Deshacer IA
            </Button>
          ) : null}
          <InfoTip help={HELP.aiTools} label="IA opcional" />
        </div>
      </div>

      {hasGuide ? (
        <p className="px-1 text-[11px] leading-snug text-faint">
          Con guía alineada el prompt se escribe a mano (empieza por body_swap: y describe &lt;Picture 1&gt;). Las
          herramientas de IA quedan desactivadas para no inventar tokens de vídeo.
        </p>
      ) : null}
      {directorError ? (
        <p role="alert" className="text-pretty rounded-xl border border-danger/35 bg-danger-soft/30 px-2.5 py-1.5 text-[11px] text-danger">
          {directorError}
        </p>
      ) : null}

      <PromptChatDialog
        open={chatOpen}
        onOpenChange={setChatOpen}
        mode={mode}
        length={length}
        currentPrompt={prompt}
        references={toReferenceInputs(references)}
        onUsePrompt={applyChatPrompt}
      />

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        {preview ? (
          <DialogPanel
            title="Propuesta de AI Director"
            description="Compara tu prompt con la propuesta. No cambia nada hasta que la apliques."
            className="w-[min(64rem,calc(100vw-2rem))]"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <section aria-label="Original prompt" className="space-y-2">
                <h3 className="text-balance text-xs font-medium text-muted">Tu prompt</h3>
                <pre className="max-h-[22rem] overflow-auto whitespace-pre-wrap rounded border border-line bg-ink-950 p-3 text-pretty text-xs leading-relaxed text-muted">
                  {preview.original_prompt}
                </pre>
              </section>
              <section aria-label="Enhanced prompt" className="space-y-2">
                <h3 className="text-balance text-xs font-medium text-accent">Propuesta para H3</h3>
                <pre className="max-h-[22rem] overflow-auto whitespace-pre-wrap rounded border border-accent/30 bg-ink-950 p-3 text-pretty text-xs leading-relaxed text-fg">
                  {preview.enhanced_prompt}
                </pre>
              </section>
            </div>
            {preview.analyses.length > 0 ? (
              <details className="mt-4 rounded border border-line bg-ink-850 px-3 py-2">
                <summary className="cursor-pointer text-xs text-muted">
                  Lectura de referencias · {preview.cached_analyses}/{preview.analyses.length} reutilizadas
                </summary>
                <ul className="mt-2 space-y-2">
                  {preview.analyses.map((analysis) => (
                    <li key={`${analysis.asset_id}-${analysis.role}`} className="text-pretty text-[11px] leading-relaxed text-faint">
                      <span className="font-mono text-accent">{analysis.token}</span> · {analysis.role}: {analysis.summary}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
            <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-4">
              <span className="truncate text-[10px] text-faint">Modelo local: {preview.model}</span>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setPreview(null)}>
                  Quedarme con el mío
                </Button>
                <Button variant="primary" size="sm" onClick={applyPreview} aria-label="Apply enhanced prompt">
                  <Sparkles aria-hidden />
                  Aplicar propuesta
                </Button>
              </div>
            </div>
          </DialogPanel>
        ) : null}
      </Dialog>
    </div>
  )
}
