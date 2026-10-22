"""H3's 17k+5 frame grid and the 24fps duration math."""

from __future__ import annotations

import pytest

from app.workflow.constants import PREFERRED_LENGTHS, TRAINED_FRAME_MAX, TRAINED_FRAME_MIN
from app.workflow.frames import (
    is_native_length,
    is_valid_length,
    length_to_seconds,
    preferred_length_options,
    seconds_to_length,
    snap_dimension,
    snap_length,
)


@pytest.mark.parametrize("frames", PREFERRED_LENGTHS)
def test_preferred_lengths_are_on_the_grid(frames: int) -> None:
    assert is_valid_length(frames)
    assert (frames - 5) % 17 == 0


@pytest.mark.parametrize("frames", [0, 4, 6, 100, 123, 125, 200, 363])
def test_off_grid_lengths_are_rejected(frames: int) -> None:
    assert not is_valid_length(frames)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(1, 5), (5, 5), (120, 124), (124, 124), (130, 124), (133, 141), (240, 243), (360, 362), (10_000, 3592)],
)
def test_snap_length_lands_on_the_grid(raw: int, expected: int) -> None:
    snapped = snap_length(raw)
    assert snapped == expected
    assert is_valid_length(snapped)


def test_snap_length_is_idempotent() -> None:
    for raw in range(5, 600, 7):
        once = snap_length(raw)
        assert snap_length(once) == once


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5.0, 124), (5.17, 124), (7.3, 175), (8.0, 192), (10.0, 243), (15.0, 362)],
)
def test_seconds_map_to_the_documented_lengths(seconds: float, expected: int) -> None:
    assert seconds_to_length(seconds) == expected


def test_length_to_seconds_uses_24fps() -> None:
    assert length_to_seconds(124) == pytest.approx(5.167, abs=0.001)
    assert length_to_seconds(243) == pytest.approx(10.125, abs=0.001)
    assert length_to_seconds(362) == pytest.approx(15.083, abs=0.001)


def test_trained_window_is_reported_honestly() -> None:
    assert is_native_length(TRAINED_FRAME_MIN)
    assert is_native_length(TRAINED_FRAME_MAX)
    assert not is_native_length(TRAINED_FRAME_MIN - 17)
    assert not is_native_length(TRAINED_FRAME_MAX + 17)


def test_preferred_options_are_all_native() -> None:
    options = preferred_length_options()
    assert [option.frames for option in options] == list(PREFERRED_LENGTHS)
    assert all(option.native for option in options)


@pytest.mark.parametrize(
    ("raw", "expected"), [(0, 32), (33, 32), (48, 64), (1000, 992), (1024, 1024), (99_999, 1536)]
)
def test_dimensions_snap_to_multiples_of_32(raw: int, expected: int) -> None:
    assert snap_dimension(raw, step=32, minimum=32, maximum=1536) == expected
