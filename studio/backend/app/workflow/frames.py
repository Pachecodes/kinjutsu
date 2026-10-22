"""Frame-grid math for H3.

H3 runs at 24 fps and only accepts frame counts on the 17k+5 grid. Everything
the UI shows in seconds is derived from these pure helpers so the backend and
the frontend agree on what "10 seconds" means.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    FPS,
    FRAME_BASE,
    FRAME_MAX,
    FRAME_MIN,
    FRAME_STEP,
    PREFERRED_LENGTHS,
    TRAINED_FRAME_MAX,
    TRAINED_FRAME_MIN,
)


def is_valid_length(frames: int) -> bool:
    """True when `frames` sits exactly on the 17k+5 grid and inside bounds."""
    if frames < FRAME_MIN or frames > FRAME_MAX:
        return False
    return (frames - FRAME_BASE) % FRAME_STEP == 0


def snap_length(frames: int) -> int:
    """Snap an arbitrary frame count onto the nearest valid 17k+5 value."""
    frames = max(FRAME_MIN, min(FRAME_MAX, int(frames)))
    k = round((frames - FRAME_BASE) / FRAME_STEP)
    snapped = FRAME_BASE + FRAME_STEP * k
    if snapped < FRAME_MIN:
        snapped = FRAME_MIN
    while snapped > FRAME_MAX:
        snapped -= FRAME_STEP
    return snapped


def seconds_to_length(seconds: float) -> int:
    """Convert a wall-clock duration to the closest valid frame count."""
    return snap_length(round(seconds * FPS))


def length_to_seconds(frames: int) -> float:
    return round(frames / FPS, 3)


def is_native_length(frames: int) -> bool:
    """Inside the ~124-362 frame window the model was actually trained on."""
    return TRAINED_FRAME_MIN <= frames <= TRAINED_FRAME_MAX


@dataclass(frozen=True)
class LengthOption:
    frames: int
    seconds: float
    label: str
    native: bool


def preferred_length_options() -> list[LengthOption]:
    return [
        LengthOption(
            frames=frames,
            seconds=length_to_seconds(frames),
            label=f"{length_to_seconds(frames):.2f}s",
            native=is_native_length(frames),
        )
        for frames in PREFERRED_LENGTHS
    ]


def snap_dimension(value: int, *, step: int, minimum: int, maximum: int) -> int:
    value = max(minimum, min(maximum, int(value)))
    snapped = int(round(value / step)) * step
    return max(minimum, min(maximum, snapped))
