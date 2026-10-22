"""HTTP surface for the Studio.

Clients address everything by opaque id. No endpoint accepts a filesystem path,
and the two file-serving routes resolve strictly inside their own directory.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .capabilities import CapabilityService
from .presets import PRESETS
from .schemas import (
    AssetOut,
    CapabilityResponse,
    CreateJobResponse,
    DirectorRequest,
    DirectorResponse,
    GenerationRequest,
    HealthResponse,
    JobEventListResponse,
    JobEventOut,
    JobListResponse,
    JobOut,
    PromptChatRequest,
    PromptChatResponse,
    ValidationResponse,
)
from .services.assets import AssetService, UploadRejected
from .services.director import DirectorError
from .services.jobs import JobConflict, JobNotFound, JobRejected, JobService, workflow_json
from .workflow import constants as C
from .workflow.estimate import estimate_basis, estimate_seconds
from .workflow.continuity import plan_continuity
from .workflow.validation import has_errors

from .services.prepare_guide import router as prepare_guide_router

router = APIRouter(prefix="/api")
router.include_router(prepare_guide_router)
from .services.model_manager import router as model_manager_router
router.include_router(model_manager_router)
from .services.offline_prompts import router as offline_prompts_router
router.include_router(offline_prompts_router)
from .services.workstation import router as workstation_router
router.include_router(workstation_router)


def _presets_with_availability(capabilities: CapabilityResponse) -> list[dict[str, Any]]:
    methods = {method.id: method for method in capabilities.methods}
    result: list[dict[str, Any]] = []
    for preset in PRESETS:
        method_id = str(preset.get("patch", {}).get("method", "baseline"))
        method = methods.get(method_id)
        reason = None if method and method.available else (
            method.unavailable_reason if method else f"Method {method_id} is not registered."
        )
        if preset["id"].startswith("10eros-"):
            if not capabilities.comfy_online:
                reason = "H3 runtime offline; checkpoint availability is unknown."
            elif not capabilities.weights.get("erosmax_beta5"):
                reason = "10Eros-Max Beta 5 checkpoint is missing from the live loader."
            elif preset["patch"]["sampler_name"] not in capabilities.samplers:
                reason = "Required sampler is missing from the live runtime."
            elif preset["patch"].get("custom_sigmas") and not capabilities.manual_sigmas:
                reason = "ManualSigmas node is missing from the live runtime."
        if preset["id"] in {"character-swap-v11", "character-swap-hd-turbo8", "character-swap-playground"}:
            if preset["id"] != "character-swap-playground" and not capabilities.aligned_guides:
                reason = "Live aligned-guide support is unavailable (MiniMaxH3AddGuide/native video loaders)."
            elif any(lora["name"] not in {l.name for l in capabilities.loras} for lora in preset["patch"]["lora_chain"]):
                reason = "An exact Character Swap recipe LoRA is missing from the live loader."
            elif not next((m.available for m in capabilities.modes if m.id.value == "ref2va"), False):
                reason = "Native Ref2VA mode is unavailable."
        mode_id = preset.get('suggests_mode')
        if reason is None and mode_id and not next((m.available for m in capabilities.modes if m.id.value == mode_id), False):
            reason = 'El modo requiere pesos/nodos que no estan instalados.'
        weight = preset.get('patch', {}).get('weights', 'int8')
        if reason is None and not capabilities.weights.get(weight, False):
            reason = 'Faltan los pesos requeridos por esta receta.'
        encoder = preset.get('patch', {}).get('encoder', 'standard')
        if reason is None and not capabilities.encoders.get(encoder, False):
            reason = 'Falta el encoder requerido por esta receta.'
        if reason is None and any(lora['name'] not in {l.name for l in capabilities.loras} for lora in preset.get('patch', {}).get('lora_chain', [])):
            reason = 'Falta una LoRA exacta de esta receta.'
        result.append(
            {
                **preset,
                "available": reason is None,
                "unavailable_reason": reason,
            }
        )
    return result


def get_jobs(request: Request) -> JobService:
    return request.app.state.jobs


def get_assets(request: Request) -> AssetService:
    return request.app.state.assets


def get_capabilities(request: Request) -> CapabilityService:
    return request.app.state.capabilities


JobsDep = Annotated[JobService, Depends(get_jobs)]
AssetsDep = Annotated[AssetService, Depends(get_assets)]
CapabilitiesDep = Annotated[CapabilityService, Depends(get_capabilities)]


# --- health / config ------------------------------------------------------
@router.get("/preview")
async def latest_preview(jobs: JobsDep) -> Response:
    preview = jobs.latest_preview()
    if preview is None:
        return Response(status_code=204)
    return JSONResponse(content=preview, headers={"Cache-Control": "no-store"})


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, jobs: JobsDep, capabilities: CapabilitiesDep) -> HealthResponse:
    caps = await capabilities.get()
    return HealthResponse(
        status="ok" if caps.comfy_online else "degraded",
        version=__version__,
        comfy_online=caps.comfy_online,
        comfy_url=caps.comfy_url,
        active_jobs=jobs.active_count,
        data_dir=str(request.app.state.settings.data_dir),
    )


@router.get("/capabilities", response_model=CapabilityResponse)
async def get_capability_report(
    capabilities: CapabilitiesDep,
    refresh: bool = Query(default=False, description="Bypass the capability cache"),
) -> CapabilityResponse:
    return await capabilities.get(force=refresh)


@router.get("/config")
async def get_config(request: Request, capabilities: CapabilitiesDep) -> dict[str, Any]:
    settings = request.app.state.settings
    caps = await capabilities.get()
    return {
        "version": __version__,
        "capabilities": caps.model_dump(mode="json"),
        "presets": _presets_with_availability(caps),
        "defaults": {
            "width": 1024,
            "height": 576,
            "length": 124,
            "steps": C.DEFAULT_STEPS,
            "sampler_name": C.DEFAULT_SAMPLER,
            "scheduler": C.DEFAULT_SCHEDULER,
            "method": "baseline",
            "ref_image_size": "match",
        },
        "upload_limits": {
            "image_mb": settings.max_image_mb,
            "video_mb": settings.max_video_mb,
            "audio_mb": settings.max_audio_mb,
        },
        "estimate_basis": estimate_basis("baseline"),
        "method_profiles": {
            key: {
                "measured_seconds": profile["measured_seconds"],
                "measured_ssim": profile["measured_ssim"],
                "caveat": profile["caveat"],
            }
            for key, profile in C.METHOD_PROFILES.items()
        },
    }


@router.get("/presets")
async def list_presets(capabilities: CapabilitiesDep) -> dict[str, Any]:
    caps = await capabilities.get()
    return {"presets": _presets_with_availability(caps)}


@router.post("/director/enhance", response_model=DirectorResponse)
async def enhance_prompt(request: Request, jobs: JobsDep, body: DirectorRequest) -> DirectorResponse:
    async with request.app.state.gpu_gate:
        if jobs.active_count:
            raise HTTPException(status_code=409, detail="AI Director waits until the active H3 render finishes.")
        if not request.app.state.settings.director_enabled:
            raise HTTPException(status_code=503, detail="AI Director is disabled on this Studio.")
        try:
            return await request.app.state.director.enhance(body)
        except DirectorError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/director/chat", response_model=PromptChatResponse)
async def prompt_chat(request: Request, jobs: JobsDep, body: PromptChatRequest) -> PromptChatResponse:
    async with request.app.state.gpu_gate:
        if jobs.active_count:
            raise HTTPException(status_code=409, detail="Prompt Chat waits until the active H3 render finishes.")
        if not request.app.state.settings.director_enabled:
            raise HTTPException(status_code=503, detail="Local Prompt Chat is disabled on this Studio.")
        try:
            return await request.app.state.director.chat(body)
        except DirectorError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


# --- validation -----------------------------------------------------------
@router.post("/validate", response_model=ValidationResponse)
async def validate(jobs: JobsDep, request_body: GenerationRequest) -> ValidationResponse:
    normalized, issues = await jobs.validate(request_body)
    continuity_plan = plan_continuity(normalized)
    return ValidationResponse(
        ok=not has_errors(issues),
        issues=issues,
        normalized=normalized,
        estimate_seconds=estimate_seconds(
            method=normalized.method.value,
            width=normalized.width,
            height=normalized.height,
            length=continuity_plan.sampled_frames,
            steps=normalized.steps,
        ),
        estimate_basis=estimate_basis(normalized.method.value),
        continuity_plan=continuity_plan,
    )


# --- assets ---------------------------------------------------------------
@router.post("/assets", response_model=AssetOut, status_code=201)
async def upload_asset(assets: AssetsDep, file: Annotated[UploadFile, File()]) -> AssetOut:
    try:
        return await assets.ingest_async(filename=file.filename or "upload", stream=file.file)
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    finally:
        await file.close()


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(assets: AssetsDep) -> list[AssetOut]:
    return assets.list_assets()


@router.get("/assets/{asset_id}/file")
async def get_asset_file(assets: AssetsDep, asset_id: str) -> FileResponse:
    record = assets.db.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Reference not found.")
    try:
        path = assets.resolve_stored(record["stored_name"])
    except UploadRejected as exc:  # pragma: no cover - stored names are generated
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Reference file is missing on disk.")
    return FileResponse(path, media_type=record["mime"], filename=record["original_name"])


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(assets: AssetsDep, asset_id: str) -> Response:
    if not assets.delete(asset_id):
        raise HTTPException(status_code=404, detail="Reference not found.")
    return Response(status_code=204)


# --- jobs -----------------------------------------------------------------
@router.post("/jobs", response_model=CreateJobResponse, status_code=201)
async def create_job(request: Request, jobs: JobsDep, request_body: GenerationRequest) -> CreateJobResponse:
    async with request.app.state.gpu_gate:
        release_prompt_model = getattr(request.app.state.director, "release_prompt_model", None)
        if release_prompt_model is not None:
            try:
                await release_prompt_model()
            except DirectorError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            job = await jobs.create(request_body)
        except JobRejected as exc:
            return JSONResponse(  # type: ignore[return-value]
                status_code=422,
                content={
                    "detail": str(exc),
                    "issues": [issue.model_dump(mode="json") for issue in exc.issues],
                },
            )
        return CreateJobResponse(job=job)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    jobs: JobsDep,
    include_hidden: bool = Query(default=False),
    status: Annotated[list[str] | None, Query()] = None,
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListResponse:
    items, total = jobs.list(include_hidden=include_hidden, statuses=status, limit=limit, offset=offset)
    return JobListResponse(jobs=items, total=total)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(jobs: JobsDep, job_id: str) -> JobOut:
    try:
        return jobs.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc


class JobPatch(BaseModel):
    hidden: bool | None = None
    title: str | None = Field(default=None, max_length=120)


@router.patch("/jobs/{job_id}", response_model=JobOut)
async def patch_job(jobs: JobsDep, job_id: str, patch: JobPatch) -> JobOut:
    try:
        if patch.title is not None:
            jobs.db.update_job(job_id, title=patch.title)
        if patch.hidden is not None:
            return jobs.set_hidden(job_id, patch.hidden)
        return jobs.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(jobs: JobsDep, job_id: str) -> JobOut:
    try:
        return await jobs.cancel(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(jobs: JobsDep, job_id: str) -> Response:
    try:
        jobs.delete(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/jobs/{job_id}/events", response_model=JobEventListResponse)
async def job_events(jobs: JobsDep, job_id: str) -> JobEventListResponse:
    try:
        rows = jobs.events(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc
    return JobEventListResponse(events=[JobEventOut.model_validate(row) for row in rows])


@router.get("/jobs/{job_id}/workflow")
async def job_workflow(jobs: JobsDep, job_id: str) -> dict[str, Any]:
    row = jobs.db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Take not found.")
    return {"workflow": workflow_json(row)}


# --- outputs --------------------------------------------------------------
def _output_response(jobs: JobService, output_id: str, *, disposition: Literal["inline", "attachment"]) -> FileResponse:
    record = jobs.db.get_output(output_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Output not found.")
    path = jobs.resolve_output(record["stored_name"])
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Output file is missing on disk.")
    media_type = {
        "video": "video/mp4",
        "audio": "audio/wav",
        "image": "image/png",
    }.get(record["kind"], "application/octet-stream")
    if disposition == "attachment":
        return FileResponse(path, media_type=media_type, filename=record["filename"])
    # FileResponse handles Range requests, which video scrubbing depends on.
    return FileResponse(path, media_type=media_type)


@router.get("/outputs/{output_id}/file")
async def get_output_file(jobs: JobsDep, output_id: str) -> FileResponse:
    return _output_response(jobs, output_id, disposition="inline")


@router.get("/outputs/{output_id}/download")
async def download_output(jobs: JobsDep, output_id: str) -> FileResponse:
    return _output_response(jobs, output_id, disposition="attachment")


@router.post("/jobs/{job_id}/reuse", response_model=GenerationRequest)
async def reuse_job(jobs: JobsDep, job_id: str, body: Annotated[dict[str, Any] | None, Body()] = None) -> GenerationRequest:
    """Return the exact request that produced a take, optionally re-seeded."""
    try:
        job = jobs.get(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="Take not found.") from exc
    if job.request is None:
        raise HTTPException(status_code=409, detail="This take has no stored recipe.")
    keep_seed = bool((body or {}).get("keep_seed", True))
    return job.request.model_copy(update={"seed": job.seed if keep_seed else None})
