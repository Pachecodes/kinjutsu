# FastH3 Omni: evaluación documental para H3 Studio / ComfyUI

> **Nota histórica:** este documento conserva la evaluación previa a las pruebas. El estado posterior, la receta de escenas ejercitada en RTX4090 y la integración opcional están en [FASTH3-OMNI.md](FASTH3-OMNI.md). El dictamen original de «no se ha probado aquí» no describe el estado actual. Omni no sustituye la receta ganadora Character Swap.

**Dictamen:** candidato experimental para Ref2VA acelerado; no reemplazo validado del flujo CharacterSwap. Hay pesos Omni nativos para ComfyUI, incluido INT8 ConvRot. No se ha probado aquí su ejecución, calidad, velocidad, memoria ni compatibilidad con LoRAs. No se descargaron pesos, instalaron dependencias ni ejecutaron trabajos GPU o servicios.

## Anuncio exacto y alcance

- [Anuncio de eternityspring](https://x.com/eternityspring/status/2112712730155311227?s=20): enlaza la [colección FastH3 Omni](https://huggingface.co/collections/FastVideo/fasth3-omni). La afirmación de control total de personaje, movimiento y voz es lenguaje del autor, no garantía de conservación ni resultado local.
- [Omni BF16](https://huggingface.co/FastVideo/FastVideo-FastH3-Omni-8-Step-V1): texto más referencias ordenadas de imagen, video y audio; ocho evaluaciones del transformer; salida AV sincronizada, 24 FPS y audio estéreo de 32 kHz. La ficha admite hasta nueve imágenes, tres videos y tres audios, doce referencias en total; requiere al menos una imagen o un video.
- [V2](https://huggingface.co/FastVideo/FastVideo-FastH3-8-Step-V2) no es equivalente: es **T2VA**, no video sin audio. Ref2VA y FL2VA no fueron destilados. El anuncio simplifica esto como texto-a-video. V2 usa shift de video 10; Omni prescribe video/audio 12/3. Ambos usan ocho forwards, pero no son intercambiables.
- El [post citado del 7 de octubre](https://x.com/eternityspring/status/2107822061163077856) reporta RTX 4080, mismo prompt completo, 640×640, ocho segundos, semilla 20261007: V2 58.23 s frente a MiniMax H3 INT8 255.92 s. Es medición del autor sobre **V2**, no Omni ni una reproducción propia. No documenta en ese texto todos los detalles de sampler, offload, warmup, versiones y fronteras de tiempo. No trasladar esos tiempos a RTX 4090, Ref2VA, CharacterSwap o Comfy Omni.

## Artefactos realmente publicados

Metadatos leídos mediante la API de Hugging Face con `blobs=true`; tamaños exactos de archivo, no estimaciones de VRAM:

- [Omni Comfy, revisión 82eff2a6eee6c962846879f4bab52610a4df24d3](https://huggingface.co/FastVideo/FastH3-Omni-Comfy/tree/82eff2a6eee6c962846879f4bab52610a4df24d3):
  - `diffusion_models/fasth3_omniref_8step_pruned_bf16.safetensors`: 44,240,780,704 bytes.
  - `diffusion_models/fasth3_omniref_8step_pruned_int8_convrot.safetensors`: 22,213,723,064 bytes; SHA256 `851b2dc9670ed864b7f1e951ac9da047d83b1c04ded9bfcc1a9e5bba0ee33f80`.
- [Omni FP8 Comfy, revisión c45ffde960cba19428ca2e2c948efdadcd15218a](https://huggingface.co/FastVideo/FastH3-Omni-FP8-Comfy/tree/c45ffde960cba19428ca2e2c948efdadcd15218a): `fasth3_omniref_fp8_comfy.safetensors`, 23,046,497,628 bytes.
- [Omni NVFP4 QAD Comfy, revisión 36dbf15cd11113471114b1040c4f38646c031549](https://huggingface.co/FastVideo/FastH3-Omni-NVFP4-QAD-Comfy/tree/36dbf15cd11113471114b1040c4f38646c031549): `fasth3_omniref_qad_nvfp4_comfy.safetensors`, 13,773,998,700 bytes. La ficha exige Blackwell para inferencia NVFP4 acelerada; no asumir esa aceleración en Ada/RTX 4090.
- El [original BF16](https://huggingface.co/FastVideo/FastVideo-FastH3-Omni-8-Step-V1/tree/53e0d26a1691aa473b6262d8196a8feb2c297df0) contiene catorce shards de `transformer_ref`, configuración y schedulers. No es el archivo nativo Comfy.
- No aparece una variante **Omni W4A8** en los repositorios/colección oficiales revisados. El INT8 ConvRot publicado no debe relabelarse W4A8; tampoco el NVFP4 QAD. Que exista W4A8 para otros H3 no acredita Omni W4A8.

### Procedencia y límites de validación

- [SOURCE_PINS.json](https://huggingface.co/FastVideo/FastH3-Omni-Comfy/blob/82eff2a6eee6c962846879f4bab52610a4df24d3/conversion/upstream/SOURCE_PINS.json) fija ComfyUI `b1a247c9cf9dbfda4b2c0a0c1d50950667eeaa0c` y comfy-model-tools `d6797787e6bdb1a1fb0094d588a26f8e71a1c757`. El [audit de cuantización](https://huggingface.co/FastVideo/FastH3-Omni-Comfy/blob/82eff2a6eee6c962846879f4bab52610a4df24d3/conversion/QUANTIZATION_COMPATIBILITY.md) refiere comfy-kitchen 0.2.39.
- [Conversión documentada](https://huggingface.co/FastVideo/FastH3-Omni-Comfy/blob/82eff2a6eee6c962846879f4bab52610a4df24d3/conversion/CONVERSION.md): fuente BF16 congelada `88d512c5e7cc38dda499fbb65688ce58611f9c80`; fusión QKV, cambio de orden SwiGLU, preservación de 32 heads PDD y compresión aproximada AdaLN rank-8. «Pruned» no significa quitar bloques transformer entrenados.
- El INT8 se reutilizó sin recuantizar; hay comprobaciones de identidad y muestras de filas, no una validación end-to-end CUDA/calidad por ese audit. La etiqueta comercial «verified» no sustituye una prueba local.
- Los FP8 y NVFP4 de FastVideo y Comfy tienen layouts/escalas distintos. Los repos Comfy dedicados existen, pero no son un simple renombrado byte-idéntico del original. No copiar un checkpoint FastVideo al loader Comfy esperando equivalencia numérica.

## Reutilización sin duplicados

No es necesario descargar todo el checkpoint ni clonar todas las variantes para usar Comfy: escoger **un diffusion model Omni** y componentes auxiliares compatibles. La documentación declara válidos los encoders Comfy existentes de V2 y los VAEs originales completos de 36 capas.

[Plan de componentes compartidos y hashes](https://huggingface.co/FastVideo/FastH3-Omni-Comfy/blob/82eff2a6eee6c962846879f4bab52610a4df24d3/provenance/shared-copy-plan.json):

- Qwen3-VL-32B BF16: 51,506,295,256 bytes.
- Qwen3-VL-32B INT8 ConvRot: 27,141,342,152 bytes.
- Qwen3-VL-32B NVFP4 AWQ: 15,687,142,551 bytes; SHA256 `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6`.
- Video VAE FP16: 5,207,808,496 bytes; SHA256 `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522`.
- Audio VAE FP32: 605,254,808 bytes; SHA256 `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48`.
- Video VAE INT8 ConvRot alternativo: 2,811,065,184 bytes.

Compartir rutas de modelos/aliases en lugar de duplicar archivos, después de comparar hashes y comprobar que el encoder incluye la torre visual de referencias. Los hashes publicados no prueban que un archivo local del mismo nombre sea idéntico. La ficha recomienda BF16 o INT8 fuera de Blackwell para el encoder; el NVFP4 AWQ ya utilizable en otra configuración no acredita aceleración nativa NVFP4 ni compatibilidad Omni end-to-end en Ada. No reemplazarlo o redescargarlo automáticamente: verificar primero el backend/fallback real y su torre visual.

## Integración Comfy y CharacterSwap

- La ficha pide ComfyUI actual con soporte nativo MiniMax-H3 y **`MiniMaxH3ReferenceToVideo`**. [Código fijado de nodos](https://github.com/Comfy-Org/ComfyUI/blob/b1a247c9cf9dbfda4b2c0a0c1d50950667eeaa0c/comfy_extras/nodes_minimax_h3.py): referencias producen `minimax_refs`; `MiniMaxH3AddGuide` ancla imágenes/clips/audio a `frame_idx` mediante `minimax_keyframes`. Son mecanismos distintos, aunque coexistan en el código.
- Una referencia de video permite condicionar movimiento y contenido, pero no demuestra transferencia frame-aligned ni conservación exacta de interpretación, vestuario, cámara o escenario. No sustituye por sí sola AddGuide ni un CharacterSwap especializado.
- No encontré evidencia en las fichas/código revisados de compatibilidad validada **Omni + BFS CharacterSwap v1.1 + Turbo8 Ref2VA**. Cargar una LoRA sin error tampoco demostraría buena semántica. Omni ya es un student de ocho forwards: no apilar de entrada otra LoRA de aceleración. La supuesta equivalencia con Alibaba MiniMax-H3-Acc-LoRAs queda sin verificar.
- Ocho pasos, guidance 1.0, shifts 12/3 son prescripción publicada, no un benchmark local. El audit advierte diferencias en grilla PDD y atención VSA/densa entre Comfy y FastVideo. No presentar una plantilla V2 con shift 10 como workflow Omni.
- Una versión existente de Studio/Comfy no queda validada por el pin usado en la conversión. Antes de ofrecer un preset, verificar loader/detección PDD, esquema de ReferenceToVideo, kernels y serialización del request; mantener el flujo estable separado.

## FastVideo no es el runtime nativo Windows de Comfy

- [Instalación GPU oficial](https://haoailab.com/FastVideo/getting_started/installation/gpu/): **Linux o Windows WSL**, Python 3.10–3.12, CUDA 12.6/13.0. No documenta la ruta NVIDIA como Windows nativo.
- [Código FastVideo revisado](https://github.com/hao-ai-lab/FastVideo/tree/fa2d1324c60050cd65209c6aaeac470e7fb412f5), [dependencias](https://github.com/hao-ai-lab/FastVideo/blob/fa2d1324c60050cd65209c6aaeac470e7fb412f5/pyproject.toml): torch 2.12.0, transformers >=5.15.0, diffusers >=0.38.0; FlashInfer y fastvideo-kernel 0.3.5 condicionados a Linux. El extra fasth3 añade kernels adicionales. No instalar ese conjunto encima del Python de Comfy.
- [Guía Omni](https://github.com/hao-ai-lab/FastVideo/blob/fa2d1324c60050cd65209c6aaeac470e7fb412f5/docs/inference/fasth3_omniref.md) y [receta RTX 4090](https://github.com/hao-ai-lab/FastVideo/blob/fa2d1324c60050cd65209c6aaeac470e7fb412f5/examples/inference/basic/basic_fasth3_omniref_rtx4090.yaml): existe ruta oficial FP8 con offload layerwise, 16 bloques residentes, encoder no residente, atención VSA Triton BF16 y VAE denso. No usa el stack NVFP4 de Blackwell.
- Esa receta usa 832×480, 124 frames, ocho forwards, guidance 1.0 y proceso por clip; requiere composición de componentes compatibles y tabla AdaLN. La guía advierte sobre recargas del encoder y memoria de su entorno. Su existencia no garantiza ejecución, cabida ni tiempo en otro Windows/WSL o en Comfy; los tamaños de archivo tampoco bastan para garantizar 24 GB de VRAM.

## Licencias: puerta de entrada antes de probar/publicar

- [Pesos: MiniMax H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), no Apache/MIT. El texto excluye UE, Reino Unido, Corea del Sur y Estados Unidos, y limita también uso/distribución de outputs fuera del territorio autorizado. Para despliegue en territorios excluidos propone autorización separada. Confirmar alcance territorial y autorización aplicable; no inferir permiso de la descarga pública.
- Incluye autorización comercial previa sobre USD 20 millones anuales, identificación MiniMax H3 en UI comercial, obligaciones de redistribución/NOTICE, AUP y salvaguardas para servicios; prohíbe usar outputs para mejorar modelos ajenos a H3/derivados. CharacterSwap requiere derechos/consentimiento de identidad y material.
- [Código FastVideo](https://github.com/hao-ai-lab/FastVideo/blob/fa2d1324c60050cd65209c6aaeac470e7fb412f5/LICENSE): Apache-2.0. Tooling Comfy incluido: GPLv3, según los archivos fijados de licencia. Qwen3-VL tiene Apache-2.0 según la nota del acuerdo. Ninguna licencia de código elimina las restricciones de los pesos H3.

## Menor prueba futura útil, no ejecutada

1. Resolver licencia/territorio. Auditar sin GPU el esquema de nodos, pin de Comfy, soporte PDD y hashes de componentes ya disponibles. Si falla, registrar el bloqueo sin descargar nada.
2. Con autorización explícita posterior, aislar **un Omni INT8 Comfy** y reutilizar auxiliares compatibles; no instalar FastVideo ni duplicar VAEs. Validar carga/formato primero.
3. Un smoke mínimo puede usar 256×256, 22 frames, una referencia de imagen, ocho pasos, guidance 1.0 y shifts 12/3. Es fuera del rango de duración entrenado publicado: solo verifica cableado/AV, nunca calidad o rendimiento representativo. Para evaluar comportamiento usar luego un clip de 124 frames, una imagen + un video controlado, y resolución modesta compatible.
4. Comparar contra la línea base CharacterSwap con mismos medios, prompt, seed y geometría; primero Omni sin Turbo/BFS, después añadir una sola variable y AddGuide/BFS únicamente como experimentos separados. Registrar tiempos fríos/calientes, alcance de medición, VRAM/RAM, identidad, movimiento, vestuario, entorno y sincronía AV. No prometer mejoras antes de esas mediciones.

**Estado de publicación:** nota de investigación documental; no anuncia soporte productivo, equivalencia con CharacterSwap, permiso legal ni resultados medidos.
