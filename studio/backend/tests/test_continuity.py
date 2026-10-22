from __future__ import annotations

from app.schemas import ContinuityOptions, GenerationRequest, Mode, WeightVariant
from app.workflow.continuity import plan_continuity


def request(**patch) -> GenerationRequest:
    values = {
        "mode": Mode.text,
        "prompt": "A continuous tracking shot.",
        "width": 1024,
        "height": 576,
        "length": 124,
        "continuity": ContinuityOptions(auto_split=True),
    }
    values.update(patch)
    return GenerationRequest(**values)


def test_auto_keeps_a_safe_take_in_one_window() -> None:
    plan = plan_continuity(request(length=124))
    assert plan.split is False
    assert plan.window_frames == 141
    assert plan.window_count == 1
    assert plan.delivered_frames == 124


def test_auto_splits_a_risky_15_second_take_for_the_4090() -> None:
    plan = plan_continuity(request(length=362))
    assert plan.split is True
    assert plan.window_frames == 141
    assert plan.window_count == 3
    assert plan.sampled_frames == 423
    assert plan.rendered_frames == 379
    assert plan.delivered_frames == 362


def test_auto_uses_larger_windows_for_a_small_canvas() -> None:
    plan = plan_continuity(request(width=608, height=352, length=362))
    assert plan.split is True
    assert plan.window_frames == 243
    assert plan.window_count == 2


def test_gguf_uses_its_lower_activation_rate() -> None:
    plan = plan_continuity(request(weights=WeightVariant.gguf_q3km, length=362, mode=Mode.ref2va))
    assert plan.window_frames >= 192


def test_manual_single_window_disables_continuity_planning() -> None:
    plan = plan_continuity(request(length=362, continuity=ContinuityOptions(auto_split=False)))
    assert plan.split is False
    assert plan.window_count == 1
    assert plan.window_frames == 362


def test_exact_duration_is_preserved_after_overlap_trim() -> None:
    plan = plan_continuity(request(length=481))
    assert plan.rendered_frames >= 481
    assert plan.delivered_frames == 481
    assert plan.trim_frames == plan.rendered_frames - 481
