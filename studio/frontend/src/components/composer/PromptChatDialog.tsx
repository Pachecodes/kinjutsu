import { Loader2, MessageSquareText, Plus, Send, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { t, useT } from '../../i18n'
import { ApiError, api } from '../../lib/api'
import type { Mode, PromptChatMessage, ReferenceInput } from '../../lib/types'
import { Button } from '../ui/button'
import { Dialog, DialogPanel } from '../ui/dialog'
import { Textarea } from '../ui/field'

interface PromptChatDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: Mode
  length: number
  currentPrompt: string
  references: ReferenceInput[]
  onUsePrompt: (prompt: string) => void
}

interface LocalMessage extends PromptChatMessage {
  id: number
}

const STARTERS = [
  'Turn my current idea into a production-ready H3 prompt.',
  'Help me improve identity and temporal continuity in this shot.',
  'Ask me only the essential questions before writing the final prompt.',
]

export function PromptChatDialog({
  open,
  onOpenChange,
  mode,
  length,
  currentPrompt,
  references,
  onUsePrompt,
}: PromptChatDialogProps) {
  useT()
  const imageCount = references.filter((reference) => reference.kind === 'image').length
  const contextKey = `${mode}\u0000${currentPrompt}\u0000${references
    .map((reference) => `${reference.asset_id}:${reference.kind}:${reference.role}`)
    .join('|')}`
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [model, setModel] = useState('gemma4-e2b-h3-prompts-gpu')
  const nextId = useRef(1)
  const previousContextKey = useRef(contextKey)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (previousContextKey.current === contextKey) return
    previousContextKey.current = contextKey
    nextId.current = 1
    setMessages([])
    setDraft('')
    setError(null)
  }, [contextKey])

  useEffect(() => {
    if (open) requestAnimationFrame(() => end.current?.scrollIntoView({ block: 'end' }))
  }, [messages, open, sending])

  const submit = async (text = draft) => {
    const content = text.trim()
    if (!content || sending) return
    const userMessage: LocalMessage = { id: nextId.current++, role: 'user', content }
    const visible = [...messages, userMessage].slice(-23)
    setMessages(visible)
    setDraft('')
    setError(null)
    setSending(true)
    try {
      const response = await api.chatPrompt({
        mode,
        current_prompt: currentPrompt,
        length,
        references,
        messages: visible.map(({ role, content: messageContent }) => ({ role, content: messageContent })),
      })
      setModel(response.model)
      const assistantMessage: LocalMessage = {
        id: nextId.current++,
        role: 'assistant',
        content: response.message,
      }
      setMessages((current) => [...current, assistantMessage].slice(-24))
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : t('GPU Prompt Chat no pudo responder.'))
    } finally {
      setSending(false)
    }
  }

  const reset = () => {
    setMessages([])
    setDraft('')
    setError(null)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPanel
        title="GPU Prompt Chat"
        description={t('Gemma 4 E2B multimodal sin censura en GPU · se libera automáticamente antes de cada render de H3.')}
        className="h-[min(78dvh,46rem)] w-[min(52rem,calc(100vw-1rem))]"
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-line pb-3">
            <span className="truncate text-[10px] text-faint">{t('{model} · contexto 8K · GPU bajo demanda · se libera tras 3 minutos inactiva', { model })}</span>
            <Button variant="ghost" size="sm" onClick={reset} disabled={sending || messages.length === 0}>
              <Plus aria-hidden />
              {t('Nuevo chat')}
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto py-4 pr-1" aria-live="polite">
            {messages.length === 0 ? (
              <div className="mx-auto flex h-full max-w-lg flex-col justify-center gap-4 py-6">
                <div className="space-y-1.5">
                  <MessageSquareText className="size-5 text-accent" aria-hidden />
                  <h3 className="display-title text-sm text-fg">{t('Da forma a la toma conversando')}</h3>
                  <p className="text-pretty text-xs leading-relaxed text-faint">
                    {imageCount === 1
                      ? t('Gemma ve 1 imagen adjunta y recibe su rol exacto de H3, el prompt actual, la duración y las reglas de continuidad.')
                      : imageCount > 1
                        ? t('Gemma ve {n} imágenes adjuntas y recibe sus roles exactos de H3, el prompt actual, la duración y las reglas de continuidad.', { n: imageCount })
                        : t('No hay ninguna imagen adjunta. Gemma recibe como texto el modo actual, la duración, el prompt y las reglas de continuidad de H3.')}
                  </p>
                </div>
                <div className="grid gap-2">
                  {STARTERS.map((starter) => (
                    <button
                      key={starter}
                      type="button"
                      onClick={() => void submit(starter)}
                      className="rounded border border-line bg-ink-850 px-3 py-2 text-left text-xs leading-relaxed text-muted transition-colors hover:border-line-strong hover:text-fg active:translate-y-px"
                    >
                      {starter}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={
                      message.role === 'user'
                        ? 'ml-auto max-w-[85%] rounded-lg bg-ink-800 px-3 py-2.5'
                        : 'max-w-[94%] border-l-2 border-accent/55 pl-3 pr-2 py-1'
                    }
                  >
                    <div className="mb-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-faint">
                      {message.role === 'user' ? t('Tú') : 'Gemma'}
                    </div>
                    <pre className="whitespace-pre-wrap font-sans text-pretty text-xs leading-relaxed text-fg">
                      {message.content}
                    </pre>
                    {message.role === 'assistant' ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => onUsePrompt(message.content)}
                      >
                        <Sparkles aria-hidden />
                        {t('Usar como prompt de H3')}
                      </Button>
                    ) : null}
                  </article>
                ))}
                {sending ? (
                  <div className="flex items-center gap-2 border-l-2 border-accent/55 py-2 pl-3 text-xs text-faint">
                    <Loader2 className="size-3.5 animate-spin text-accent" aria-hidden />
                    {t('Gemma está escribiendo con la guía de H3…')}
                  </div>
                ) : null}
                <div ref={end} />
              </div>
            )}
          </div>

          {error ? (
            <p role="alert" className="mb-2 rounded border border-danger/35 bg-danger-soft/30 px-2.5 py-1.5 text-[11px] text-danger">
              {error}
            </p>
          ) : null}

          <div className="border-t border-line pt-3">
            <label htmlFor="gpu-prompt-chat" className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.12em] text-faint">
              {t('Mensaje')}
            </label>
            <div className="flex items-end gap-2">
              <Textarea
                id="gpu-prompt-chat"
                value={draft}
                rows={2}
                maxLength={12000}
                placeholder={t('Describe el cambio, pide opciones o solicita el prompt final de H3…')}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void submit()
                  }
                }}
                className="min-h-[4.25rem] flex-1 resize-none"
              />
              <Button
                variant="primary"
                size="icon"
                aria-label={t('Enviar mensaje a Gemma')}
                disabled={!draft.trim() || sending}
                onClick={() => void submit()}
              >
                {sending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
              </Button>
            </div>
            <p className="mt-1.5 text-[10px] text-faint">{t('Enter para enviar · Shift+Enter para una nueva línea')}</p>
          </div>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
