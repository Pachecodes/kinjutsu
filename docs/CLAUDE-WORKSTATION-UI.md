# Claude: controles visuales de instalación / Comfy / carpetas

El backend ya está implementado y registrado. Contrato completo: `docs/WORKSTATION-API.md`. Detectar rutas en `/api/openapi.json`; no inventar responses ni aceptar rutas/comandos del formulario.

## Acciones

- `GET /api/workstation/status`: estado/capabilities/generation_binding.
- `GET /api/workstation/discover`: candidatos opacos y roots; búsqueda acotada, sin escaneo recursivo ni descarga.
- `GET /api/workstation/roots`: raíces disponibles para el perfil.
- `POST /api/workstation/select`: `{candidate_id,acknowledge:true}` sobre runtime aprobado.
- `POST /api/workstation/roots/select`: mismo payload para root aprobada, con hash completo antes de reutilizar. Puede tardar minutos; bloquear doble envío y explicar que no copia pesos.
- `POST /api/workstation/comfy/start`: `{}`; solo perfil autorizado y puerto libre. Si ya está sano devuelve reused:true, sin interrumpir jobs.
- `POST /api/workstation/comfy/open`: `{}`; abre navegador en el escritorio del servidor, no arranca el motor.
- `POST /api/workstation/folders/{kind}/open`: `{}`; kind=models|loras|outputs. Nunca pedir ni enviar un path arbitrario.

## Reglas visuales obligatorias

- Separar «Abrir ComfyUI» de «Iniciar motor». Start devuelve starting, no éxito listo; sondear status hasta online. No llamar POST desde efectos, tour, polling ni al abrir la página.
- Botones según capabilities. Port_conflict/unhealthy/configuration_changed/launch_unverified NO ofrecen matar/reiniciar/reintentar a ciegas. No hay endpoint Stop/Restart.
- Mostrar «usa esta instalación para generar» solo si generation_binding=matches y capacidades del renderer lo confirman. Seleccionar un runtime NO redirige automáticamente los clientes de generación existentes. Different exige cambio administrativo en un límite idle.
- La instalación propia verificada crea automáticamente un perfil aprobado si no existe otro. No pisa configuración del administrador ni selecciona por el usuario. Otras instalaciones detectadas necesitan aprobación administrativa antes de poder seleccionarlas/arrancarlas. No prometer auto-adopción de cualquier carpeta encontrada.
- **Solo controles locales**: peer, Host y Origin deben ser loopback/same-origin. Por Tailnet/HTTPS remoto responden403 deliberadamente. Ocultar o explicar controles de escritorio fuera del contexto local; abrir carpeta/browser afecta a Windows del servidor, no al teléfono del usuario.
- Receipts, perfiles, raíces y paths son estado privado e ignorado porGit; nunca incluirlos en informes/exportaciones ni renderizarlos comoHTML.
- Actualizar tour/tooltips: Studio vs motor, modelo base vs encoder/LoRA, reuso verificado vs encontrado, disco vs VRAM, perfil aprobado vs simplemente detectado.

## Estado de integración

El backend está probado con fixtures CPU y validación real de selección/status sobre una instalación existente, sin arrancar un segundo Comfy ni mover pesos. No hay botones workstation en el frontend todavía: esa es esta entrega visual. Modelos y Plantilla ya funcionan; no deshacer esos flujos.

Diseñar/probar con mocks del contrato o backend aislado; no abrir Explorer/browser del usuario, descargar modelos ni iniciar renders desde tests. No desplegar en vivo mientras existan jobs. Ver `VERIFICATION.md` para gates y límites reales.
