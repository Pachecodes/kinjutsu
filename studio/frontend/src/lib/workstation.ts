/**
 * How the local workstation state reads for a creator. Pure; no React, no network.
 *
 * Every sentence keeps three things apart: this Studio (the app in the browser),
 * the ComfyUI engine (the process that renders on the GPU) and the model files
 * on disk. Detection is never presented as approval, and opening a page is
 * never presented as starting the engine.
 */

import type { FolderKind, WorkstationState, WorkstationStatus } from './types'
import { localized, t } from '../i18n'

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

export const STATE_COPY: Record<WorkstationState, StateCopy> = localized(() => ({
  configuration_required: {
    label: t('Sin instalación elegida'),
    tone: 'idle',
    body: t('Studio no tiene todavía un ComfyUI aprobado y elegido en este equipo.'),
    next: t('Busca instalaciones y elige una aprobada. Si la tuya no está aprobada, el administrador debe aprobarla en la configuración local.'),
  },
  stopped: {
    label: t('Motor detenido'),
    tone: 'idle',
    body: t('La instalación elegida está lista y su puerto está libre, pero el motor ComfyUI no está en marcha.'),
    next: t('Pulsa «Iniciar motor» cuando quieras generar. No arranca solo.'),
  },
  starting: {
    label: t('Motor arrancando'),
    tone: 'busy',
    body: t('El motor que inició Studio sigue cargando. Arrancado no es lo mismo que listo.'),
    next: t('Espera: el estado se actualiza solo hasta que esté en línea. No hace falta pulsar nada más.'),
  },
  online: {
    label: t('Motor en línea'),
    tone: 'ok',
    body: t('El motor ComfyUI responde y es exactamente la instalación elegida.'),
    next: t('Puedes abrir ComfyUI en el navegador del equipo o trabajar desde Studio.'),
  },
  unhealthy: {
    label: t('Motor sin responder bien'),
    tone: 'warn',
    body: t('El proceso de la instalación elegida existe, pero todavía no responde como sano.'),
    next: t('Puede estar cargando o atascado. Revisa sus registros en el equipo; esta pantalla no lo reinicia ni lo detiene.'),
  },
  port_conflict: {
    label: t('Puerto ocupado por otro programa'),
    tone: 'error',
    body: t('Otro proceso usa el puerto de la instalación elegida, aunque parezca un ComfyUI.'),
    next: t('No se arranca, adopta ni detiene nada. Cierra ese programa tú mismo o pide al administrador que cambie el puerto.'),
  },
  configuration_changed: {
    label: t('Configuración cambiada'),
    tone: 'error',
    body: t('Sigue vivo un arranque anterior hecho con otra configuración.'),
    next: t('El administrador debe revisarlo en el equipo antes de continuar. No hay botón de reintento a propósito.'),
  },
  launch_unverified: {
    label: t('Arranque sin verificar'),
    tone: 'error',
    body: t('Se intentó arrancar el motor, pero no quedó un registro completo del proceso.'),
    next: t('El administrador debe revisar el proceso y el registro local antes de nada. No se ofrece reintentar ni reiniciar a ciegas.'),
  },
}))

export const BINDING_COPY: Record<WorkstationStatus['generation_binding'], { tone: Tone; text: string }> = localized(() => ({
  matches: {
    tone: 'ok',
    text: t('Studio está configurado para generar con esta misma instalación; genera solo cuando el motor está en línea.'),
  },
  different: {
    tone: 'warn',
    text: t('Studio sigue generando con otra dirección de ComfyUI. Elegir aquí no redirige las tomas: el administrador debe cambiarlo en un momento sin renders.'),
  },
  not_selected: {
    tone: 'idle',
    text: t('Aún no hay instalación elegida, así que no se puede comparar con la que usa Studio para generar.'),
  },
  unknown: {
    tone: 'idle',
    text: t('No se pudo comparar con la dirección que usa Studio para generar.'),
  },
}))

/**
 * «Esta instalación genera tus tomas» only when the backend says the URLs match
 * and the live H3 capabilities agree the engine is reachable.
 */
export function generatesHere(status: WorkstationStatus, comfyOnline: boolean): boolean {
  return status.generation_binding === 'matches' && status.state === 'online' && comfyOnline
}

export const FOLDER_LABEL: Record<FolderKind, string> = localized(() => ({
  models: t('Modelos'),
  loras: t('LoRAs'),
  outputs: t('Resultados'),
}))

export const FOLDER_KINDS: FolderKind[] = ['models', 'loras', 'outputs']
