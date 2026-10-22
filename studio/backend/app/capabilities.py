"""Capability discovery.

The UI must never offer something the live Comfy instance cannot do, so every
mode, method, checkpoint, sampler and scheduler the frontend renders comes from
here. When Comfy is unreachable we still answer - with everything honestly
marked unavailable - so the workspace can explain itself instead of hanging.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .comfy import ComfyClientProtocol, ComfyError
from .config import REPO_ROOT
from .db import utcnow
from .schemas import CapabilityResponse, LoraInfo, MethodInfo, Mode, ModeInfo
from .workflow import constants as C
from .workflow.frames import preferred_length_options

CONTRACT_PATH = REPO_ROOT / "docs" / "contracts" / "h3-node-contracts.json"

MODE_META: dict[Mode, dict[str, str]] = {
    Mode.text: {
        "label": "Text to video",
        "blurb": "Prompt only. H3 writes the picture and the sound.",
    },
    Mode.first_frame: {
        "label": "First frame",
        "blurb": "Start from one still and let the scene move from there.",
    },
    Mode.first_last: {
        "label": "First + last frame",
        "blurb": "Pin the opening and closing image, H3 fills the middle.",
    },
    Mode.ref2va: {
        "label": "References",
        "blurb": "Up to 9 images, 3 clips and 3 audios as identity and style anchors.",
    },
    Mode.performance: {
        "label": "Performance transfer",
        "blurb": "One canonical identity, one motion clip, optional source voice.",
    },
}


def _combo_options(info: dict[str, Any], node: str, input_name: str) -> list[str]:
    """Read a combo input's option list from an /object_info payload."""
    spec = info.get(node, {}).get("input", {})
    for section in ("required", "optional"):
        entry = spec.get(section, {}).get(input_name)
        if entry is None:
            continue
        if isinstance(entry, list) and entry:
            head = entry[0]
            if isinstance(head, list):
                return [str(item) for item in head]
            if isinstance(head, str) and head == "COMBO" and len(entry) > 1:
                options = entry[1].get("options") if isinstance(entry[1], dict) else None
                if isinstance(options, list):
                    return [str(item) for item in options]
    return []


def _load_contract() -> dict[str, Any]:
    try:
        return json.loads(Path(CONTRACT_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):  # pragma: no cover - contract ships with the repo
        return {}


def build_capabilities(
    info: dict[str, Any],
    *,
    comfy_url: str,
    comfy_online: bool,
    source: str,
    error: str | None = None,
) -> CapabilityResponse:
    nodes = set(info)
    unet_options = set(_combo_options(info, C.NODE_UNET_LOADER, "unet_name"))
    gguf_options = set(_combo_options(info, C.NODE_UNET_LOADER_GGUF, "unet_name"))
    vae_options = set(_combo_options(info, C.NODE_VAE_LOADER, "vae_name"))
    clip_options = set(_combo_options(info, C.NODE_CLIP_LOADER, "clip_name"))
    lora_options = _combo_options(info, C.NODE_LORA_LOADER_MODEL_ONLY, "lora_name")
    live_samplers = set(_combo_options(info, C.NODE_KSAMPLER_SELECT, "sampler_name"))
    live_schedulers = set(_combo_options(info, C.NODE_BASIC_SCHEDULER, "scheduler"))
    latent_upscalers = set(_combo_options(info, C.NODE_H3_LATENT_UPSCALER_3D, "model_name"))
    trt_decoders = set(_combo_options(info, C.NODE_TRT_VAE_LOADER, "decoder"))
    trt_encoders = set(_combo_options(info, C.NODE_TRT_VAE_LOADER, "encoder"))

    guide_schema = info.get("MiniMaxH3AddGuide", {}).get("input", {})
    guide_inputs = {**guide_schema.get("required", {}), **guide_schema.get("optional", {})}
    guide_contract_ok = all(
        isinstance(guide_inputs.get(name), (list, tuple)) and guide_inputs[name][0] == kind
        for name, kind in {"positive":"CONDITIONING", "latent":"LATENT", "vae":"VAE", "image":"IMAGE", "frame_idx":"INT"}.items()
    )
    core_ok = all(node in nodes for node in C.REQUIRED_NODES)
    vaes_ok = C.VIDEO_VAE in vae_options and C.AUDIO_VAE in vae_options
    clip_ok = C.CLIP_NAME in clip_options
    encoders = {
        "standard": C.CLIP_NAME in clip_options,
        "heretic": C.HERETIC_CLIP_NAME in clip_options,
    }
    foundation_ok = comfy_online and core_ok and vaes_ok and clip_ok

    weights = {
        "int8": C.REF2VA_INT8 in unet_options or C.FL2VA_INT8 in unet_options,
        "gguf_q3km": C.NODE_UNET_LOADER_GGUF in nodes and C.REF2VA_GGUF_Q3KM in gguf_options,
        "pinkcherry_v03": C.PINKCHERRY_FL2VA_INT8_V03 in unet_options,
        "erosmax_beta4": C.EROSMAX_BETA4 in unet_options,
        "erosmax_beta5": C.EROSMAX_BETA5 in unet_options,
    }

    def foundation_reason() -> str | None:
        if not comfy_online:
            return f"H3 Lab ComfyUI at {comfy_url} is not responding."
        missing = [node for node in C.REQUIRED_NODES if node not in nodes]
        if missing:
            return f"Missing Comfy nodes: {', '.join(missing[:4])}."
        if not clip_ok:
            return f"Text encoder {C.CLIP_NAME} is not installed."
        if not vaes_ok:
            return "The H3 video and audio VAEs are not both installed."
        return None

    base_reason = foundation_reason()

    modes: list[ModeInfo] = []
    for mode, meta in MODE_META.items():
        reason = base_reason
        if reason is None:
            if mode in (Mode.text, Mode.first_frame, Mode.first_last):
                if C.NODE_IMAGE_TO_VIDEO not in nodes:
                    reason = f"{C.NODE_IMAGE_TO_VIDEO} is not installed."
                elif C.FL2VA_INT8 not in unet_options:
                    reason = "The FL2VA checkpoint is not installed."
                elif mode is not Mode.text and C.NODE_LOAD_IMAGE not in nodes:
                    reason = "LoadImage is not installed."
            else:
                if C.NODE_REFERENCE_TO_VIDEO not in nodes:
                    reason = f"{C.NODE_REFERENCE_TO_VIDEO} is not installed."
                elif not (C.REF2VA_INT8 in unet_options or weights["gguf_q3km"]):
                    reason = "No Ref2VA checkpoint is installed."
                elif C.NODE_LOAD_IMAGE not in nodes:
                    reason = "LoadImage is not installed."
                elif mode is Mode.performance and not {
                    C.NODE_LOAD_VIDEO,
                    C.NODE_GET_VIDEO_COMPONENTS,
                }.issubset(nodes):
                    reason = "Video reference nodes are not installed."
        modes.append(
            ModeInfo(
                id=mode,
                label=meta["label"],
                blurb=meta["blurb"],
                available=reason is None,
                unavailable_reason=reason,
            )
        )

    methods: list[MethodInfo] = []
    for profile in C.METHOD_PROFILES.values():
        missing_nodes = [node for node in profile["requires_nodes"] if node not in nodes]
        reason = base_reason
        if reason is None and missing_nodes:
            reason = f"{missing_nodes[0]} is not installed on this Comfy instance."
        if reason is None:
            missing_unets = [name for name in profile.get("requires_unets", ()) if name not in unet_options]
            missing_loras = [name for name in profile.get("requires_loras", ()) if name not in lora_options]
            missing_samplers = [name for name in profile.get("requires_samplers", ()) if name not in live_samplers]
            missing_schedulers = [name for name in profile.get("requires_schedulers", ()) if name not in live_schedulers]
            missing_latent_upscalers = [
                name for name in profile.get("requires_latent_upscalers", ()) if name not in latent_upscalers
            ]
            missing_vae_engines = [
                name
                for name in profile.get("requires_vae_engines", ())
                if name not in trt_decoders and name not in trt_encoders
            ]
            if missing_unets:
                reason = f"Checkpoint {missing_unets[0]} is not installed."
            elif missing_loras:
                reason = f"LoRA {missing_loras[0]} is not installed."
            elif missing_samplers:
                reason = f"Sampler {missing_samplers[0]} is not installed."
            elif missing_schedulers:
                reason = f"Scheduler {missing_schedulers[0]} is not installed."
            elif missing_latent_upscalers:
                reason = f"Latent upscaler {missing_latent_upscalers[0]} is not installed."
            elif missing_vae_engines:
                reason = f"TensorRT VAE engine {missing_vae_engines[0]} is not installed."
        methods.append(
            MethodInfo(
                id=profile["id"],
                label=profile["label"],
                blurb=profile["blurb"],
                experimental=profile["experimental"],
                available=reason is None,
                unavailable_reason=reason,
                measured_seconds=profile["measured_seconds"],
                measured_ssim=profile["measured_ssim"],
                measured_steps=int(profile.get("basis_steps", C.BENCHMARK_BASIS["steps"])),
                caveat=profile["caveat"],
            )
        )

    samplers = [name for name in C.SAMPLERS if not live_samplers or name in live_samplers]
    schedulers = [name for name in C.SCHEDULERS if not live_schedulers or name in live_schedulers]

    return CapabilityResponse(
        aligned_guides=(foundation_ok and source == "live" and guide_contract_ok and {"MiniMaxH3AddGuide", C.NODE_LOAD_VIDEO, C.NODE_GET_VIDEO_COMPONENTS}.issubset(nodes)),
        comfy_online=comfy_online,
        comfy_url=comfy_url,
        source="live" if source == "live" else "contract-fallback",
        checked_at=utcnow(),
        error=error,
        modes=modes,
        methods=methods,
        weights={
            "int8": bool(weights["int8"]) and foundation_ok,
            "gguf_q3km": bool(weights["gguf_q3km"]) and foundation_ok,
            "pinkcherry_v03": bool(weights["pinkcherry_v03"]) and foundation_ok,
            "erosmax_beta4": bool(weights["erosmax_beta4"]) and foundation_ok,
            "erosmax_beta5": bool(weights["erosmax_beta5"]) and foundation_ok,
        },
        encoders={
            "standard": bool(encoders["standard"]) and foundation_ok,
            "heretic": bool(encoders["heretic"]) and foundation_ok,
        },
        loras=(
            [
                LoraInfo(
                    name=name,
                    label=str(C.KNOWN_LORAS.get(name, {}).get("label", Path(name).stem)),
                    recommended_strength=float(
                        C.KNOWN_LORAS.get(name, {}).get("recommended_strength", 1.0)
                    ),
                    checkpoint=C.KNOWN_LORAS.get(name, {}).get("checkpoint", "any"),
                    note=C.KNOWN_LORAS.get(name, {}).get("note"),
                )
                for name in lora_options
                if name
                not in {
                    C.LIGHTX2V_4STEP_LORA,
                    C.REF2VA_TURBO_4STEP_LORA,
                    C.REF2VA_VSA_GATE,
                    C.TAOMATE_3STEP_LORA,
                }
            ]
            if C.NODE_LORA_LOADER_MODEL_ONLY in nodes
            else []
        ),
        manual_sigmas=comfy_online and C.NODE_MANUAL_SIGMAS in nodes,
        samplers=samplers,
        schedulers=schedulers,
        preferred_lengths=[
            {
                "frames": option.frames,
                "seconds": option.seconds,
                "label": option.label,
                "native": option.native,
            }
            for option in preferred_length_options()
        ],
        limits={
            "max_ref_images": C.MAX_REF_IMAGES,
            "max_ref_videos": C.MAX_REF_VIDEOS,
            "max_ref_audios": C.MAX_REF_AUDIOS,
            "max_ref_total": C.MAX_REF_TOTAL,
            "max_ref_video_seconds": C.MAX_REF_VIDEO_SECONDS,
            "min_ref_video_seconds": C.MIN_REF_VIDEO_SECONDS,
            "max_ref_audio_seconds": C.MAX_REF_AUDIO_SECONDS,
            "fps": C.FPS,
            "frame_step": C.FRAME_STEP,
            "frame_base": C.FRAME_BASE,
            "trained_frame_min": C.TRAINED_FRAME_MIN,
            "trained_frame_max": C.TRAINED_FRAME_MAX,
            "dimension_step": C.DIMENSION_STEP,
            "dimension_min": C.DIMENSION_MIN,
            "dimension_max": C.DIMENSION_MAX,
            "max_steps": 100,
        },
        benchmark_basis=dict(C.BENCHMARK_BASIS),
    )


class CapabilityService:
    """Caches the capability probe for `ttl` seconds."""

    def __init__(
        self,
        client: ComfyClientProtocol,
        *,
        comfy_url: str,
        ttl: float = 30.0,
        experimental_client: ComfyClientProtocol | None = None,
        experimental_comfy_url: str | None = None,
    ) -> None:
        self._client = client
        self._comfy_url = comfy_url
        self._experimental_client = experimental_client
        self._experimental_comfy_url = experimental_comfy_url
        self._ttl = ttl
        self._cached: CapabilityResponse | None = None
        self._cached_at = 0.0

    def invalidate(self) -> None:
        self._cached = None
        self._cached_at = 0.0

    async def get(self, *, force: bool = False) -> CapabilityResponse:
        now = time.monotonic()
        if not force and self._cached is not None and (now - self._cached_at) < self._ttl:
            return self._cached
        try:
            info = await self._client.object_info()
            result = build_capabilities(info, comfy_url=self._comfy_url, comfy_online=True, source="live")
        except (ComfyError, ValueError) as exc:
            result = build_capabilities(
                _load_contract(),
                comfy_url=self._comfy_url,
                comfy_online=False,
                source="contract-fallback",
                error=str(exc),
            )
        if self._experimental_client is not None and self._experimental_comfy_url:
            try:
                experimental_info = await self._experimental_client.object_info()
                experimental = build_capabilities(
                    experimental_info,
                    comfy_url=self._experimental_comfy_url,
                    comfy_online=True,
                    source="live",
                )
            except (ComfyError, ValueError) as exc:
                experimental = build_capabilities(
                    _load_contract(),
                    comfy_url=self._experimental_comfy_url,
                    comfy_online=False,
                    source="contract-fallback",
                    error=str(exc),
                )
            experimental_methods = {method.id: method for method in experimental.methods}
            merged_methods = [
                experimental_methods.get(method.id, method)
                if C.METHOD_PROFILES.get(method.id, {}).get("backend") == "experimental"
                else method
                for method in result.methods
            ]
            result = result.model_copy(update={"methods": merged_methods})
        self._cached = result
        self._cached_at = now
        return result

    async def available_methods(self) -> set[str]:
        capabilities = await self.get()
        return {method.id for method in capabilities.methods if method.available}
