# Contrato de administrador de modelos (para integración UI)

Implementado en `studio/backend/app/services/model_manager.py`, registrado en `app/api.py`.

- `GET /api/models/catalog`: `manifest_sha256`, `free_bytes` (espacio libre del volumen destino `models/`, no VRAM), `models[]` con `id` opaco (índice estable del manifiesto), `target`, `label`, `role`, `required_by`, `size`, `sha256`, `repo`, `revision`, `included`, `installed`, `verified`, `reused`, `partial_bytes`, `partial_valid_size`; documentos de licencia. Los nombres/roles se derivan de los seis artefactos conocidos sin modificar el manifiesto de pesos. `partial_bytes` persiste tras reiniciar; no certifica integridad del parcial ni reanuda automáticamente. `partial_valid_size:false` exige inspección si el parcial supera el tamaño fijado. Realiza hash completo en raíces autorizadas; puede tardar con 44 GB. Ejecutar como tarea UI con indicador, no polling cada segundo.
- `GET /api/models/licenses/{name}`: texto plano UTF-8, únicamente `MINIMAX-H3-LICENSE.txt`, `BFS-CHARACTER-SWAP-LICENSE.md` y `BFS-ASSET-SCOPE.md`. No acepta rutas ni sirve otros archivos; no interpretar el texto de licencia como HTML. Desconocidos/traversal/archivo ausente: 404.
- `GET /api/models/status`: `downloads[]` con `id`, `status`, `bytes`, `total`, `error`; `restart_comfy_after_install: true`. Estados: queued/downloading/verifying/installed/cancelled/error. Estado de trabajos en memoria; tras reinicio vuelve a descubrir pesos y `.part`, no reanuda sin consentimiento explícito.
- `POST /api/models/{id}/install`, JSON `{"license_acknowledged":true}`: consentimiento explícito obligatorio. Una descarga activa por proceso. Reutiliza archivo exacto verificado sin copiar; de lo contrario descarga solo URL HF/revisión/path del manifiesto. No acepta URL, ruta ni auth del cliente. HTTP 409 para errores de selección, licencia, disco, final incorrecto o descarga activa.
- `POST /api/models/{id}/cancel`, sin body: solicita cancelación. No borra `.part`; la lectura HTTP puede tardar hasta timeout 30 s en observarla. Para reanudar, volver a pulsar Instalar y aceptar licencia; valida HTTP Range/Content-Range y SHA256 antes de promoción atómica. No se sobrescribe un final incorrecto.

Solo mutaciones locales sin Origin externo; JSON rechaza campos extra. No son endpoints públicos/autenticados: no exponer la aplicación a LAN/túneles. No hay claves, pagos ni llamadas de agentes.

## Descubrimiento sin duplicados

Configuración administrativa **local y offline**, no un selector de rutas API: `runtime/model-roots.json`, forma `{"roots":["X:/Models/ComfyUI/models","X:/Models/vae"]}`. Deben ser carpetas absolutas existentes. Solo consulta `raiz/target` y `raiz/nombre_exacto`, sin rglob ni disco completo; rechaza escapes por symlink fuera de raíz. Hash completo incluso si tamaño coincide. No hay importación automática de un YAML arbitrario de Comfy: seleccione explícitamente sus raíces.

Mapeo generado: `runtime/extra_model_paths.yaml`; `base_path` apunta al padre del archivo **verificado**, en su categoría. No copia ni hardlinka pesos. Reinicie Comfy mediante DETENER/INICIAR después de cambios. Recibos reales de descarga: `runtime/download-receipts/{sha256}.json`, con URL fija, revisión, bytes, hash y aceptación. No hay recibo inventado para modelos reutilizados. No comparta ese runtime local.

## UX que debe conectar Claude

Mostrar tarjetas de catálogo con tamaño/faltante/verificado/reutilizado; explicar licencia y pedir confirmación antes de red. Botón explícito Instalar/Reanudar, progreso real, Cancelar, errores españoles y aviso de reinicio. No prometer generación saludable hasta que core/pesos/nodos estén disponibles. La instalación de un clic inicial sigue descargando la base tras consentimiento; no existe todavía un modo de instalación liviana sin torch/modelos que abra una pantalla inicial de administración.

Presets conservan todos los métodos y parámetros avanzados. API añade `group: recommended|control|experimental`, `default: true` solo para HD Turbo8. No interpretar `recommended` como modelo instalado ni ranking nuevo. Disponibilidad real requiere pesos/encoder/LoRA/modo y nodos; presets faltantes se desactivan con motivo. Crear colección experimental opt-in sin retirar Baseline Quality20, Fast Preview EasyCache, W4A8+LightX2V y controles. Mantener Advanced libre pero capability-gated. Añadir tooltips/tour interactivo y explicar duración real en cuadrícula, guía normalizada y procedencia.

## Pruebas

`tests/test_model_manager.py`: servidor HTTP real local con Range, parcial real, SHA256, recibo, mapping, reuso sin copia, tamaño correcto/hash incorrecto, cancelación+reanudación, final incorrecto, licencia e ID ajeno. Solo fixtures de pocos MB; no descarga base en pruebas.
