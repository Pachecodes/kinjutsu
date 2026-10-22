# Integration contract — deterministic local H3 form renderer

## Files and callable

- `prompting/renderer.py`: self-contained standard-library module; no relative imports, environment configuration, media decoding, HTTP, model/agent calls or mutable global state.
- `prompting/__init__.py`: `from prompting import render_prompt, PromptValidationError` when the package root is on `sys.path`.
- `prompting/catalog.json`: six template IDs, triggers, section style, asset roles and preset compatibility **metadata**, never a patch to a render recipe.
- `prompting/request.schema.json`: Draft 2020-12 structural schema for the **input** object. Template-role/timing/token semantics are additionally enforced by Python. No JSON Schema library is required.
- `scripts/build_prompt.py`: local CLI; `--template ID --input FILE [--output FILE]`, `--list`, `--help`. Exit 0 on success, 2 on validation/JSON/I/O failure.
- `prompting/examples/*.json`: six synthetic human-media-free fixtures, one per template.
- `prompting/tests/test_renderer.py`: stdlib unittest suite, including real CLI subprocesses.
- `skills/h3-prompt-writing/SKILL.md`, `references/base-en.txt`, `references/ref-en.txt`: complete generalized source instructions and guides. Optional agent UI metadata is not required/exported.

```python
from prompting.renderer import render_prompt, PromptValidationError
prompt = render_prompt("motion-ref2va", form_data)  # string, UTF-8 when written
```

Same template + identical form = identical output, including section order, speaker IDs, timestamps and final newline. The renderer does not mutate the request. It returns no title or settings patch. Never pass renderer output into an agent by default. Never silently fall back to an LLM on input errors.

## Input shape

```json
{
  "duration_seconds": 6.25,
  "identity": "A single adult fictional performer with short dark hair",
  "style": "Live-action, matching the reference colors",
  "assets": [
    {"kind":"image", "role":"identity", "token":"<Picture 1>", "description":"The supplied fictional identity portrait"},
    {"kind":"video", "role":"motion", "token":"<Video 1>", "description":"A continuous hand gesture with a static camera"}
  ],
  "shots": [
    {"start_seconds":0, "scene":"A plain rehearsal room", "performance":"The performer raises one hand and lowers it", "camera":"The camera holds a static medium shot", "lighting":"Soft window light from frame left", "sound":"Quiet room tone and fabric movement"}
  ],
  "audio": {"soundscape":"Quiet room tone continues throughout.", "music":"N/A", "silent":false},
  "dialogue": []
}
```

Dialogue entry: `{"shot":1,"start_seconds":1,"end_seconds":2,"speaker":"The adult performer with a low measured voice","language":"Spanish","text":"¡Mira, aquí estoy!","delivery":"quietly","subject":1}`. `subject:1` is optional, Motion-only, and binds the vocal event to the referenced identity subject. Omit it for independent voices. `voiceover:true` is optional and prints the guide's required off-screen phrase and lips-closed instruction. Speaker IDs follow chronological actual vocal events, not asset order. There is one identity performer in this renderer; secondary image roles describe scene/costume/style, not additional speaking characters.

Unknown fields at all object levels are rejected. No file paths/media bytes are accepted as structured assets: assets describe the mapping to attachments already selected by the UI. This is not a security scanner for arbitrary prose; callers should never put secrets in prose. Visual/audio paragraphs must be supplied in English; no language inference or translation happens. Dialogue words/punctuation are preserved exactly. This preserves the stricter verbatim Base rule rather than applying punctuation cleanup to full-reference spoken text.

Durations: renderer accepts finite positive seconds up to 3600 with at most three decimal places (including native 10.125-second targets); shot/dialogue times accept at most millisecond precision. **This is a prompt-format bound, not a supported H3 rendering duration.** The backend must still enforce actual frame/FPS/model/mode limits and derive effective duration from its authoritative render settings. Reject duration disagreement instead of silently changing form data or the recipe. No frames conversion is duplicated here.

Assets: images are numbered consecutively by image attachment order, independently from videos. Motion needs exactly one identity image and one ordinary video with role `motion`, token `<Video 1>`; optional additional images have roles `scene`, `costume`, `style`. All secondary images apply across all shots. Standalone audio refs, copied source soundtrack, multiple Motion videos and multi-character image identities are intentionally unsupported in v1; they fail explicitly instead of inventing `<Audio N>` or labels. An audio track in a video does not automatically become a reference.

Aligned is exactly `[image identity Picture 1, tokenless aligned_guide]`. Never serialize that guide into the ordinary video-reference list or attach a `<Video 1>` token. Keep the existing backend's aligned guide path and geometry/frame/FPS checks. Prompt duration changes do not realign media. Its approved ownership/prefix is retained; no claim of a new GPU validation is made. Aligned supports one continuous user-described shot, natural generated ambience or explicit silence, and no dialogue/music. The guide owns clothing, environment, performance **and local lighting**; the portrait owns identity/hair/intrinsic complexion, including hands. User guide-description fields must describe the existing guide, not a replacement scene.

FL2VA/L2VA use the actual final shot number and duration in the initial alignment instruction. The first shot has no timestamp; later cuts use `MM:SS.mmm` and strictly increasing in-range times. Spoken lines must fit entirely inside a shot, cannot overlap, and preserve their supplied language. Cross-cut speech/automatic `<scenetrans>` and `<cutoff>` are not supported by the form; ask the creator to segment or edit consciously. Renderer validation cannot judge whether a line can be spoken naturally in the allotted time, validate English prose, infer media contents, or detect contradictory visual instructions. Full Ref2VA guidance recommends 350–500 English words in the detailed body; provide that detail in the form when needed, rather than padding with fabricated observations.

## Installed backend route (Kinjutsu package; not the live source app)

The package now registers `GET /api/prompting/catalog` and `POST /api/prompting/build` through `studio/backend/app/services/offline_prompts.py`. These are local text-only endpoints, separate from Director/agent and generation routes. Request envelope is `{"template":"motion-ref2va","input":{...form...}}`. Response is `{"template":"motion-ref2va","prompt":"...","requires_agent":false,"submits_render":false}`. Invalid form data returns 422 with a readable error; do not replace the editor prompt on errors. Input prose is bounded to 64 KiB. Duration supports millisecond precision. The frontend form remains for the UI integrator; do not assume the independent live Studio source already has these package-only routes.

The following is an alternative reference implementation only; do not register it again in the package:

Example placement if editing `studio/backend/app/main.py` (package tree must preserve the root `prompting/` folder):

```python
from pathlib import Path
import sys
from fastapi import HTTPException

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
from prompting.renderer import PromptValidationError, render_prompt

@app.post("/api/prompting/build")
def build_prompt_from_form(payload: dict):
    if set(payload) != {"template", "input"}:
        raise HTTPException(422, "Expected exactly template and input")
    try:
        prompt = render_prompt(payload["template"], payload["input"])
    except PromptValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"template": payload["template"], "prompt": prompt,
            "requires_agent": False, "submits_render": False}
```

Alternatively copy **only** `renderer.py` to `app/services/h3_form_prompt.py` and use `from .services.h3_form_prompt import ...`; the file is deliberately standalone. Keep catalog/schema alongside packaged UI resources if using this strategy. If your packaging does not include the root folder and you do not copy the standalone file, `from prompting` will fail: make inclusion explicit. Do not edit the renderer to import Studio, FastAPI, Pydantic, a model library or a local profile skill.

A read-only catalog endpoint can load the JSON once from `PACKAGE_ROOT / "prompting/catalog.json"`. Keep this endpoint independent from Director provider configuration. Enforce existing local-only/auth/origin/body-size policies used by Studio; this route does not need an agent provider or model to be online.

UI suggested mapping: selector from catalog; duration readonly/synced to effective project duration; assets populated from authoritative current attachment roles/order; explicit identity/style/scene/performance/camera/lighting/sound/audio fields; optional timeline/dialogue rows. Validate that `assets` matches the **current** attachments before and after rendering. Do not invent reference labels based on filenames. Provide a Preview/Copy or explicit Apply Prompt button; preserve all recipes/weights/LoRAs/settings and never trigger a render. Any UI title clearing is the preset/UI's existing responsibility, not this generator's.

## Verify locally

From the package root, with any suitable local Python 3.10+ (tested with Python 3.12):

```console
python -m unittest discover -s prompting/tests -v
python scripts/build_prompt.py --list
python scripts/build_prompt.py --template motion-ref2va --input prompting/examples/motion-ref2va.json --output prompting/motion-preview.txt
```

The CLI test executes all six templates, compares their generated files to the callable result, exercises `--list`/`--help`, and checks failure exit 2. No services, GPU, models or human media are used. The standalone import test verifies the module does not depend on this package's location. Do not describe this test as a model-quality validation.
