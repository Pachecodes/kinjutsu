import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { BRAND } from '../../lib/brand'
import { cn } from '../../lib/cn'
import { HELP, type HelpEntry } from '../../lib/help'
import { isReferenceMode } from '../../lib/references'
import type { CapabilityResponse, MethodId, WeightVariant } from '../../lib/types'
import { useComposer } from '../../state/composer'
import { MethodPicker } from '../composer/MethodPicker'
import { Button } from '../ui/button'
import { Field, Input } from '../ui/field'
import { InfoTip } from '../ui/info-tip'
import { Segmented } from '../ui/segmented'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Slider } from '../ui/slider'
import { Switch } from '../ui/switch'

function Section({
  title,
  help,
  children,
  defaultOpen = false,
  note,
}: {
  title: string
  help?: HelpEntry
  children: ReactNode
  defaultOpen?: boolean
  note?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  const bodyId = useId()
  return (
    <div className="border-t border-white/[0.06] pt-3 first:border-t-0 first:pt-0">
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen(!open)}
          className="flex min-h-9 flex-1 items-center justify-between gap-2 py-1 text-left"
        >
          <span className="eyebrow text-muted">{title}</span>
          <ChevronDown className={cn('size-3.5 text-faint transition-transform', open && 'rotate-180')} aria-hidden />
        </button>
        {help ? <InfoTip help={help} label={title} side="left" /> : null}
      </div>
      {note ? <p className="mb-2 text-[11px] leading-snug text-faint">{note}</p> : null}
      {open ? (
        <div id={bodyId} className="space-y-3 pb-1 pt-2">
          {children}
        </div>
      ) : null}
    </div>
  )
}

function checkpointLabel(weights: WeightVariant, referenceMode: boolean): string {
  if (weights === 'erosmax_beta5') return 'ErosMax Beta 5'
  if (weights === 'erosmax_beta4') return 'ErosMax Beta 4'
  if (weights === 'pinkcherry_v03') return 'Pink Cherry v0.3'
  if (weights === 'gguf_q3km') return 'GGUF Q3_K_M'
  return `Default / OG · ${referenceMode ? 'Ref2VA' : 'FL2VA'}`
}

/**
 * Every technical control the live contract supports, grouped by what it
 * changes: the base model, the prompt encoder, adapters, the sampler and the
 * method's own knobs. Nothing is removed for simplicity — it is only out of the
 * primary flow, with a plain explanation beside each control.
 */
export function SettingsPanel({ capabilities }: { capabilities: CapabilityResponse }) {
  const state = useComposer()
  const [loraToAdd, setLoraToAdd] = useState('')
  const referenceMode = isReferenceMode(state.mode)
  const w4a8Method =
    state.method === 'w4a8_lightx2v' ||
    state.method === 'w4a8_lightx2v_trt' ||
    state.method === 'w4a8_latent2x_refine3'
  const trtMethod = state.method === 'w4a8_lightx2v_trt'
  const premiumMethod = state.method === 'w4a8_latent2x_refine3'
  const vsaMethod = state.method === 'ref2va_vsa'
  const recipeLocked = w4a8Method || vsaMethod
  const checkpointFamily = referenceMode ? 'ref2va' : 'fl2va'
  const selectedLoras = new Set(state.lora_chain.map((lora) => lora.name))

  return (
    <div className="space-y-3" id="advanced-settings" data-tour="advanced-panel">
      <p className="text-[11px] leading-snug text-faint">
        Todo lo técnico vive aquí. Las recetas ya lo rellenan; cambia solo lo que entiendas. Más pasos, fuerza o
        resolución no garantizan mejor resultado.
      </p>

      <Section
        title="Modelo base (checkpoint)"
        help={HELP.checkpoint}
        defaultOpen
        note={
          vsaMethod
            ? 'Ref2VA Turbo4 + compuerta VSA 75 %. Frames, checkpoint, codificador, LoRAs y continuidad siguen editables.'
            : referenceMode
              ? 'Solo el checkpoint Ref2VA tiene versión GGUF.'
              : trtMethod
                ? 'W4A8 + Turbo 4 pasos v1.1 a 1.0. VAE INT8 estándar para condicionar; TensorRT solo decodifica vídeo.'
                : premiumMethod
                  ? 'Pipeline verificado: W4A8 + LightX2V4 0,75, generación a media resolución, latente 3D 2× y Refine3 HD.'
                  : state.method === 'w4a8_lightx2v'
                    ? 'Este método usa automáticamente el checkpoint W4A8 FL2VA con LightX2V4 a 0,75.'
                    : 'Default / OG sigue a la tarea: FL2VA para texto y fotogramas, Ref2VA para referencias. El Studio solo libera VRAM al cambiar de checkpoint si ComfyUI está libre; nunca interrumpe un render.'
        }
      >
        <Segmented
          label="Checkpoint"
          value={state.weights}
          onValueChange={state.setWeights}
          options={[
            {
              value: 'int8',
              label: `Default / OG · ${referenceMode ? 'Ref2VA' : 'FL2VA'}`,
              disabled: w4a8Method || !capabilities.weights.int8,
              tooltip: capabilities.weights.int8 ? 'Checkpoint INT8 podado.' : 'El checkpoint INT8 no está instalado.',
            },
            {
              value: 'gguf_q3km',
              label: 'GGUF Q3_K_M',
              disabled: w4a8Method || !referenceMode || !capabilities.weights.gguf_q3km,
              tooltip: !referenceMode
                ? 'No existe versión GGUF del checkpoint FL2VA.'
                : capabilities.weights.gguf_q3km
                  ? 'Ref2VA más pequeño: menos VRAM, menos fidelidad.'
                  : 'La versión GGUF de Ref2VA no está instalada.',
            },
            {
              value: 'erosmax_beta5',
              label: '10Eros-Max · ErosMax Beta 5',
              disabled: w4a8Method || !capabilities.weights.erosmax_beta5,
              tooltip: capabilities.weights.erosmax_beta5
                ? 'TenStrip/10Eros-Max Beta 5 · híbrido W4A8/INT8 Turbo verificado. UNETLoader nativo. El tamaño no garantiza la VRAM.'
                : 'h3ErosMax_beta5.safetensors no está instalado en H3 Lab.',
            },
          ]}
        />
        <p className="text-[11px] leading-snug text-faint">
          {!capabilities.comfy_online
            ? 'Disponibilidad de checkpoints desconocida · H3 Lab desconectado.'
            : capabilities.weights.erosmax_beta5
              ? '10Eros-Max · instalado en el UNETLoader en vivo.'
              : '10Eros-Max · no está en el UNETLoader en vivo.'}
        </p>
        <p className="rounded-xl border border-accent/40 bg-accent/10 px-2.5 py-2 text-xs font-semibold text-fg">
          {`Checkpoint elegido: ${checkpointLabel(state.weights, referenceMode)}`}
        </p>
        {recipeLocked ? (
          <p className="text-[11px] leading-snug text-accent">
            {vsaMethod
              ? 'Núcleo activo: Ref2VA Turbo4 a 1.0 · VSA 0,75 · sigma shifts 12/3 · euler/simple · 4 pasos. El resto sigue editable.'
              : premiumMethod
                ? 'Receta activa: W4A8 FL2VA · LightX2V4 0,75 · latente 3D 2× · euler Refine3 · 124 frames.'
                : trtMethod
                  ? 'Receta activa: W4A8 FL2VA · Turbo 4 pasos v1.1 a 1.0 · res_multistep/simple · VAE estándar · TRT solo decodifica.'
                  : 'Receta activa: W4A8 FL2VA · LightX2V4 0,75 · er_sde · simple · 4 pasos.'}
          </p>
        ) : null}
      </Section>

      <Section title="Codificador de prompt" help={HELP.encoder} defaultOpen>
        <Segmented
          label="Codificador de prompt"
          value={state.encoder}
          onValueChange={state.setEncoder}
          options={[
            {
              value: 'standard',
              label: 'Standard',
              disabled: !capabilities.encoders.standard,
              tooltip: 'Condicionador Qwen3-VL oficial de H3.',
            },
            {
              value: 'heretic',
              label: 'Heretic',
              disabled: !capabilities.encoders.heretic,
              tooltip: capabilities.encoders.heretic
                ? 'Condicionador Qwen experimental. Cambia el condicionamiento del prompt, no los pesos de vídeo.'
                : 'El condicionador Heretic NVFP4 no está instalado.',
            },
          ]}
        />
        {state.encoder === 'heretic' ? (
          <p className="text-[11px] leading-snug text-warn">
            Experimental. Puede reducir rechazos del prompt, pero no sustituye ni modifica el generador H3.
          </p>
        ) : null}
      </Section>

      <Section
        title={`LoRAs${state.lora_chain.length ? ` · ${state.lora_chain.length}` : ''}`}
        help={HELP.loras}
        defaultOpen={state.lora_chain.length > 0}
        note="Adaptadores opcionales. Se aplican en el orden de la lista, antes del método."
      >
        {capabilities.loras.length ? (
          <div className="space-y-3">
            <div className="flex items-end gap-2">
              <Field label="Añadir LoRA" htmlFor="lora-select" className="min-w-0 flex-1">
                <Select value={loraToAdd || undefined} onValueChange={setLoraToAdd}>
                  <SelectTrigger id="lora-select">
                    <SelectValue placeholder="Elige un LoRA instalado" />
                  </SelectTrigger>
                  <SelectContent>
                    {capabilities.loras.map((lora) => {
                      const compatible = lora.checkpoint === 'any' || lora.checkpoint === checkpointFamily
                      return (
                        <SelectItem
                          key={lora.name}
                          value={lora.name}
                          disabled={!compatible || selectedLoras.has(lora.name)}
                          description={!compatible ? `Solo ${lora.checkpoint.toUpperCase()}` : undefined}
                        >
                          {lora.label}
                        </SelectItem>
                      )
                    })}
                  </SelectContent>
                </Select>
              </Field>
              <Button
                variant="outline"
                size="icon"
                aria-label="Añadir el LoRA elegido"
                disabled={!loraToAdd || state.lora_chain.length >= 8}
                onClick={() => {
                  const lora = capabilities.loras.find((entry) => entry.name === loraToAdd)
                  if (!lora || (lora.checkpoint !== 'any' && lora.checkpoint !== checkpointFamily)) return
                  state.addLora(lora.name, lora.recommended_strength)
                  setLoraToAdd('')
                }}
              >
                <Plus aria-hidden />
              </Button>
            </div>

            <ol className="space-y-2">
              {state.lora_chain.map((selected, index) => {
                const metadata = capabilities.loras.find((lora) => lora.name === selected.name)
                const name = metadata?.label ?? selected.name
                return (
                  <li key={selected.name} className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-3">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-fg">
                          <span className="tabular mr-1.5 text-faint">{index + 1}.</span>
                          {name}
                        </p>
                        {metadata?.note ? <p className="mt-1 text-[11px] leading-snug text-faint">{metadata.note}</p> : null}
                      </div>
                      <div className="flex shrink-0 items-center">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Subir ${name} en la cadena`}
                          disabled={index === 0}
                          onClick={() => state.moveLora(index, index - 1)}
                        >
                          <ChevronUp aria-hidden />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Bajar ${name} en la cadena`}
                          disabled={index === state.lora_chain.length - 1}
                          onClick={() => state.moveLora(index, index + 1)}
                        >
                          <ChevronDown aria-hidden />
                        </Button>
                        <Button variant="ghost" size="icon-sm" aria-label={`Quitar ${name}`} onClick={() => state.removeLora(index)}>
                          <Trash2 aria-hidden />
                        </Button>
                      </div>
                    </div>
                    <Field label="Fuerza" help={HELP.loraStrength} aside={selected.strength.toFixed(2)}>
                      <Slider
                        value={[selected.strength]}
                        min={-2}
                        max={2}
                        step={0.05}
                        aria-label={`Fuerza de ${name}`}
                        onValueChange={([strength]) => state.setLoraStrength(index, strength)}
                      />
                    </Field>
                  </li>
                )
              })}
            </ol>
            {state.lora_chain.length >= 8 ? (
              <p className="text-[11px] text-warn">Cadena completa (máximo 8 LoRAs).</p>
            ) : null}
          </div>
        ) : (
          <p className="text-xs leading-snug text-faint">No hay LoRAs instalados en H3 Lab.</p>
        )}
      </Section>

      <Section title="Método / acelerador" help={HELP.method}>
        <MethodPicker methods={capabilities.methods} comfyOnline={capabilities.comfy_online} />
      </Section>

      <Section
        title="Muestreo"
        help={HELP.sampler}
        defaultOpen
        note={
          premiumMethod
            ? 'Pase base fijo: er_sde · simple · 4 pasos. El refinado HD usa euler con el esquema de tres pasos verificado.'
            : trtMethod
              ? 'Pase validado fijo: res_multistep · simple · 4 pasos.'
              : undefined
        }
      >
        <Field label="Pasos" help={HELP.steps} htmlFor="steps-slider" aside={String(state.steps)}>
          <Slider
            id="steps-slider"
            value={[state.steps]}
            min={1}
            max={capabilities.limits.max_steps}
            step={1}
            aria-label="Pasos de muestreo"
            disabled={recipeLocked}
            onValueChange={([next]) => state.setSteps(next)}
          />
        </Field>

        <Field label="Sampler" help={HELP.sampler} htmlFor="sampler-select">
          <Select value={state.sampler_name} disabled={recipeLocked} onValueChange={state.setSampler}>
            <SelectTrigger id="sampler-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {capabilities.samplers.map((sampler) => (
                <SelectItem key={sampler} value={sampler}>
                  {sampler}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Scheduler" help={HELP.scheduler} htmlFor="scheduler-select">
          <Select value={state.scheduler} disabled={recipeLocked} onValueChange={state.setScheduler}>
            <SelectTrigger id="scheduler-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {capabilities.schedulers.map((scheduler) => (
                <SelectItem key={scheduler} value={scheduler}>
                  {scheduler}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field
          label="Sigmas manuales" help={HELP.sigmas}
          htmlFor="custom-sigmas"
          hint="Lista descendente separada por comas, terminada en 0. Sustituye al scheduler. Se aplica al salir del campo; vacíalo para volver al scheduler."
        >
          <Input
            id="custom-sigmas"
            key={String(state.custom_sigmas)}
            defaultValue={state.custom_sigmas?.join(', ') ?? ''}
            onBlur={(event) => {
              const value = event.target.value.trim()
              const sigmas = value ? value.split(',').map(Number) : null
              useComposer.setState({ custom_sigmas: sigmas, presetId: null })
            }}
          />
        </Field>
      </Section>

      {state.method === 'easycache' ? (
        <Section title="Caché de Fast Preview" defaultOpen>
          <Field label="Umbral de reutilización" help={HELP.easycacheThreshold} aside={state.easycache.reuse_threshold.toFixed(2)}>
            <Slider
              value={[state.easycache.reuse_threshold]}
              min={0}
              max={3}
              step={0.05}
              aria-label="Umbral de reutilización de EasyCache"
              onValueChange={([reuse_threshold]) => state.setEasyCache({ reuse_threshold })}
            />
          </Field>
          <Field
            label="Tramo de caché" help={HELP.easycacheWindow}
            aside={`${state.easycache.start_percent.toFixed(2)} – ${state.easycache.end_percent.toFixed(2)}`}
            hint="El inicio debe ir antes del final."
          >
            <Slider
              value={[state.easycache.start_percent, state.easycache.end_percent]}
              min={0}
              max={1}
              step={0.05}
              minStepsBetweenThumbs={1}
              aria-label="Tramo de EasyCache"
              onValueChange={([start_percent, end_percent]) => state.setEasyCache({ start_percent, end_percent })}
            />
          </Field>
        </Section>
      ) : null}

      {state.method === 'sol' ? (
        <Section title="SolAttn (experimental)" defaultOpen note="Medido más lento que Quality y con SSIM 0,778.">
          <Field label="Tau" help={HELP.solTau} aside={state.sol.tau.toFixed(2)}>
            <Slider
              value={[state.sol.tau]}
              min={0}
              max={4}
              step={0.05}
              aria-label="Sol tau"
              onValueChange={([tau]) => state.setSol({ tau })}
            />
          </Field>
          <Field label="Tramo del parche" aside={`${state.sol.start_percent.toFixed(2)} – ${state.sol.end_percent.toFixed(2)}`}>
            <Slider
              value={[state.sol.start_percent, state.sol.end_percent]}
              min={0}
              max={1}
              step={0.05}
              minStepsBetweenThumbs={1}
              aria-label="Tramo de Sol"
              onValueChange={([start_percent, end_percent]) => state.setSol({ start_percent, end_percent })}
            />
          </Field>
          <Field label="Tokens mínimos" htmlFor="sol-min-tokens">
            <Input
              id="sol-min-tokens"
              type="number"
              min={0}
              max={1048576}
              value={state.sol.min_tokens}
              onChange={(event) => state.setSol({ min_tokens: Math.max(0, Number(event.target.value) || 0) })}
            />
          </Field>
          <Field label="Sink conditioning" htmlFor="sol-sink">
            <Select
              value={state.sol.sink_conditioning}
              onValueChange={(value) => state.setSol({ sink_conditioning: value as typeof state.sol.sink_conditioning })}
            >
              <SelectTrigger id="sol-sink">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="exact_kv">exact_kv</SelectItem>
                <SelectItem value="exact_kv_and_rows">exact_kv_and_rows</SelectItem>
                <SelectItem value="off">off</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <div className="space-y-2">
            <label className="flex items-center justify-between gap-2 text-xs text-muted">
              INT8 QK
              <Switch checked={state.sol.int8_qk} onCheckedChange={(int8_qk) => state.setSol({ int8_qk })} aria-label="INT8 QK" />
            </label>
            <label className="flex items-center justify-between gap-2 text-xs text-muted">
              Orden Morton
              <Switch checked={state.sol.morton} onCheckedChange={(morton) => state.setSol({ morton })} aria-label="Orden Morton" />
            </label>
            {state.sol.morton ? (
              <Field label="Curva Morton" htmlFor="sol-curve">
                <Select
                  value={state.sol.morton_curve}
                  onValueChange={(value) => state.setSol({ morton_curve: value as typeof state.sol.morton_curve })}
                >
                  <SelectTrigger id="sol-curve">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="3d">3d</SelectItem>
                    <SelectItem value="2d_frame">2d_frame</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            ) : null}
            <label className="flex items-center justify-between gap-2 text-xs text-muted">
              Usar TMA
              <Switch checked={state.sol.use_tma} onCheckedChange={(use_tma) => state.setSol({ use_tma })} aria-label="Usar TMA" />
            </label>
          </div>
        </Section>
      ) : null}

      <Section title="Continuidad" help={HELP.continuity} note="Divide tomas largas en ventanas seguras para la VRAM y fija latentes AV entre ventanas.">
        <label className="flex items-center justify-between gap-3 text-xs text-muted">
          <span>
            <span className="block text-fg">Continuidad automática</span>
            <span className="mt-0.5 block text-[11px] leading-snug text-faint">
              Detecta cuándo una ventana no es segura; las tomas cortas no cambian.
            </span>
          </span>
          <Switch
            checked={state.continuity.auto_split}
            onCheckedChange={(auto_split) => state.setContinuity({ auto_split })}
            aria-label="Continuidad automática"
          />
        </label>

        <Field label="Ventana de continuidad" help={HELP.continuityWindow} htmlFor="continuity-window">
          <Select
            value={state.continuity.window}
            disabled={!state.continuity.auto_split}
            onValueChange={(window) => state.setContinuity({ window: window as typeof state.continuity.window })}
          >
            <SelectTrigger id="continuity-window" aria-label="Ventana de continuidad">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Auto · ajustar a la RTX 4090</SelectItem>
              {['243', '192', '141', '124', '90'].map((frames) => (
                <SelectItem key={frames} value={frames}>
                  {frames} frames
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Solape de latentes" help={HELP.continuityPin} htmlFor="continuity-pin">
          <Select
            value={state.continuity.pin_frames}
            disabled={!state.continuity.auto_split}
            onValueChange={(pin_frames) => state.setContinuity({ pin_frames: pin_frames as typeof state.continuity.pin_frames })}
          >
            <SelectTrigger id="continuity-pin" aria-label="Solape de latentes">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="5">5 frames · ligero</SelectItem>
              <SelectItem value="22">22 frames · recomendado</SelectItem>
              <SelectItem value="39">39 frames · fuerte</SelectItem>
              <SelectItem value="56">56 frames · máximo</SelectItem>
            </SelectContent>
          </Select>
        </Field>

        {state.continuity.auto_split &&
        (state.mode === 'first_frame' || state.mode === 'first_last' || state.mode === 'performance') ? (
          <p className="text-[11px] leading-snug text-warn">
            La continuidad automática no funciona con fotogramas ni Performance: apágala o elige Texto o Referencias.
          </p>
        ) : null}
        {state.continuity.auto_split && state.references.some((slot) => slot.role === 'aligned_guide') ? (
          <p className="text-[11px] leading-snug text-warn">Una guía alineada necesita la continuidad apagada.</p>
        ) : null}
        {state.continuity.auto_split && (trtMethod || premiumMethod) ? (
          <p className="text-[11px] leading-snug text-warn">
            La continuidad por latentes no admite el condicionamiento TRT ni el refinado de dos pasadas.
          </p>
        ) : null}
      </Section>

      {referenceMode ? (
        <Section title="Detalle de referencias" help={HELP.refDetail}>
          <Segmented
            label="Detalle de referencias"
            value={state.ref_image_size}
            onValueChange={state.setRefImageSize}
            options={[
              { value: 'match', label: 'Igual al cuadro' },
              { value: 'max', label: 'Máximo detalle' },
            ]}
          />
          <p className="text-[11px] leading-snug text-faint">
            {state.ref_image_size === 'max'
              ? 'Máximo mantiene cada referencia a 2048 px en todos los pasos. El render puede tardar varias veces la estimación.'
              : 'Igual al cuadro lee las referencias al tamaño de la toma.'}
          </p>
        </Section>
      ) : null}

      <Section
        title="Base de las medidas"
        note={`Perfiles medidos en ${BRAND.machine} a ${capabilities.benchmark_basis.width}×${capabilities.benchmark_basis.height} y ${capabilities.benchmark_basis.seconds} s; cada fila indica sus pasos. Son referencia, no garantía.`}
      >
        <dl className="space-y-1.5">
          {capabilities.methods.map((method) => (
            <div key={method.id} className="flex items-start justify-between gap-2">
              <dt className={cn('text-xs', method.id === (state.method as MethodId) ? 'text-fg' : 'text-muted')}>{method.label}</dt>
              <dd className="tabular text-right text-[11px] text-faint">
                {method.measured_seconds !== null
                  ? `${method.measured_seconds.toFixed(2)} s @ ${method.measured_steps ?? capabilities.benchmark_basis.steps} pasos`
                  : '—'}
                {method.measured_ssim !== null ? ` · SSIM ${method.measured_ssim.toFixed(3)}` : ''}
              </dd>
            </div>
          ))}
        </dl>
      </Section>
    </div>
  )
}
