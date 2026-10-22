/**
 * Creator-facing help for every control, in one place so tooltips, the tour and
 * the inspector cannot drift apart.
 *
 * Each entry answers three questions: what it does, when to touch it, and what it
 * costs or cannot do. Nothing here promises quality: more steps, strength or
 * resolution are never presented as a guaranteed improvement.
 */

import { BRAND } from './brand'
import type { RefRole } from './types'

export interface HelpEntry {
  what: string
  when?: string
  cost?: string
}

export const HELP = {
  mode: {
    what: 'La tarea: qué le das a H3 como punto de partida (solo texto, una imagen, dos imágenes o referencias).',
    when: 'Elige primero la tarea; las referencias y recetas se adaptan a ella.',
    cost: 'Cambiar de tarea puede quitar referencias o LoRAs que no encajan; se avisa siempre.',
  },
  recipe: {
    what: 'Una receta carga parámetros (y a veces un prompt) en el compositor. No genera nada por sí sola.',
    when: 'Úsala como punto de partida; todo queda editable en Avanzado.',
    cost: 'Si la receta trae prompt, sustituye el tuyo. Se pide confirmación antes.',
  },
  duration: {
    what: 'Duración de la toma. H3 trabaja a 24 fps y solo acepta longitudes 17k+5 (124, 175, 192, 243, 362 frames…).',
    when: 'Prueba a 5 s; alarga cuando el resultado te convenza.',
    cost: 'El render crece con frames y píxeles. Fuera de 124–362 frames (5,17–15,08 s) la calidad no está probada.',
  },
  frame: {
    what: 'Tamaño del cuadro en píxeles, en múltiplos de 32.',
    when: 'Vertical 9:16 para redes, 16:9 para cine. Con guía alineada debe coincidir con la guía.',
    cost: 'Más píxeles = más VRAM y más tiempo. No garantiza más detalle.',
  },
  autoRatio: {
    what: 'Ajusta la proporción a la primera imagen que subas, conservando más o menos el área de píxeles.',
    when: 'Déjalo activo salvo que necesites un formato fijo.',
  },
  method: {
    what: 'Método / acelerador: cómo se ejecuta el muestreo (caché, atención, recetas de pocos pasos). No cambia el modelo base.',
    when: 'Fast Preview para explorar ideas; Quality cuando la fidelidad importa.',
    cost: `Los tiempos son medidas puntuales en ${BRAND.machine} (608×352, 5 s). Tu escena puede tardar más. Los experimentales pueden perder detalle.`,
  },
  checkpoint: {
    what: 'Modelo base (checkpoint): los pesos de H3 que generan el vídeo. FL2VA para texto y fotogramas; Ref2VA para referencias.',
    when: 'Déjalo en Default salvo que la receta pida otro.',
    cost: 'Cambiar de checkpoint obliga a recargar pesos (la primera toma tarda más).',
  },
  encoder: {
    what: 'Codificador de prompt (Qwen3-VL): convierte tu texto en condicionamiento. No genera el vídeo.',
    when: 'Standard siempre. Heretic es experimental.',
    cost: 'Heretic no está validado y puede cambiar cómo se interpreta el prompt.',
  },
  loras: {
    what: 'Adaptadores que modifican estilo o habilitan recetas (Turbo, Character Swap). Se aplican en el orden de la lista.',
    when: 'Solo si una receta los pide o sabes qué hace el LoRA.',
    cost: 'Más fuerza no es mejor. Los que no son compatibles con el checkpoint actual quedan desactivados.',
  },
  loraStrength: {
    what: 'Cuánto pesa este LoRA sobre el modelo base.',
    when: 'Empieza por la fuerza recomendada y cambia en pasos pequeños.',
    cost: 'Valores altos suelen quemar texturas o deformar caras.',
  },
  steps: {
    what: 'Iteraciones de muestreo.',
    when: 'Respeta los pasos de la receta (Turbo8 = 8, Turbo4 = 4).',
    cost: 'Más pasos = más tiempo. Con LoRAs turbo, más pasos no mejora y puede empeorar.',
  },
  sampler: {
    what: 'Algoritmo que recorre el ruido hacia la imagen (euler, res_multistep, er_sde…).',
    when: 'Solo si una receta lo indica.',
    cost: 'Cambiarlo altera el resultado aunque uses la misma semilla.',
  },
  scheduler: {
    what: 'Cómo se reparten los niveles de ruido entre los pasos.',
    when: 'Solo si una receta lo indica.',
  },
  sigmas: {
    what: 'Lista manual de niveles de ruido (descendente, termina en 0). Sustituye al scheduler.',
    when: 'Solo para reproducir una receta que lo especifique.',
    cost: 'Requiere Quality y continuidad apagada; nada se ignora en silencio.',
  },
  seed: {
    what: 'Semilla: fija el ruido inicial. Misma semilla + mismos ajustes ≈ mismo resultado.',
    when: 'Bloquéala para comparar cambios de prompt; déjala aleatoria para explorar.',
  },
  continuity: {
    what: 'Divide tomas largas en ventanas seguras para la VRAM y las une por latentes.',
    when: 'Solo para texto o referencias más largas que la ventana entrenada.',
    cost: 'No funciona con fotogramas, Performance ni guías alineadas.',
  },
  continuityWindow: {
    what: 'Frames por ventana cuando la toma se divide.',
    when: 'Auto ajusta la ventana a la RTX 4090 y al tamaño actual.',
  },
  continuityPin: {
    what: 'Frames que se solapan entre ventanas para mantener movimiento, color y sonido.',
    when: '22 es el recomendado.',
    cost: 'Más solape = más cómputo por ventana.',
  },
  refDetail: {
    what: 'Resolución con la que H3 lee las referencias.',
    when: 'Match para casi todo; Max solo para identidades muy detalladas.',
    cost: 'Max mantiene cada referencia a 2048 px en todos los pasos: el render puede tardar varias veces más.',
  },
  includeAudio: {
    what: 'Pasa la pista de sonido del clip a H3 para guiar el ritmo.',
    when: 'Para sincronía con música o diálogo del clip.',
    cost: 'No copia la voz original tal cual; H3 genera su propio audio.',
  },
  promptTags: {
    what: 'Etiquetas como <Picture 1> o <Video 1> nombran cada referencia en el prompt, en el orden de la bandeja.',
    when: 'Menciona cada referencia; H3 las respeta más cuando las nombras.',
  },
  promptBuilder: {
    what: 'Plantilla determinista: une tus campos (sujeto, acción, escena, cámara, luz, sonido) en un prompt.',
    when: 'Cuando no sepas por dónde empezar. Siempre puedes editar el resultado.',
    cost: 'No mira tus imágenes ni “mejora” el texto: solo lo ordena.',
  },
  aiTools: {
    what: 'AI Director y Prompt chat usan un modelo local (Gemma) para proponer prompts. Son opcionales.',
    when: 'Si quieres ideas. Nunca son necesarios para generar.',
    cost: 'Ocupan GPU un momento antes de H3; se liberan solos. Desactivados con guía alineada.',
  },
  prepareGuide: {
    what: 'Crea una copia del vídeo a 24 fps exactos, con el tamaño y los frames de la salida. Usa CPU, no la GPU.',
    when: 'Siempre que la guía no coincida con la salida (tamaño, frames o fps).',
    cost: 'Nunca modifica el original ni lanza un render. Si el vídeo es corto, se rechaza: no congela ni repite.',
  },
  guideFit: {
    what: 'Pad conserva todo el encuadre con bandas negras; Crop recorta los bordes para llenar el cuadro.',
    when: 'Pad si no quieres perder nada; Crop si las bandas molestan.',
    cost: 'Crop elimina parte de la imagen.',
  },
  easycacheThreshold: {
    what: 'Cuánto cambio tolera Fast Preview antes de recalcular un paso.',
    when: '0,3 es el valor medido.',
    cost: 'Valores altos aceleran pero suavizan detalle fino y labios.',
  },
  easycacheWindow: {
    what: 'Tramo del muestreo en el que se reutiliza la caché.',
    when: '0,2–0,9 es el tramo medido.',
  },
  engine: {
    what: 'El motor ComfyUI es el proceso que renderiza en la GPU. Studio (esta app) prepara y envía las tomas; sin motor en línea no se genera.',
    when: 'Inícialo cuando vayas a generar. Abrir la página de ComfyUI no lo arranca.',
    cost: 'Arrancar carga pesos en VRAM y tarda; un puerto ocupado por otro programa bloquea el arranque.',
  },
  installation: {
    what: 'Detectada significa que existe en el equipo; aprobada significa que el administrador autorizó usarla y arrancarla.',
    when: 'Elige una instalación aprobada. Para aprobar otra, edita la configuración local del equipo.',
    cost: 'Elegirla no cambia con qué genera Studio ahora; eso se ajusta sin renders en curso.',
  },
  diskVsVram: {
    what: 'El espacio en disco guarda los modelos; la VRAM de la GPU es donde se cargan al generar. Son cosas distintas.',
    cost: 'Tener disco libre no garantiza VRAM suficiente, ni al revés.',
  },
  solTau: {
    what: 'Umbral de la atención dispersa SolAttn (experimental).',
    cost: 'Medido más lento que Quality y con SSIM 0,778. Nunca por defecto.',
  },
} satisfies Record<string, HelpEntry>

export type HelpKey = keyof typeof HELP

/** What each reference role contributes, phrased for a creator. */
export const ROLE_HELP: Record<RefRole, HelpEntry> = {
  first_frame: { what: 'La imagen con la que abre la toma.' },
  last_frame: { what: 'La imagen con la que cierra la toma. H3 rellena el movimiento entre ambas.' },
  identity: {
    what: 'Retrato canónico del personaje: cara, pelo y tono de piel.',
    when: 'Una imagen nítida, de frente, buena luz. Es <Picture 1> si va primera.',
  },
  subject: { what: 'Otra persona, criatura u objeto que debe aparecer.' },
  scene: { what: 'Lugar, decorado o fondo.' },
  style: { what: 'Paleta, gradación y tratamiento visual.' },
  prop: { what: 'Un objeto que el sujeto usa o lleva.' },
  motion: {
    what: 'Clip cuyo movimiento, ritmo y cámara se transfieren. Es un token <Video n> del prompt.',
    cost: 'Experimental en Character Swap y muy lento en la 4090.',
  },
  aligned_guide: {
    what: 'Guía alineada: el vídeo entero guía pose, gestos, ropa, escena y cámara desde el frame 0. No es un token <Video n>.',
    when: 'Para Character Swap aprobado. Debe coincidir en tamaño, frames y 24 fps con la salida.',
    cost: 'Sin audio: H3 genera su propio sonido.',
  },
  scene_video: { what: 'Referencia de entorno en movimiento.' },
  voice: {
    what: 'Voz que guía la forma de la boca.',
    cost: 'Máximo 15 s y debe ir con una imagen o un vídeo.',
  },
  ambience: { what: 'Ambiente, música o efectos como referencia de sonido.' },
}
