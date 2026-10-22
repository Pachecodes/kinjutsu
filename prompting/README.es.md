# Prompts H3 sin agente: guía práctica

Este paquete **ordena lo que tú escribes**, sin llamar a Claude, OpenAI, MiniMax, Qwen ni otro LLM. No necesita claves API ni tokens de agente. El video final sí necesita el runtime H3/Comfy y sus modelos; este generador solamente produce texto.

**No mira imágenes ni videos. No traduce. No descubre la escena, la identidad, la voz ni la iluminación.** Describe tú los datos visuales y sonoros en inglés; escribe el diálogo en su idioma original. Si falta un campo esencial, muestra un error en vez de inventarlo. Tampoco evalúa consentimiento: usa solamente material autorizado de adultos para Character Swap.

## 1. Escoge la plantilla

| ID | Uso | Referencias |
|---|---|---|
| `character-swap-aligned` | Character Swap aprobado, prefijo `body_swap:` | `<Picture 1>` Identity + un Aligned guide **sin token de video** |
| `motion-ref2va` | Movimiento como referencia normal, seis secciones | Una imagen Identity + un Motion `<Video 1>`; opcionales imágenes Scene/Costume/Style |
| `t2va` | Video desde texto | Ninguna |
| `i2va` | Desarrollo desde primer frame | `<Picture 1>` First frame |
| `fl2va` | Trayectoria del primer al último frame | `<Picture 1>` First frame y `<Picture 2>` Last frame |
| `l2va` | Convergencia hacia último frame | `<Picture 1>` Last frame |

**Aligned guide no es Motion.** No cambies el rol de un video solo para evitar un error. Motion no equivale a la receta alineada aprobada y puede resultar muy lento con Qwen. El generador no alinea, recorta, convierte ni verifica archivos de video. El renderer valida la estructura del texto, no certifica una receta ni la calidad de la imagen.

## 2. Copia un formulario de ejemplo

Desde la carpeta del paquete, con el Python que hayas instalado:

```console
python scripts/build_prompt.py --list
python scripts/build_prompt.py --help
python scripts/build_prompt.py --template character-swap-aligned --input prompting/examples/character-swap-aligned.json --output prompting/mi-prompt.txt
```

También puedes usar el Python portátil del instalador si está disponible, sustituyendo `python` por su ejecutable. Los seis ejemplos son solamente JSON de texto ficticio; no contienen retratos ni videos. Edita una copia del JSON y vuelve a ejecutar el comando. `--output` reemplaza el archivo indicado: elige un archivo de salida propio. Sin `--output`, imprime el prompt UTF-8 en la terminal.

## 3. Rellena los campos sin inventar

- `duration_seconds`: duración efectiva del objetivo, positiva, máximo tres decimales. Por ejemplo `10.125`, **no siempre cinco segundos**. Usa el valor efectivo que presenta Studio. Este campo de texto no cambia los frames del proyecto.
- `identity`: identidad/apariencia que quieres conservar. Para aligned, una sola persona adulta. Nada de nombres o descripciones heredadas de otra escena.
- `style`: estilo en inglés. En I2VA/FL2VA/L2VA, descríbelo a partir de los frames que tú ves. En aligned, conserva el estilo del guía.
- `assets`: lista de referencias **realmente adjuntas**, en su orden. No pegues archivos, rutas personales, URLs, secretos o base64. Cada entrada tiene `kind`, `role`, `description`; las imágenes y el video Motion también tienen `token`.
- `shots`: cada toma necesita `start_seconds`, `scene`, `performance`, `camera`, `lighting` y `sound`. Escribe inglés concreto, no «lo que haya en la foto». Un movimiento de cámara se expresa como frase, por ejemplo `The camera pushes in with small amplitude at slow speed`.
- `audio`: `soundscape` describe ambiente/ruidos, sin repetir diálogo; `music` describe instrumentos, tempo y cambios o `N/A` si no hay música de fondo. `silent` debe ser `true` solo si pides **silencio total**; en ese caso `soundscape`, `music` y todos los `shots[].sound` deben ser `N/A`, sin diálogo.
- `dialogue`: lista opcional. Cada línea declara `shot` (desde 1), `start_seconds`, `end_seconds`, `speaker` (descripción estable de la voz/persona), `language`, `text` y `delivery`. Ejemplo: `language: "Spanish"`, `text: "¡Mira, aquí estoy!"`. El texto hablado se conserva literalmente, sin traducción ni corrección de puntuación. `voiceover: true` añade la instrucción de labios cerrados. En Motion, usa `subject: 1` cuando habla el personaje Identity; omítelo para una voz independiente.

Los campos son párrafos de una sola línea. No escribas llaves de plantilla, `TODO`, etiquetas incompletas, nuevas secciones manuales ni HTML. Los nombres técnicos de sección quedan en inglés automáticamente.

### Numeración exacta

Las imágenes se numeran entre imágenes, videos entre videos, independientemente de la posición en la lista: imagen Identity `<Picture 1>`, video Motion `<Video 1>`, imagen Scene `<Picture 2>`. No uses `<Picture 3>` si solo adjuntaste dos imágenes. En Motion puede ir una Scene antes de Identity: en ese caso Identity será `<Picture 2>`. Hay una sola identidad y un solo video Motion; varias imágenes adicionales pueden aportar escena, vestuario o estilo. Cada imagen secundaria se usa en todas las tomas de esta versión del formulario.

En aligned, el orden es **una imagen Identity `<Picture 1>` y un `kind: "aligned_guide", role: "aligned_guide"` sin propiedad `token`**. Nunca añadas `<Video 1>` al prompt aligned. El retrato aporta cara/proporciones, pelo y complexión intrínseca de toda la piel; el guía aporta actuación, expresión, boca, cuerpo/poses, ropa, accesorios, props, entorno, cámara, iluminación local y timing. Completa `scene`, `performance`, `camera` y `lighting` describiendo **el guía existente**, no una escena alternativa. Esta plantilla no permite nuevas tomas, diálogo ni música. No copia la voz del video.

### Tiempos

La primera toma empieza en 0; no recibe timestamp en el texto. Las siguientes tienen tiempos de corte estrictamente crecientes, menores que la duración total; se imprimen como `[Shot 2] At 00:03.125, ...`. Las líneas habladas tienen inicio y fin, no se solapan y caben enteras en una toma. Si atraviesan un corte, divide tú la línea: esta versión no genera automáticamente `<scenetrans>` ni `<cutoff>`. El generador no mide velocidad del habla: que los tiempos sean válidos no garantiza que el texto quepa al pronunciarlo.

## 4. Revisa y pega en Studio

Verifica tus etiquetas y que el prompt corresponde al material cargado. Copia el resultado al campo Prompt y revisa los controles y el video guía antes de generar. El programa **no cambia pesos, LoRAs, sampler, receta, título, duración del proyecto ni controles; no envía un render**. La aprobación de la plantilla aligned es de la estructura/ownership ya existente, no una garantía de calidad para todas las identidades o duraciones.

Las secciones Base son `integrated_multimodal_description`, `overall_soundscape`, `non_diegetic_music`. Motion usa `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`. Aligned usa su formato especializado `body_swap:`, no fuerza las seis secciones generales. Para Motion, aporta suficiente detalle en el formulario: la guía completa recomienda normalmente 350–500 palabras en la descripción; este renderer no rellena texto para alcanzar un conteo.

## Opcional: pedir ayuda a Claude u otro agente

No hace falta para ejecutar el programa. Si prefieres asistencia para escribir inglés o planificar tomas, comparte voluntariamente solo `skills/h3-prompt-writing/SKILL.md`, `references/base-en.txt`, `references/ref-en.txt` y una descripción autorizada de tu idea. No compartas archivos privados ni credenciales. Pídele conservar las secciones, el idioma del diálogo y las etiquetas exactas de tus adjuntos. Esto **no** activa una conexión desde Kinjutsu y el uso externo puede tener su propio coste. Para aligned, añade las reglas de ownership de esta guía; no conviertas el guía en Video 1.

## Errores comunes

- `missing required fields`: completa exactamente el campo indicado; no se inspeccionará tu media para llenarlo.
- `expected exact attached token`: corrige el orden/etiqueta para coincidir con Studio, no inventes adjuntos.
- `unsupported fields`: no pegues la solicitud completa de render; entrega solamente el formulario del esquema.
- `first must be 0` / `dialogue ... fit wholly`: revisa los tiempos y la duración efectiva.

Contrato técnico: `request.schema.json`; catálogo: `catalog.json`; integración local: `INTEGRATION.md`. Las validaciones específicas por plantilla viven en `renderer.py`, no solo en el JSON Schema.
