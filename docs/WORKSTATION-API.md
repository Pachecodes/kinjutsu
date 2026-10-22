# Local workstation API — Kinjutsu / H3 Studio

Frontend handoff: register under the existing `/api` router. OpenAPI is at
`/api/openapi.json`; `WorkstationStatus`, `WorkstationCapabilities`,
`SelectionRequest`, `ActionRequest` and the folder enum describe UI gating.
No endpoint accepts a client path, URL, executable, argument vector or shell command.

## Safety and first run

- All workstation routes, including discovery/status, require a loopback peer and
  loopback Host (`localhost`, `127.0.0.1`, `::1`). A supplied Origin must equal the
  request origin. Remote/Tailnet creator clients receive 403; do not offer desktop
  buttons there. Opening a folder/browser affects the **server's Windows desktop**.
- GET is read-only. There is no autostart, model download/copy, process stop,
  interruption, queue clearing, model unload or external Comfy config mutation.
- With no approved selection, status is `configuration_required`. Explain
  “Configure an existing ComfyUI locally, then explicitly select it.” Discovery
  is not permission to launch or adopt a service.
- A verified managed installation seeds its own approved profile if no prior config exists, without selecting it or starting services in that step. Existing administrator authorization is never overwritten. Other discovered installations still need explicit local approval before selection.
- The local administrator can create `runtime/workstation.json` under `KINJUTSU_ROOT`
  (otherwise the package root). Protect this file with the same local account/ACLs
  as the launcher. Never expose an HTTP config editor or publish the machine's
  populated config, process receipts or logs. Source examples below are synthetic.
- Runtime changes invalidate the selection digest and require reselection.
  Use one Studio worker/process for workstation mutations; locks serialize threads,
  not independent ASGI worker processes. This API is a local single-user control
  plane, not a multi-user service manager.

## Administrator-only config

All paths must already exist and be absolute, local, non-UNC paths. A runtime
must contain `main.py`, `folder_paths.py`, `comfy/`. `cwd` must equal its root.
Only a Python interpreter is accepted, and argv must execute that exact absolute
`main.py`, optionally preceded by `-s`, `-u` and/or `-X utf8`. Exactly one `--listen 127.0.0.1`
and one matching `--port` (1024–65535) are required. Additional arguments are
trusted administrator data, not HTTP inputs. Use `--disable-auto-launch`.
Configured folders need not be under Comfy if explicitly approved here; this
supports existing shared models and custom output directories.

```json
{
  "version": 1,
  "runtimes": [{
    "key": "existing",
    "label": "My existing H3 ComfyUI",
    "approved": true,
    "root": "C:/Kinjutsu/runtime/ComfyUI",
    "cwd": "C:/Kinjutsu/runtime/ComfyUI",
    "port": 8218,
    "executable": "C:/Kinjutsu/runtime/venv/Scripts/python.exe",
    "argv": ["-s", "C:/Kinjutsu/runtime/ComfyUI/main.py", "--listen", "127.0.0.1", "--port", "8218", "--disable-auto-launch", "--extra-model-paths-config", "C:/Kinjutsu/runtime/extra_model_paths.yaml"],
    "model_roots": ["C:/Kinjutsu/models"],
    "folders": {
      "models": "C:/Kinjutsu/models",
      "loras": "C:/Kinjutsu/models/loras",
      "outputs": "C:/Kinjutsu/runtime/ComfyUI/output"
    }
  }]
}
```

For a portable existing installation, use its interpreter, exact root, actual
arguments and existing roots instead. Do not install a second copy of weights.
`runtime/studio-launch.json` is the separate existing launcher config; this API
neither overwrites it nor silently edits an external `extra_model_paths.yaml`.

## Endpoints

| Method | Path | Payload / result |
|---|---|---|
| GET | `/api/workstation/status` | `WorkstationStatus`; never starts anything |
| GET | `/api/workstation/discover` | `{runtimes, roots, limits, automatic_downloads:false}` |
| GET | `/api/workstation/roots` | `{roots, configuration_required, verification_required:true}` |
| POST | `/api/workstation/select` | `{candidate_id, acknowledge:true}`; approved runtime ID only |
| POST | `/api/workstation/roots/select` | same payload, approved selected-runtime root ID only |
| POST | `/api/workstation/comfy/start` | `{}` or no body; fixed configured command only |
| POST | `/api/workstation/comfy/open` | `{}` or no body; selected healthy loopback URL only |
| POST | `/api/workstation/folders/{kind}/open` | `{}` or no body; kind = `models`, `loras`, `outputs` |

Extra JSON properties are rejected (422). Unknown/unapproved IDs, missing
confirmation, conflicts and unavailable operations return 409 with `detail`.
Invalid folder enums return 422; origin/peer/Host violations return 403.

Candidate IDs are stable opaque `comfy_…` / `root_…` hashes of canonical local
paths. Display `label` and optional `location` **only in the local UI**; never
put paths or IDs in shell commands. Candidate `online` means observed Comfy
health during this discovery, **not ownership approval**. Discovery can omit a
busy/slow candidate; a configured runtime is still checked independently by status.

### Discovery bounds

Only exact installation paths are inspected: package `runtime/ComfyUI`,
`~/ComfyUI`, `~/ComfyUI_windows_portable/ComfyUI`, and that portable path directly
under `~/Downloads` and `~/Desktop`, plus `COMFYUI_PATH` / `COMFYUI_HOME`, explicit
administrator runtime/model roots and `runtime/model-roots.json`. No directory
recursion, user-home recursion, whole-drive search, weight hashing or downloading
occurs during discovery. Up to 32 local listener candidates are inspected; only
absolute `main.py` arguments with Comfy markers and loopback `/system_stats`
health can add an unapproved running candidate. Paths from process data are
never executable launch authorization.

The cooperative discovery budget is two seconds, depth zero, up to 64 standard
paths, 32 configured runtimes, and bounded/truncated result lists. Each HTTP
probe has a 350 ms socket timeout and 256 KiB response cap, disables proxies and
redirects, and requires JSON with `system` object and `devices` array. OS process
enumeration/filesystem calls are synchronous and cannot be forcibly timed out;
this is a cooperative budget, not a hard real-time guarantee.

### State / UI contract

`capabilities.start` drives “Start ComfyUI”; `capabilities.open_comfy` drives
“Open ComfyUI”; `capabilities.folders[kind]` drives each folder button. Refresh
status after an action. Do not call POST from effects, onboarding or polling.

- `configuration_required`: no selection, revoked approval or changed config.
- `stopped`: selected configured port free; start can be requested explicitly.
- `starting`: exact owned process still initializing; poll, never start again.
- `online`: Comfy health **and** exact listener executable/argv/cwd verified.
- `unhealthy`: matching selected listener exists but health is not ready; inspect
  logs, never restart/kill it from this UI.
- `port_conflict`: unknown/foreign process or inaccessible identity on the selected
  port, even if HTTP looks like Comfy; no launch, adoption, restart or termination.
- `configuration_changed`: an older owned startup process is still alive under a
  different selected config; administrator inspection required.
- `launch_unverified`: launch was attempted but no complete process receipt was
  saved (including crash during startup). Fail closed; administrator must inspect
  listener/process/log, then remove the stale `runtime/state/workstation-comfy.json`
  **only after proving no owned startup remains**. Do not offer a retry/reset button.

`start` returns `online,reused:true` for an already healthy exact selected
listener without touching its jobs. A new launch returns `starting,reused:false`
and a package-relative log reference, **not readiness success**. Poll until
`online`. An exact owned startup receipt includes PID, create time, executable,
argv and cwd, plus configuration hash; PID alone is never treated as identity.
Receipts are private files and their commands are never included in API JSON.
Explorer uses an explicit executable/path argv with `shell=False`; start uses
fixed argv, `shell=False`, hidden-console flags and redirected logs. `open` returns
`requested:true`, meaning the OS/browser accepted a request, not proof a GUI window
was visually displayed in a service session.

### Generation routing is intentionally separate

Selection controls workstation actions; it does **not** rewire running Studio
job clients or restart Studio/Comfy. `/select` explicitly returns
`generation_routing_changed:false`. Status `generation_binding` is `matches`,
`different`, `not_selected` or `unknown`, comparing the selected URL with the
actual app settings when available. Never claim generation uses the selected
runtime unless this is `matches` and existing Studio capabilities agree.
An administrator/integration launcher must bind `H3_COMFY_URL` (and the separate
experimental URL if intended) at an idle deployment boundary. Existing jobs and
external services must remain untouched. This API deliberately has no hot
reroute, stop, restart or auto-adopt endpoint.

### Model root reuse

A root must appear in the approved selected runtime's `model_roots`. Selecting it
hashes only manifest target paths / exact flat basenames, enforces containment,
size and SHA256, requires at least one verified pinned artifact, and rejects an
existing bad manifest artifact before changing config. Missing other artifacts
are allowed and remain missing; the response reports `verified_models`. Other
files are not imported. Successful adoption adds a deduplicated root to existing
`runtime/model-roots.json` and regenerates only the **package's** model mapping.
No weight copying, repair, downloads, external Comfy mapping edits or restarts.
Existing model manager sees the shared root dynamically. Large hashes are
synchronous and can take minutes; show a verification-in-progress state and do
not resubmit. Do not run root adoption concurrently with model install/download.
External Comfy must already expose its mappings or be configured separately by
its administrator; `external_comfy_mapping_changed:false` is explicit.

## Verification receipts

`studio/backend/tests/test_workstation.py` is CPU-only. It uses temporary Comfy
marker directories, fake child/browser/Explorer launchers and a real loopback
HTTP fixture; it never starts Comfy, loads a GPU or opens desktop windows. Covers
first run/read-only GET, stable IDs/deduplication, strict config, selection,
foreign ports/identity, startup receipt idempotence, PID reuse, failed-recording
fail-closed behavior, root SHA256 reuse/corruption, bounded nonrecursive discovery,
redirect refusal, local-origin/Host/peer guards, payload rejection, OpenAPI and
real Studio router registration. Parent integration owns deployed browser/GPU QA.
