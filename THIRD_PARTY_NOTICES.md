# Pachecodes : Kinjutsu — avisos de terceros

Este kit reúne una interfaz y procedimientos de instalación; no convierte modelos ni dependencias en propiedad de Pachecodes. Cada componente mantiene sus autores y términos. No se aplica una licencia única a todos los pesos/código. Conservar este archivo y `licenses/` al compartir la carpeta. No publicar automáticamente en GitHub ni vender los pesos como producto independiente.

## Character Swap v1.1 — Alissonerdx

Archivo: `minimax_h3_character_swap_v1.1_ref2va_fro.safetensors`.
Fuente: https://huggingface.co/Alissonerdx/Minimax-H3-ComfyUI
Licencia y alcance copiados íntegros en `licenses/BFS-CHARACTER-SWAP-LICENSE.md` y `licenses/BFS-ASSET-SCOPE.md`.

BFS Character Swap Community License1.1 permite descargar, usar, modificar y compartir los pesos conservando licencia/copyright; permite crear y vender medios. Organizaciones por encima del umbral de ingresos indicado deben atribuir al autor. Prohíbe vender/reempaquetar pesos o cobrar por su acceso como producto independiente y ofrecer pesos o funcionalidad como API hospedada, SaaS u otro servicio de inferencia remoto, gratuito o pagado. El propósito de este kit es uso local interno, no operar una plataforma de swaps para terceros. Este resumen no sustituye el texto completo.

## MiniMax H3 — MiniMaxAI; empaquetado Comfy-Org

Pesos base se descargan aparte: https://huggingface.co/Comfy-Org/MiniMax-H3
Modelo original: https://huggingface.co/MiniMaxAI/MiniMax-H3
Términos copiados en `licenses/MINIMAX-H3-LICENSE.txt`; model card del empaquetado en `licenses/COMFY-MODEL-CARD.md`. Revisar condiciones de uso/comercialización, atribución y restricciones aplicables antes de instalar o publicar resultados. El usuario debe aceptar los términos si la fuente lo requiere; el agente no debe evadir una puerta de autenticación/licencia.

El encoder Qwen cuantizado está documentado por el empaquetador como derivado de Qwen3-VL-32B-Instruct-NVFP4. Mantener también los términos de sus fuentes y dependencias; el formato de cuantización no elimina derechos upstream.

## Ref2VA Turbo8 — LightX2V / ModelTC

Fuente exacta y revisión en `models/manifest.json`.
Model card preservado en `licenses/LIGHTX2V-MODEL-CARD.md`.
Código/documentación upstream: https://github.com/ModelTC/Minimax-H3-Turbo y https://github.com/ModelTC/LightX2V
No inferir una licencia de pesos a partir de una licencia de código: el model card preservado remite a los términos del repositorio y los del modelo base siguen aplicando. El archivo local tiene un alias histórico `latest_h3_...`; la revisión y SHA256 fijan su contenido real, no se resuelve a latest durante la instalación. Este paquete no concede derechos adicionales.

## ComfyUI y AddGuide

ComfyUI: https://github.com/Comfy-Org/ComfyUI
Core y licencia se conservan en la instalación del motor. Las adaptaciones incluidas deben conservar avisos/copyright originales. AddGuide se distribuye junto a su licencia y procedencia en `runtime/`; ver README técnico de ese componente. No relicenciar código GPL o de otro autor como propio. Los parches mínimos existen para compatibilidad temporal de guía/referencias, no para alterar las condiciones del modelo.

## H3 Studio

Se incluye el código fuente generalizado de la interfaz usada para la receta, sin historial, credenciales, datos personales o modelos base. Se conserva un README/procedencia dentro de `studio/`. Pachecodes : Kinjutsu es el nombre de este paquete, no una afirmación de autoría de modelos externos. Las dependencias de frontend/backend mantienen sus propias licencias y sus lockfiles/metadatos.

## Materiales de entrada

No se incluyen fotos de personas, videos comerciales, certificados particulares, voces ni outputs de otra persona. El destinatario debe aportar materiales con derechos/consentimientos apropiados. Los resultados deben revisarse antes de publicación; la instalación no verifica esos derechos ni constituye una autorización universal.
