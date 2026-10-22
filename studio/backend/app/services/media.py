"""Upload sniffing, sanitising and probing.

Rules enforced here:
  * extension allow-list AND magic-byte signature must agree
  * per-kind size caps
  * stored filenames are always generated UUIDs, never creator input
  * ffprobe is invoked with an argv array, never a shell string
  * resolved paths must stay inside the configured data directory
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..schemas import RefKind

ALLOWED_EXTENSIONS: dict[RefKind, dict[str, str]] = {
    RefKind.image: {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    },
    RefKind.video: {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    },
    RefKind.audio: {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    },
}

EXTENSION_TO_KIND: dict[str, RefKind] = {
    extension: kind for kind, table in ALLOWED_EXTENSIONS.items() for extension in table
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class UploadRejected(ValueError):
    """The upload failed validation. The message is safe to show a creator."""

    def __init__(self, message: str, *, code: str = "upload_rejected") -> None:
        super().__init__(message)
        self.code = code


def sanitize_display_name(name: str, *, fallback: str = "upload") -> str:
    """Make a creator-supplied filename safe to store as *display text*.

    The bytes are still written under a generated UUID name; this is only what
    we show in the gallery.
    """
    name = unicodedata.normalize("NFKD", name or "")
    name = name.replace("\\", "/").split("/")[-1]
    name = _SAFE_NAME.sub("_", name).strip("._")
    name = name[:120]
    return name or fallback


def sniff_kind(data: bytes) -> RefKind | None:
    """Identify a container from its magic bytes."""
    if len(data) < 12:
        return None
    head = data[:12]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return RefKind.image
    if head.startswith(b"\xff\xd8\xff"):
        return RefKind.image
    if head.startswith(b"RIFF"):
        if data[8:12] == b"WEBP":
            return RefKind.image
        if data[8:12] == b"WAVE":
            return RefKind.audio
        return None
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        # Matroska/WebM. Could be either; treat as video (audio-only mkv is rare
        # and ffprobe will still tell the truth about the streams).
        return RefKind.video
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand[:3] in (b"M4A", b"M4B"):
            return RefKind.audio
        return RefKind.video
    if head.startswith(b"fLaC"):
        return RefKind.audio
    if head.startswith(b"OggS"):
        return RefKind.audio
    if head.startswith(b"ID3") or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return RefKind.audio
    return None


@dataclass(frozen=True)
class DetectedUpload:
    kind: RefKind
    extension: str
    mime: str


def detect_upload(filename: str, data: bytes) -> DetectedUpload:
    extension = Path(sanitize_display_name(filename)).suffix.lower()
    if extension not in EXTENSION_TO_KIND:
        raise UploadRejected(
            f"'{extension or 'file'}' is not a supported reference format.",
            code="extension_not_allowed",
        )
    declared_kind = EXTENSION_TO_KIND[extension]
    sniffed = sniff_kind(data)
    if sniffed is None:
        raise UploadRejected("The file contents do not look like a media file.", code="signature_unrecognised")
    if sniffed is not declared_kind:
        # .m4a is an MP4 container: allow the audio/video pairing that ffprobe resolves.
        mp4_family = {RefKind.audio, RefKind.video}
        if not (extension in (".m4a", ".mp4", ".mov") and sniffed in mp4_family):
            raise UploadRejected(
                f"File extension says {declared_kind.value} but the contents are {sniffed.value}.",
                code="signature_mismatch",
            )
    return DetectedUpload(
        kind=declared_kind,
        extension=extension,
        mime=ALLOWED_EXTENSIONS[declared_kind][extension],
    )


def enforce_size(kind: RefKind, size_bytes: int, *, limits_mb: dict[RefKind, int]) -> None:
    limit_mb = limits_mb[kind]
    if size_bytes <= 0:
        raise UploadRejected("The uploaded file is empty.", code="empty_file")
    if size_bytes > limit_mb * 1024 * 1024:
        raise UploadRejected(
            f"{kind.value.title()} references are limited to {limit_mb} MB.", code="file_too_large"
        )


def safe_child(root: Path, name: str) -> Path:
    """Resolve `name` under `root`, refusing anything that escapes it.

    `name` must be a bare filename produced by this application. Traversal
    attempts, absolute paths and symlink escapes all raise.
    """
    if not name or name in (".", ".."):
        raise UploadRejected("Invalid file reference.", code="invalid_path")
    candidate = Path(name)
    if candidate.is_absolute() or candidate.drive or candidate.anchor:
        raise UploadRejected("Invalid file reference.", code="invalid_path")
    if len(candidate.parts) != 1 or ".." in candidate.parts:
        raise UploadRejected("Invalid file reference.", code="invalid_path")
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise UploadRejected("Invalid file reference.", code="invalid_path")
    return resolved


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool | None = None


def probe_media(path: Path, *, ffprobe: str | None, timeout: float = 20.0) -> ProbeResult:
    """Read duration/resolution/audio presence with ffprobe (argv array, no shell)."""
    if not ffprobe:
        return ProbeResult()
    argv = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, trusted binary
            argv,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ProbeResult()
    if completed.returncode != 0:
        return ProbeResult()
    try:
        payload = json.loads(completed.stdout or b"{}")
    except ValueError:
        return ProbeResult()

    streams = payload.get("streams") or []
    fmt = payload.get("format") or {}
    duration: float | None = None
    raw_duration = fmt.get("duration")
    if raw_duration is not None:
        try:
            duration = round(float(raw_duration), 3)
        except (TypeError, ValueError):
            duration = None

    width = height = None
    has_audio = False
    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and width is None:
            width = stream.get("width")
            height = stream.get("height")
            if duration is None and stream.get("duration"):
                try:
                    duration = round(float(stream["duration"]), 3)
                except (TypeError, ValueError):
                    pass
        elif codec_type == "audio":
            has_audio = True

    return ProbeResult(
        duration_seconds=duration,
        width=int(width) if isinstance(width, int) else None,
        height=int(height) if isinstance(height, int) else None,
        has_audio=has_audio,
    )
