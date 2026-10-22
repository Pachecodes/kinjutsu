"""Runtime estimates scaled from the measured reference RTX 4090 workstation benchmark table.

These are estimates and are always labelled as such in the UI. The basis is a
single measured configuration (5.17s / 608x352 / 16 steps on an RTX 4090):

    baseline  79.98s
    easycache 57.53s   SSIM 0.914 vs baseline
    sage      76.06s   SSIM 0.861
    sol       82.99s   SSIM 0.778 (measured 82.01-83.98s)
"""

from __future__ import annotations

from .constants import BENCHMARK_BASIS, METHOD_PROFILES, TRAINED_FRAME_MIN

_BASIS_PIXELS = BENCHMARK_BASIS["width"] * BENCHMARK_BASIS["height"]
_BASIS_FRAMES = TRAINED_FRAME_MIN  # 124 frames == 5.17s at 24fps
_BASIS_STEPS = BENCHMARK_BASIS["steps"]

BASIS_TEXT = (
    f"Scaled from a measured reference RTX 4090 workstation run: {BENCHMARK_BASIS['seconds']}s clip, "
    f"{BENCHMARK_BASIS['width']}x{BENCHMARK_BASIS['height']}, {BENCHMARK_BASIS['steps']} steps."
)


def estimate_seconds(*, method: str, width: int, height: int, length: int, steps: int) -> float | None:
    """Linear scale of the measured profile time by frames x pixels x steps."""
    profile = METHOD_PROFILES.get(method) or METHOD_PROFILES["baseline"]
    measured = profile["measured_seconds"]
    if measured is None:
        return None
    base = float(measured)
    basis_steps = int(profile.get("basis_steps", _BASIS_STEPS))
    basis_width = int(profile.get("basis_width", BENCHMARK_BASIS["width"]))
    basis_height = int(profile.get("basis_height", BENCHMARK_BASIS["height"]))
    basis_frames = int(profile.get("basis_frames", _BASIS_FRAMES))
    basis_pixels = basis_width * basis_height
    scale = (length / basis_frames) * ((width * height) / basis_pixels) * (steps / basis_steps)
    return round(base * scale, 1)


def estimate_basis(method: str) -> str:
    profile = METHOD_PROFILES.get(method) or METHOD_PROFILES["baseline"]
    if profile["measured_seconds"] is None:
        return f"{profile['label']} is installed but has not been benchmarked on reference RTX 4090 workstation."
    basis_steps = int(profile.get("basis_steps", _BASIS_STEPS))
    basis_width = int(profile.get("basis_width", BENCHMARK_BASIS["width"]))
    basis_height = int(profile.get("basis_height", BENCHMARK_BASIS["height"]))
    basis_frames = int(profile.get("basis_frames", _BASIS_FRAMES))
    basis_seconds = basis_frames / 24
    basis = (
        f"Scaled from a measured reference RTX 4090 workstation run: {basis_seconds:.2f}s clip, "
        f"{basis_width}x{basis_height}, {basis_steps} base steps."
    )
    return f"{basis} {profile['label']} measured at {profile['measured_seconds']}s there."
