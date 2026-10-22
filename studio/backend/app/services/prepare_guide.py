"""Owned-video → new, decoded/verified H3 guide. Never invokes Comfy or a GPU."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas import AssetOut, RefKind
from ..workflow.constants import DIMENSION_MAX, DIMENSION_MIN, DIMENSION_STEP, FRAME_MAX
from ..workflow.frames import is_valid_length
from .assets import AssetService, UploadRejected, probe_aligned_video

TIMEOUT_SECONDS = 180
# Fail fast instead of queueing arbitrary CPU work behind an active conversion.
_GATE = threading.BoundedSemaphore(1)
router = APIRouter()


class PrepareGuideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    width: int = Field(ge=DIMENSION_MIN, le=DIMENSION_MAX)
    height: int = Field(ge=DIMENSION_MIN, le=DIMENSION_MAX)
    length: int = Field(ge=5, le=FRAME_MAX)
    fit: Literal["pad", "crop"] = "pad"
    start_seconds: float = Field(default=0.0, ge=0, le=3600, allow_inf_nan=False)

    @model_validator(mode="after")
    def grid(self):
        if self.width % DIMENSION_STEP or self.height % DIMENSION_STEP or not is_valid_length(self.length):
            raise ValueError("Usa las dimensiones y fotogramas seleccionados en la cuadrícula H3 (32 px; 17k+5).")
        return self


class PrepareGuideResponse(BaseModel):
    asset: AssetOut
    source_asset_id: str
    verified: dict[str, int | float]
    fit: Literal["pad", "crop"]
    start_seconds: float


class GuideRejected(ValueError):
    def __init__(self, message: str, code: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


def _run(argv: list[str], *, timeout: int = TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(argv, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), shell=False, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise GuideRejected("Se agotó el tiempo de preparación. Reduce la duración o el tamaño e inténtalo otra vez.", "guide_timeout", 504) from exc
    except OSError as exc:
        raise GuideRejected("No se pudo ejecutar FFmpeg/ffprobe en este Studio.", "guide_tools_unavailable", 503) from exc
    if result.returncode:
        raise GuideRejected("No se pudo decodificar el vídeo. Prueba otro archivo de origen.", "guide_decode_failed")
    return result


def prepare_guide(assets: AssetService, asset_id: str, body: PrepareGuideRequest) -> PrepareGuideResponse:
    # IDs are opaque: NEVER derive a filename from one or accept a path.
    # Flatten persisted chains to the original owned ID, never the short derivative.
    original_id = asset_id
    seen = set()
    while True:
        if original_id in seen:
            raise GuideRejected('Procedencia de guía inválida. Selecciona el vídeo original desde la biblioteca.', 'guide_invalid_provenance')
        seen.add(original_id)
        provenance = assets.db.get_guide_provenance(original_id)
        if not provenance:
            break
        original_id = provenance['source_asset_id']
    record = assets.db.get_asset(original_id)
    if not record:
        raise GuideRejected("El vídeo de origen ya no existe. Vuelve a añadirlo.", "asset_not_found", 404)
    if record["kind"] != RefKind.video.value:
        raise GuideRejected("Preparar guía requiere un vídeo.", "guide_requires_video")
    source = assets.resolve_stored(record["stored_name"])
    if not source.is_file():
        raise GuideRejected("No se encuentra el archivo del vídeo de origen.", "asset_not_found", 404)
    probe = assets.ffprobe_path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg and probe:
        sibling = Path(probe).with_name("ffmpeg.exe" if Path(probe).suffix.lower() == ".exe" else "ffmpeg")
        if sibling.is_file():
            ffmpeg = str(sibling)
    if not ffmpeg or not probe:
        raise GuideRejected("Se necesitan FFmpeg y ffprobe para preparar una guía.", "guide_tools_unavailable", 503)
    if not _GATE.acquire(blocking=False):
        raise GuideRejected("Ya se está preparando una guía. Espera a que termine e inténtalo otra vez.", "guide_busy", 409)
    temporary = assets.uploads_dir / f"{uuid.uuid4().hex}.mp4"
    try:
        payload = json.loads(_run([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-threads", "2", "-select_streams", "v:0", "-show_streams", "-show_format", "-of", "json", str(source)], timeout=20).stdout)
        stream = payload.get("streams", [])[0]
        duration = float(stream.get("duration") or payload.get("format", {}).get("duration", 0))
        required = body.length / 24
        available = duration - body.start_seconds
        if not math.isfinite(duration) or available + 0.000001 < required:
            legacy_hint = ' Si esta es una guía antigua sin procedencia, selecciona el vídeo original desde Library (biblioteca).' if original_id == asset_id else ''
            raise GuideRejected(f"Vídeo demasiado corto: quedan {max(0, available):.3f} s; necesitas {required:.3f} s ({body.length} fotogramas). Reduce la duración de salida, adelanta el inicio o usa un vídeo más largo. No se congela ni se repite el final.{legacy_hint}", "guide_source_too_short")
        w, h = body.width, body.height
        # FFmpeg's default autorotation applies display matrices before filters.
        # First bake non-square SAR into pixels, then fit/crop with square pixels.
        geometry = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black" if body.fit == "pad" else f"scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}")
        filters = f"setpts=PTS-STARTPTS,trim=start={body.start_seconds}:duration={required},setpts=PTS-STARTPTS,scale=trunc(iw*sar/2)*2:ih,setsar=1,{geometry},fps=fps=24:round=near:eof_action=pass,trim=end_frame={body.length},setpts=N/(24*TB),setsar=1"
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-xerror", "-hwaccel", "none", "-protocol_whitelist", "file,pipe", "-threads", "2", "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", filters, "-filter_threads", "1", "-frames:v", str(body.length), "-fps_mode", "cfr", "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-movflags", "+faststart", "-fs", str(assets.max_bytes[RefKind.video]), "-n", str(temporary)])
        verified = probe_aligned_video(probe, temporary)
        expected = {"width": w, "height": h, "frame_count": body.length, "fps": 24.0}
        if verified != expected:
            raise GuideRejected("El vídeo no produjo todos los fotogramas solicitados. Reduce la duración de salida o usa un origen más largo; no se congela ni se repite el final.", "guide_verification_failed")
        # Full error-fatal CPU decode, not just trusting container metadata.
        _run([ffmpeg, "-v", "error", "-nostdin", "-xerror", "-hwaccel", "none", "-threads", "2", "-i", str(temporary), "-map", "0:v:0", "-f", "null", "-"])
        with temporary.open("rb") as handle:
            asset = assets.ingest(filename=f"guia-{w}x{h}-{body.length}f-{body.fit}.mp4", stream=handle)
        try:
            assets.db.insert_guide_provenance(asset.id, original_id, body.fit, body.start_seconds, duration)
        except Exception:
            assets.delete(asset.id)
            raise
        asset = assets.to_out(assets.db.get_asset(asset.id))
        return PrepareGuideResponse(asset=asset, source_asset_id=asset_id, verified=verified, fit=body.fit, start_seconds=body.start_seconds)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, (GuideRejected, UploadRejected)):
            raise
        raise GuideRejected("No se pudo leer la duración del vídeo de origen.", "guide_unreadable_source") from exc
    finally:
        temporary.unlink(missing_ok=True)
        _GATE.release()


@router.post("/assets/{asset_id}/prepare-guide", response_model=PrepareGuideResponse, status_code=201)
def prepare_guide_endpoint(asset_id: str, body: PrepareGuideRequest, request: Request):
    # Sync route runs off the event loop; uploads, rendering and status stay responsive.
    try:
        return prepare_guide(request.app.state.assets, asset_id, body)
    except GuideRejected as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
