"""Reference limits, duration bounds, frame grid and mode shape rules."""

from __future__ import annotations

import pytest

from app.schemas import EncoderVariant, GenerationRequest, MethodId, Mode, RefKind, ReferenceInput, RefRole, Severity, WeightVariant
from app.workflow.constants import MAX_REF_AUDIOS, MAX_REF_IMAGES, MAX_REF_TOTAL, MAX_REF_VIDEOS
from app.workflow.validation import ResolvedAsset, has_errors, normalize_request, validate_request


def image(index: int) -> ResolvedAsset:
    return ResolvedAsset(id=f"img{index}", kind=RefKind.image, comfy_name=f"img{index}.png")


def video(index: int, duration: float = 5.0, has_audio: bool = True) -> ResolvedAsset:
    return ResolvedAsset(
        id=f"vid{index}",
        kind=RefKind.video,
        comfy_name=f"vid{index}.mp4",
        duration_seconds=duration,
        has_audio=has_audio,
    )


def audio(index: int, duration: float = 4.0) -> ResolvedAsset:
    return ResolvedAsset(
        id=f"aud{index}", kind=RefKind.audio, comfy_name=f"aud{index}.wav", duration_seconds=duration
    )


ASSETS = {
    **{f"img{i}": image(i) for i in range(12)},
    **{f"vid{i}": video(i) for i in range(5)},
    **{f"aud{i}": audio(i) for i in range(5)},
}


def ref(asset_id: str, kind: RefKind, role: RefRole, include_audio: bool = False) -> ReferenceInput:
    return ReferenceInput(asset_id=asset_id, kind=kind, role=role, include_audio=include_audio)


def codes(issues, severity: Severity | None = None) -> set[str]:
    return {i.code for i in issues if severity is None or i.severity is severity}


def base(mode: Mode, **kwargs) -> GenerationRequest:
    return GenerationRequest(mode=mode, prompt=kwargs.pop("prompt", "a scene"), **kwargs)


# --- normalization --------------------------------------------------------
def test_off_grid_length_is_snapped_with_a_warning() -> None:
    normalized, issues = normalize_request(base(Mode.text, length=200))
    assert normalized.length == 192
    assert "length_snapped" in codes(issues, Severity.warning)


def test_dimensions_snap_to_multiples_of_32() -> None:
    normalized, issues = normalize_request(base(Mode.text, width=1000, height=570))
    assert (normalized.width, normalized.height) == (992, 576)
    assert "dimensions_snapped" in codes(issues, Severity.warning)


def test_length_outside_the_trained_window_warns_but_does_not_block() -> None:
    normalized, issues = normalize_request(base(Mode.text, length=39))
    assert normalized.length == 39
    assert "length_outside_trained_range" in codes(issues, Severity.warning)
    assert not has_errors(issues)


def test_native_length_is_silent() -> None:
    _, issues = normalize_request(base(Mode.text, length=243))
    assert issues == []


def test_auto_continuity_reports_the_planned_windows() -> None:
    _, issues = normalize_request(base(Mode.text, length=362, continuity={"auto_split": True}))
    notice = next(issue for issue in issues if issue.code == "continuity_auto_split")
    assert "3 windows" in notice.message
    assert notice.severity is Severity.info


def test_auto_continuity_blocks_modes_that_cannot_preserve_their_semantics() -> None:
    first_frame = base(
        Mode.first_frame,
        length=362,
        continuity={"auto_split": True},
        references=[ref("img0", RefKind.image, RefRole.first_frame)],
    )
    first_last = base(
        Mode.first_last,
        length=362,
        continuity={"auto_split": True},
        references=[
            ref("img0", RefKind.image, RefRole.first_frame),
            ref("img1", RefKind.image, RefRole.last_frame),
        ],
    )
    for request in (first_frame, first_last):
        _, issues = validate_request(request, ASSETS)
        assert "continuity_mode_unsupported" in codes(issues, Severity.error)


def test_auto_continuity_caps_the_chain_at_four_windows() -> None:
    _, issues = validate_request(
        base(Mode.text, length=600, continuity={"auto_split": True}),
        ASSETS,
    )
    assert "continuity_too_many_windows" in codes(issues, Severity.error)


def test_auto_continuity_refuses_reference_roles_it_cannot_preserve() -> None:
    request = base(
        Mode.ref2va,
        length=362,
        continuity={"auto_split": True},
        references=[
            ref("img0", RefKind.image, RefRole.identity),
            ref("vid0", RefKind.video, RefRole.scene_video),
            ref("vid1", RefKind.video, RefRole.motion),
            ref("aud0", RefKind.audio, RefRole.ambience),
        ],
    )
    _, issues = validate_request(request, ASSETS)
    assert "continuity_reference_roles_unsupported" in codes(issues, Severity.error)


# --- reference limits -----------------------------------------------------
def test_nine_images_are_allowed_and_ten_are_not() -> None:
    nine = [ref(f"img{i}", RefKind.image, RefRole.identity) for i in range(MAX_REF_IMAGES)]
    _, issues = validate_request(base(Mode.ref2va, references=nine), ASSETS)
    assert "too_many_images" not in codes(issues)

    ten = [ref(f"img{i}", RefKind.image, RefRole.identity) for i in range(MAX_REF_IMAGES + 1)]
    _, issues = validate_request(base(Mode.ref2va, references=ten), ASSETS)
    assert "too_many_images" in codes(issues, Severity.error)


def test_video_and_audio_slot_caps() -> None:
    videos = [ref(f"vid{i}", RefKind.video, RefRole.scene_video) for i in range(MAX_REF_VIDEOS + 1)]
    _, issues = validate_request(base(Mode.ref2va, references=videos), ASSETS)
    assert "too_many_videos" in codes(issues, Severity.error)

    audios = [
        ref("img0", RefKind.image, RefRole.identity),
        *[ref(f"aud{i}", RefKind.audio, RefRole.voice) for i in range(MAX_REF_AUDIOS + 1)],
    ]
    _, issues = validate_request(base(Mode.ref2va, references=audios), ASSETS)
    assert "too_many_audios" in codes(issues, Severity.error)


def test_combined_reference_cap_is_twelve() -> None:
    references = [
        *[ref(f"img{i}", RefKind.image, RefRole.identity) for i in range(9)],
        *[ref(f"vid{i}", RefKind.video, RefRole.scene_video) for i in range(3)],
        ref("aud0", RefKind.audio, RefRole.voice),
    ]
    assert len(references) == MAX_REF_TOTAL + 1
    _, issues = validate_request(base(Mode.ref2va, references=references), ASSETS)
    assert "too_many_references" in codes(issues, Severity.error)


def test_reference_audio_needs_a_visual_companion() -> None:
    only_audio = [ref("aud0", RefKind.audio, RefRole.voice)]
    _, issues = validate_request(base(Mode.ref2va, references=only_audio), ASSETS)
    assert "audio_needs_visual" in codes(issues, Severity.error)

    with_image = [ref("img0", RefKind.image, RefRole.identity), ref("aud0", RefKind.audio, RefRole.voice)]
    _, issues = validate_request(base(Mode.ref2va, references=with_image), ASSETS)
    assert "audio_needs_visual" not in codes(issues)


# --- durations ------------------------------------------------------------
def test_single_reference_video_over_fifteen_seconds_is_rejected() -> None:
    assets = {**ASSETS, "vid0": video(0, duration=16.0)}
    references = [ref("img0", RefKind.image, RefRole.identity), ref("vid0", RefKind.video, RefRole.motion)]
    _, issues = validate_request(base(Mode.performance, references=references), assets)
    assert "video_too_long" in codes(issues, Severity.error)


def test_combined_reference_video_over_fifteen_seconds_is_rejected() -> None:
    assets = {**ASSETS, "vid0": video(0, 8.0), "vid1": video(1, 8.0)}
    references = [
        ref("img0", RefKind.image, RefRole.identity),
        ref("vid0", RefKind.video, RefRole.scene_video),
        ref("vid1", RefKind.video, RefRole.scene_video),
    ]
    _, issues = validate_request(base(Mode.ref2va, references=references), assets)
    assert "video_total_too_long" in codes(issues, Severity.error)


def test_combined_reference_audio_over_fifteen_seconds_is_rejected() -> None:
    assets = {**ASSETS, "aud0": audio(0, 8.0), "aud1": audio(1, 8.0)}
    references = [
        ref("img0", RefKind.image, RefRole.identity),
        ref("aud0", RefKind.audio, RefRole.voice),
        ref("aud1", RefKind.audio, RefRole.ambience),
    ]
    _, issues = validate_request(base(Mode.ref2va, references=references), assets)
    assert "audio_total_too_long" in codes(issues, Severity.error)


def test_short_reference_video_warns_only() -> None:
    assets = {**ASSETS, "vid0": video(0, duration=1.0)}
    references = [ref("img0", RefKind.image, RefRole.identity), ref("vid0", RefKind.video, RefRole.motion)]
    _, issues = validate_request(base(Mode.performance, references=references), assets)
    assert "video_very_short" in codes(issues, Severity.warning)
    assert not has_errors(issues)


def test_passing_through_a_silent_clips_audio_is_an_error() -> None:
    assets = {**ASSETS, "vid0": video(0, 5.0, has_audio=False)}
    references = [
        ref("img0", RefKind.image, RefRole.identity),
        ref("vid0", RefKind.video, RefRole.motion, include_audio=True),
    ]
    _, issues = validate_request(base(Mode.performance, references=references), assets)
    assert "video_has_no_audio" in codes(issues, Severity.error)


def test_unknown_duration_warns_instead_of_blocking() -> None:
    assets = {**ASSETS, "vid0": ResolvedAsset(id="vid0", kind=RefKind.video, comfy_name="v.mp4")}
    references = [ref("img0", RefKind.image, RefRole.identity), ref("vid0", RefKind.video, RefRole.motion)]
    _, issues = validate_request(base(Mode.performance, references=references), assets)
    assert "video_duration_unknown" in codes(issues, Severity.warning)


# --- mode shapes ----------------------------------------------------------
def test_text_mode_refuses_references() -> None:
    references = [ref("img0", RefKind.image, RefRole.first_frame)]
    _, issues = validate_request(base(Mode.text, references=references), ASSETS)
    assert "text_mode_no_references" in codes(issues, Severity.error)


def test_first_frame_mode_needs_exactly_one_frame() -> None:
    _, issues = validate_request(base(Mode.first_frame), ASSETS)
    assert "first_frame_required" in codes(issues, Severity.error)

    ok = [ref("img0", RefKind.image, RefRole.first_frame)]
    _, issues = validate_request(base(Mode.first_frame, references=ok), ASSETS)
    assert not has_errors(issues)

    with_last = [*ok, ref("img1", RefKind.image, RefRole.last_frame)]
    _, issues = validate_request(base(Mode.first_frame, references=with_last), ASSETS)
    assert "last_frame_unsupported" in codes(issues, Severity.error)


def test_first_last_mode_needs_both_frames() -> None:
    only_first = [ref("img0", RefKind.image, RefRole.first_frame)]
    _, issues = validate_request(base(Mode.first_last, references=only_first), ASSETS)
    assert "first_last_required" in codes(issues, Severity.error)

    both = [*only_first, ref("img1", RefKind.image, RefRole.last_frame)]
    _, issues = validate_request(base(Mode.first_last, references=both), ASSETS)
    assert not has_errors(issues)


def test_reference_modes_reject_frame_roles() -> None:
    references = [ref("img0", RefKind.image, RefRole.first_frame)]
    _, issues = validate_request(base(Mode.ref2va, references=references), ASSETS)
    assert "frame_role_unsupported" in codes(issues, Severity.error)


def test_reference_mode_requires_at_least_one_reference() -> None:
    _, issues = validate_request(base(Mode.ref2va), ASSETS)
    assert "references_required" in codes(issues, Severity.error)


def test_performance_transfer_needs_one_identity_and_one_motion_clip() -> None:
    _, issues = validate_request(
        base(Mode.performance, references=[ref("img0", RefKind.image, RefRole.identity)]), ASSETS
    )
    assert "motion_video_required" in codes(issues, Severity.error)

    _, issues = validate_request(
        base(Mode.performance, references=[ref("vid0", RefKind.video, RefRole.motion)]), ASSETS
    )
    assert "identity_image_required" in codes(issues, Severity.error)

    good = [ref("img0", RefKind.image, RefRole.identity), ref("vid0", RefKind.video, RefRole.motion)]
    _, issues = validate_request(base(Mode.performance, references=good), ASSETS)
    assert not has_errors(issues)


def test_two_motion_clips_are_refused() -> None:
    references = [
        ref("img0", RefKind.image, RefRole.identity),
        ref("vid0", RefKind.video, RefRole.motion),
        ref("vid1", RefKind.video, RefRole.motion),
    ]
    _, issues = validate_request(base(Mode.performance, references=references), ASSETS)
    assert "motion_video_required" in codes(issues, Severity.error)


# --- assets ---------------------------------------------------------------
def test_missing_asset_is_an_error() -> None:
    references = [ref("nope", RefKind.image, RefRole.identity)]
    _, issues = validate_request(base(Mode.ref2va, references=references), ASSETS)
    assert "unknown_asset" in codes(issues, Severity.error)


def test_kind_mismatch_is_an_error() -> None:
    references = [ref("img0", RefKind.video, RefRole.motion)]
    _, issues = validate_request(base(Mode.performance, references=references), ASSETS)
    assert "asset_kind_mismatch" in codes(issues, Severity.error)


def test_duplicate_slots_warn() -> None:
    references = [
        ref("img0", RefKind.image, RefRole.identity),
        ref("img0", RefKind.image, RefRole.style),
    ]
    _, issues = validate_request(base(Mode.ref2va, references=references), ASSETS)
    assert "duplicate_asset" in codes(issues, Severity.warning)


def test_role_must_match_kind_at_the_schema_level() -> None:
    with pytest.raises(ValueError, match="not valid for a"):
        ReferenceInput(asset_id="x", kind=RefKind.image, role=RefRole.motion)


# --- method / weights -----------------------------------------------------
def test_unavailable_method_is_blocked() -> None:
    request = base(Mode.text, method=MethodId.sage)
    _, issues = validate_request(request, ASSETS, available_methods={"baseline", "easycache"})
    assert "method_unavailable" in codes(issues, Severity.error)


def test_ref2va_vsa_accepts_creator_selected_length_encoder_weights_loras_and_continuity() -> None:
    valid = base(
        Mode.ref2va,
        method=MethodId.ref2va_vsa,
        length=270,
        steps=4,
        sampler_name="euler",
        scheduler="simple",
        weights=WeightVariant.gguf_q3km,
        encoder=EncoderVariant.heretic,
        prompt="<Picture 1> smiles.",
        references=[ref("img0", RefKind.image, RefRole.identity)],
        lora_chain=[{"name": "MysticXXX_MMH3-V3.safetensors", "strength": 0.7}],
        continuity={"auto_split": True, "window": "124", "pin_frames": "22"},
    )
    _, valid_issues = validate_request(valid, ASSETS)
    assert not codes(valid_issues, Severity.error)

    wrong_mode = base(
        Mode.text,
        method=MethodId.ref2va_vsa,
        length=124,
        steps=4,
        sampler_name="euler",
        scheduler="simple",
    )
    _, mode_issues = validate_request(wrong_mode, ASSETS)
    assert "ref2va_vsa_mode_unsupported" in codes(mode_issues, Severity.error)


def test_ref2va_vsa_still_requires_the_four_step_sampling_recipe() -> None:
    request = base(
        Mode.ref2va,
        method=MethodId.ref2va_vsa,
        length=175,
        steps=6,
        sampler_name="er_sde",
        scheduler="beta",
        prompt="<Picture 1> smiles.",
        references=[ref("img0", RefKind.image, RefRole.identity)],
        lora_chain=[{"name": "MysticXXX_MMH3-V3.safetensors", "strength": 0.7}],
    )
    _, issues = validate_request(request, ASSETS)
    assert "ref2va_vsa_recipe" in codes(issues, Severity.error)
    assert "ref2va_vsa_loras_unsupported" not in codes(issues, Severity.error)


def test_premium_latent2x_refine3_requires_verified_recipe_and_2x_grid() -> None:
    request = base(
        Mode.first_frame,
        method=MethodId.w4a8_latent2x_refine3,
        width=608,
        height=352,
        steps=20,
        sampler_name="res_multistep",
        scheduler="beta",
    )
    _, issues = validate_request(request, ASSETS)
    assert "w4a8_latent2x_refine3_recipe" in codes(issues, Severity.error)
    assert "w4a8_latent2x_refine3_dimensions" in codes(issues, Severity.error)


def test_experimental_methods_always_carry_their_measured_caveat() -> None:
    _, issues = validate_request(base(Mode.text, method=MethodId.sol), ASSETS)
    sol = next(i for i in issues if i.code == "sol_experimental")
    assert "0.778" in sol.message
    _, issues = validate_request(base(Mode.text, method=MethodId.sage), ASSETS)
    sage = next(i for i in issues if i.code == "sage_experimental")
    assert "76.06" in sage.message


def test_easycache_window_must_be_ordered() -> None:
    request = base(Mode.text, method=MethodId.easycache)
    request = request.model_copy(
        update={"easycache": request.easycache.model_copy(update={"start_percent": 0.9, "end_percent": 0.2})}
    )
    _, issues = validate_request(request, ASSETS)
    assert "easycache_window" in codes(issues, Severity.error)


def test_gguf_is_only_offered_for_reference_modes() -> None:
    _, issues = validate_request(base(Mode.text, weights=WeightVariant.gguf_q3km), ASSETS)
    assert "gguf_mode_unsupported" in codes(issues, Severity.error)

    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, issues = validate_request(
        base(Mode.ref2va, weights=WeightVariant.gguf_q3km, references=references, prompt="<Picture 1>"),
        ASSETS,
    )
    assert "gguf_mode_unsupported" not in codes(issues)


def test_pink_cherry_is_only_offered_for_frame_modes() -> None:
    _, frame_issues = validate_request(
        base(Mode.text, weights=WeightVariant.pinkcherry_v03), ASSETS
    )
    assert "pinkcherry_mode_unsupported" not in codes(frame_issues)

    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, reference_issues = validate_request(
        base(
            Mode.ref2va,
            weights=WeightVariant.pinkcherry_v03,
            references=references,
            prompt="<Picture 1>",
        ),
        ASSETS,
    )
    assert "pinkcherry_mode_unsupported" in codes(reference_issues, Severity.error)


def test_erosmax_beta5_is_offered_for_frame_and_reference_modes() -> None:
    _, frame_issues = validate_request(
        base(Mode.text, weights=WeightVariant.erosmax_beta5), ASSETS
    )
    assert "erosmax_mode_unsupported" not in codes(frame_issues)

    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, reference_issues = validate_request(
        base(
            Mode.ref2va,
            weights=WeightVariant.erosmax_beta5,
            references=references,
            prompt="<Picture 1>",
        ),
        ASSETS,
    )
    assert "erosmax_mode_unsupported" not in codes(reference_issues)


def test_unknown_sampler_or_scheduler_is_refused() -> None:
    _, issues = validate_request(base(Mode.text, sampler_name="not_a_sampler"), ASSETS)
    assert "unknown_sampler" in codes(issues, Severity.error)
    _, issues = validate_request(base(Mode.text, scheduler="not_a_scheduler"), ASSETS)
    assert "unknown_scheduler" in codes(issues, Severity.error)


# --- prompt tags / ref_image_size ----------------------------------------
def test_missing_reference_tags_are_informational_only() -> None:
    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, issues = validate_request(base(Mode.ref2va, references=references, prompt="no tags"), ASSETS)
    tags = next(i for i in issues if i.code == "prompt_missing_reference_tags")
    assert tags.severity is Severity.info
    assert "<Picture 1>" in tags.message
    assert not has_errors(issues)


def test_tagged_prompt_is_silent() -> None:
    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, issues = validate_request(
        base(Mode.ref2va, references=references, prompt="<Picture 1> waves"), ASSETS
    )
    assert "prompt_missing_reference_tags" not in codes(issues)


def test_max_reference_detail_warns_about_cost() -> None:
    references = [ref("img0", RefKind.image, RefRole.identity)]
    _, issues = validate_request(
        base(Mode.ref2va, references=references, ref_image_size="max", prompt="<Picture 1>"), ASSETS
    )
    assert "ref_image_size_max_cost" in codes(issues, Severity.warning)
