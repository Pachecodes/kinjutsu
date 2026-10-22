# Verificación de integración FastH3 Omni

## Resultado

La revisión independiente final aprobó backend, frontend, instalación opcional y recuperación de arranques fallidos, sin incidencias de seguridad o lógica pendientes. El código añade una segunda ruta; no cambia el core, lock ni receta predeterminada Character Swap.

Pruebas ejecutadas sobre la rama de integración, en Windows, con Python3.12.10 y Node22.22.0 fijados:

| Comprobación | Resultado real |
|---|---|
| Suite raíz completa (`pytest tests`) |47 aprobadas,1 omitida|
| Backend completo |465 aprobadas,25 omitidas,1 fallo de temporización ya presente en la base|
| Frontend completo (Vitest,32 archivos) |187 aprobadas|
| TypeScript (`tsc -b`) |aprobado|
| ESLint |aprobado|
| Build de producción Vite |aprobado; incluido en el repo|
| Escaneo de líneas nuevas |sin hallazgos de secretos, shell injection, eval/exec, pickle o SQL interpolado|
| Gate de privacidad e inventario Git |aprobado, sin pesos ni estado local privado|

Son suites independientes con cobertura superpuesta: no sumar estos números como un total único de casos.

### Fallo de base conocido

`tests/test_workstation.py::test_probe_read_timeout_is_bounded` exige menos de1.5s. El pase completo final midió aproximadamente1.86s. El mismo test falló en el worktree intacto de la base `6a49582287f0474fbb1a52f25e7c8ebb49a584c1` (aproximadamente2.59s). No se modificó el umbral ni se ocultó el fallo para publicar esta funcionalidad. Los tests específicos de seguridad y recuperación de arranque Omni aprobaron.

Las primeras ejecuciones con el Node26 global y excesivo paralelismo mostraron incompatibilidad de localStorage y timeouts de interfaz. El pase válido usó el Node22.22.0 del contrato y workers limitados. No se cambió la aplicación para esconder esa diferencia de entorno.

## Comprobación HTTP y navegador

Se arrancó una instancia CPU de Studio en un puerto loopback distinto del Studio en uso, con base de datos/directorio de prueba propios:

- Salud200; método y preset Omni aparecen con su backend independiente.
- Motor Omni deliberadamente apagado: disponibilidad `false`, motivo explícito; validación rechazada en lugar de enviarse al motor normal.
- Subida de una imagen sintética de prueba: lectura de bytes idéntica; borrado y404 posterior comprobados. No se presentó esa imagen como una generación.
- En navegador, Character Swap siguió siendo el preset predeterminado. Omni apareció separado, bloqueado al faltar su motor, con acceso alcanzable a configuración y modelos. Abrir ese acceso no inició instalación, descarga ni inferencia.

## Regresiones cubiertas

- Historial Omni con preset incompatible no vuelve a asignar `aligned_guide` ni descarta un video adjunto.
- Defaults de lienzo Omni se resuelven antes del ajuste a múltiplos32.
- El lienzo previamente ejercitado832×480 es válido; el límite operativo es399360píxeles y124frames. El ajuste automático de proporción no supera ese límite; los lienzos manuales y el sizing legacy no se alteran silenciosamente.
- Una excepción de spawn o un hijo muerto inmediatamente limpia solo su propio claim/proceso. Un listener/PID ajeno nunca se adopta ni se termina.
- Upload, envío, progreso, historial, outputs y cancelación se enrutan al cliente Omni; no reutilizan a ciegas nombres del motor normal.
- Instalación base ignora pesos opcionales; el perfil Omni tiene core/entorno/mapping separados y verificación completa de auxiliares reutilizados.

## Alcance que no debe confundirse

La receta nativa y el checkpoint ya se ejercitaron previamente en RTX4090 con clips AV reales; métricas y límites están en [FASTH3-OMNI.md](FASTH3-OMNI.md). Esta actualización de código se comprobó con tests CPU, contratos de transporte y navegador: **no se repitió una instalación GPU limpia ni un nuevo render CUDA desde esta rama**. Tampoco se volvió a descargar el checkpoint de22GB para simular una instalación nueva.

Los outputs ficticios de fixtures de transporte solo comprueban enrutamiento HTTP; no son evidencia de calidad de video. No hay benchmark nuevo contra Character Swap, garantía universal de dos minutos, voz clonada ni certificación de referencias múltiples/HD/tomas largas.

El código, locks y frontend compilado se publican sin modelos, retratos, clips privados, historiales, configuraciones de otra computadora o credenciales. Publicar el repo no equivale a actualizar la instalación viva de Studio.
