# Pachecodes : Kinjutsu — Studio

Local FastAPI + React interface for a separately installed MiniMax H3 ComfyUI runtime.
Use the repository root installer and setup instructions for the complete environment.
Studio defaults to **http://127.0.0.1:8220**, ComfyUI to **http://127.0.0.1:8218**.
Nothing here downloads base weights or starts GPU inference automatically.

## Manual development

Requires Python 3.12+, Node.js compatible with Vite 8 (22.12+ or a supported newer release), and FFmpeg/ffprobe on PATH.

```sh
cd studio/backend
python -m venv .venv
# Windows bash:
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
cd ../frontend
npm ci
npm test
npm run typecheck
npm run build
cd ../backend
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8220
```

On Linux use `.venv/bin/python` instead. The backend serves `frontend/dist` at the same origin.
For hot reload, run `npm run dev` in `frontend`; its loopback-only Vite proxy targets Studio 8220.

## Configuration and storage

Copy `.env.example` to `.env` only if overrides are needed; never commit the resulting file.
Settings use the `H3_` prefix. Relative data/frontend directories are resolved against `studio`, independent of the current directory. Runtime uploads, outputs, thumbnails and SQLite state are created under `studio/data`; none are distributed. There is no authentication: retain loopback binding and do not expose the service publicly.

Prompt Chat / AI Director is **disabled by default**. No prompt model is supplied. Opt in only after configuring your own loopback model endpoint. Automatic managed GPU launch and automatic Ollama launch are both off. Optional managed llama.cpp requires explicitly supplied executable, model and multimodal-projector paths; it remains an advanced unbundled feature.

## Character Swap v1.1

The API and UI retain `aligned_guide` video references, `MiniMaxH3AddGuide` conditioning at frame 0, strict resolution/frame-count/fps matching, manual prompt requirements and capability-gated availability. Missing live node schema, missing adapter or offline ComfyUI fails closed. Ordinary video references are not aligned guides. Guide workflows cannot be split into continuity windows.

The built-in Character Swap preset is the conservative 20-step baseline. The repository-level Turbo 8 + Character Swap recipe is separate: Turbo first, Character Swap second, both strength 1.0, Euler/simple, 8 steps. Do not confuse the built-in preset with that recipe.

Experimental methods and advanced adapters are preserved for compatibility, not installed or certified by this copy. The UI reads live capabilities. Historical reference timings are estimates from another environment, not measurements of your GPU or this repository. The sanitized `docs/contracts` file is only an offline/test schema, **not** proof of installed models. `docs/fixtures` and test snapshots contain synthetic example names/prompts, not bundled media.

## Verification scope

Backend tests use an in-memory ComfyUI stand-in; generated solid-color video tests use FFmpeg CPU encoding/probing. Frontend tests cover state, aligned-guide controls and title. Build/typecheck validate the sanitized frontend. These tests do not establish GPU inference quality, speed, model licensing or a working external runtime. See `docs/VALIDATION.md` for this copy's executed results.

## Provenance and licensing

Adapted from an existing MiniMax H3 Studio source tree; production files and services were not changed. Only application source, dependency declarations/lockfile, tests and sanitized schema fixtures were copied. Original deployment history, private documentation, environment values, user media, weights, caches and dependencies were excluded.

No upstream Studio LICENSE was present in the source root inspected during packaging. **Do not infer a redistribution license from this copy.** Confirm Studio source rights and preserve applicable notices before sharing publicly. MiniMax H3, ComfyUI, custom nodes, dependencies and adapters retain their own licenses. Adapter license descriptions in UI metadata are informational, not a legal grant; review the actual license files supplied with each model. This Studio directory includes no model weights.
