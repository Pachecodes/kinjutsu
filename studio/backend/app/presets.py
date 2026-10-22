"""Creator presets.

A preset is a *visible state loader*: it patches the composer with a known-good
recipe and then gets out of the way. Nothing here locks a mode, hides Advanced,
or prevents the creator from changing any single value afterwards.
"""

from __future__ import annotations

from typing import Any

from .schemas import MethodId, Mode
from .workflow import constants as C
from .workflow.estimate import estimate_seconds
from .workflow.frames import length_to_seconds


def _preset(
    *,
    preset_id: str,
    label: str,
    blurb: str,
    suggests_mode: Mode | None,
    patch: dict[str, Any],
    recipe: list[str],
    caveats: list[str],
    needs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": preset_id,
        "group": ("control" if preset_id == "character-swap-v11" else "recommended" if preset_id in {"character-swap-hd-turbo8", "quality", "preview", "baseline-quality", "fast-preview", "w4a8-lightx2v", "fast-preview-5s", "balanced-10s", "lightx2v8-creator-5s", "identity-locked", "lip-sync", "performance-transfer", "premium-vertical-5s", "final-15s"} else "experimental"),
        "default": preset_id == "character-swap-hd-turbo8",
        "label": label,
        "blurb": blurb,
        "suggests_mode": suggests_mode.value if suggests_mode else None,
        "patch": patch,
        "recipe": recipe,
        "caveats": caveats,
        "needs": needs or [],
        "recommended_duration_seconds": round(length_to_seconds(patch["length"]), 3),
        "estimate_seconds": (
            estimate_seconds(
                method=patch.get("method", MethodId.baseline.value),
                width=patch["width"],
                height=patch["height"],
                length=patch["length"],
                steps=patch["steps"],
            )
            if not preset_id.startswith("10eros-") and C.METHOD_PROFILES.get(patch.get("method", MethodId.baseline.value), {}).get("measured_seconds")
            is not None
            else None
        ),
    }


def _seconds(frames: int) -> str:
    return f"{length_to_seconds(frames):.2f}s"


CHARACTER_SWAP_HD_PROMPT = (
    "body_swap: Replace the single adult person in the aligned guide with the character in <Picture 1>. "
    "Picture 1 owns the entire person's identity: facial proportions, hair, and consistent intrinsic skin complexion "
    "across face, neck, both arms, both hands and every finger, allowing natural local lighting and shadows. "
    "The aligned guide owns only performance, expressions, mouth movements, pose, clothing, accessories, "
    "props, environment, framing, camera motion and timing, not the original person's identity or complexion. "
    "Preserve the guide clothing and scene. Follow the original hand trajectories and gestures precisely "
    "without inventing actions. Keep the same coherent reference face throughout. "
    "Exactly one coherent adult character, anatomically plausible separated fingers "
    "and stable scene geometry throughout. No added people, cuts, text, captions, watermark or collage. "
    "Soundscape: quiet natural ambience appropriate to the guide scene, no narration, singing or music."
)

PRESETS: list[dict[str, Any]] = [
    _preset(
        preset_id="character-swap-playground",
        label="Character Swap · Experimentar",
        blurb="Template libre: carga LoRAs + prompt. Video como referencia normal, sin exigir guía prealineada.",
        suggests_mode=Mode.ref2va,
        patch={"width":576,"height":1024,"length":124,"steps":8,
               "method":"baseline","weights":"int8","encoder":"standard",
               "sampler_name":"euler","scheduler":"simple","custom_sigmas":None,
               "ref_image_size":"match","title":"",
               "prompt":"body_swap: Replace the single adult person in <Video 1> with the character in <Picture 1>. Picture 1 owns facial identity, hair and consistent skin complexion across face, neck, arms and both hands. Video 1 provides the performance, expressions, pose, clothing, props, scene and camera motion. Preserve the original scene and clothing. Keep one coherent adult character, plausible hands and stable scene geometry. No added people, captions, watermark or collage. Soundscape: natural ambience, no narration, singing or music.",
               "lora_chain":[
                   {"name":"latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors","strength":1.0},
                   {"name":"minimax_h3_character_swap_v1.1_ref2va_fro.safetensors","strength":1.0}],
               "continuity":{"auto_split":False,"window":"auto","pin_frames":"22"}},
        recipe=["Imagen Identity = <Picture 1>; video Motion = <Video 1>",
                "Ref2VA Turbo8 1.0 → BFS Character Swap v1.1 1.0; Euler/simple8",
                "Tamaño, duración, pasos, LoRAs y prompt quedan editables",
                "No convierte, alinea ni recorta el video; se usa como referencia normal"],
        caveats=["EXPERIMENTAL: no equivale a la receta ganadora Aligned guide; parecido, movimiento y encuadre pueden variar.",
                 "Sin prueba GPU de esta variante. Las validaciones normales de H3 siguen activas (referencias, duración, modelos y límites).",
                 "Carga una imagen y un clip de 2–15s. El audio del video queda desactivado; no se copia la voz original.",
                 "El botón reemplaza el prompt y limpia el título; no genera automáticamente. Derechos/consentimiento y licencias aplicables."],
        needs=["1 imagen Identity", "1 video Motion como referencia normal"],
    ),
    _preset(
        preset_id="character-swap-hd-turbo8",
        label="Character Swap · HD Turbo8 ✓",
        blurb="Receta ganadora: otra identidad + video guía. Carga parámetros y prompt editable; no genera automáticamente.",
        suggests_mode=Mode.ref2va,
        patch={"width":736,"height":1280,"length":124,"steps":8,
               "method":"baseline","weights":"int8","encoder":"standard",
               "sampler_name":"euler","scheduler":"simple","custom_sigmas":None,
               "ref_image_size":"match","prompt":CHARACTER_SWAP_HD_PROMPT,"title":"",
               "lora_chain":[
                   {"name":"latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors","strength":1.0},
                   {"name":"minimax_h3_character_swap_v1.1_ref2va_fro.safetensors","strength":1.0}],
               "continuity":{"auto_split":False,"window":"auto","pin_frames":"22"}},
        recipe=["Picture 1 = primera imagen de identidad; el guía NO usa token <Video N>",
                "Ref2VA INT8 · encoder Standard · Ref2VA Turbo8 1.0 → BFS Character Swap v1.1 1.0",
                "Euler / simple · 8 pasos · match · 124 frames / 24 FPS",
                "Imagen → Identity; video → Aligned guide, audio desactivado",
                "Guía exacta 736×1280 / 124 frames / 24 FPS; crop final manual 8 px por lado → 720×1280"],
        caveats=["Aprobada por the operator en los previews de the reference character; otras identidades/escenas requieren revisar cara, manos y piel.",
                 "Este botón reemplaza el prompt actual con una plantilla genérica, sin the reference character ni detalles del sofá; edítala para tu escena.",
                 "Sube una sola identidad y un solo video guía ya alineado. No se recorta ni convierte el video automáticamente.",
                 "El audio es generado: no copia la voz ni la pista original. Sin additional adapters, VSA, cache ni upscale.",
                 "Uso privado con derechos/consentimiento y licencias aplicables; BFS prohíbe servicio de modelo alojado."],
        needs=["1 imagen Identity", "1 video Aligned guide · 736×1280 · 124 frames · 24 FPS"],
    ),
    _preset(
        preset_id="character-swap-v11",
        label="Character Swap · Quality20 control",
        blurb="Control conservador de 20 pasos a 576×1024. Para la receta ganadora, usa HD Turbo8.",
        suggests_mode=Mode.ref2va,
        patch={"width":576,"height":1024,"length":124,"steps":20,
               "method":"baseline","weights":"int8","encoder":"standard",
               "sampler_name":"res_multistep","scheduler":"beta","custom_sigmas":None,
               "ref_image_size":"match",
               "lora_chain":[{"name":"minimax_h3_character_swap_v1.1_ref2va_fro.safetensors","strength":1.0}],
               "continuity":{"auto_split":False,"window":"auto","pin_frames":"22"}},
        recipe=["Character image = Picture 1 (Identity)", "Guide video role = Aligned guide; MiniMaxH3AddGuide frame_idx=0", "Exact output size/frame count, 24 FPS; no soundtrack copy", "body_swap: prompt prefix; baseline 20 steps"],
        caveats=["Author docs still describe v1.0; strength 1.0 is inherited, not a proven v1.1 quality setting.", "Experimental identity transfer; rights/consent required. BFS license forbids hosted model-service use.", "Ref2VA VSA remains optional and unproven with this adapter; validate baseline first."],
        needs=["Identity image", "Aligned 124-frame 576x1024 guide at 24 FPS"],
    ),
    *[
        _preset(
            preset_id=preset_id,
            label=label,
            blurb=note,
            suggests_mode=None,
            patch={
                "width": 608, "height": 352, "length": 124,
                "steps": 7 if sigmas else 6,
                "method": "baseline", "weights": "erosmax_beta5",
                "sampler_name": sampler, "scheduler": "simple",
                "custom_sigmas": sigmas, "lora_chain": [],
                "continuity": {"auto_split": False, "window": "auto", "pin_frames": "22"},
            },
            recipe=["10Eros-Max Beta 5 · native mixed W4A8/INT8 · baked Turbo", f"{sampler} · {'custom sigmas · 7' if sigmas else 'simple · 6'} steps"],
            caveats=["Community checkpoint under H3/source-model licenses. Presets remain editable; prompt, seed, LoRAs and resolution affect results.", "No cache for reference accuracy. Tiny smoke validation is not a visual-quality benchmark."],
            needs=["weights.erosmax_beta5"],
        )
        for preset_id, label, note, sampler, sigmas in [
            ("10eros-motion6", "10Eros-Max · Motion 6", "Author motion recipe: res_multistep/simple, six steps.", "res_multistep", None),
            ("10eros-sde6", "10Eros-Max · SDE 6", "Requested er_sde/simple six-step recipe.", "er_sde", None),
            ("10eros-custom7", "10Eros-Max · Preferred 7", "Requested preferred er_sde manual sigma schedule (not in pinned card).", "er_sde", [1.0, .94, .83, .72, .55, .30, .10, 0.0]),
        ]
    ],
    _preset(
        preset_id="fasth3-v2-8step-experimental",
        label="FastH3 V2 8-Step (Experimental)",
        blurb="Official FastVideo DMD2 eight-step T2VA recipe on the isolated runtime.",
        suggests_mode=Mode.text,
        patch={
            "length": 124,
            "width": 1344,
            "height": 768,
            "steps": 8,
            "method": MethodId.fast_h3_v2_8step.value,
            "scheduler": "simple",
            "sampler_name": "res_multistep",
            "weights": "int8",
            "encoder": "standard",
            "lora_chain": [],
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 1344x768, 8 steps",
            "FastH3 V2 INT8 ConvRot checkpoint; no extra LoRA",
            "res_multistep + simple; sigma shift video/audio 10/3",
            "Comfy Kitchen attention + VSA 10% from 20%-100%",
            "Native FP16 video VAE, FP32 audio VAE, NVFP4-AWQ encoder",
        ],
        caveats=[
            "Installed but not validated on this RTX 4090. the operator will run the first visual/audio test.",
            "H3VAE-PyOpt is intentionally omitted; this preset uses the native ComfyUI 0.36 FP16/FP32 VAE path.",
            "Text-to-video only. FL2VA and Ref2VA conditioning were not distilled for this checkpoint.",
        ],
    ),
    _preset(
        preset_id="taomate-h3-3step-experimental",
        label="TaoMate H3 3-Step (Draft/Experimental)",
        blurb="Official TaoMate three-step FL2VA LoRA recipe on the isolated runtime.",
        suggests_mode=Mode.text,
        patch={
            "length": 124,
            "width": 1024,
            "height": 576,
            "steps": 3,
            "method": MethodId.taomate_3step.value,
            "scheduler": "simple",
            "sampler_name": "euler",
            "weights": "int8",
            "encoder": "standard",
            "lora_chain": [],
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 1024x576, 3 steps",
            "FL2VA INT8 + TaoMate BF16 LoRA at strength 1.0",
            "Euler + simple; CFG/guider 1.0",
            "Native FP16 video VAE, FP32 audio VAE, NVFP4-AWQ encoder",
        ],
        caveats=[
            "Installed but not validated on this RTX 4090. Treat as Draft/Experimental until the operator completes QA.",
            "H3VAE-PyOpt is intentionally omitted; this preset uses the native ComfyUI 0.36 FP16/FP32 VAE path.",
            "Do not raise CFG above 1.0; the official model card warns that distilled ODE output burns with guidance.",
        ],
    ),
    _preset(
        preset_id="fast-preview-5s",
        label="Fast Preview 5s",
        blurb="Cheapest honest look at an idea before you commit.",
        suggests_mode=Mode.text,
        patch={
            "length": 124,
            "width": 832,
            "height": 480,
            "steps": 16,
            "method": MethodId.easycache.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "easycache": dict(C.EASYCACHE_DEFAULTS),
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 832x480, 16 steps",
            "Fast Preview cache: reuse 0.3, window 0.2-0.9",
        ],
        caveats=[
            "EasyCache measured 57.53s vs 79.98s baseline at 608x352/16 steps, SSIM 0.914. "
            "Fine texture and small lip detail soften first.",
        ],
    ),
    _preset(
        preset_id="balanced-10s",
        label="Balanced 10s",
        blurb="The everyday take: full native length, still cached.",
        suggests_mode=Mode.text,
        patch={
            "length": 243,
            "width": 1024,
            "height": 576,
            "steps": 20,
            "method": MethodId.easycache.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "easycache": dict(C.EASYCACHE_DEFAULTS),
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(243)} at 1024x576, 20 steps",
            "Fast Preview cache kept on for turnaround",
        ],
        caveats=[
            "Roughly 4x the render time of the 5s preview: more frames, more pixels, more steps.",
        ],
    ),
    _preset(
        preset_id="fast-final-trt-5s",
        label="Fast Final TRT 5s",
        blurb="Validated four-step W4A8 final with fast TensorRT video decode.",
        suggests_mode=Mode.text,
        patch={
            "length": 124,
            "width": 608,
            "height": 352,
            "steps": 4,
            "method": MethodId.w4a8_lightx2v_trt.value,
            "scheduler": "simple",
            "sampler_name": "res_multistep",
            "weights": "int8",
            "encoder": "standard",
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 608x352, 4 steps",
            "W4A8 FL2VA + Turbo 4-step v1.1 at 1.0",
            "res_multistep + simple; standard INT8 VAE conditioning, TRT video decode only",
        ],
        caveats=[
            "Measured at 63.445s and 22,944 MiB peak VRAM on reference RTX 4090 workstation RTX 4090.",
            "TRT encode is intentionally not used: its 17-frame engine fails on one-frame I2V conditioning.",
        ],
    ),
    _preset(
        preset_id="lightx2v8-creator-5s",
        label="LightX2V8 Creator 5s",
        blurb="The exact eight-step recipe used by the imported final creator videos.",
        suggests_mode=Mode.first_frame,
        patch={
            "length": 124,
            "width": 1024,
            "height": 576,
            "steps": 8,
            "method": MethodId.baseline.value,
            "scheduler": "beta",
            "sampler_name": "er_sde",
            "weights": "int8",
            "encoder": "standard",
            "lora_chain": [
                {
                    "name": "minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors",
                    "strength": 1.0,
                }
            ],
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 24 fps, 8 steps",
            "FL2VA INT8 + LightX2V 768p Turbo LoRA at 1.0",
            "er_sde sampler + beta scheduler",
        ],
        caveats=[
            "The stored workflows prove the imported finals used FL2VA INT8, not the W4A8 checkpoint.",
            "Use Reuse on a final take to restore its exact dimensions, prompt, reference and seed.",
        ],
        needs=["Optional first-frame image for the same identity-driven workflow"],
    ),
    _preset(
        preset_id="identity-locked",
        label="Identity Locked",
        blurb="Maximum reference fidelity for canonical characters.",
        suggests_mode=Mode.ref2va,
        patch={
            "length": 243,
            "width": 1024,
            "height": 576,
            "steps": 24,
            "method": MethodId.baseline.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "ref_image_size": "max",
        },
        recipe=[
            f"{_seconds(243)} at 1024x576, 24 steps",
            "Quality profile, references held at 2048px short edge",
        ],
        caveats=[
            "Max reference detail keeps every reference token alive through every sampling step. "
            "This can run several times longer than the estimate shown.",
            "Name each reference in the prompt (<Picture 1>, <Picture 2>...) or identity drifts.",
        ],
        needs=["At least one identity image"],
    ),
    _preset(
        preset_id="lip-sync",
        label="Lip-sync",
        blurb="Drive a character's mouth from a reference voice track.",
        suggests_mode=Mode.ref2va,
        patch={
            "length": 243,
            "width": 832,
            "height": 480,
            "steps": 20,
            "method": MethodId.baseline.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(243)} at 832x480, 20 steps",
            "Quality profile - caching is the first thing to blur mouth shapes",
        ],
        caveats=[
            "Reference audio has to travel with an image or a video; H3 will not take a bare voice track.",
            "Keep the voice clip under 15s and write the exact spoken line into the prompt.",
        ],
        needs=["One identity image", "One voice audio (max 15s)"],
    ),
    _preset(
        preset_id="performance-transfer",
        label="Performance Transfer",
        blurb="Your character, someone else's take: motion, timing and camera.",
        suggests_mode=Mode.performance,
        patch={
            "length": 124,
            "width": 576,
            "height": 1024,
            "steps": 12,
            "method": MethodId.baseline.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 576x1024 (vertical), 12 steps",
            "Identity image + motion clip, clip soundtrack passed through for timing",
        ],
        caveats=[
            "The motion clip controls movement only. Say so in the prompt or its wardrobe and "
            "colours leak into your character.",
            "Reference video must be 2-15s at 24fps.",
        ],
        needs=["One canonical identity image", "One motion video (2-15s)"],
    ),
    _preset(
        preset_id="premium-vertical-5s",
        label="Premium Vertical 5s",
        blurb="The bear/robots quality pipeline: generate small, upscale latent 2×, then refine HD.",
        suggests_mode=Mode.first_frame,
        patch={
            "length": 124,
            "width": 640,
            "height": 1152,
            "steps": 4,
            "method": MethodId.w4a8_latent2x_refine3.value,
            "scheduler": "simple",
            "sampler_name": "er_sde",
            "weights": "int8",
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(124)} at 640x1152 final output",
            "320x576 W4A8 + LightX2V4 base → latent 3D 2× → euler Refine3",
        ],
        caveats=[
            "Measured at 169.45s and ~23.8 GiB peak VRAM on reference RTX 4090 workstation RTX 4090.",
            "Keep other GPU services stopped; final dimensions must stay on the 64px grid.",
        ],
        needs=["Optional first-frame image for strongest identity fidelity"],
    ),
    _preset(
        preset_id="final-15s",
        label="Final 15s",
        blurb="Longest native take at full quality. Plan for a long render.",
        suggests_mode=Mode.text,
        patch={
            "length": 362,
            "width": 1024,
            "height": 576,
            "steps": 24,
            "method": MethodId.baseline.value,
            "scheduler": "beta",
            "sampler_name": C.DEFAULT_SAMPLER,
            "ref_image_size": "match",
        },
        recipe=[
            f"{_seconds(362)} at 1024x576, 24 steps",
            "Quality profile, no caching or attention patches",
        ],
        caveats=[
            f"{_seconds(362)} is the top of H3's trained window "
            f"({C.TRAINED_FRAME_MIN}-{C.TRAINED_FRAME_MAX} frames). Anything longer is untested.",
            "Expect a multi-minute render on a 4090 and keep the box free while it runs.",
        ],
    ),
]

PRESETS_BY_ID = {preset["id"]: preset for preset in PRESETS}
