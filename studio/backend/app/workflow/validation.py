"""Pure validation of a GenerationRequest against the live H3 contract.

No I/O happens here. Callers pass in already-resolved asset metadata so the
whole rule set is unit-testable and the frontend can call `/api/validate` for
live feedback without touching the GPU.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..schemas import (
    EncoderVariant,
    GenerationRequest,
    Issue,
    MethodId,
    Mode,
    RefKind,
    RefRole,
    Severity,
    WeightVariant,
)
from .constants import (
    DIMENSION_MAX,
    DIMENSION_MIN,
    DIMENSION_STEP,
    MAX_REF_AUDIO_SECONDS,
    MAX_REF_AUDIOS,
    MAX_REF_IMAGES,
    MAX_REF_TOTAL,
    MAX_REF_VIDEO_SECONDS,
    MAX_REF_VIDEOS,
    MIN_REF_VIDEO_SECONDS,
    SAMPLERS,
    SCHEDULERS,
    TRAINED_FRAME_MAX,
    TRAINED_FRAME_MIN,
)
from .frames import is_native_length, is_valid_length, length_to_seconds, snap_dimension, snap_length
from .continuity import plan_continuity


@dataclass(frozen=True)
class ResolvedAsset:
    """The subset of stored asset metadata the rules care about."""

    id: str
    kind: RefKind
    comfy_name: str
    duration_seconds: float | None = None
    has_audio: bool | None = None
    width: int | None = None
    height: int | None = None
    frame_count: int | None = None
    fps: float | None = None


REFERENCE_MODES = {Mode.ref2va, Mode.performance}
FRAME_ROLES = {RefRole.first_frame, RefRole.last_frame}


def _err(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code=code, message=message, severity=Severity.error, field=field)


def _warn(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code=code, message=message, severity=Severity.warning, field=field)


def _info(code: str, message: str, field: str | None = None) -> Issue:
    return Issue(code=code, message=message, severity=Severity.info, field=field)


def normalize_request(request: GenerationRequest) -> tuple[GenerationRequest, list[Issue]]:
    """Snap dimensions and length onto the grids H3 accepts."""
    issues: list[Issue] = []
    updates: dict[str, object] = {}

    width = snap_dimension(request.width, step=DIMENSION_STEP, minimum=DIMENSION_MIN, maximum=DIMENSION_MAX)
    height = snap_dimension(request.height, step=DIMENSION_STEP, minimum=DIMENSION_MIN, maximum=DIMENSION_MAX)
    if width != request.width or height != request.height:
        issues.append(
            _warn(
                "dimensions_snapped",
                f"Frame size snapped to {width}x{height} (multiples of {DIMENSION_STEP}).",
                "width",
            )
        )
        updates["width"] = width
        updates["height"] = height

    if not is_valid_length(request.length):
        snapped = snap_length(request.length)
        issues.append(
            _warn(
                "length_snapped",
                f"Length snapped from {request.length} to {snapped} frames "
                f"({length_to_seconds(snapped):.2f}s) to sit on H3's 17k+5 grid.",
                "length",
            )
        )
        updates["length"] = snapped

    normalized = request.model_copy(update=updates) if updates else request

    continuity = plan_continuity(normalized)
    if continuity.split:
        issues.append(_info("continuity_auto_split", continuity.summary, "continuity"))
        if normalized.mode in {Mode.first_frame, Mode.first_last, Mode.performance}:
            issues.append(
                _err(
                    "continuity_mode_unsupported",
                    "Automatic raw-latent continuity supports Text and References; "
                    "it does not reinterpret frame-conditioned or Performance modes.",
                    "continuity",
                )
            )
        continuity_videos = [ref for ref in normalized.references if ref.kind is RefKind.video]
        continuity_ambience = [ref for ref in normalized.references if ref.role is RefRole.ambience]
        if len(continuity_videos) > 1 or continuity_ambience:
            issues.append(
                _err(
                    "continuity_reference_roles_unsupported",
                    "Automatic continuity currently accepts at most one reference video and maps audio only as "
                    "voice anchors; remove extra videos or ambience audio, or switch Auto continuity off.",
                    "references",
                )
            )
        if normalized.method in {MethodId.w4a8_lightx2v_trt, MethodId.w4a8_latent2x_refine3}:
            issues.append(
                _err(
                    "continuity_method_unsupported",
                    "Raw-latent continuity cannot use TRT conditioning or the two-pass latent refinement method.",
                    "method",
                )
            )
        if continuity.window_count > 4:
            issues.append(
                _err(
                    "continuity_too_many_windows",
                    f"This plan needs {continuity.window_count} windows. H3 continuity is currently capped at 4 "
                    "because texture and sharpening drift becomes visible beyond that; lower duration or resolution.",
                    "length",
                )
            )

    if not is_native_length(normalized.length):
        issues.append(
            _warn(
                "length_outside_trained_range",
                f"{normalized.length} frames ({length_to_seconds(normalized.length):.2f}s) is outside H3's "
                f"trained window of {TRAINED_FRAME_MIN}-{TRAINED_FRAME_MAX} frames "
                f"({length_to_seconds(TRAINED_FRAME_MIN):.2f}-{length_to_seconds(TRAINED_FRAME_MAX):.2f}s). "
                "Quality is untested there.",
                "length",
            )
        )

    return normalized, issues


def _validate_assets(
    request: GenerationRequest, assets: Mapping[str, ResolvedAsset]
) -> tuple[list[Issue], list[ResolvedAsset]]:
    issues: list[Issue] = []
    resolved: list[ResolvedAsset] = []
    seen: set[str] = set()

    for index, ref in enumerate(request.references):
        field = f"references[{index}]"
        asset = assets.get(ref.asset_id)
        if asset is None:
            issues.append(_err("unknown_asset", "Reference file is missing or was removed.", field))
            continue
        if asset.kind != ref.kind:
            issues.append(
                _err(
                    "asset_kind_mismatch",
                    f"Reference slot expects {ref.kind.value} but the file is {asset.kind.value}.",
                    field,
                )
            )
            continue
        if ref.asset_id in seen:
            issues.append(_warn("duplicate_asset", "The same file is used in more than one slot.", field))
        seen.add(ref.asset_id)
        resolved.append(asset)

    return issues, resolved


def _validate_counts(request: GenerationRequest) -> list[Issue]:
    issues: list[Issue] = []
    images = [r for r in request.references if r.kind is RefKind.image]
    videos = [r for r in request.references if r.kind is RefKind.video]
    audios = [r for r in request.references if r.kind is RefKind.audio]

    if request.mode in REFERENCE_MODES:
        if len(images) > MAX_REF_IMAGES:
            issues.append(
                _err("too_many_images", f"H3 accepts at most {MAX_REF_IMAGES} reference images.", "references")
            )
        if len(videos) > MAX_REF_VIDEOS:
            issues.append(
                _err("too_many_videos", f"H3 accepts at most {MAX_REF_VIDEOS} reference videos.", "references")
            )
        if len(audios) > MAX_REF_AUDIOS:
            issues.append(
                _err("too_many_audios", f"H3 accepts at most {MAX_REF_AUDIOS} reference audios.", "references")
            )
        if len(request.references) > MAX_REF_TOTAL:
            issues.append(
                _err(
                    "too_many_references",
                    f"H3 accepts at most {MAX_REF_TOTAL} references in total.",
                    "references",
                )
            )
        if not request.references:
            issues.append(_err("references_required", "This mode needs at least one reference.", "references"))
        if audios and not (images or videos):
            issues.append(
                _err(
                    "audio_needs_visual",
                    "Reference audio must travel with at least one reference image or video.",
                    "references",
                )
            )
        for index, ref in enumerate(request.references):
            if ref.role in FRAME_ROLES:
                issues.append(
                    _err(
                        "frame_role_unsupported",
                        "First/last frame slots only exist in the frame-driven modes.",
                        f"references[{index}]",
                    )
                )
    return issues


def _validate_mode_shape(request: GenerationRequest) -> list[Issue]:
    issues: list[Issue] = []
    images = [r for r in request.references if r.kind is RefKind.image]
    videos = [r for r in request.references if r.kind is RefKind.video]
    firsts = [r for r in request.references if r.role is RefRole.first_frame]
    lasts = [r for r in request.references if r.role is RefRole.last_frame]

    if request.mode is Mode.text:
        if request.references:
            issues.append(
                _err("text_mode_no_references", "Text mode renders from the prompt only.", "references")
            )
    elif request.mode is Mode.first_frame:
        if len(firsts) != 1:
            issues.append(_err("first_frame_required", "Add exactly one first frame image.", "references"))
        if lasts:
            issues.append(
                _err("last_frame_unsupported", "Switch to First + Last frame to use an end frame.", "references")
            )
        if len(request.references) != len(firsts):
            issues.append(
                _err(
                    "frame_mode_extra_references",
                    "First frame mode only takes the first frame image.",
                    "references",
                )
            )
    elif request.mode is Mode.first_last:
        if len(firsts) != 1 or len(lasts) != 1:
            issues.append(
                _err("first_last_required", "Add exactly one first frame and one last frame.", "references")
            )
        if len(request.references) != len(firsts) + len(lasts):
            issues.append(
                _err(
                    "frame_mode_extra_references",
                    "First + Last frame mode only takes those two images.",
                    "references",
                )
            )
    elif request.mode is Mode.performance:
        motions = [r for r in videos if r.role is RefRole.motion]
        identities = [r for r in images if r.role is RefRole.identity]
        if len(motions) != 1:
            issues.append(
                _err("motion_video_required", "Performance transfer needs exactly one motion video.", "references")
            )
        if not identities:
            issues.append(
                _err("identity_image_required", "Add the canonical identity image to lock the character.", "references")
            )

    return issues


def _validate_durations(request: GenerationRequest, assets: Mapping[str, ResolvedAsset]) -> list[Issue]:
    issues: list[Issue] = []
    video_total = 0.0
    audio_total = 0.0

    for index, ref in enumerate(request.references):
        asset = assets.get(ref.asset_id)
        if asset is None:
            continue
        field = f"references[{index}]"
        duration = asset.duration_seconds

        if ref.kind is RefKind.video:
            if duration is None:
                issues.append(
                    _warn("video_duration_unknown", "Could not read this clip's duration; H3 may reject it.", field)
                )
            else:
                video_total += duration
                if duration > MAX_REF_VIDEO_SECONDS + 1e-6:
                    issues.append(
                        _err(
                            "video_too_long",
                            f"Reference video is {duration:.2f}s. H3 accepts up to {MAX_REF_VIDEO_SECONDS:.0f}s.",
                            field,
                        )
                    )
                elif duration < MIN_REF_VIDEO_SECONDS - 1e-6:
                    issues.append(
                        _warn(
                            "video_very_short",
                            f"Reference video is {duration:.2f}s. H3 expects roughly "
                            f"{MIN_REF_VIDEO_SECONDS:.0f}-{MAX_REF_VIDEO_SECONDS:.0f}s.",
                            field,
                        )
                    )
            if ref.include_audio and asset.has_audio is False:
                issues.append(
                    _err("video_has_no_audio", "This clip has no soundtrack to pass through.", field)
                )

        elif ref.kind is RefKind.audio:
            if duration is None:
                issues.append(
                    _warn("audio_duration_unknown", "Could not read this audio's duration; H3 may reject it.", field)
                )
            else:
                audio_total += duration
                if duration > MAX_REF_AUDIO_SECONDS + 1e-6:
                    issues.append(
                        _err(
                            "audio_too_long",
                            f"Reference audio is {duration:.2f}s. H3 accepts up to {MAX_REF_AUDIO_SECONDS:.0f}s.",
                            field,
                        )
                    )

    if video_total > MAX_REF_VIDEO_SECONDS + 1e-6:
        issues.append(
            _err(
                "video_total_too_long",
                f"Combined reference video is {video_total:.2f}s. The limit is {MAX_REF_VIDEO_SECONDS:.0f}s.",
                "references",
            )
        )
    if audio_total > MAX_REF_AUDIO_SECONDS + 1e-6:
        issues.append(
            _err(
                "audio_total_too_long",
                f"Combined reference audio is {audio_total:.2f}s. The limit is {MAX_REF_AUDIO_SECONDS:.0f}s.",
                "references",
            )
        )

    return issues


def _validate_sampling(request: GenerationRequest, available_methods: set[str] | None) -> list[Issue]:
    import math
    issues: list[Issue] = []
    sigmas = request.custom_sigmas
    if sigmas is not None:
        if (len(sigmas) != request.steps + 1 or sigmas[-1] != 0 or sigmas[0] <= 0
                or any(not math.isfinite(value) or value < 0 or value > 1 for value in sigmas)
                or any(a <= b for a, b in zip(sigmas, sigmas[1:]))):
            issues.append(_err("custom_sigmas_invalid", "Custom sigmas must be finite, strictly descending in [0,1], end at zero, and contain steps + 1 values.", "custom_sigmas"))
        if request.continuity.auto_split or request.method is not MethodId.baseline:
            issues.append(_err("custom_sigmas_profile", "Custom sigmas require Quality/baseline and auto continuity off; no schedule is silently ignored.", "custom_sigmas"))
    if request.weights is WeightVariant.erosmax_beta5 and request.method in {
        MethodId.w4a8_lightx2v, MethodId.w4a8_lightx2v_trt,
        MethodId.w4a8_latent2x_refine3, MethodId.fast_h3_v2_8step, MethodId.taomate_3step,
    }:
        issues.append(_err("checkpoint_method_conflict", "This method overrides the checkpoint. Choose Quality for 10Eros-Max; no fallback is allowed.", "method"))
    if request.sampler_name not in SAMPLERS:
        issues.append(_err("unknown_sampler", f"Sampler '{request.sampler_name}' is not offered.", "sampler_name"))
    if request.scheduler not in SCHEDULERS:
        issues.append(_err("unknown_scheduler", f"Scheduler '{request.scheduler}' is not offered.", "scheduler"))

    if available_methods is not None and request.method.value not in available_methods:
        issues.append(
            _err(
                "method_unavailable",
                f"The {request.method.value} profile is not installed on this Comfy instance.",
                "method",
            )
        )

    if request.method is MethodId.fast_h3_v2_8step:
        if request.mode is not Mode.text:
            issues.append(_err("fasth3_v2_mode", "FastH3 V2 is distilled for text-to-video only.", "method"))
        if not (
            request.steps == 8
            and request.sampler_name == "res_multistep"
            and request.scheduler == "simple"
        ):
            issues.append(
                _err(
                    "fasth3_v2_recipe",
                    "FastH3 V2 requires 8 steps, res_multistep, and the simple scheduler.",
                    "method",
                )
            )
        if request.lora_chain:
            issues.append(_err("fasth3_v2_loras", "FastH3 V2 does not accept extra LoRAs in its official recipe.", "lora_chain"))
        issues.append(_warn("fasth3_v2_unvalidated", "FastH3 V2 is installed but not yet validated on this RTX 4090.", "method"))

    if request.method is MethodId.taomate_3step:
        if request.mode in REFERENCE_MODES:
            issues.append(_err("taomate_mode", "TaoMate uses the FL2VA checkpoint; choose Text, First frame, or First + last frame.", "method"))
        if not (
            request.steps == 3
            and request.sampler_name == "euler"
            and request.scheduler == "simple"
        ):
            issues.append(
                _err(
                    "taomate_recipe",
                    "TaoMate requires 3 steps, Euler, simple scheduler, CFG 1.0, and LoRA strength 1.0.",
                    "method",
                )
            )
        if request.lora_chain:
            issues.append(_err("taomate_loras", "TaoMate's draft recipe does not accept extra LoRAs.", "lora_chain"))
        issues.append(_warn("taomate_unvalidated", "TaoMate is installed but not yet validated on this RTX 4090.", "method"))

    if request.method in {MethodId.fast_h3_v2_8step, MethodId.taomate_3step}:
        if request.encoder is not EncoderVariant.standard:
            issues.append(
                _err(
                    "experimental_encoder_unavailable",
                    "The isolated experimental runtime only has the Standard prompt encoder installed.",
                    "encoder",
                )
            )

    if request.method is MethodId.easycache:
        if request.easycache.start_percent >= request.easycache.end_percent:
            issues.append(
                _err("easycache_window", "Cache start must come before cache end.", "easycache")
            )
    if request.method is MethodId.ref2va_vsa:
        if request.mode is not Mode.ref2va:
            issues.append(
                _err(
                    "ref2va_vsa_mode_unsupported",
                    "Ref2VA VSA is validated only for References mode.",
                    "method",
                )
            )
        if not (
            request.steps == 4
            and request.sampler_name == "euler"
            and request.scheduler == "simple"
        ):
            issues.append(
                _err(
                    "ref2va_vsa_recipe",
                    "Ref2VA VSA requires 4 steps, Euler, and the simple scheduler.",
                    "method",
                )
            )

        issues.append(
            _warn(
                "ref2va_vsa_experimental",
                "Ref2VA VSA is newly released. reference RTX 4090 workstation measured 94.299s warm at 1344x768 with 23,279 MiB peak VRAM.",
                "method",
            )
        )
    if request.method in {
        MethodId.w4a8_lightx2v,
        MethodId.w4a8_lightx2v_trt,
        MethodId.w4a8_latent2x_refine3,
    }:
        prefix = (
            "w4a8_latent2x_refine3" if request.method is MethodId.w4a8_latent2x_refine3 else request.method.value
        )
        label = (
            "Premium 2× Refine3"
            if request.method is MethodId.w4a8_latent2x_refine3
            else "Fast Final TRT 5s"
            if request.method is MethodId.w4a8_lightx2v_trt
            else "W4A8 + LightX2V4"
        )
        if request.mode in REFERENCE_MODES:
            issues.append(
                _err(
                    f"{prefix}_mode_unsupported",
                    f"{label} uses the FL2VA checkpoint. Choose Text, First frame, or First + last frame.",
                    "method",
                )
            )
        expected_sampler = "res_multistep" if request.method is MethodId.w4a8_lightx2v_trt else "er_sde"
        recipe_ok = (
            request.steps == 4
            and request.sampler_name == expected_sampler
            and request.scheduler == "simple"
        )
        if request.method is MethodId.w4a8_latent2x_refine3:
            recipe_ok = recipe_ok and request.length == 124
        if not recipe_ok:
            message = f"{label} requires 4 steps, {expected_sampler}, and the simple scheduler."
            if request.method is MethodId.w4a8_latent2x_refine3:
                message += " The verified premium window is 124 frames."
            issues.append(_err(f"{prefix}_recipe", message, "method"))
        if request.method is MethodId.w4a8_latent2x_refine3 and (
            request.width % 64 != 0
            or request.height % 64 != 0
            or request.width * request.height > 768 * 1024
        ):
            issues.append(
                _err(
                    "w4a8_latent2x_refine3_dimensions",
                    "Premium 2× Refine3 requires output dimensions divisible by 64 and no more than 768×1024 pixels total on the RTX 4090.",
                    "width",
                )
            )
    if request.method is MethodId.sol:
        if request.sol.start_percent >= request.sol.end_percent:
            issues.append(_err("sol_window", "Sol-Attn start must come before end.", "sol"))
        issues.append(
            _warn(
                "sol_experimental",
                "SolAttn is experimental: measured slower than Quality (82.0-84.0s vs 79.98s) at SSIM 0.778.",
                "method",
            )
        )
    if request.method is MethodId.sage:
        issues.append(
            _warn(
                "sage_experimental",
                "Sage attention is experimental. Measured 76.06s at SSIM 0.861 - use it for VRAM headroom.",
                "method",
            )
        )

    if request.weights is WeightVariant.gguf_q3km and request.mode not in REFERENCE_MODES:
        issues.append(
            _err(
                "gguf_mode_unsupported",
                "Only the Ref2VA checkpoint has a GGUF build. Use INT8 for the frame-driven modes.",
                "weights",
            )
        )

    if request.weights is WeightVariant.pinkcherry_v03 and request.mode in REFERENCE_MODES:
        issues.append(
            _err(
                "pinkcherry_mode_unsupported",
                "Pink Cherry v0.3 is an FL2VA checkpoint. Use it with Text, First frame, or First + last frame.",
                "weights",
            )
        )

    if request.weights is WeightVariant.erosmax_beta4 and request.mode not in REFERENCE_MODES:
        issues.append(
            _err(
                "erosmax_mode_unsupported",
                "H3 ErosMax Beta 4 is a custom Ref2VA checkpoint. Use it with References or Performance transfer.",
                "weights",
            )
        )

    return issues


def _validate_prompt_tags(request: GenerationRequest) -> list[Issue]:
    if request.mode not in REFERENCE_MODES:
        return []
    images = [r for r in request.references if r.kind is RefKind.image]
    videos = [r for r in request.references if r.kind is RefKind.video and r.role is not RefRole.aligned_guide]
    audios = [r for r in request.references if r.kind is RefKind.audio]
    missing: list[str] = []
    for index in range(len(images)):
        if f"<Picture {index + 1}>" not in request.prompt:
            missing.append(f"<Picture {index + 1}>")
    for index in range(len(videos)):
        if f"<Video {index + 1}>" not in request.prompt:
            missing.append(f"<Video {index + 1}>")
    for index in range(len(audios)):
        if f"<Audio {index + 1}>" not in request.prompt:
            missing.append(f"<Audio {index + 1}>")
    if not missing:
        return []
    return [
        _info(
            "prompt_missing_reference_tags",
            "Reference conditioning is strongest when the prompt names each slot. Missing: "
            + ", ".join(missing),
            "prompt",
        )
    ]


CHARACTER_SWAP_V11 = "minimax_h3_character_swap_v1.1_ref2va_fro.safetensors"


def validate_aligned_guides(request: GenerationRequest, assets: Mapping[str, ResolvedAsset], *, available: bool) -> list[Issue]:
    """Author-correct full-clip keyframe guides. Fail closed; never reinterpret as refs."""
    guides = [r for r in request.references if r.role is RefRole.aligned_guide]
    swap = any(l.name == CHARACTER_SWAP_V11 for l in request.lora_chain)
    issues: list[Issue] = []
    if swap:
        playground = request.preset_id == "character-swap-playground" and request.mode is Mode.ref2va and not guides
        if playground:
            issues.append(_warn("character_swap_playground", "Experimental template: the video is a normal reference, not an aligned guide. Motion, framing and identity transfer are not the approved HD recipe. Ordinary H3 reference limits still apply.", "references"))
        elif len(guides) != 1:
            issues.append(_err("character_swap_guide_required", "Character Swap v1.1 needs exactly one aligned guide video.", "references"))
        if not request.prompt.lstrip().startswith("body_swap:") or "<Picture 1>" not in request.prompt:
            issues.append(_err("character_swap_trigger", "Start with body_swap: and describe the character as <Picture 1>.", "prompt"))
        images = [r for r in request.references if r.kind is RefKind.image]
        if not images or images[0].role not in {RefRole.identity, RefRole.subject}:
            issues.append(_err("character_swap_identity", "Picture 1 must be the character identity/subject image.", "references"))
    if not guides:
        return issues
    if not available:
        issues.append(_err("guide_unavailable", "Live MiniMaxH3AddGuide and native video loaders are required.", "references"))
    if len(guides) != 1 or request.mode is not Mode.ref2va:
        issues.append(_err("guide_mode", "Aligned guides currently require References mode and exactly one guide.", "references"))
    if request.continuity.auto_split or plan_continuity(request).split:
        issues.append(_err("guide_continuity", "Disable auto continuity for an aligned full-clip guide.", "continuity"))
    if request.method not in {MethodId.baseline, MethodId.ref2va_vsa} or request.weights is not WeightVariant.int8:
        issues.append(_err("guide_recipe", "Aligned guides support the original INT8 Ref2VA checkpoint with Baseline or experimental Ref2VA VSA only.", "method"))
    for ref in guides:
        if ref.include_audio:
            issues.append(_err("guide_audio_unsupported", "Aligned guide audio is not enabled; disable Include audio. This does not copy the soundtrack.", "references"))
        asset = assets.get(ref.asset_id)
        if asset is None:
            continue  # normal asset validation reports this
        if any(v is None for v in (asset.width, asset.height, asset.frame_count, asset.fps)):
            issues.append(_err("guide_metadata_missing", "No se pudo certificar esta guía: requiere FPS constantes, sin rotación pendiente y conteo de frames decodificable. Una grabación con FPS variables puede disparar este error aunque ffprobe esté instalado. Prepara una guía CFR a 24 FPS o usa Character Swap · Experimentar para referencia normal.", "references"))
        elif (asset.width, asset.height, asset.frame_count) != (request.width, request.height, request.length) or abs(asset.fps - 24) > 0.001:
            issues.append(_err("guide_alignment", f"Guide must be exactly {request.width}x{request.height}, {request.length} frames at 24 FPS; got {asset.width}x{asset.height}, {asset.frame_count} frames at {asset.fps} FPS. Prepare an aligned clip first.", "references"))
    return issues


def _validate_ref_image_size(request: GenerationRequest) -> list[Issue]:
    if request.mode in REFERENCE_MODES and request.ref_image_size == "max":
        return [
            _warn(
                "ref_image_size_max_cost",
                "Max reference detail keeps every reference at 2048px short edge. Those tokens ride through "
                "every sampling step, so the render can take several times longer than the estimate.",
                "ref_image_size",
            )
        ]
    return []


def validate_request(
    request: GenerationRequest,
    assets: Mapping[str, ResolvedAsset],
    *,
    available_methods: set[str] | None = None,
    available_loras: Mapping[str, str] | None = None,
    aligned_guides_available: bool = False,
) -> tuple[GenerationRequest, list[Issue]]:
    """Return the normalized request plus every issue we can detect offline."""
    normalized, issues = normalize_request(request)

    asset_issues, _ = _validate_assets(normalized, assets)
    issues.extend(asset_issues)
    issues.extend(validate_aligned_guides(normalized, assets, available=aligned_guides_available))
    issues.extend(_validate_counts(normalized))
    issues.extend(_validate_mode_shape(normalized))
    issues.extend(_validate_durations(normalized, assets))
    issues.extend(_validate_sampling(normalized, available_methods))
    issues.extend(_validate_ref_image_size(normalized))
    issues.extend(_validate_prompt_tags(normalized))

    seen_loras: set[str] = set()
    checkpoint_family = "fl2va" if normalized.mode not in REFERENCE_MODES else "ref2va"
    for index, lora in enumerate(normalized.lora_chain):
        field = f"lora_chain[{index}]"
        if lora.name in seen_loras:
            issues.append(_err("duplicate_lora", f"LoRA '{lora.name}' is selected more than once.", field))
        seen_loras.add(lora.name)
        if available_loras is not None:
            compatibility = available_loras.get(lora.name)
            if compatibility is None:
                issues.append(_err("lora_unavailable", f"LoRA '{lora.name}' is not installed.", field))
            elif compatibility not in ("any", checkpoint_family):
                issues.append(
                    _err(
                        "lora_checkpoint_mismatch",
                        f"LoRA '{lora.name}' is for {compatibility.upper()}, not {checkpoint_family.upper()}.",
                        field,
                    )
                )

    return normalized, issues


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.severity is Severity.error for issue in issues)
