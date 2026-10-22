import { BRAND } from '../../lib/brand'
import type { MobileView } from '../../state/ui'
import { localizedList, t } from '../../i18n'

export interface TourStep {
  id: string
  title: string
  body: string[]
  /** `data-tour` ids, in priority order; the first visible one is highlighted. */
  targets: string[]
  /** On phones, the tab that holds the target. */
  mobileView?: MobileView
}

/**
 * The guided tour, in the order a creator actually works. It only points and
 * explains: it never uploads, generates, downloads models or changes settings.
 */
export const TOUR_STEPS: TourStep[] = localizedList(() => [
  {
    id: 'welcome',
    title: t('Bienvenido a {product}', { product: BRAND.product }),
    body: [
      t('Un recorrido corto por el camino completo: elegir tarea, subir referencias, preparar la guía, escribir el prompt, generar y reutilizar.'),
      t('Mientras lo recorres no se sube, genera ni descarga nada. Puedes salir en cualquier paso con Esc.'),
    ],
    targets: [],
  },
  {
    id: 'recipes',
    title: t('1 · Elige una receta'),
    body: [
      t('Las recetas cargan ajustes curados. «Character Swap · HD Turbo8 ✓» es la ruta aprobada para cambiar el personaje de un vídeo.'),
      t('Una receta nunca genera sola. Si trae prompt propio, te pregunta antes de sustituir el tuyo. Las experimentales están aparte y hay que activarlas.'),
    ],
    targets: ['recipes', 'settings-chips'],
    mobileView: 'compose',
  },
  {
    id: 'mode',
    title: t('2 · La tarea'),
    body: [
      t('Texto, animar una imagen, inicio + final, referencias o performance. Define qué le das a H3 como punto de partida.'),
      t('Al cambiar de tarea, lo que no encaja se quita y se avisa.'),
    ],
    targets: ['mode-switch'],
    mobileView: 'compose',
  },
  {
    id: 'references',
    title: t('3 · Identidad y guía'),
    body: [
      t('El retrato de identidad (<Picture 1>) aporta cara, pelo y tono de piel.'),
      t('El vídeo guía aporta pose, gestos, ropa, escena y cámara. Con la receta aprobada va como «Guía alineada», sin token de vídeo y sin sonido.'),
    ],
    // Text mode has no tray: point at the task switch, where references begin.
    targets: ['reference-tray', 'mode-switch'],
    mobileView: 'compose',
  },
  {
    id: 'duration',
    title: t('4 · Duración y encuadre'),
    body: [
      t('H3 trabaja a 24 fps con longitudes 17k+5 (124 frames = 5,17 s). La ventana entrenada llega a 362 frames (15,08 s).'),
      t('La guía debe coincidir exactamente con la salida. Si no, «Preparar guía» crea una copia nueva a 24 fps con CPU, sin tocar el original ni la GPU.'),
    ],
    targets: ['guide-sync', 'settings-chips'],
    mobileView: 'compose',
  },
  {
    id: 'prompt',
    title: t('5 · El prompt'),
    body: [
      t('Escríbelo a mano o usa «Plantilla» para ordenar sujeto, acción, escena, cámara, luz y sonido. La plantilla no usa IA.'),
      t('Director y Chat son ayudas opcionales con un modelo local; nunca hacen falta para generar.'),
    ],
    targets: ['prompt'],
    mobileView: 'compose',
  },
  {
    id: 'generate',
    title: t('6 · Generar y seguir el progreso'),
    body: [
      t('Generar está bloqueado mientras falte algo, y el motivo aparece al lado. La estimación es una referencia, no un compromiso.'),
      t('El escenario muestra la etapa actual y su porcentaje por separado del tiempo total. Cancelar pide confirmación.'),
    ],
    targets: ['generate'],
    mobileView: 'compose',
  },
  {
    id: 'gallery',
    title: t('7 · Descargar y reutilizar'),
    body: [
      t('Cada toma queda en la galería con su receta. Reutilizar la carga en el compositor (no genera); también puedes copiar el prompt, descargar, ocultar o eliminar.'),
    ],
    targets: ['gallery'],
    mobileView: 'gallery',
  },
  {
    id: 'workstation',
    title: t('8 · Studio, motor y modelos'),
    body: [
      t('Studio es esta app; el motor ComfyUI es el proceso que renderiza en la GPU; los modelos y LoRAs son archivos en disco que el motor carga en VRAM. Studio puede funcionar con el motor detenido, pero así no se genera.'),
      t('Si tu instalación lo incluye, «Instalación» separa Iniciar motor de Abrir ComfyUI, abre carpetas en el equipo servidor y busca instalaciones: encontrar una no la aprueba. «Modelos» instala solo lo que falta, con licencia y espacio en disco a la vista. Esos controles solo funcionan en el propio equipo.'),
    ],
    targets: ['workstation', 'models-button', 'advanced'],
    mobileView: 'compose',
  },
  {
    id: 'advanced',
    title: t('9 · Avanzado cuando lo necesites'),
    body: [
      t('Modelo base, codificador, LoRAs (en orden), método, sampler y continuidad viven en Avanzado, con una explicación en cada control.'),
      t('Si tu instalación lo incluye, el botón «Modelos» comprueba e instala pesos con tu consentimiento. Puedes repetir este recorrido desde «Guía».'),
    ],
    targets: ['advanced-panel', 'advanced'],
    mobileView: 'compose',
  },
])
