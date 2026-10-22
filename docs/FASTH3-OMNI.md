# FastH3 Omni · Escenas

FastH3 Omni es una segunda receta, no una actualización del Character Swap existente ni una LoRA adicional. [Verificación de integración y límites de pruebas](FASTH3-OMNI-VERIFICATION.md).

- **Character Swap HD Turbo8** conserva la actuación de una guía alineada y reemplaza al personaje con Ref2VA + Turbo8 + Character Swap v1.1.
- **FastH3 Omni · Escenas** crea una escena nueva a partir de referencias y un prompt, con acción y audio generados. No admite mezclar los adaptadores de la receta Character Swap.

## Pesos opcionales, no incluidos en Git

El catálogo contiene el checkpoint opcional:

- Repositorio: `FastVideo/FastH3-Omni-Comfy`.
- Revisión: `82eff2a6eee6c962846879f4bab52610a4df24d3`.
- Archivo: `diffusion_models/fasth3_omniref_8step_pruned_int8_convrot.safetensors`.
- Tamaño exacto: **22,213,723,064 bytes**.
- SHA256: `851b2dc9670ed864b7f1e951ac9da047d83b1c04ded9bfcc1a9e5bba0ee33f80`.

La instalación base Character Swap no debe descargar este archivo automáticamente. Instalar Omni es una elección explícita. El gestor conserva descargas parciales reanudables y solo promueve un `.part` tras verificar tamaño y SHA256 completos. Las raíces locales autorizadas permiten reutilizar pesos verificados existentes antes de descargar. No se redistribuyen los modelos desde GitHub.

Omni reutiliza el encoder Qwen3-VL 32B y los VAEs de video/audio ya declarados en el manifiesto. No necesita una segunda copia de esos tres archivos si se encuentran y verifican en una raíz autorizada. No se escanea todo el disco ni se adopta un archivo solo porque tenga el tamaño correcto.

## Motor independiente

La receta usa el core ComfyUI auditado `b1a247c9cf9dbfda4b2c0a0c1d50950667eeaa0c`, con soporte nativo Omni/PDD, y un entorno Python propio. No se actualiza por debajo el motor histórico de Character Swap ni se aplican sus parches antiguos sobre el core nuevo.

- Loopback del motor Omni: `127.0.0.1:8237`.
- URL backend configurable: `H3_OMNI_COMFY_URL`.
- Seleccionar un método no instala pesos, acepta licencias ni inicia una inferencia por sí solo.
- Si el motor, soporte nativo o pesos requeridos no están disponibles, el método debe explicar el bloqueo en vez de enviar el job al motor anterior.
- No hay autoarranque, TensorRT ni custom nodes necesarios para Omni.

La configuración conservadora ejercitada en RTX4090 es NORMAL_VRAM con `--reserve-vram 6.0 --disable-dynamic-vram --disable-async-offload --disable-cuda-malloc`. Es una configuración de compatibilidad/margen WDDM, no una promesa de máxima velocidad en cualquier GPU. Dos motores instalados no implican que deban generar simultáneamente en la misma tarjeta.

## Instalación y arranque explícitos

Con la instalación base de Kinjutsu preparada, instalar explícitamente el perfil **FastH3 Omni** mediante la CLI que aparece abajo. Después, en **Workstation**, buscar y elegir esa instalación aprobada para iniciar su motor. **El panel no instala el runtime por sí solo.** Instalar/reutilizar el checkpoint opcional desde **Modelos**, con el consentimiento de licencia, antes de arrancar el motor. La instalación del runtime y la descarga del checkpoint son decisiones separadas; los tres auxiliares compartidos deben estar verificados.

Instrucciones desde la raíz del paquete en PowerShell:

```powershell
# Inspección offline, sin instalaciones ni arranque
.\runtime\venv\Scripts\python.exe .\scripts\kinjutsu.py plan --profile fasth3-omni
# Instala solo el motor/entorno separado; no inicia inferencia
.\runtime\venv\Scripts\python.exe .\scripts\kinjutsu.py install --profile fasth3-omni
# Opción explícita para descargar únicamente el checkpoint Omni faltante;
# leer antes las licencias y comprobar los auxiliares compartidos.
.\runtime\venv\Scripts\python.exe .\scripts\kinjutsu.py install --profile fasth3-omni --download-models
.\runtime\venv\Scripts\python.exe .\scripts\kinjutsu.py start --profile fasth3-omni
.\runtime\venv\Scripts\python.exe .\scripts\kinjutsu.py stop --profile fasth3-omni
```

No ejecutar ambas variantes de instalación por rutina: la segunda solo corresponde si se eligió descargar los pesos mediante CLI en lugar de Modelos. Esperar salud/capacidades reales antes de generar; `starting` no es `online`. Cambiar perfiles no descarga la VRAM del motor anterior por sí solo.

## Receta de generación

Método API `fast_h3_omni_8step`; preset `fasth3-omni-scenes`.

- Referencias nativas (`ref2va`), al menos una imagen o video. No es el método FastH3 V2 de texto-a-video.
- Checkpoint Omni INT8 y encoder estándar.
- Euler / simple / **8 pasos**, BasicGuider (guidance1), denoise1.
- `MiniMaxH3SigmaShift`: video12 / audio3; scheduler y guider usan el modelo desplazado.
- Sin LoRAs adicionales, guía alineada de Character Swap, mezcla con otros métodos ni partición automática de continuidad.
- Referencia de imagen `max` en el preset creativo. `match` es un ahorro opcional de detalle/contexto y no equivale a la configuración de referencia completa usada en estas pruebas.
- Punto de partida: **124 fotogramas a24FPS**, aproximadamente5.17s. Dimensiones múltiplos32 y proporción adecuada para la referencia.

El soporte nativo de múltiples tipos de referencia no certifica cada combinación, idioma, duración o resolución. Los tiempos y aceptación inicial se obtuvieron con una sola imagen y un clip corto; no se deben extrapolar a HD,15s o referencias de video largas.

## Prompts y voz

Usar `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape` y `non_diegetic_music`. Referenciar los activos adjuntos mediante `<Picture 1>`, `<Video 1>` o `<Audio 1>` según su orden real. No inventar tokens para archivos ausentes.

La foto define identidad/rasgos/ropa; describir una acción realizable, entorno y cámara. Es condicionamiento generativo, no bloqueo de primer frame ni garantía de identidad exacta. Para una frase breve: `<d>[Spanish] El café está listo. ¿Te quedas?</d>`.

El audio de Omni es nativo y generado. Una referencia visual no crea una voz de identidad clonada. Un transcript ASR exacto no certifica escucha subjetiva, entonación perfecta ni sincronización labial medida.

## Evidencia previa de la receta en RTX4090

Pruebas del runtime nativo aislado, no benchmarks universales:

- Desayuno,832×480,124frames:627.421s desde motor recién iniciado;123.337s en repetición caliente real.
- Nueva escena con foto, acción y frase española,512×640,124frames:86.443s con el mismo motor ya abierto.
- En la repetición del desayuno se recalculó condicionamiento y se ejecutaron ocho pasos: no se reutilizó un video final cacheado. Los fotogramas decodificados coincidieron exactamente.
- Caliente conserva objetos/cachés de modelos y RAM/offload; no significa que toda la pila quepa simultáneamente en VRAM. El primer caso no controla la caché de archivos del sistema operativo.

No son comparaciones de velocidad con Character Swap ni con un control Ref2VA20 de calidad equivalente. Comfy INT8 no es una reproducción numérica de FastVideo NVFP4 QAD; la4090 no tiene aceleración FP4 nativa de Blackwell.

## QA y operación

Verificar propietarios/colas de todos los motores antes de GPU. No interrumpir trabajos ajenos ni liberar modelos calientes sin necesidad/autorización. Guardar petición, workflow ejecutado, semilla, versión, tiempos y VRAM.

Validar dimensiones, frames,24FPS y streams con ffprobe; decodificar video/audio completos con FFmpeg. Revisar apertura densa y clip completo para cara, manos, objetos, ropa y continuidad; comprobar diálogo cuando se solicitó. No publicar un resultado defectuoso como exitoso solo porque el MP4 decodifica.

Conservar siempre la receta ganadora Character Swap por separado. La combinación Omni + Character Swap v1.1 encajó por forma de tensores y terminó inferencia, pero no estableció un reemplazo convincente en el fixture probado; no es una tercera receta recomendada.

Los términos de MiniMax y las autorizaciones aplicables a los pesos siguen siendo independientes de las licencias del código del Studio.
