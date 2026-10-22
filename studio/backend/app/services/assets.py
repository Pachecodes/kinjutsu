"""Secure upload handling.

Rules enforced here, all of them non-negotiable:

* clients never supply a filesystem path - only opaque asset ids;
* stored names are generated UUIDs plus a whitelisted extension;
* the declared extension, the sniffed magic bytes and the resulting media kind
  must all agree before anything is written to the assets table;
* size caps are enforced *while streaming*, not after;
* duration/stream probing shells out to ffprobe through an argv array, never
  through a shell string.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from ..db import Database, utcnow
from ..schemas import AssetOut, RefKind

CHUNK = 1024 * 1024
PROBE_TIMEOUT_SECONDS = 20

#: extension -> (kind, canonical mime)
ALLOWED_EXTENSIONS: dict[str, tuple[RefKind, str]] = {
    ".png": (RefKind.image, "image/png"),
    ".jpg": (RefKind.image, "image/jpeg"),
    ".jpeg": (RefKind.image, "image/jpeg"),
    ".webp": (RefKind.image, "image/webp"),
    ".mp4": (RefKind.video, "video/mp4"),
    ".mov": (RefKind.video, "video/quicktime"),
    ".webm": (RefKind.video, "video/webm"),
    ".mkv": (RefKind.video, "video/x-matroska"),
    ".wav": (RefKind.audio, "audio/wav"),
    ".mp3": (RefKind.audio, "audio/mpeg"),
    ".flac": (RefKind.audio, "audio/flac"),
    ".m4a": (RefKind.audio, "audio/mp4"),
    ".ogg": (RefKind.audio, "audio/ogg"),
}

_UUID_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{2,5}$")
_UNSAFE_DISPLAY = re.compile(r"[^A-Za-z0-9 ._-]+")


class UploadRejected(ValueError):
    """The upload failed a security or contract check."""

    def __init__(self, message: str, *, code: str = "upload_rejected") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProbeResult:
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool | None = None


def safe_display_name(name: str) -> str:
    """A human label for the UI. Never used to build a path."""
    # Strip POSIX traversal consistently, then neutralize Windows separators
    # instead of letting host-specific Path semantics change the display label.
    leaf = PurePosixPath(name or "").name
    cleaned = _UNSAFE_DISPLAY.sub("_", leaf).strip(" ._")
    return (cleaned or "upload")[:120]


def extension_of(name: str) -> str:
    return Path(name or "").suffix.lower()


def sniff_mime(head: bytes) -> str | None:
    """Identify a file from its magic bytes. Returns None when unrecognised."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B ", b"M4P "):
            return "audio/mp4"
        if brand == b"qt  ":
            return "video/quicktime"
        return "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"ID3"):
        return "audio/mpeg"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    return None


#: Magic-byte families that may legitimately back a given extension. Matroska
#: and WebM share a container, and MP4/MOV/M4A all report an ftyp box.
_MIME_FAMILIES: dict[str, set[str]] = {
    "image/png": {"image/png"},
    "image/jpeg": {"image/jpeg"},
    "image/webp": {"image/webp"},
    "video/mp4": {"video/mp4", "video/quicktime", "audio/mp4"},
    "video/quicktime": {"video/mp4", "video/quicktime"},
    "video/webm": {"video/webm"},
    "video/x-matroska": {"video/webm"},
    "audio/wav": {"audio/wav"},
    "audio/mpeg": {"audio/mpeg"},
    "audio/flac": {"audio/flac"},
    "audio/mp4": {"video/mp4", "audio/mp4"},
    "audio/ogg": {"audio/ogg"},
}


def mime_matches_extension(declared_mime: str, sniffed: str | None) -> bool:
    if sniffed is None:
        return False
    return sniffed in _MIME_FAMILIES.get(declared_mime, {declared_mime})


def probe_media(ffprobe: str | None, path: Path) -> ProbeResult:
    """Run ffprobe over an argv array. Never a shell string, never user paths."""
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
        completed = subprocess.run(  # noqa: S603 - argv array, shell=False
            argv,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=PROBE_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ProbeResult()
    if completed.returncode != 0:
        return ProbeResult()
    try:
        payload: dict[str, Any] = json.loads(completed.stdout or b"{}")
    except ValueError:
        return ProbeResult()

    streams = payload.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    duration: float | None = None
    raw_duration = (payload.get("format") or {}).get("duration")
    try:
        if raw_duration is not None:
            duration = round(float(raw_duration), 3)
    except (TypeError, ValueError):
        duration = None
    if duration is None:
        for stream in streams:
            try:
                duration = round(float(stream["duration"]), 3)
                break
            except (KeyError, TypeError, ValueError):
                continue

    width = height = None
    if video_streams:
        try:
            width = int(video_streams[0]["width"])
            height = int(video_streams[0]["height"])
        except (KeyError, TypeError, ValueError):
            width = height = None

    # A still image reports a video stream with no meaningful duration.
    is_still = bool(video_streams) and video_streams[0].get("codec_name") in {
        "png",
        "mjpeg",
        "webp",
        "bmp",
    }
    if is_still:
        duration = None

    return ProbeResult(
        duration_seconds=duration,
        width=width,
        height=height,
        has_audio=bool(audio_streams) if streams else None,
    )


def probe_aligned_video(ffprobe: str | None, path: Path) -> dict[str, Any]:
    """Decode-count only the owned guide; unknown/VFR/rotated media fails closed."""
    from fractions import Fraction
    if not ffprobe:
        return {}
    try:
        result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_streams', '-of', 'json', str(path)], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=PROBE_TIMEOUT_SECONDS, shell=False, check=False)
        if result.returncode:
            return {}
        stream = json.loads(result.stdout)['streams'][0]
        fps = float(Fraction(stream['avg_frame_rate']))
        nominal = float(Fraction(stream['r_frame_rate']))
        if abs(fps - nominal) > 0.001 or any(int(s.get('rotation', 0)) % 360 for s in stream.get('side_data_list', [])):
            return {}
        return {'width': int(stream['width']), 'height': int(stream['height']), 'frame_count': int(stream['nb_read_frames']), 'fps': fps}
    except (OSError, subprocess.SubprocessError, KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return {}


class AssetService:
    def __init__(
        self,
        db: Database,
        *,
        uploads_dir: Path,
        max_bytes: dict[RefKind, int],
        ffprobe_path: str | None,
    ) -> None:
        self.db = db
        self.uploads_dir = uploads_dir.resolve()
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.ffprobe_path = ffprobe_path

    # -- path safety -------------------------------------------------------
    def resolve_stored(self, stored_name: str) -> Path:
        """Resolve a stored name inside the uploads dir, or refuse.

        `stored_name` always comes from our own database, but this is the last
        line of defence against a traversal ever reaching the filesystem.
        """
        if not _UUID_NAME.match(stored_name or ""):
            raise UploadRejected("Refusing to resolve a non-generated file name.", code="unsafe_name")
        candidate = (self.uploads_dir / stored_name).resolve()
        if candidate.parent != self.uploads_dir:
            raise UploadRejected("Refusing to resolve a path outside the uploads directory.", code="path_escape")
        return candidate

    # -- ingest ------------------------------------------------------------
    def _store_stream(self, source: BinaryIO, extension: str, limit: int) -> tuple[Path, int, bytes]:
        stored_name = f"{uuid.uuid4().hex}{extension}"
        destination = self.uploads_dir / stored_name
        total = 0
        head = b""
        try:
            with destination.open("wb") as handle:
                while True:
                    chunk = source.read(CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise UploadRejected(
                            f"File is larger than the {limit // (1024 * 1024)} MB limit for this media type.",
                            code="file_too_large",
                        )
                    if len(head) < 32:
                        head += chunk[: 32 - len(head)]
                    handle.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        if total == 0:
            destination.unlink(missing_ok=True)
            raise UploadRejected("The uploaded file is empty.", code="empty_file")
        return destination, total, head

    def ingest(self, *, filename: str, stream: BinaryIO) -> AssetOut:
        extension = extension_of(filename)
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise UploadRejected(
                f"'{safe_display_name(filename)}' is not a supported file type. Allowed: {allowed}.",
                code="extension_not_allowed",
            )
        kind, mime = ALLOWED_EXTENSIONS[extension]
        limit = self.max_bytes[kind]

        destination, size, head = self._store_stream(stream, extension, limit)
        try:
            sniffed = sniff_mime(head)
            if not mime_matches_extension(mime, sniffed):
                raise UploadRejected(
                    f"File contents do not look like {mime}. Refusing the upload.",
                    code="mime_mismatch",
                )
            probe = probe_media(self.ffprobe_path, destination)
            if kind in (RefKind.video, RefKind.audio) and probe.duration_seconds is None and self.ffprobe_path:
                raise UploadRejected(
                    "Could not read a duration from this media file.", code="unreadable_media"
                )
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        record = {
            "id": uuid.uuid4().hex,
            "kind": kind.value,
            "original_name": safe_display_name(filename),
            "stored_name": destination.name,
            "mime": mime,
            "size_bytes": size,
            "width": probe.width,
            "height": probe.height,
            "duration_seconds": probe.duration_seconds,
            "has_audio": None if probe.has_audio is None else int(probe.has_audio),
            "comfy_name": None,
            "created_at": utcnow(),
        }
        self.db.insert_asset(record)
        return self.to_out(record)

    async def ingest_async(self, *, filename: str, stream: BinaryIO) -> AssetOut:
        return await asyncio.to_thread(self.ingest, filename=filename, stream=stream)

    # -- reads -------------------------------------------------------------
    def to_out(self, record: dict[str, Any]) -> AssetOut:
        has_audio = record.get("has_audio")
        return AssetOut(
            guide_provenance=self.db.get_guide_provenance(record['id']),
            id=record["id"],
            kind=RefKind(record["kind"]),
            original_name=record["original_name"],
            stored_name=record["stored_name"],
            mime=record["mime"],
            size_bytes=record["size_bytes"],
            width=record.get("width"),
            height=record.get("height"),
            duration_seconds=record.get("duration_seconds"),
            has_audio=None if has_audio is None else bool(has_audio),
            created_at=record["created_at"],
            url=f"/api/assets/{record['id']}/file",
        )

    def list_assets(self, limit: int = 200) -> list[AssetOut]:
        return [self.to_out(record) for record in self.db.list_assets(limit)]

    def delete(self, asset_id: str) -> bool:
        record = self.db.delete_asset(asset_id)
        if record is None:
            return False
        try:
            self.resolve_stored(record["stored_name"]).unlink(missing_ok=True)
        except UploadRejected:  # pragma: no cover - stored names are generated
            pass
        return True
