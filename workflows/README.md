# Pachecodes : Kinjutsu — ComfyUI workflows

- **`character-swap-turbo8-ui.json`** — complete importable ComfyUI canvas, with 20 nodes and 26 links. Drag it onto ComfyUI or use Workflow → Open. The canvas group is titled **Pachecodes : Kinjutsu**.
- **`character-swap-turbo8-api.json`** — executable API graph and **ground truth** for node classes, values and wiring. This is not the editor/canvas format. Keep it authoritative if editing or migrating the GUI workflow.

## Before running

1. Install the pinned runtime, required nodes and models using the package's setup instructions. This workflow is built against ComfyUI **0.33.4**, revision **`7a131a3afadc8200120f67f9236311a2c48b7445`**, and frontend **1.49.6**. Older frontends without V3 autogrow/dynamic-combo support are not supported. In particular, the `MiniMaxH3AddGuide` extension must be present.
2. Open the **UI JSON**. Upload your own consented adult identity image using **Upload reference-person.png** (`LoadImage`). Then select the server filename returned by upload. The placeholder `reference-person.png` is not an included asset.
3. Upload your own pre-aligned guide video using **Upload guide-aligned.mp4** (`LoadVideo`), then select its uploaded filename. The placeholder `guide-aligned.mp4` is not an included asset. Prepare/crop/resize/time-align the guide before this workflow; it does not contain preprocessing or tracking nodes. Match the intended framing and 24 fps timeline. Default generation is 736 × 1280, 124 frames, 24 fps.
4. Check all model and LoRA selectors. Keep the Turbo LoRA followed by the character-swap LoRA, both model-only at strength 1.0. Keep Euler / simple / 8 steps / denoise 1.0 for this preset. The seed starts fixed at `20261021`.
5. Review the prompt and reference. Only run after replacing both upload placeholders. A missing-file/invalid-selection indicator on these two loader nodes is expected before upload; it is not a missing graph dependency.

No personal images/videos are shipped or embedded. Model filenames are exact selectors, not bundled base-model weights.

## Wiring that must be preserved

- `UNETLoader → Turbo 8-step LoraLoaderModelOnly → character-swap LoraLoaderModelOnly → BasicGuider.model`.
- `BasicScheduler.model` intentionally uses the original `UNETLoader` output, matching the API graph. No `ModelPreviewOverrideKJ` node is required or present.
- `LoadImage.IMAGE → MiniMaxH3ReferenceToVideo.ref_images.ref_image_0`. This is the **native V3 autogrow input**, not a widget or a flat `ref_image` port. The empty `ref_images.ref_image_1` socket is created by the real frontend; leave it unconnected for this single-reference preset. Other empty reference sockets are normal.
- `LoadVideo → GetVideoComponents.images → MiniMaxH3AddGuide.image`, with reference conditioning and latent also entering AddGuide and the video VAE connected. AddGuide's conditioning output goes to BasicGuider. The sampler's latent input remains connected to ReferenceToVideo's latent output, exactly as in the API graph.
- The guide's audio output is deliberately **not** connected to AddGuide. This preset anchors guide images and generates audio; it does not preserve or copy the source soundtrack.
- `SamplerCustomAdvanced` feeds both native `VAEDecode` and `VAEDecodeAudio`. Native `CreateVideo` joins images and generated audio at 24 fps, 8-bit; native `SaveVideo` uses MP4 / automatic codec and prefix `Kinjutsu/character-swap`. No VHS video-combine dependency is needed.

The two selected LoRAs are:

- `latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors`
- `minimax_h3_character_swap_v1.1_ref2va_fro.safetensors`

AddGuide follows the model's valid guide clip lengths (5, 22, 39, …; 17k + 5); its node implementation may crop the guide batch accordingly. Default 124 frames is a valid length. Generation length is not inferred automatically from the uploaded video.

## Verification

From the package root, offline (Python standard library only):

```bash
python -m unittest discover -s tests -p test_workflow_ui.py -v
```

Optional read-only schema verification against an already-running matching ComfyUI, in Git Bash:

```bash
KINJUTSU_COMFY_URL=http://127.0.0.1:8218 python -m unittest discover -s tests -p test_workflow_ui.py -v
```

PowerShell equivalent:

```powershell
$env:KINJUTSU_COMFY_URL = 'http://127.0.0.1:8218'
python -m unittest discover -s tests -p test_workflow_ui.py -v
```

The tests reconstruct the API graph from GUI socket indices, links and widget values and compare every node/input to the ground-truth API graph. They check reciprocal links, absence of dangling links, native autogrow/upload controls, fixed seed, and absence of embedded assets/absolute host paths. The optional test reads `/object_info` and verifies output indices/types and declared input types, including dynamic reference templates. It never submits `/prompt`.

**Additional build verification performed:** the running pinned frontend itself imported the API graph using `app.loadApiJson`, serialized a real LiteGraph canvas, re-imported the final UI JSON using `app.loadGraphData`, and exported it using `app.graphToPrompt`. After removing UI-only `_meta` titles, the resulting API graph matched the packaged API graph exactly (20 nodes, 26 links). Non-read-only fetch requests and queueing were disabled in the isolated test browser. All three automated tests passed against the live read-only schema.

This verifies importability and serialization, **not an inference run or identity/temporal quality**. No generation, queue submission, GPU service restart, or asset upload was performed during this verification. Validate the result visually with your own inputs before relying on output quality. On a different ComfyUI/frontend/node revision, re-check import/export parity rather than assuming socket/widget layouts remain compatible.
