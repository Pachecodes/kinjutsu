"""Pure ComfyUI workflow builder for every H3 Studio product mode.

`build_workflow` is a pure function: same request + same resolved assets in,
byte-identical prompt graph out. That is what makes the snapshot and contract
tests against `docs/fixtures/*.json` meaningful.

Graph shape (matches the shipped fixtures):

    1  UNETLoader / UnetLoaderGGUF
    2  CLIPLoader
    3  VAELoader  (video)
    4  VAELoader  (audio)
    5  MiniMaxH3ImageToVideo | MiniMaxH3ReferenceToVideo
    6  BasicGuider
    7  RandomNoise
    8  KSamplerSelect
    9  BasicScheduler
    10 SamplerCustomAdvanced
    11 VAEDecode
    12 VAEDecodeAudio
    13 CreateVideo
    14 SaveVideo
    15+ reference loaders, allocated in creator order
    100 optional method patch (EasyCache / Sage / SolAttn)

The scheduler deliberately reads the *unpatched* model, exactly like the
fixtures: sigmas must not move between method profiles or the measured
baseline/EasyCache/Sage/Sol comparison stops meaning anything.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..schemas import EncoderVariant, GenerationRequest, MethodId, Mode, RefKind, RefRole, WeightVariant
from . import constants as C
from .continuity import plan_continuity
from .validation import ResolvedAsset

NodeId = str
Link = list[Any]

ID_UNET: NodeId = "1"
ID_CLIP: NodeId = "2"
ID_VIDEO_VAE: NodeId = "3"
ID_AUDIO_VAE: NodeId = "4"
ID_CONDITIONING: NodeId = "5"
ID_GUIDER: NodeId = "6"
ID_NOISE: NodeId = "7"
ID_SAMPLER: NodeId = "8"
ID_SCHEDULER: NodeId = "9"
ID_SAMPLE: NodeId = "10"
ID_DECODE_VIDEO: NodeId = "11"
ID_DECODE_AUDIO: NodeId = "12"
ID_CREATE_VIDEO: NodeId = "13"
ID_SAVE_VIDEO: NodeId = "14"
ID_PATCH: NodeId = "100"
ID_PREVIEW: NodeId = "101"
ID_TRT_VIDEO_VAE: NodeId = "102"
ID_SIGMA_SHIFT: NodeId = "103"
ID_ATTENTION_BACKEND: NodeId = "104"
ID_BLOCK_SPARSE: NodeId = "105"
ID_SEPARATE_AV: NodeId = "200"
ID_LATENT_UPSCALE: NodeId = "201"
ID_CONCAT_AV: NodeId = "202"
ID_REFINE_CONDITIONING: NodeId = "203"
ID_REFINE_GUIDER: NodeId = "204"
ID_REFINE_SAMPLER: NodeId = "205"
ID_REFINE_SIGMAS: NodeId = "206"
ID_REFINE_SAMPLE: NodeId = "207"
FIRST_LORA_ID = 110
FIRST_REFERENCE_ID = 15

FRAME_MODES = {Mode.text, Mode.first_frame, Mode.first_last}
REFERENCE_MODES = {Mode.ref2va, Mode.performance}
W4A8_METHODS = {MethodId.w4a8_lightx2v, MethodId.w4a8_lightx2v_trt, MethodId.w4a8_latent2x_refine3}
EXPERIMENTAL_METHODS = {MethodId.fast_h3_v2_8step, MethodId.taomate_3step}

_PREFIX_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


class WorkflowBuildError(ValueError):
    """Raised when a request cannot be expressed with the live node contract."""


@dataclass(frozen=True)
class BuiltWorkflow:
    prompt: dict[NodeId, dict[str, Any]]
    output_node_id: NodeId
    filename_prefix: str
    checkpoint: str
    reference_tags: list[str] = field(default_factory=list)


def sanitize_prefix_component(value: str, *, fallback: str = "take") -> str:
    """Collapse anything a creator typed into a filesystem-safe token."""
    cleaned = _PREFIX_SAFE.sub("_", (value or "").strip()).strip("_")
    cleaned = cleaned[:48].strip("_")
    return cleaned or fallback


def _multishot_script(prompt: str) -> str:
    """Keep bracketed production headings on the plain-script parser path.

    H3 Multishot interprets every script whose first non-space character is
    `[` or `{` as JSON. Studio/Director prompts commonly begin with headings
    such as `[REFERENCE USE]`, which are plain text rather than JSON arrays.
    A neutral prefix preserves the prompt verbatim while preventing that
    parser misclassification.
    """
    stripped = prompt.lstrip()
    if re.match(r"^\[[A-Za-z][^\]\r\n]*\]", stripped) or re.match(
        r"^\{[A-Za-z][^{}\r\n]*\}", stripped
    ):
        return f"H3 prompt sections:\n{prompt}"
    return prompt


def make_filename_prefix(job_id: str, title: str | None) -> str:
    slug = sanitize_prefix_component(title or "", fallback="Take")
    short = sanitize_prefix_component(job_id, fallback="job")[:8]
    return f"{C.OUTPUT_PREFIX_ROOT}_{slug}_{short}"


def checkpoint_for(mode: Mode, weights: WeightVariant) -> tuple[str, str]:
    """Return (node class, checkpoint file) for the requested mode + variant."""
    if weights is WeightVariant.erosmax_beta5:
        return C.NODE_UNET_LOADER, C.EROSMAX_BETA5
    if weights is WeightVariant.erosmax_beta4:
        if mode not in REFERENCE_MODES:
            raise WorkflowBuildError("H3 ErosMax Beta 4 is a custom Ref2VA checkpoint and cannot run frame modes.")
        return C.NODE_UNET_LOADER, C.EROSMAX_BETA4
    if mode in FRAME_MODES:
        if weights is WeightVariant.gguf_q3km:
            raise WorkflowBuildError("No GGUF build exists for the FL2VA checkpoint.")
        if weights is WeightVariant.pinkcherry_v03:
            return C.NODE_UNET_LOADER, C.PINKCHERRY_FL2VA_INT8_V03
        return C.NODE_UNET_LOADER, C.FL2VA_INT8
    if weights is WeightVariant.pinkcherry_v03:
        raise WorkflowBuildError("Pink Cherry v0.3 is an FL2VA checkpoint and cannot run Ref2VA modes.")
    if weights is WeightVariant.gguf_q3km:
        return C.NODE_UNET_LOADER_GGUF, C.REF2VA_GGUF_Q3KM
    return C.NODE_UNET_LOADER, C.REF2VA_INT8


def encoder_for(variant: EncoderVariant) -> str:
    """Map the explicit conditioning variant to an installed CLIP filename."""
    if variant is EncoderVariant.heretic:
        return C.HERETIC_CLIP_NAME
    return C.CLIP_NAME


def _loader_node(request: GenerationRequest) -> tuple[dict[str, Any], str]:
    if request.method is MethodId.fast_h3_v2_8step:
        return (
            {"class_type": C.NODE_UNET_LOADER, "inputs": {"unet_name": C.FASTH3_V2, "weight_dtype": "default"}},
            C.FASTH3_V2,
        )
    if request.method is MethodId.taomate_3step:
        return (
            {"class_type": C.NODE_UNET_LOADER, "inputs": {"unet_name": C.FL2VA_INT8, "weight_dtype": "default"}},
            C.FL2VA_INT8,
        )
    if request.method in W4A8_METHODS:
        if request.mode not in FRAME_MODES:
            raise WorkflowBuildError("W4A8 + LightX2V4 is FL2VA-only; use Text, First frame, or First + last frame.")
        return (
            {"class_type": C.NODE_UNET_LOADER, "inputs": {"unet_name": C.FL2VA_W4A8, "weight_dtype": "default"}},
            C.FL2VA_W4A8,
        )
    mode, weights = request.mode, request.weights
    class_type, checkpoint = checkpoint_for(mode, weights)
    if class_type == C.NODE_UNET_LOADER_GGUF:
        return {"class_type": class_type, "inputs": {"unet_name": checkpoint}}, checkpoint
    return (
        {"class_type": class_type, "inputs": {"unet_name": checkpoint, "weight_dtype": "default"}},
        checkpoint,
    )


def _patch_node(request: GenerationRequest, model_link: Link) -> dict[str, Any] | None:
    """Method profile -> optional MODEL patch node fed by the LoRA chain."""
    if request.method is MethodId.baseline:
        return None
    if request.method in W4A8_METHODS or request.method in EXPERIMENTAL_METHODS:
        return None
    if request.method is MethodId.easycache:
        return {
            "class_type": C.NODE_EASYCACHE,
            "inputs": {
                "model": model_link,
                "reuse_threshold": request.easycache.reuse_threshold,
                "start_percent": request.easycache.start_percent,
                "end_percent": request.easycache.end_percent,
                "verbose": request.easycache.verbose,
            },
        }
    if request.method is MethodId.ref2va_vsa:
        return {
            "class_type": C.NODE_REF2VA_VSA_PATCH,
            "inputs": {
                "model": model_link,
                "gate_file": C.REF2VA_VSA_GATE,
                "sparsity": C.REF2VA_VSA_SPARSITY,
            },
        }
    if request.method is MethodId.sage:
        return {"class_type": C.NODE_SAGE_PATCH, "inputs": {"model": model_link}}
    if request.method is MethodId.sol:
        sol = request.sol
        return {
            "class_type": C.NODE_SOL_PATCH,
            "inputs": {
                "model": model_link,
                "tau": sol.tau,
                "start_percent": sol.start_percent,
                "end_percent": sol.end_percent,
                "min_tokens": sol.min_tokens,
                "int8_qk": sol.int8_qk,
                "sink_conditioning": sol.sink_conditioning,
                "morton": sol.morton,
                "morton_curve": sol.morton_curve,
                "verbose": sol.verbose,
                "use_tma": sol.use_tma,
            },
        }
    raise WorkflowBuildError(f"Unhandled method profile: {request.method}")


@dataclass
class _ReferenceWiring:
    nodes: dict[NodeId, dict[str, Any]] = field(default_factory=dict)
    image_links: list[Link] = field(default_factory=list)
    video_image_links: list[Link] = field(default_factory=list)
    video_audio_links: dict[int, Link] = field(default_factory=dict)
    audio_links: list[Link] = field(default_factory=list)
    first_frame: Link | None = None
    last_frame: Link | None = None
    tags: list[str] = field(default_factory=list)
    guide_links: list[Link] = field(default_factory=list)


def _resolve(request: GenerationRequest, assets: Mapping[str, ResolvedAsset]) -> _ReferenceWiring:
    wiring = _ReferenceWiring()
    next_id = FIRST_REFERENCE_ID
    video_index = 0

    for ref in request.references:
        asset = assets.get(ref.asset_id)
        if asset is None:
            raise WorkflowBuildError(f"Reference asset {ref.asset_id} is not available.")
        if asset.kind != ref.kind:
            raise WorkflowBuildError(f"Reference asset {ref.asset_id} is a {asset.kind.value}, not a {ref.kind.value}.")

        if ref.kind is RefKind.image:
            node_id = str(next_id)
            next_id += 1
            wiring.nodes[node_id] = {
                "class_type": C.NODE_LOAD_IMAGE,
                "inputs": {"image": asset.comfy_name},
            }
            if ref.role is RefRole.first_frame:
                wiring.first_frame = [node_id, 0]
            elif ref.role is RefRole.last_frame:
                wiring.last_frame = [node_id, 0]
            else:
                wiring.image_links.append([node_id, 0])
                wiring.tags.append(f"<Picture {len(wiring.image_links)}>")

        elif ref.kind is RefKind.video:
            load_id = str(next_id)
            components_id = str(next_id + 1)
            next_id += 2
            wiring.nodes[load_id] = {
                "class_type": C.NODE_LOAD_VIDEO,
                "inputs": {"file": asset.comfy_name},
            }
            wiring.nodes[components_id] = {
                "class_type": C.NODE_GET_VIDEO_COMPONENTS,
                "inputs": {"video": [load_id, 0]},
            }
            if ref.role is RefRole.aligned_guide:
                wiring.guide_links.append([components_id, 0])
                continue
            wiring.video_image_links.append([components_id, 0])
            if ref.include_audio:
                wiring.video_audio_links[video_index] = [components_id, 1]
            video_index += 1
            wiring.tags.append(f"<Video {len(wiring.video_image_links)}>")

        else:  # audio
            node_id = str(next_id)
            next_id += 1
            wiring.nodes[node_id] = {
                "class_type": C.NODE_LOAD_AUDIO,
                "inputs": {"audio": asset.comfy_name},
            }
            wiring.audio_links.append([node_id, 0])
            wiring.tags.append(f"<Audio {len(wiring.audio_links)}>")

    return wiring


def _conditioning_node(request: GenerationRequest, wiring: _ReferenceWiring) -> dict[str, Any]:
    if request.mode in FRAME_MODES:
        inputs: dict[str, Any] = {
            "clip": [ID_CLIP, 0],
            "vae": [ID_VIDEO_VAE, 0],
            "prompt": request.prompt,
            "width": request.width,
            "height": request.height,
            "length": request.length,
        }
        if wiring.first_frame is not None:
            inputs["first_frame"] = wiring.first_frame
        if wiring.last_frame is not None:
            inputs["last_frame"] = wiring.last_frame
        if request.mode is Mode.text and (wiring.first_frame or wiring.last_frame):
            raise WorkflowBuildError("Text mode cannot carry frame references.")
        if request.mode is Mode.first_frame and wiring.first_frame is None:
            raise WorkflowBuildError("First frame mode needs a first frame image.")
        if request.mode is Mode.first_last and (wiring.first_frame is None or wiring.last_frame is None):
            raise WorkflowBuildError("First + last frame mode needs both frames.")
        return {"class_type": C.NODE_IMAGE_TO_VIDEO, "inputs": inputs}

    inputs = {
        "clip": [ID_CLIP, 0],
        "vae": [ID_VIDEO_VAE, 0],
        "audio_vae": [ID_AUDIO_VAE, 0],
        "prompt": request.prompt,
        "width": request.width,
        "height": request.height,
        "length": request.length,
        "ref_image_size": request.ref_image_size,
    }
    for index, link in enumerate(wiring.image_links):
        inputs[f"ref_images.ref_image_{index}"] = link
    for index, link in enumerate(wiring.video_image_links):
        inputs[f"ref_videos.ref_video_{index}"] = link
    for index in sorted(wiring.video_audio_links):
        inputs[f"ref_video_audios.ref_video_audio_{index}"] = wiring.video_audio_links[index]
    for index, link in enumerate(wiring.audio_links):
        inputs[f"ref_audios.ref_audio_{index}"] = link
    return {"class_type": C.NODE_REFERENCE_TO_VIDEO, "inputs": inputs}


def build_workflow(
    request: GenerationRequest,
    assets: Mapping[str, ResolvedAsset],
    *,
    seed: int,
    filename_prefix: str,
) -> BuiltWorkflow:
    """Build the Comfy prompt graph for one render. Pure."""
    if request.method is MethodId.ref2va_vsa:
        if request.mode is not Mode.ref2va:
            raise WorkflowBuildError("Ref2VA VSA is validated only for References mode.")
        if not (
            request.steps == 4
            and request.sampler_name == "euler"
            and request.scheduler == "simple"
        ):
            raise WorkflowBuildError("Ref2VA VSA requires 4 steps, Euler, and the simple scheduler.")
    if request.mode in FRAME_MODES:
        for ref in request.references:
            if ref.role not in (RefRole.first_frame, RefRole.last_frame):
                raise WorkflowBuildError(f"{request.mode.value} mode does not accept a '{ref.role.value}' reference.")
    else:
        for ref in request.references:
            if ref.role in (RefRole.first_frame, RefRole.last_frame):
                raise WorkflowBuildError("Frame roles are only available in the frame-driven modes.")

    if any(r.role is RefRole.aligned_guide for r in request.references):
        from .validation import validate_aligned_guides, has_errors
        guide_issues = validate_aligned_guides(request, assets, available=True)
        if has_errors(guide_issues):
            raise WorkflowBuildError("; ".join(i.message for i in guide_issues if i.severity.value == "error"))
    continuity_plan = plan_continuity(request)
    if continuity_plan.split:
        return _build_continuity_workflow(
            request,
            assets,
            seed=seed,
            filename_prefix=filename_prefix,
            plan=continuity_plan,
        )

    wiring = _resolve(request, assets)
    premium = request.method is MethodId.w4a8_latent2x_refine3
    conditioning_request = request.model_copy(
        update={"width": request.width // 2, "height": request.height // 2}
    ) if premium else request
    loader, checkpoint = _loader_node(request)
    model_link: Link = [ID_UNET, 0]
    lora_nodes: dict[NodeId, dict[str, Any]] = {}
    if request.method is MethodId.taomate_3step:
        lora_nodes["109"] = {
            "class_type": C.NODE_LORA_LOADER_MODEL_ONLY,
            "inputs": {
                "model": model_link,
                "lora_name": C.TAOMATE_3STEP_LORA,
                "strength_model": 1.0,
            },
        }
        model_link = ["109", 0]
    elif request.method in W4A8_METHODS or request.method is MethodId.ref2va_vsa:
        fast_final_trt = request.method is MethodId.w4a8_lightx2v_trt
        ref2va_vsa = request.method is MethodId.ref2va_vsa
        lora_nodes["109"] = {
            "class_type": C.NODE_LORA_LOADER_MODEL_ONLY,
            "inputs": {
                "model": model_link,
                "lora_name": (
                    C.REF2VA_TURBO_4STEP_LORA
                    if ref2va_vsa
                    else C.FAST_FINAL_4STEP_LORA
                    if fast_final_trt
                    else C.LIGHTX2V_4STEP_LORA
                ),
                "strength_model": (
                    1.0
                    if ref2va_vsa
                    else C.FAST_FINAL_4STEP_STRENGTH
                    if fast_final_trt
                    else C.LIGHTX2V_4STEP_STRENGTH
                ),
            },
        }
        model_link = ["109", 0]
    for index, lora in enumerate(request.lora_chain):
        node_id = str(FIRST_LORA_ID + index)
        lora_nodes[node_id] = {
            "class_type": C.NODE_LORA_LOADER_MODEL_ONLY,
            "inputs": {
                "model": model_link,
                "lora_name": lora.name,
                "strength_model": lora.strength,
            },
        }
        model_link = [node_id, 0]
    patch = _patch_node(request, model_link)
    patched_model: Link = [ID_PATCH, 0] if patch else model_link
    if request.method is MethodId.ref2va_vsa:
        patched_model = [ID_SIGMA_SHIFT, 0]
    elif request.method is MethodId.fast_h3_v2_8step:
        patched_model = [ID_BLOCK_SPARSE, 0]
    preview_node = {
        "class_type": "ModelPreviewOverrideKJ",
        "inputs": {
            "model": patched_model,
            "max_resolution": 1024,
            "jpeg_quality": 80,
            "suppress_default_preview": True,
            "preview_frames": request.length,
            "preview_fps": 12,
            "tiny_vae": "taeh3.safetensors",
        },
    }
    guider_model: Link = patched_model if request.method in EXPERIMENTAL_METHODS else [ID_PREVIEW, 0]

    prompt: dict[NodeId, dict[str, Any]] = {
        ID_UNET: loader,
        ID_CLIP: {
            "class_type": C.NODE_CLIP_LOADER,
            "inputs": {"clip_name": encoder_for(request.encoder), "type": C.CLIP_TYPE, "device": "default"},
        },
        ID_VIDEO_VAE: {
            "class_type": C.NODE_VAE_LOADER,
            "inputs": {
                "vae_name": C.W4A8_VIDEO_VAE if request.method in W4A8_METHODS else C.VIDEO_VAE
            },
        },
        ID_AUDIO_VAE: {"class_type": C.NODE_VAE_LOADER, "inputs": {"vae_name": C.AUDIO_VAE}},
    }
    prompt.update(wiring.nodes)
    prompt.update(lora_nodes)
    if request.method is MethodId.w4a8_lightx2v_trt:
        prompt[ID_TRT_VIDEO_VAE] = {
            "class_type": C.NODE_TRT_VAE_LOADER,
            "inputs": {"decoder": C.TRT_VAE_DECODER, "encoder": C.TRT_VAE_ENCODER},
        }
    if request.method not in EXPERIMENTAL_METHODS:
        prompt[ID_PREVIEW] = preview_node
    if request.method is MethodId.fast_h3_v2_8step:
        prompt[ID_SIGMA_SHIFT] = {
            "class_type": C.NODE_H3_SIGMA_SHIFT,
            "inputs": {"model": [ID_UNET, 0], "shift_video": 10, "shift_audio": 3},
        }
        prompt[ID_ATTENTION_BACKEND] = {
            "class_type": C.NODE_MODEL_ATTENTION_BACKEND,
            "inputs": {"model": [ID_SIGMA_SHIFT, 0], "attention": "comfy kitchen attention"},
        }
        prompt[ID_BLOCK_SPARSE] = {
            "class_type": C.NODE_BLOCK_SPARSE_ATTENTION,
            "inputs": {
                "model": [ID_ATTENTION_BACKEND, 0],
                "selection": "vsa",
                "selection.keep_percent": 10,
                "start_percent": 0.2,
                "end_percent": 1.0,
                "dense_blocks": "",
                "min_tokens": 12288,
                "extra_tokens": 256,
                "sink_conditioning": "exact_kv_and_rows",
                "verbose": False,
            },
        }
    prompt[ID_CONDITIONING] = _conditioning_node(conditioning_request, wiring)
    conditioning_link = [ID_CONDITIONING, 0]
    if wiring.guide_links:
        prompt["106"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
            "positive": conditioning_link, "latent": [ID_CONDITIONING, 1],
            "vae": [ID_VIDEO_VAE, 0], "image": wiring.guide_links[0], "frame_idx": 0,
        }}
        conditioning_link = ["106", 0]
    prompt[ID_GUIDER] = {
        "class_type": C.NODE_BASIC_GUIDER,
        "inputs": {"model": guider_model, "conditioning": conditioning_link},
    }
    prompt[ID_NOISE] = {"class_type": C.NODE_RANDOM_NOISE, "inputs": {"noise_seed": seed}}
    prompt[ID_SAMPLER] = {
        "class_type": C.NODE_KSAMPLER_SELECT,
        "inputs": {"sampler_name": request.sampler_name},
    }
    prompt[ID_SCHEDULER] = {
        "class_type": C.NODE_BASIC_SCHEDULER,
        # Unpatched model on purpose - see module docstring.
        "inputs": {
            "model": (
                patched_model
                if request.method is MethodId.ref2va_vsa or request.method in EXPERIMENTAL_METHODS
                else model_link
                if request.method in W4A8_METHODS
                else [ID_UNET, 0]
            ),
            "scheduler": request.scheduler,
            "steps": request.steps,
            "denoise": 1.0,
        },
    }
    if request.custom_sigmas is not None:
        prompt[ID_SCHEDULER] = {
            "class_type": C.NODE_MANUAL_SIGMAS,
            "inputs": {"sigmas": ", ".join(str(value) for value in request.custom_sigmas)},
        }
    prompt[ID_SAMPLE] = {
        "class_type": C.NODE_SAMPLER_CUSTOM_ADVANCED,
        "inputs": {
            "noise": [ID_NOISE, 0],
            "guider": [ID_GUIDER, 0],
            "sampler": [ID_SAMPLER, 0],
            "sigmas": [ID_SCHEDULER, 0],
            "latent_image": [ID_CONDITIONING, 1],
        },
    }
    decode_source: Link = [ID_SAMPLE, 0]
    if premium:
        prompt[ID_SEPARATE_AV] = {
            "class_type": C.NODE_SEPARATE_AV_LATENT,
            "inputs": {"av_latent": [ID_SAMPLE, 0]},
        }
        prompt[ID_LATENT_UPSCALE] = {
            "class_type": C.NODE_H3_LATENT_UPSCALER_3D,
            "inputs": {
                "latent": [ID_SEPARATE_AV, 0],
                "model_name": C.H3_LATENT_UPSCALER_3D,
                "precision": "bf16",
                "mode": "scale by multiplier",
                "mode.scale": 2.0,
                "device": "cuda",
                "enable_chunking": True,
                "align": 32,
            },
        }
        prompt[ID_CONCAT_AV] = {
            "class_type": C.NODE_CONCAT_AV_LATENT,
            "inputs": {
                "video_latent": [ID_LATENT_UPSCALE, 0],
                "audio_latent": [ID_SEPARATE_AV, 1],
            },
        }
        prompt[ID_REFINE_CONDITIONING] = _conditioning_node(request, wiring)
        prompt[ID_REFINE_GUIDER] = {
            "class_type": C.NODE_BASIC_GUIDER,
            "inputs": {"model": model_link, "conditioning": [ID_REFINE_CONDITIONING, 0]},
        }
        prompt[ID_REFINE_SAMPLER] = {
            "class_type": C.NODE_KSAMPLER_SELECT,
            "inputs": {"sampler_name": "euler"},
        }
        prompt[ID_REFINE_SIGMAS] = {
            "class_type": C.NODE_MANUAL_SIGMAS,
            "inputs": {"sigmas": C.PREMIUM_REFINE_SIGMAS},
        }
        prompt[ID_REFINE_SAMPLE] = {
            "class_type": C.NODE_SAMPLER_CUSTOM_ADVANCED,
            "inputs": {
                "noise": [ID_NOISE, 0],
                "guider": [ID_REFINE_GUIDER, 0],
                "sampler": [ID_REFINE_SAMPLER, 0],
                "sigmas": [ID_REFINE_SIGMAS, 0],
                "latent_image": [ID_CONCAT_AV, 0],
            },
        }
        decode_source = [ID_REFINE_SAMPLE, 0]
    prompt[ID_DECODE_VIDEO] = {
        "class_type": C.NODE_VAE_DECODE,
        "inputs": {
            "samples": decode_source,
            # The TRT encoder expects 17 frames and fails on one-frame I2V.
            # Conditioning/encode stays on node 3; TRT is video decode only.
            "vae": [ID_TRT_VIDEO_VAE, 0]
            if request.method is MethodId.w4a8_lightx2v_trt
            else [ID_VIDEO_VAE, 0],
        },
    }
    prompt[ID_DECODE_AUDIO] = {
        "class_type": C.NODE_VAE_DECODE_AUDIO,
        "inputs": {"samples": decode_source, "vae": [ID_AUDIO_VAE, 0]},
    }
    prompt[ID_CREATE_VIDEO] = {
        "class_type": C.NODE_CREATE_VIDEO,
        "inputs": {
            "images": [ID_DECODE_VIDEO, 0],
            "audio": [ID_DECODE_AUDIO, 0],
            "fps": C.FPS,
            "bit_depth": 8,
        },
    }
    prompt[ID_SAVE_VIDEO] = {
        "class_type": C.NODE_SAVE_VIDEO,
        "inputs": {
            "video": [ID_CREATE_VIDEO, 0],
            "filename_prefix": filename_prefix,
            "format": "mp4",
            "codec": "auto",
        },
    }
    if patch is not None:
        prompt[ID_PATCH] = patch
    if request.method is MethodId.ref2va_vsa:
        prompt[ID_SIGMA_SHIFT] = {
            "class_type": C.NODE_H3_SIGMA_SHIFT,
            "inputs": {"model": [ID_PATCH, 0], "shift_video": 12, "shift_audio": 3},
        }

    return BuiltWorkflow(
        prompt=prompt,
        output_node_id=ID_SAVE_VIDEO,
        filename_prefix=filename_prefix,
        checkpoint=checkpoint,
        reference_tags=wiring.tags,
    )


def _build_continuity_workflow(
    request: GenerationRequest,
    assets: Mapping[str, ResolvedAsset],
    *,
    seed: int,
    filename_prefix: str,
    plan: Any,
) -> BuiltWorkflow:
    """Build one Comfy graph whose sampler owns all context-pinned windows."""
    if request.mode in {Mode.first_frame, Mode.first_last}:
        raise WorkflowBuildError("Automatic raw-latent continuity currently supports Text and References modes, not frame-conditioned modes.")
    if request.mode is Mode.performance:
        raise WorkflowBuildError("Automatic continuity cannot preserve performance-transfer semantics yet; use References or First frame.")
    if request.method in {MethodId.w4a8_lightx2v_trt, MethodId.w4a8_latent2x_refine3}:
        raise WorkflowBuildError("Automatic raw-latent continuity is incompatible with TRT conditioning and two-pass latent refinement.")

    wiring = _resolve(request, assets)
    loader, checkpoint = _loader_node(request)
    model_link: Link = [ID_UNET, 0]
    graph: dict[NodeId, dict[str, Any]] = {
        ID_UNET: loader,
        ID_CLIP: {
            "class_type": C.NODE_CLIP_LOADER,
            "inputs": {"clip_name": encoder_for(request.encoder), "type": C.CLIP_TYPE, "device": "default"},
        },
        ID_VIDEO_VAE: {
            "class_type": C.NODE_VAE_LOADER,
            "inputs": {"vae_name": C.W4A8_VIDEO_VAE if request.method in W4A8_METHODS else C.VIDEO_VAE},
        },
        ID_AUDIO_VAE: {"class_type": C.NODE_VAE_LOADER, "inputs": {"vae_name": C.AUDIO_VAE}},
    }
    graph.update(wiring.nodes)

    if request.method in W4A8_METHODS or request.method is MethodId.ref2va_vsa:
        graph["109"] = {
            "class_type": C.NODE_LORA_LOADER_MODEL_ONLY,
            "inputs": {
                "model": model_link,
                "lora_name": (
                    C.REF2VA_TURBO_4STEP_LORA
                    if request.method is MethodId.ref2va_vsa
                    else C.LIGHTX2V_4STEP_LORA
                ),
                "strength_model": (
                    1.0 if request.method is MethodId.ref2va_vsa else C.LIGHTX2V_4STEP_STRENGTH
                ),
            },
        }
        model_link = ["109", 0]
    for index, lora in enumerate(request.lora_chain):
        node_id = str(FIRST_LORA_ID + index)
        graph[node_id] = {
            "class_type": C.NODE_LORA_LOADER_MODEL_ONLY,
            "inputs": {"model": model_link, "lora_name": lora.name, "strength_model": lora.strength},
        }
        model_link = [node_id, 0]
    patch = _patch_node(request, model_link)
    if patch is not None:
        graph[ID_PATCH] = patch
        model_link = [ID_PATCH, 0]
    if request.method is MethodId.ref2va_vsa:
        graph[ID_SIGMA_SHIFT] = {
            "class_type": C.NODE_H3_SIGMA_SHIFT,
            "inputs": {"model": model_link, "shift_video": 12, "shift_audio": 3},
        }
        model_link = [ID_SIGMA_SHIFT, 0]

    memory_inputs: dict[str, Any] = {
        "model": model_link,
        "clip": [ID_CLIP, 0],
        "video_vae": [ID_VIDEO_VAE, 0],
        "audio_vae": [ID_AUDIO_VAE, 0],
        "script": _multishot_script(request.prompt),
        "shot_count": plan.window_count,
        "width": request.width,
        "height": request.height,
        "frames_per_shot": plan.window_frames,
        "seed": seed,
        "steps": request.steps,
        "seed_per_shot": True,
        "memory_frames": 0,
        "anchor_frames": 1,
        "sampler_name": request.sampler_name,
        "scheduler": request.scheduler,
        "bank_pinned": 1,
        "chain_gain_control": "off",
        "continuity": "context_pin",
        "bank_clip_frames": 22,
        "color_level": "off",
        "join_anchor_noise": 0.0,
        "join_blend": False,
        "handoff_release": 0.3,
        "bank_ref_noise": 0.0,
        "end_anchor": False,
        "join_fx": "off",
        "audio_lock": True,
        "handoff_taper": 0,
        "handoff_depth": "block",
        "self_anchor_voice": False,
        "reference_image_size": "match" if request.ref_image_size == "match" else "model_default",
        "preview_first_shot": False,
        "output_scale": 1.0,
        "save_every_shot": False,
        "upscale_model_name": "(none)",
        "master_normalize": "luma+contrast",
        "pin_frames": str(plan.pin_frames),
        "pin_noise": 0.05,
        "pin_renorm": True,
        "reference_subjects": "",
        "low_ram_master": False,
        "audio_pin_frames": 24,
    }
    if wiring.first_frame is not None:
        memory_inputs["start_image"] = wiring.first_frame
    if wiring.image_links:
        if len(wiring.image_links) == 1:
            memory_inputs["reference_images"] = wiring.image_links[0]
        else:
            graph["304"] = {
                "class_type": C.NODE_BATCH_IMAGES,
                "inputs": {f"images.image{index}": link for index, link in enumerate(wiring.image_links)},
            }
            memory_inputs["reference_images"] = ["304", 0]
    if wiring.audio_links:
        for index, link in enumerate(wiring.audio_links[:3]):
            memory_inputs["voice_ref" if index == 0 else f"voice_ref_{index + 1}"] = link
    if wiring.video_image_links:
        memory_inputs["reference_video"] = wiring.video_image_links[0]
        if 0 in wiring.video_audio_links:
            memory_inputs["reference_video_audio"] = wiring.video_audio_links[0]

    graph["300"] = {"class_type": C.NODE_H3_MULTISHOT_MEMORY, "inputs": memory_inputs}
    graph["301"] = {
        "class_type": C.NODE_IMAGE_RANGE,
        "inputs": {"start_index": 0, "num_frames": request.length, "images": ["300", 0]},
    }
    graph["302"] = {
        "class_type": C.NODE_TRIM_AUDIO_DURATION,
        "inputs": {"audio": ["300", 1], "start_index": 0.0, "duration": request.length / C.FPS},
    }
    graph[ID_CREATE_VIDEO] = {
        "class_type": C.NODE_CREATE_VIDEO,
        "inputs": {"images": ["301", 0], "audio": ["302", 0], "fps": C.FPS, "bit_depth": 8},
    }
    graph[ID_SAVE_VIDEO] = {
        "class_type": C.NODE_SAVE_VIDEO,
        "inputs": {"video": [ID_CREATE_VIDEO, 0], "filename_prefix": filename_prefix, "format": "mp4", "codec": "auto"},
    }
    return BuiltWorkflow(
        prompt=graph,
        output_node_id=ID_SAVE_VIDEO,
        filename_prefix=filename_prefix,
        checkpoint=checkpoint,
        reference_tags=wiring.tags,
    )
