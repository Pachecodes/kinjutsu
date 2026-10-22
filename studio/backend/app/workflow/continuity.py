"""Pure planning for safe H3 long-take windows on reference RTX 4090 workstation.

The equations mirror ComfyUI-H3-Multishot's H3ExtendTake planner, but use the
native INT8/W4A8 activation rate instead of its GGUF fallback.  This lets the
API explain the plan before ComfyUI loads a model.
"""

from __future__ import annotations

from ..schemas import ContinuityPlan, GenerationRequest, WeightVariant

WINDOWS = (243, 226, 209, 192, 175, 158, 141, 124, 107, 90)
CARD_GB = 24.0
KEEPOUT_GB = 1.0
WDDM_FRACTION = 0.09
RESIDENT_TARGET = 0.60
NATIVE_WEIGHTS_GB = 15.0
GGUF_WEIGHTS_GB = 8.0
NATIVE_RATE_GB_PER_MCELL = 4.3
GGUF_RATE_GB_PER_MCELL = 2.4


def _cells(width: int, height: int, frames: int) -> float:
    temporal = 0.2961 * frames + 0.35
    return 24.0 * temporal * (height / 16.0) * (width / 16.0)


def _auto_window(request: GenerationRequest) -> int:
    gguf = request.weights is WeightVariant.gguf_q3km
    weights = GGUF_WEIGHTS_GB if gguf else NATIVE_WEIGHTS_GB
    rate = GGUF_RATE_GB_PER_MCELL if gguf else NATIVE_RATE_GB_PER_MCELL
    margins = KEEPOUT_GB + CARD_GB * WDDM_FRACTION
    budget = CARD_GB - margins - RESIDENT_TARGET * weights
    for candidate in WINDOWS:
        pool = rate * _cells(request.width, request.height, candidate) / 1_000_000.0
        if pool <= budget:
            # The 24 GB field-tested comfort window is 141 frames at a
            # 1024x576-class canvas. Do not spend the whole theoretical pool:
            # WDDM and decode need headroom during a long chained take.
            if not gguf and request.width * request.height >= 1024 * 576:
                return min(candidate, 141)
            return candidate
    return WINDOWS[-1]


def plan_continuity(request: GenerationRequest) -> ContinuityPlan:
    options = request.continuity
    if not options.auto_split:
        return ContinuityPlan(
            split=False,
            strategy="single",
            window_frames=request.length,
            window_count=1,
            pin_frames=0,
            sampled_frames=request.length,
            rendered_frames=request.length,
            delivered_frames=request.length,
            trim_frames=0,
            summary=f"Single H3 window: {request.length} frames ({request.length / 24:.2f}s).",
        )

    window = _auto_window(request) if options.window == "auto" else int(options.window)
    pin = int(options.pin_frames)
    if request.length <= window:
        return ContinuityPlan(
            split=False,
            strategy="single",
            window_frames=window,
            window_count=1,
            pin_frames=pin,
            sampled_frames=request.length,
            rendered_frames=request.length,
            delivered_frames=request.length,
            trim_frames=0,
            summary=f"Safe as one window: {request.length} frames; auto limit {window}.",
        )

    stride = max(1, window - pin)
    count = 1
    rendered = window
    while rendered < request.length:
        count += 1
        rendered = window + (count - 1) * stride
    trim = rendered - request.length
    return ContinuityPlan(
        split=True,
        strategy="context_pin",
        window_frames=window,
        window_count=count,
        pin_frames=pin,
        sampled_frames=count * window,
        rendered_frames=rendered,
        delivered_frames=request.length,
        trim_frames=trim,
        summary=(
            f"Auto continuity: {count} windows × {window} frames, {pin}-frame raw-latent pins; "
            f"trim {trim} tail frames to deliver exactly {request.length} frames "
            f"({request.length / 24:.2f}s)."
        ),
    )


__all__ = ["WINDOWS", "plan_continuity"]