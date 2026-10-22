"""Upload security: traversal, extension/MIME agreement, size caps, argv probing."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.db import Database
from app.schemas import RefKind
from app.services.assets import (
    AssetService,
    UploadRejected,
    probe_media,
    safe_display_name,
    sniff_mime,
)

WAV = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture
def service(tmp_path: Path) -> AssetService:
    return AssetService(
        Database(tmp_path / "studio.sqlite3"),
        uploads_dir=tmp_path / "uploads",
        max_bytes={RefKind.image: 1024, RefKind.video: 4096, RefKind.audio: 2048},
        ffprobe_path=None,
    )


# --- path traversal -------------------------------------------------------
@pytest.mark.parametrize(
    "hostile",
    [
        "../../../../etc/passwd",
        "..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "subdir/file.png",
        "....//....//etc/passwd",
        "%2e%2e%2fetc%2fpasswd",
        "file.png\x00.txt",
        "",
        ".",
        "..",
    ],
)
def test_resolve_stored_refuses_anything_but_a_generated_name(service: AssetService, hostile: str) -> None:
    with pytest.raises(UploadRejected):
        service.resolve_stored(hostile)


def test_resolve_stored_accepts_a_generated_name(service: AssetService) -> None:
    name = "0123456789abcdef0123456789abcdef.png"
    resolved = service.resolve_stored(name)
    assert resolved.parent == service.uploads_dir
    assert resolved.name == name


def test_a_symlink_out_of_the_uploads_dir_is_not_followed(service: AssetService, tmp_path: Path) -> None:
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"secret")
    link_name = "ffffffffffffffffffffffffffffffff.png"
    (service.uploads_dir / link_name).symlink_to(outside)
    with pytest.raises(UploadRejected, match="outside the uploads directory"):
        service.resolve_stored(link_name)


def test_uploaded_filenames_never_reach_the_filesystem(service: AssetService, png_bytes: bytes) -> None:
    asset = service.ingest(filename="../../evil.png", stream=io.BytesIO(png_bytes))
    assert asset.stored_name != "evil.png"
    assert asset.stored_name.endswith(".png")
    assert len(asset.stored_name) == 36  # 32 hex + '.png'
    assert asset.original_name == "evil.png"
    assert (service.uploads_dir / asset.stored_name).is_file()
    assert sorted(p.name for p in service.uploads_dir.iterdir()) == [asset.stored_name]


def test_display_name_is_stripped_of_path_and_control_characters() -> None:
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("C:\\Users\\me\\shot.png") == "C_Users_me_shot.png"
    assert safe_display_name("") == "upload"
    assert len(safe_display_name("x" * 500)) == 120


# --- extension + MIME agreement ------------------------------------------
@pytest.mark.parametrize("name", ["evil.exe", "payload.svg", "notes.txt", "archive.zip", "noextension"])
def test_disallowed_extensions_are_rejected(service: AssetService, name: str) -> None:
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename=name, stream=io.BytesIO(b"whatever"))
    assert excinfo.value.code == "extension_not_allowed"


def test_extension_and_magic_bytes_must_agree(service: AssetService) -> None:
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename="actually-a-script.png", stream=io.BytesIO(b"#!/bin/sh\nrm -rf /\n"))
    assert excinfo.value.code == "mime_mismatch"


def test_renaming_a_wav_to_png_is_rejected(service: AssetService) -> None:
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename="sneaky.png", stream=io.BytesIO(WAV))
    assert excinfo.value.code == "mime_mismatch"


def test_nothing_is_left_on_disk_when_an_upload_is_rejected(service: AssetService) -> None:
    with pytest.raises(UploadRejected):
        service.ingest(filename="sneaky.png", stream=io.BytesIO(WAV))
    assert list(service.uploads_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff\xe0", "image/jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBP", "image/webp"),
        (WAV, "audio/wav"),
        (MP4, "video/mp4"),
        (b"\x1a\x45\xdf\xa3", "video/webm"),
        (b"fLaC", "audio/flac"),
        (b"OggS", "audio/ogg"),
        (b"ID3\x04", "audio/mpeg"),
        (b"nonsense", None),
    ],
)
def test_magic_byte_sniffing(payload: bytes, expected: str | None) -> None:
    assert sniff_mime(payload) == expected


# --- size limits ----------------------------------------------------------
def test_oversized_uploads_are_rejected_while_streaming(service: AssetService, png_bytes: bytes) -> None:
    oversized = png_bytes + b"\x00" * 4096
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename="big.png", stream=io.BytesIO(oversized))
    assert excinfo.value.code == "file_too_large"
    assert list(service.uploads_dir.iterdir()) == []


def test_limits_are_per_media_kind(service: AssetService) -> None:
    # 2 KB of "video" fits the 4 KB video cap but would blow the 1 KB image cap.
    asset = service.ingest(filename="clip.mp4", stream=io.BytesIO(MP4 + b"\x00" * 2000))
    assert asset.kind is RefKind.video
    assert asset.size_bytes > 1024


def test_empty_uploads_are_rejected(service: AssetService) -> None:
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename="empty.png", stream=io.BytesIO(b""))
    assert excinfo.value.code == "empty_file"


# --- ffprobe --------------------------------------------------------------
def test_probe_is_a_noop_without_ffprobe(tmp_path: Path) -> None:
    result = probe_media(None, tmp_path / "missing.mp4")
    assert result.duration_seconds is None


def test_probe_never_uses_a_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = b'{"format": {"duration": "5.5"}, "streams": [{"codec_type": "audio"}]}'

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr("app.services.assets.subprocess.run", fake_run)
    result = probe_media("/usr/bin/ffprobe", tmp_path / "a b; rm -rf /.wav")

    assert isinstance(seen["argv"], list), "ffprobe must be invoked with an argv array"
    assert seen["kwargs"]["shell"] is False
    assert str(tmp_path / "a b; rm -rf /.wav") in seen["argv"]
    assert result.duration_seconds == 5.5
    assert result.has_audio is True


def test_probe_survives_a_broken_ffprobe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(argv, **kwargs):
        raise OSError("ffprobe exploded")

    monkeypatch.setattr("app.services.assets.subprocess.run", boom)
    assert probe_media("/usr/bin/ffprobe", tmp_path / "x.wav").duration_seconds is None


def test_media_without_a_readable_duration_is_rejected(
    monkeypatch: pytest.MonkeyPatch, service: AssetService
) -> None:
    service.ffprobe_path = "/usr/bin/ffprobe"
    monkeypatch.setattr("app.services.assets.probe_media", lambda *_a, **_k: __import__(
        "app.services.assets", fromlist=["ProbeResult"]
    ).ProbeResult())
    with pytest.raises(UploadRejected) as excinfo:
        service.ingest(filename="clip.mp4", stream=io.BytesIO(MP4))
    assert excinfo.value.code == "unreadable_media"
    assert list(service.uploads_dir.iterdir()) == []


# --- deletion -------------------------------------------------------------
def test_deleting_an_asset_removes_the_file(service: AssetService, png_bytes: bytes) -> None:
    asset = service.ingest(filename="shot.png", stream=io.BytesIO(png_bytes))
    path = service.uploads_dir / asset.stored_name
    assert path.is_file()
    assert service.delete(asset.id) is True
    assert not path.exists()
    assert service.delete(asset.id) is False
