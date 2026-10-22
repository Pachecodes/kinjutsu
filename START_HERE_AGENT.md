# Pachecodes : Kinjutsu — instrucciones para el agente instalador

## No necesitas agente

El uso normal es doble clic en `INICIAR.vbs` y luego `DETENER.vbs`. No requiere Claude, Hermes ni claves API. Lo siguiente es asistencia opcional para diagnóstico técnico; no un paso obligatorio.

## Tu encargo opcional

Instala y verifica la receta local Character Swap HD Turbo8 de este repositorio para Windows11 + RTX4090. Este documento funciona con Claude Code u otro agente con terminal. Todo lo necesario está en esta carpeta, salvo los modelos base/dependencias descargables y las futuras imágenes/videos del propietario. No requiere Hermes ni acceso al equipo de quien preparó el paquete.

## Antes de cambiar nada

1. Lee `README.md`, `THIRD_PARTY_NOTICES.md`, `docs/INSTALLATION-TECHNICAL.md`, `dependencies/`, `models/manifest.json` y los SKILL.md de `skills/`.
2. Inspecciona sistema, driver, nvidia-smi, RAM, disco, Python/Git/Node/uv/ffmpeg y puertos8218/8220. Descubre herramientas antes de instalar. No uses el username como hostname.
3. Conserva la carpeta completa: los dos LoRA están físicamente incluidos; no descargues modelos base duplicados si ya existen y su SHA256 coincide. No modifiques instalaciones ajenas, otros perfiles de agentes, drivers o servicios sin aprobación.
4. Usa los scripts de este repo; léelos antes de ejecutarlos. No sustituyas versiones fijadas por latest ni instales paquetes GPU al azar. Si un requisito falla, informa del error real y corrige dentro del entorno aislado. No simules salidas.
5. Verifica el alcance de las licencias. No expongas el servicio como API pública/SaaS, no crees túneles externos ni agregues secretos al repo. El uso de la interfaz local como herramienta interna no equivale a autorizar una plataforma para terceros.

## Procedimiento de instalación

1. Ejecuta las pruebas de paquete y la verificación offline disponible. Los scripts PowerShell deben pasar el parser antes de ejecutarse. El README técnico describe los switches reales; no inventes parámetros.
2. Ejecuta `scripts/Install-Kinjutsu.ps1` desde PowerShell. Usa instalación aislada y versiones de `dependencies/`. Instalación/download no equivalen a render.
3. Los modelos externos requeridos son SOLO los cuatro `included=false` de `models/manifest.json`: Ref2VA pruned INT8ConvRot, Qwen3VL32BNVFP4AWQ, videoVAEfp16 y audioVAEfp32. Descarga desde las revisiones fijadas, de forma reanudable a.part, comprueba tamaño y SHA256 antes de renombrar. Los2LoRA `included=true` se mantienen en el árbol central y se mapean al motor, sin copia.
4. Instala el core ComfyUI fijado y aplica los backports de `runtime/`. **Registrar un nodo AddGuide no basta:** el core debe soportar las filas temporales completas y concatenación de guía/referencias. Verifica la aplicabilidad y tests; no reemplaces por referencia de video normal.
5. Instala backend y frontend del Studio limpio. Compila frontend o verifica el build distribuido. No copies .env/historial ni rutas de otra computadora.
6. Arranca con `scripts/Start-Kinjutsu.ps1`. Escucha solo127.0.0.1: Comfy8218 y Studio8220. Guarda logs/PIDs propios; sin autoarranque.
7. Verifica `/api/health`, `/api/capabilities?refresh=true`, catálogos `/object_info` y `/api/openapi.json`. Requiere `aligned_guides=true` y MiniMaxH3AddGuide. Comprueba que los catálogos vean exactamente todos los archivos del manifiesto.
8. Ejecuta `scripts/Verify-Kinjutsu.ps1` y las pruebas del repo. No des por completada la instalación si el backend está offline o el frontend es un build distinto al código limpio.

## Primera ejecución real

Cuando la instalación esté lista, solicita al propietario una foto nítida de identidad y un video guía propios. No inventes personajes ni descargues rostros personales como prueba. Evita gastar GPU generando un render sin esos inputs y el permiso del propietario.

1. Revisa la foto y una hoja de contacto del video; una persona adulta, cara visible, buena luz y movimiento continuo facilitan el primer ensayo. Inspecciona resolución/duración/FPS con ffprobe.
2. Prepara los primeros124frames a24FPS/736x1280, conservando velocidad/aspecto. El flujo completo y requisitos están en `skills/kinjutsu-character-swap/SKILL.md` y `workflows/README.md`.
3. Subir foto y guía a `/api/assets` (multipart campofile), descargar y comparar hash. No reutilices IDs de otra DB. Sustituye ambos placeholders de `workflows/approved-api.json` por los IDs devueltos. Personaliza SOLO descripción de la escena, ropa, accesorios y actuación según el guía.
4. Mantén mode=ref2va,method=baseline,weights=int8,encoder=standard,Turbo8→Swapv1.1ambos1.0,Euler/simple8,match,BasicGuider,continuityoff,seed20261021 para la prueba inicial. `baseline` es una etiqueta de método, no una orden de usar20pasos.
5. POST `/api/validate`; exige ok=true. Solo entonces POST `/api/jobs` y captura `response.job.id`. Guarda request/recibo y lee el job; evita duplicados si ya se envió. Poll únicamente ese job.
6. Al terminar, descarga el output y `/api/jobs/{id}/workflow`. Demuestra que el grafo ejecutado usó ambos LoRA, AddGuide y8pasos.
7. Crop8px por lado a720x1280; no upscale. ffprobe, decodificación completa y QA visual densa, incluidos manos/brazos/cuello, dedos/props/ropa/final. El audio requiere escucha y no es el original salvo remux explícito.
8. Entrega el MP4 y evidencia real. Si hay defectos, descríbelos sin prometer que más fuerza/pasos arreglan todo.

## Duración y límites

Para el video completo, redondea hacia arriba los frames24FPS a17k+5, rellena solo al final clonando el último frame, renderiza alineado y recorta el relleno solo en la entrega. Aproximadamente10s fueron probados.15–30s son una ampliación a validar, no un soporte de calidad/VRAM ya demostrado. No dividas ni acortes silenciosamente una solicitud de toma continua.

## Definición de terminado

- Entorno aislado instalado, hashes correctos, Studio y Comfy responden con nodos/modelos correctos.
- Frontend limpio visible y función de guía alineada accesible.
- Prueba real solo cuando existan inputs/autorización, con MP4 decodificado y revisado.
- Sin endpoints públicos, autoarranque, historial/identidades privadas ni credenciales.
- Si una parte no pudo probarse, se declara exactamente cuál. Una prueba CPU o parser no se vende como instalación GPU limpia.

No pruebes Swapv1.5 ni cambies la receta en este paquete: es una comparación futura separada.
