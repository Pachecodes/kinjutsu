# Resultado: UI de Instalación / ComfyUI / Carpetas (Claude)

Fecha: 2026-10-22 · Rama `claude/workstation-ui`, integrada en `main`. Sin despliegue en ninguna instancia viva.
Encargo: `docs/CLAUDE-WORKSTATION-UI.md`.

## Qué hay
- **Botón «Instalación»** en la cabecera, solo si `/api/openapi.json` publica las 7 rutas workstation.
  - **Contexto remoto** (Tailnet/HTTPS, o cualquier 403): explica que los controles actúan sobre el Windows del
    servidor y solo funcionan en localhost; **no llama** a ninguna ruta workstation.
  - **Cómo encaja**: Studio vs motor ComfyUI vs modelos/LoRAs; disco ≠ VRAM.
  - **Motor**: los 8 estados con texto propio. «Iniciar motor» (`capabilities.start`) y «Abrir ComfyUI»
    (`capabilities.open_comfy`) separados y explicados. `start` → «arrancado no es listo» y sondeo **GET** de
    status cada 2 s solo mientras `starting`. `port_conflict`, `unhealthy`, `configuration_changed`,
    `launch_unverified`: sin matar, reiniciar ni reintentar. No hay botón Stop/Restart.
  - `generation_binding`: «genera aquí» solo si `matches` + estado `online` + `comfy_online` de capabilities.
    `different` explica que elegir no redirige las tomas.
  - **Carpetas**: Modelos / LoRAs / Resultados según `capabilities.folders`, POST con `{}`; aclara que abre el
    Explorador del servidor.
  - **Buscar instalaciones**: GET discover solo al pulsar. «Aprobada» vs «Solo detectada», «Respondió ahora»
    vs «Sin respuesta», «Elegida». «Usar esta instalación…» solo para aprobadas, con consentimiento
    (`acknowledge:true`); aclara que no copia modelos ni redirige la generación.
  - **Carpetas de modelos**: «Verificar y reutilizar…» solo para raíz aprobada de la instalación elegida, con
    consentimiento; bloqueo de doble envío, estado «verificando SHA256… minutos», bloqueada si hay descarga de
    modelos activa; resultado con `verified_models` y aviso de reinicio. Raíces con `runtime_id:null` →
    «Ya autorizada para Modelos».
- **Modelos**: `label` del backend, «Lo usa: …» (`required_by` → nombre de receta), espacio libre en disco
  (no VRAM) y bloqueo previo si no cabe (+1 GiB), parcial válido → «Reanudar…» con bytes; parcial inválido →
  alerta sin reanudar. Licencias legibles con «Leer» (`/api/models/licenses/{name}`), mostradas como texto en
  `<pre>` (React escapa; nunca HTML).
- **Tour**: nuevo paso «Studio, motor y modelos». **Ayudas**: motor, aprobada vs detectada, disco vs VRAM.

## Verificación
Desde `studio/frontend`: 29 archivos / **161 tests** OK (base del repo: 27/145), `eslint` y `tsc` limpios.
`studio/frontend/dist` se reconstruyó desde estas fuentes en un worktree limpio.
Tests nuevos: `components/workstation/WorkstationDialog.test.tsx` (detección, estados, start→starting→online por
GET, sin POST al cargar, conflicto de puerto sin acciones, consentimientos, doble envío, carpetas, remoto/403)
y `components/models/ModelsExtras.test.tsx` (disco, parciales, licencia escapada).

Navegador real (dev server en 127.0.0.1 contra un backend local): marca Kinjutsu y detección OK. Las capturas
usan respuestas interceptadas con la forma exacta del contrato y el estado real leído por GET
(`unhealthy`, `binding=matches`). **Ningún POST** workstation se envió (verificado), ni se abrió Explorer/
navegador, ni se arrancó Comfy. Capturas del README: `docs/assets/` (datos sintéticos, sin rutas ni medios privados).

## Observación del entorno de prueba (no causada por este cambio)
Durante la prueba, el backend local respondía muy lento: `/api/config` y `/api/health` > 20–30 s, `/api/jobs` ~8 s,
`/api/workstation/status` ~3 s → `unhealthy`; `127.0.0.1:8218/system_stats` sí respondía. La UI tarda en
cargar mientras el backend está así. Conviene revisarlo en el equipo.

## Pendiente
- Despliegue en una instancia viva: solo en un momento sin renders (decisión de Jesús/Hermes).
- Los extras de API de la ronda anterior siguen pendientes (`frame_count/fps`, `cancel_state`, `stage_id`).
- Bundle 647 kB (202 kB gzip): candidato a dividir en chunks.
