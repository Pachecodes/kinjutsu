/**
 * How the local workstation state reads for a creator. Pure; no React, no network.
 *
 * Every sentence keeps three things apart: this Studio (the app in the browser),
 * the ComfyUI engine (the process that renders on the GPU) and the model files
 * on disk. Detection is never presented as approval, and opening a page is
 * never presented as starting the engine.
 */

import type { FolderKind, WorkstationState, WorkstationStatus } from './types'

/** Workstation routes answer only on the server itself (loopback Host). */
export function isLocalContext(hostname: string = window.location.hostname): boolean {
  return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(hostname)
}

export type Tone = 'ok' | 'busy' | 'idle' | 'warn' | 'error'

export interface StateCopy {
  label: string
  tone: Tone
  /** What is true right now. */
  body: string
  /** What the creator (or the administrator) can do. Never a kill/restart. */
  next: string
}

export const STATE_COPY: Record<WorkstationState, StateCopy> = {
  configuration_required: {
    label: 'Sin instalación elegida',
    tone: 'idle',
    body: 'Studio no tiene todavía un ComfyUI aprobado y elegido en este equipo.',
    next: 'Busca instalaciones y elige una aprobada. Si la tuya no está aprobada, el administrador debe aprobarla en la configuración local.',
  },
  stopped: {
    label: 'Motor detenido',
    tone: 'idle',
    body: 'La instalación elegida está lista y su puerto está libre, pero el motor ComfyUI no está en marcha.',
    next: 'Pulsa «Iniciar motor» cuando quieras generar. No arranca solo.',
  },
  starting: {
    label: 'Motor arrancando',
    tone: 'busy',
    body: 'El motor que inició Studio sigue cargando. Arrancado no es lo mismo que listo.',
    next: 'Espera: el estado se actualiza solo hasta que esté en línea. No hace falta pulsar nada más.',
  },
  online: {
    label: 'Motor en línea',
    tone: 'ok',
    body: 'El motor ComfyUI responde y es exactamente la instalación elegida.',
    next: 'Puedes abrir ComfyUI en el navegador del equipo o trabajar desde Studio.',
  },
  unhealthy: {
    label: 'Motor sin responder bien',
    tone: 'warn',
    body: 'El proceso de la instalación elegida existe, pero todavía no responde como sano.',
    next: 'Puede estar cargando o atascado. Revisa sus registros en el equipo; esta pantalla no lo reinicia ni lo detiene.',
  },
  port_conflict: {
    label: 'Puerto ocupado por otro programa',
    tone: 'error',
    body: 'Otro proceso usa el puerto de la instalación elegida, aunque parezca un ComfyUI.',
    next: 'No se arranca, adopta ni detiene nada. Cierra ese programa tú mismo o pide al administrador que cambie el puerto.',
  },
  configuration_changed: {
    label: 'Configuración cambiada',
    tone: 'error',
    body: 'Sigue vivo un arranque anterior hecho con otra configuración.',
    next: 'El administrador debe revisarlo en el equipo antes de continuar. No hay botón de reintento a propósito.',
  },
  launch_unverified: {
    label: 'Arranque sin verificar',
    tone: 'error',
    body: 'Se intentó arrancar el motor, pero no quedó un registro completo del proceso.',
    next: 'El administrador debe revisar el proceso y el registro local antes de nada. No se ofrece reintentar ni reiniciar a ciegas.',
  },
}

export const BINDING_COPY: Record<WorkstationStatus['generation_binding'], { tone: Tone; text: string }> = {
  matches: {
    tone: 'ok',
    text: 'Studio está configurado para generar con esta misma instalación; genera solo cuando el motor está en línea.',
  },
  different: {
    tone: 'warn',
    text: 'Studio sigue generando con otra dirección de ComfyUI. Elegir aquí no redirige las tomas: el administrador debe cambiarlo en un momento sin renders.',
  },
  not_selected: {
    tone: 'idle',
    text: 'Aún no hay instalación elegida, así que no se puede comparar con la que usa Studio para generar.',
  },
  unknown: {
    tone: 'idle',
    text: 'No se pudo comparar con la dirección que usa Studio para generar.',
  },
}

/**
 * «Esta instalación genera tus tomas» only when the backend says the URLs match
 * and the live H3 capabilities agree the engine is reachable.
 */
export function generatesHere(status: WorkstationStatus, comfyOnline: boolean): boolean {
  return status.generation_binding === 'matches' && status.state === 'online' && comfyOnline
}

export const FOLDER_LABEL: Record<FolderKind, string> = {
  models: 'Modelos',
  loras: 'LoRAs',
  outputs: 'Resultados',
}

export const FOLDER_KINDS: FolderKind[] = ['models', 'loras', 'outputs']
