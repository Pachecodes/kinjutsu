# Un clic, sin agentes — actualización de contrato

La entrada recomendada es `INICIAR.vbs` → `scripts/Launch-Kinjutsu.ps1`; parada `DETENER.vbs`. Pide aceptación de licencias/descargas en primera instalación, revisa Internet/disco/controlador, instala solo si falta runtime o cambia root/lock. Arranques posteriores verifican hashes de modelos/herramientas, versiones del lock, core y frontend; no descargan ni reinstalan automáticamente ante corrupción. Muestre el log e inspeccione el archivo dañado. La interfaz compilada sanitizada ya viene incluida; **Node/npm no se instalan ni ejecutan en el equipo receptor** (solo son herramientas de desarrollo para reconstruir la UI).

`runtime/tools-manifest.json` fija URL, tamaño y SHA256; bootstrap reanuda con Range, valida bytes/hash antes de extraer y escribe recibos con hashes de cada archivo extraído. Python 3.12.10 se obtiene mediante el catálogo/checksums de la versión uv fijada, no con un script remoto sin hash. `runtime/download-receipts/` contiene solo descargas reales verificadas de pesos. No se reescriben finales incorrectos.

Modelos compartidos: `runtime/model-roots.json` con raíces absolutas seleccionadas explícitamente por el operador; exact filename+size+SHA256, sin escaneo recursivo ni copiar modelos. No se importa automáticamente el YAML externo. `docs/MODEL-MANAGER-API.md` describe catálogo/estado/instalar/cancelar y la integración visual pendiente. La instalación inicial todavía descarga la base tras aceptación; no hay modo de instalación liviana sin modelos.

Core y postimágenes ahora corresponden al snapshot de producción inspeccionado: commit sigue `7a131a3afadc8200120f67f9236311a2c48b7445`; los comentarios/formato de parches y AddGuide se fijan con los hashes reales actuales. NumPy se fijó en 2.4.6, como el runtime inspeccionado. Se preserva torch 2.13.0+cu130, torchvision 0.28.0+cu130 y torchaudio 2.11.0+cu130: divergencia de metadata de torchaudio explícita; `--no-deps` con lock auditado no es garantía ABI ni resolución transitiva estricta. No se inventa un wheel torchaudio 2.13. La dependencia completa se verificó con dry-run de hashes; instalación GPU limpia pendiente.

Servicios usan CREATE_NO_WINDOW, identidad PID+create_time+exe+cmdline y recibo ligado a root/comando/cwd/configuración. Reutiliza únicamente servicios propios saludables con configuración idéntica; para configuración cambiada o servicio propio degradado se requiere DETENER/INICIAR. No hay kill por puerto/nombre ni adopción extranjera. No ejecute dos instalaciones simultáneas en la misma raíz. Logs en runtime/logs/. No hay elevación, autoinicio ni listener público.

La receta predeterminada del composer vacío es HD Turbo8 si está disponible. Control Quality20 sigue separado. Baseline/preview y libertad avanzada se conservan; disponibilidad de modelos/encoder/LoRA/modos/nodos se comprueba en vivo. Métodos opcionales ausentes no forman parte de la reproducción mínima.

---

## Referencia previa (comandos manuales y detalles)

# Pachecodes : Kinjutsu — installation technical reference

## Supported scope

Windows 11 x64, RTX 4090 with 24 GB VRAM, current NVIDIA CUDA 13-compatible display driver. 64 GB system RAM and at least 120 GB free disk space are recommended, with more for inputs, outputs and pagefile. The installer requires base-model bytes still missing plus a 30 GB runtime/cache allowance. Internet access is needed on first install. No administrator privileges, Docker, CUDA toolkit, registry/PATH changes, scheduled tasks, services, or login autostart are configured. The display driver must already be installed; it is not bundled or changed.

This is a **portable source distribution**, not a relocated copy of a private machine's Python runtime. Choose the final directory before installing. Runtime tools, managed Python, venv, caches and logs stay under that directory. Python virtual environments are not generally relocatable after installation: if moving an installed package, retain the model tree and rebuild the environment at the new location after manually inspecting/moving the old `runtime/venv` out of the way. No installer performs a destructive environment reset.

**Local use only.** ComfyUI binds `127.0.0.1:8218`; Studio binds `127.0.0.1:8220`. Do not expose these through LAN bindings, port-forwarding, public tunnels, reverse proxies, or public hosted APIs/SaaS. In particular, the model license does not permit repackaging the weights as a public hosted API/SaaS; see the repository's third-party notices and actual upstream terms.

## Commands

From the extracted package in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Kinjutsu.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Kinjutsu.ps1 -PackageOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Kinjutsu.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-Kinjutsu.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Stop-Kinjutsu.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Kinjutsu.ps1
```

Every PowerShell entry accepts `-InstallRoot 'X:\Chosen\Kinjutsu'`. This means **the directory of an already-extracted complete package**, not a new empty copy destination; default is the parent of `scripts/`. Paths with spaces are supported. `Install -DryRun` is offline and has no bootstrap/write side effects. `Verify -PackageOnly` is offline, validates manifest syntax, bundled LoRA sizes/digests, patch sizes/digests, and expected package components. Before runtime installation it needs a Python 3.12+ interpreter on PATH. It does not require the four remote base files, torch, CUDA, or running services.

`Verify-Dependencies.ps1` performs a hash-locked `uv pip install --dry-run --no-deps`, without installing packages; `-Offline` also prohibits network access but needs previously cached metadata. Optional `Start-Kinjutsu.vbs`/`Stop-Kinjutsu.vbs` launch their PowerShell counterparts hidden; use PowerShell directly to diagnose launcher errors. Services themselves always use Windows `CREATE_NO_WINDOW` and do not require those wrappers. Installation does **not** start either service.

The stdlib Python CLI is `scripts/kinjutsu.py`: commands `plan`, `install --dry-run`, `verify-package`, `patch-check`, `install`, `verify`, `start`, `stop`; `--root` selects the complete extracted root. `patch-check --core <checkout>` performs read-only forward/reverse applicability checks against the pinned revision.

## Reproducibility and dependencies

- Managed CPython **3.12.10**, isolated `runtime/venv`, no system/user site packages.
- Portable uv **0.11.22**, MinGit **2.56.0.2**, Node **22.22.0**. Bootstrap ZIP URLs and SHA256 are hard-coded in `scripts/Common-Kinjutsu.ps1`; archives are verified before extraction. No global installations are made.
- `dependencies/requirements.in`: direct audited candidates.
- `dependencies/requirements.lock`: complete transitive versions and artifact hashes, resolved for Windows/Python 3.12.10. This is the install authority. `constraints.txt` is a convenient version-only reference, not a substitute for the hash lock.
- Dependencies install with `--no-deps --require-hashes --only-binary :all:` from the full lock, preventing a resolver from silently replacing the production override. cu130 packages use the explicit official PyTorch index alongside PyPI.
- `npm ci` uses the sanitized Studio frontend `package-lock.json`, then `npm run build`. No `npm install` or implicit frontend upgrade is used.
- FFmpeg and ffprobe are verified together as a sibling executable pair. If PATH does not supply a valid pair, a portable FFmpeg 8.0 archive is downloaded, SHA256-verified and extracted locally. The complete 105,748,282-byte archive was exercised with SHA256 `647e467caf82b9fa200a562769b5ff4d736aaf725804ed2c64ea9752106fa569`. `imageio-ffmpeg` alone is not a complete toolchain because it has no ffprobe. Paths are recorded in `runtime/tool-paths.json`, added only to the child environment, and `H3_FFPROBE_PATH` is set explicitly.

### Explicit audited divergences

Actual production imports report **torch 2.13.0+cu130**, **torchvision 0.28.0+cu130**, **torchaudio 2.11.0+cu130**, **comfy-kitchen 0.2.33**, **transformers 5.14.1**, **numpy 2.5.1**. The pinned Comfy requirements text says comfy-kitchen 0.2.31, which does not describe what production actually imports. We preserve 0.2.33 through the lock.

There is **no published torchaudio 2.13.0+cu130** on the audited index. An attempted matching-trio resolution failed. Production's torchaudio 2.11 metadata requests torch 2.11; the actual production environment deliberately differs. `dependencies/overrides.txt` records torch 2.13 and kitchen 0.2.33. Production CPU import of torch/torchvision/torchaudio and `torchaudio.functional.resample(zeros(1,240),24000,16000)` succeeded, returning `[1,160]`. The installer preserves this tested production combination rather than quietly downgrading torch or inventing an unavailable wheel. Ordinary `pip check` is expected to flag the known torch/torchaudio metadata discrepancy; this must not be mistaken for a clean ABI guarantee. The installed-runtime verifier repeats imports/resampling and CUDA availability; a fresh-machine GPU render has **not** been certified by these installer tests.

## Pinned core and AddGuide backport

Core: `https://github.com/Comfy-Org/ComfyUI`, revision **7a131a3afadc8200120f67f9236311a2c48b7445**. Installer fetches that SHA only, never updates an existing checkout to latest, never resets a checkout, and refuses a different revision or unexpected changes to either patched file.

`runtime/patches/h3-aligned-guide.patch` contains only the two exact audited changes:

1. `comfy/model_base.py`: append identity-reference latents to existing `cond_video_latents` instead of replacing the aligned guide latents.
2. `comfy/ldm/minimax/model.py`: pack multi-frame guide clips with `_video_grid`, correctly count their rows, and retain incumbent single first/last-frame timing.

`runtime/patches/ComfyUI-H3-AddGuide/__init__.py` is the isolated AddGuide class/registration backport from upstream **355cd6b14c92c19ac3188fe528e47a3f21ef5178**, retaining the audited adapter imports. Its GPL license is included. `runtime/patches/provenance.json` records upstream revision/source hash, bundled payload hashes and the two core pre/postimage hashes using neutral source labels. Production was inspected read-only. No manager, broad custom-node tree, KJNodes preview node, TensorRT node, VSA, or cache accelerator is installed.

## Model layout and download safety

`models/manifest.json` has `models[]` entries with `repo`, `path`, `revision`, `size`, `sha256`, `url`, `target`, `included`. `revision` must be an immutable 40-character lowercase commit SHA; `sha256` a 64-character lowercase digest. `target` is relative to **Comfy's model directory**, e.g. `vae/file.safetensors`, not prefixed with `models/`. The package keeps each file at `<root>/models/<target>`; generated `runtime/extra_model_paths.yaml` exposes that single central tree to Comfy, avoiding a second copy of the weights. The downloader constructs its own pinned Hugging Face resolve URL from repo/revision/path rather than trusting a convenience URL.

Two included LoRAs are hash-verified, not re-downloaded. The Turbo local alias is exactly `latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors`. Four base files total **42,470,585,471 bytes**; included LoRAs total **2,036,866,112 bytes**. Downloads write beside the destination as `.part`, resume with HTTP Range, restart the partial safely when a server ignores Range, validate Content-Range, and promote only after exact size/SHA256 verification. Interrupted downloads are preserved for a later installer rerun. Existing wrong-hash final files are **never** overwritten. A complete bad-hash or oversized `.part` stops with an inspection/removal instruction instead of silently trusting it. Traversal, absolute paths, duplicate model targets and unsupported model categories are rejected.

## Studio integration contract

The installer deliberately does not run an unpinned backend requirements file. Backend requirements are satisfied by the common 93-package hashed lock, including `uvicorn[standard]==0.30.6`. ASGI entry is `app.main:app`, working directory `studio/backend`, frontend build output `studio/frontend/dist`, readiness `/api/health` and schema `/api/openapi.json`. Readiness rejects HTML/SPA fallbacks and degraded health. `runtime/studio-launch.json` matches the sanitized Studio and was exercised with a real ephemeral CPU-only server. Host/ports remain local-only. Child environment supplies `H3_COMFY_URL`, `H3_EXPERIMENTAL_COMFY_URL`, `H3_DATA_DIR` under `runtime/studio-data`, `H3_FRONTEND_DIST`, `H3_FFPROBE_PATH`, `PYTHONUTF8`, a root-local HF cache and explicit disabled director/autostart settings. The backend must not read private machine configuration.

Workflow requirements: BasicGuider, euler/simple, eight steps; identity Picture1 conditioning plus aligned guide at frame_idx=0; native 736x1280, 124 frames, 24fps; delivery resize 720x1280; match reference timing. Preview must be optional and absent-node safe. TRT/VSA/cache nodes must not be mandatory in the approved API workflow.

## Lifecycle safety and logs

Readiness is checked by HTTP and by TCP listener process ownership/local binding. PID receipts under `runtime/state/` record PID, creation time, executable and complete command line, including child interpreter identities (important for Windows venv launchers). Stop checks each identity again before termination, including recorded children if the parent launcher has exited; PID reuse and unrelated processes on the same port are never adopted or killed. Services write append-only UTF-8 logs under `runtime/logs/comfy.log` and `studio.log`. Failed startup rolls back the processes it just created. Never kill all Python processes to repair this installation.

## Executed validation and limits

CPU-only tests exercise manifest validation, hashes, resumable downloads, exact PID ownership, safe exit-race handling, local-only launch configuration, readiness JSON rejection and patch integrity. A clean two-file snapshot passed forward patch application, exact postimage SHA256 and reverse applicability. PowerShell parser and offline dry-run passed. The full locked dependency dry-run resolved 93 packages. A fresh isolated Python3.12.10 CPU environment installed the 23-package backend closure. The real sanitized Studio was started only on an ephemeral loopback port with scratch data and Comfy offline: health reported degraded correctly, OpenAPI returned200, SPA HTML was rejected as readiness, and an uploaded synthetic64x64/0.5s video was probed successfully through the real ffprobe path. Final root suite:26 tests passed, including live read-only Comfy schema compatibility; no GPU job was submitted.

**Not executed:** full clean-Windows install, full GPU dependency installation in the portable venv, large base-model downloads, Comfy/Studio production service startup, or GPU generation. CPU HTTP test listeners used ephemeral ports only. Do not describe these checks as a successful clean-machine GPU render or installation.
