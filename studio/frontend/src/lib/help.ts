/**
 * Creator-facing help for every control, in one place so tooltips, the tour and
 * the inspector cannot drift apart.
 *
 * Each entry answers three questions: what it does, when to touch it, and what it
 * costs or cannot do. Nothing here promises quality: more steps, strength or
 * resolution are never presented as a guaranteed improvement.
 */

import { localized, t } from '../i18n'
import { BRAND } from './brand'
import type { RefRole } from './types'

export interface HelpEntry {
  what: string
  when?: string
  cost?: string
}

export const HELP = localized(() => ({
  mode: {
    what: t('La tarea: qué le das a H3 como punto de partida (solo texto, una imagen, dos imágenes o referencias).'),
    when: t('Elige primero la tarea; las referencias y recetas se adaptan a ella.'),
    cost: t('Cambiar de tarea puede quitar referencias o LoRAs que no encajan; se avisa siempre.'),
  },
  recipe: {
    what: t('Una receta carga parámetros (y a veces un prompt) en el compositor. No genera nada por sí sola.'),
    when: t('Úsala como punto de partida; todo queda editable en Avanzado.'),
    cost: t('Si la receta trae prompt, sustituye el tuyo. Se pide confirmación antes.'),
  },
  duration: {
    what: t('Duración de la toma. H3 trabaja a 24 fps y solo acepta longitudes 17k+5 (124, 175, 192, 243, 362 frames…).'),
    when: t('Prueba a 5 s; alarga cuando el resultado te convenza.'),
    cost: t('El render crece con frames y píxeles. Fuera de 124–362 frames (5,17–15,08 s) la calidad no está probada.'),
  },
  frame: {
    what: t('Tamaño del cuadro en píxeles, en múltiplos de 32.'),
    when: t('Vertical 9:16 para redes, 16:9 para cine. Con guía alineada debe coincidir con la guía.'),
    cost: t('Más píxeles = más VRAM y más tiempo. No garantiza más detalle.'),
  },
  autoRatio: {
    what: t('Ajusta la proporción a la primera imagen que subas, conservando más o menos el área de píxeles.'),
    when: t('Déjalo activo salvo que necesites un formato fijo.'),
  },
  method: {
    what: t('Método / acelerador: cómo se ejecuta el muestreo (caché, atención, recetas de pocos pasos). No cambia el modelo base.'),
    when: t('Fast Preview para explorar ideas; Quality cuando la fidelidad importa.'),
    cost: t('Los tiempos son medidas puntuales en {v0} (608×352, 5 s). Tu escena puede tardar más. Los experimentales pueden perder detalle.', { v0: BRAND.machine }),
  },
  checkpoint: {
    what: t('Modelo base (checkpoint): los pesos de H3 que generan el vídeo. FL2VA para texto y fotogramas; Ref2VA para referencias.'),
    when: t('Déjalo en Default salvo que la receta pida otro.'),
    cost: t('Cambiar de checkpoint obliga a recargar pesos (la primera toma tarda más).'),
  },
  encoder: {
    what: t('Codificador de prompt (Qwen3-VL): convierte tu texto en condicionamiento. No genera el vídeo.'),
    when: t('Standard siempre. Heretic es experimental.'),
    cost: t('Heretic no está validado y puede cambiar cómo se interpreta el prompt.'),
  },
  loras: {
    what: t('Adaptadores que modifican estilo o habilitan recetas (Turbo, Character Swap). Se aplican en el orden de la lista.'),
    when: t('Solo si una receta los pide o sabes qué hace el LoRA.'),
    cost: t('Más fuerza no es mejor. Los que no son compatibles con el checkpoint actual quedan desactivados.'),
  },
  loraStrength: {
    what: t('Cuánto pesa este LoRA sobre el modelo base.'),
    when: t('Empieza por la fuerza recomendada y cambia en pasos pequeños.'),
    cost: t('Valores altos suelen quemar texturas o deformar caras.'),
  },
  steps: {
    what: t('Iteraciones de muestreo.'),
    when: t('Respeta los pasos de la receta (Turbo8 = 8, Turbo4 = 4).'),
    cost: t('Más pasos = más tiempo. Con LoRAs turbo, más pasos no mejora y puede empeorar.'),
  },
  sampler: {
    what: t('Algoritmo que recorre el ruido hacia la imagen (euler, res_multistep, er_sde…).'),
    when: t('Solo si una receta lo indica.'),
    cost: t('Cambiarlo altera el resultado aunque uses la misma semilla.'),
  },
  scheduler: {
    what: t('Cómo se reparten los niveles de ruido entre los pasos.'),
    when: t('Solo si una receta lo indica.'),
  },
  sigmas: {
    what: t('Lista manual de niveles de ruido (descendente, termina en 0). Sustituye al scheduler.'),
    when: t('Solo para reproducir una receta que lo especifique.'),
    cost: t('Requiere Quality y continuidad apagada; nada se ignora en silencio.'),
  },
  seed: {
    what: t('Semilla: fija el ruido inicial. Misma semilla + mismos ajustes ≈ mismo resultado.'),
    when: t('Bloquéala para comparar cambios de prompt; déjala aleatoria para explorar.'),
  },
  continuity: {
    what: t('Divide tomas largas en ventanas seguras para la VRAM y las une por latentes.'),
    when: t('Solo para texto o referencias más largas que la ventana entrenada.'),
    cost: t('No funciona con fotogramas, Performance ni guías alineadas.'),
  },
  continuityWindow: {
    what: t('Frames por ventana cuando la toma se divide.'),
    when: t('Auto ajusta la ventana a la RTX 4090 y al tamaño actual.'),
  },
  continuityPin: {
    what: t('Frames que se solapan entre ventanas para mantener movimiento, color y sonido.'),
    when: t('22 es el recomendado.'),
    cost: t('Más solape = más cómputo por ventana.'),
  },
  refDetail: {
    what: t('Resolución con la que H3 lee las referencias.'),
    when: t('Match para casi todo; Max solo para identidades muy detalladas.'),
    cost: t('Max mantiene cada referencia a 2048 px en todos los pasos: el render puede tardar varias veces más.'),
  },
  includeAudio: {
    what: t('Pasa la pista de sonido del clip a H3 para guiar el ritmo.'),
    when: t('Para sincronía con música o diálogo del clip.'),
    cost: t('No copia la voz original tal cual; H3 genera su propio audio.'),
  },
  promptTags: {
    what: t('Etiquetas como <Picture 1> o <Video 1> nombran cada referencia en el prompt, en el orden de la bandeja.'),
    when: t('Menciona cada referencia; H3 las respeta más cuando las nombras.'),
  },
  promptBuilder: {
    what: t('Plantilla determinista: une tus campos (sujeto, acción, escena, cámara, luz, sonido) en un prompt.'),
    when: t('Cuando no sepas por dónde empezar. Siempre puedes editar el resultado.'),
    cost: t('No mira tus imágenes ni “mejora” el texto: solo lo ordena.'),
  },
  aiTools: {
    what: t('AI Director y Prompt chat usan un modelo local (Gemma) para proponer prompts. Son opcionales.'),
    when: t('Si quieres ideas. Nunca son necesarios para generar.'),
    cost: t('Ocupan GPU un momento antes de H3; se liberan solos. Desactivados con guía alineada.'),
  },
  prepareGuide: {
    what: t('Crea una copia del vídeo a 24 fps exactos, con el tamaño y los frames de la salida. Usa CPU, no la GPU.'),
    when: t('Siempre que la guía no coincida con la salida (tamaño, frames o fps).'),
    cost: t('Nunca modifica el original ni lanza un render. Si el vídeo es corto, se rechaza: no congela ni repite.'),
  },
  guideFit: {
    what: t('Pad conserva todo el encuadre con bandas negras; Crop recorta los bordes para llenar el cuadro.'),
    when: t('Pad si no quieres perder nada; Crop si las bandas molestan.'),
    cost: t('Crop elimina parte de la imagen.'),
  },
  easycacheThreshold: {
    what: t('Cuánto cambio tolera Fast Preview antes de recalcular un paso.'),
    when: t('0,3 es el valor medido.'),
    cost: t('Valores altos aceleran pero suavizan detalle fino y labios.'),
  },
  easycacheWindow: {
    what: t('Tramo del muestreo en el que se reutiliza la caché.'),
    when: t('0,2–0,9 es el tramo medido.'),
  },
  engine: {
    what: t('El motor ComfyUI es el proceso que renderiza en la GPU. Studio (esta app) prepara y envía las tomas; sin motor en línea no se genera.'),
    when: t('Inícialo cuando vayas a generar. Abrir la página de ComfyUI no lo arranca.'),
    cost: t('Arrancar carga pesos en VRAM y tarda; un puerto ocupado por otro programa bloquea el arranque.'),
  },
  installation: {
    what: t('Detectada significa que existe en el equipo; aprobada significa que el administrador autorizó usarla y arrancarla.'),
    when: t('Elige una instalación aprobada. Para aprobar otra, edita la configuración local del equipo.'),
    cost: t('Elegirla no cambia con qué genera Studio ahora; eso se ajusta sin renders en curso.'),
  },
  diskVsVram: {
    what: t('El espacio en disco guarda los modelos; la VRAM de la GPU es donde se cargan al generar. Son cosas distintas.'),
    cost: t('Tener disco libre no garantiza VRAM suficiente, ni al revés.'),
  },
  solTau: {
    what: t('Umbral de la atención dispersa SolAttn (experimental).'),
    cost: t('Medido más lento que Quality y con SSIM 0,778. Nunca por defecto.'),
  },
}) satisfies Record<string, HelpEntry>)

export type HelpKey = keyof typeof HELP

/** What each reference role contributes, phrased for a creator. */
export const ROLE_HELP: Record<RefRole, HelpEntry> = localized(() => ({
  first_frame: { what: t('La imagen con la que abre la toma.') },
  last_frame: { what: t('La imagen con la que cierra la toma. H3 rellena el movimiento entre ambas.') },
  identity: {
    what: t('Retrato canónico del personaje: cara, pelo y tono de piel.'),
    when: t('Una imagen nítida, de frente, buena luz. Es <Picture 1> si va primera.'),
  },
  subject: { what: t('Otra persona, criatura u objeto que debe aparecer.') },
  scene: { what: t('Lugar, decorado o fondo.') },
  style: { what: t('Paleta, gradación y tratamiento visual.') },
  prop: { what: t('Un objeto que el sujeto usa o lleva.') },
  motion: {
    what: t('Clip cuyo movimiento, ritmo y cámara se transfieren. Es un token <Video n> del prompt.'),
    cost: t('Experimental en Character Swap y muy lento en la 4090.'),
  },
  aligned_guide: {
    what: t('Guía alineada: el vídeo entero guía pose, gestos, ropa, escena y cámara desde el frame 0. No es un token <Video n>.'),
    when: t('Para Character Swap aprobado. Debe coincidir en tamaño, frames y 24 fps con la salida.'),
    cost: t('Sin audio: H3 genera su propio sonido.'),
  },
  scene_video: { what: t('Referencia de entorno en movimiento.') },
  voice: {
    what: t('Voz que guía la forma de la boca.'),
    cost: t('Máximo 15 s y debe ir con una imagen o un vídeo.'),
  },
  ambience: { what: t('Ambiente, música o efectos como referencia de sonido.') },
}))
