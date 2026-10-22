"""FastAPI application factory.

Serves the API under /api and the built SPA everywhere else, so a single
loopback origin on :8220 is the entire product surface.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router as api_router
from .capabilities import CapabilityService
from .comfy import ComfyClient
from .config import Settings, get_settings
from .db import Database
from .schemas import RefKind
from .services.assets import AssetService
from .services.director import (
    DirectorService,
    ManagedOpenAIDirectorClient,
    OllamaDirectorClient,
    OpenAIDirectorClient,
)
from .services.jobs import JobService
from .services.progress import run_progress_listener

logger = logging.getLogger("h3studio")

CACHE_FOREVER = "public, max-age=31536000, immutable"


def create_app(
    settings: Settings | None = None,
    *,
    comfy_client: object | None = None,
    experimental_comfy_client: object | None = None,
    omni_comfy_client: object | None = None,
    director_service: object | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await app.state.jobs.start()
        async def progress_streams() -> None:
            streams = [run_progress_listener(app.state.jobs, app.state.comfy_ws_url, app.state.jobs.client_id)]
            if app.state.experimental_comfy is not app.state.comfy:
                streams.append(
                    run_progress_listener(
                        app.state.jobs,
                        app.state.experimental_comfy_ws_url,
                        app.state.jobs.client_id,
                    )
                )
            if app.state.omni_comfy is not app.state.comfy and app.state.omni_comfy is not app.state.experimental_comfy:
                streams.append(run_progress_listener(app.state.jobs, app.state.omni_comfy_ws_url, app.state.jobs.client_id))
            await asyncio.gather(*streams)

        listener = asyncio.create_task(progress_streams(), name="h3-progress-listeners")
        app.state.jobs.attach_progress_listener(listener)
        try:
            yield
        finally:
            await app.state.jobs.stop()
            release_prompt_model = getattr(app.state.director, "release_prompt_model", None)
            if release_prompt_model is not None:
                await release_prompt_model()
            close = getattr(app.state.comfy, "aclose", None)
            if close is not None:
                await close()
            experimental_close = getattr(app.state.experimental_comfy, "aclose", None)
            if experimental_close is not None and app.state.experimental_comfy is not app.state.comfy:
                await experimental_close()
            if app.state.omni_comfy is not app.state.comfy and app.state.omni_comfy is not app.state.experimental_comfy:
                await app.state.omni_comfy.aclose()
            app.state.db.close()

    app = FastAPI(
        title="MiniMax H3 Studio",
        version=__version__,
        summary="Private creator interface for MiniMax H3 on the reference RTX 4090 workstation RTX 4090.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    comfy = comfy_client or ComfyClient(settings.comfy_url, timeout=settings.comfy_timeout_seconds)
    if experimental_comfy_client is not None:
        experimental_comfy = experimental_comfy_client
    elif comfy_client is not None:
        # Tests that inject a single fake stay hermetic unless they explicitly
        # provide a second runtime.
        experimental_comfy = comfy
    else:
        experimental_comfy = ComfyClient(
            settings.experimental_comfy_url,
            timeout=settings.comfy_timeout_seconds,
        )
    omni_comfy = omni_comfy_client or (comfy if comfy_client is not None else ComfyClient(settings.omni_comfy_url, timeout=settings.comfy_timeout_seconds))
    db = Database(settings.db_path)
    assets = AssetService(
        db,
        uploads_dir=settings.uploads_dir,
        max_bytes={
            RefKind.image: settings.max_image_mb * 1024 * 1024,
            RefKind.video: settings.max_video_mb * 1024 * 1024,
            RefKind.audio: settings.max_audio_mb * 1024 * 1024,
        },
        ffprobe_path=settings.resolve_ffprobe(),
    )
    capabilities = CapabilityService(
        comfy,
        comfy_url=settings.comfy_url,
        ttl=settings.capability_ttl,
        experimental_client=experimental_comfy,
        experimental_comfy_url=settings.experimental_comfy_url,
        omni_client=omni_comfy,
        omni_comfy_url=settings.omni_comfy_url,
    )  # type: ignore[arg-type]
    jobs = JobService(
        db=db,
        comfy=comfy,  # type: ignore[arg-type]
        experimental_comfy=experimental_comfy,  # type: ignore[arg-type]
        omni_comfy=omni_comfy,  # type: ignore[arg-type]
        assets=assets,
        capabilities=capabilities,
        outputs_dir=settings.outputs_dir,
        poll_interval=settings.poll_interval,
    )
    ffprobe = settings.resolve_ffprobe()
    ffmpeg = str(Path(ffprobe).with_name("ffmpeg.exe")) if ffprobe else None
    director = director_service or DirectorService(
        db=db,
        uploads_dir=settings.uploads_dir,
        ollama=OllamaDirectorClient(
            base_url=settings.director_ollama_url,
            model=settings.director_model,
            timeout=settings.director_timeout_seconds,
            autostart=settings.director_autostart_ollama,
            executable=settings.director_ollama_executable,
            models_dir=settings.director_ollama_models,
        ),
        prompt_ollama=(
            ManagedOpenAIDirectorClient(
                base_url=settings.director_openai_url,
                model=settings.director_openai_model,
                timeout=settings.director_timeout_seconds,
                executable=settings.director_openai_executable,
                model_path=settings.director_openai_model_path,
                mmproj_path=settings.director_openai_mmproj_path,
                context_size=settings.director_openai_context_size,
                gpu_layers=settings.director_openai_gpu_layers,
                idle_seconds=settings.director_openai_idle_seconds,
            )
            if settings.director_openai_managed_gpu
            else OpenAIDirectorClient(
                base_url=settings.director_openai_url,
                model=settings.director_openai_model,
                timeout=settings.director_timeout_seconds,
            )
        ),
        ffmpeg_path=ffmpeg,
    )

    app.state.settings = settings
    app.state.db = db
    app.state.comfy = comfy
    app.state.comfy_ws_url = getattr(comfy, "ws_url", "ws://127.0.0.1:8218/ws")
    app.state.experimental_comfy = experimental_comfy
    app.state.experimental_comfy_ws_url = getattr(
        experimental_comfy,
        "ws_url",
        "ws://127.0.0.1:8226/ws",
    )
    app.state.assets = assets
    app.state.omni_comfy = omni_comfy
    app.state.omni_comfy_ws_url = getattr(omni_comfy, "ws_url", "ws://127.0.0.1:8237/ws")
    app.state.capabilities = capabilities
    app.state.jobs = jobs
    app.state.director = director
    app.state.gpu_gate = asyncio.Lock()

    if settings.dev_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.dev_origin_list,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router)
    _mount_spa(app, settings.frontend_dist)
    return app


def _mount_spa(app: FastAPI, dist: Path) -> None:
    """Serve the built SPA with a history-API fallback that never eats /api."""
    index = dist / "index.html"
    static_dir = dist / "assets"

    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(request: Request, full_path: str) -> FileResponse | JSONResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unknown API route.")

        if not index.is_file():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "The Studio UI has not been built yet.",
                    "hint": "Run `npm ci && npm run build` in frontend/, or use the Vite dev server.",
                    "expected": str(index),
                },
            )

        # Serve real files (favicon, manifest, ...) straight from dist.
        if full_path:
            candidate = (dist / full_path).resolve()
            try:
                inside = candidate.is_relative_to(dist.resolve())
            except AttributeError:  # pragma: no cover - Python < 3.9
                inside = str(candidate).startswith(str(dist.resolve()))
            if inside and candidate.is_file():
                headers = {"Cache-Control": CACHE_FOREVER} if full_path.startswith("assets/") else None
                return FileResponse(candidate, headers=headers)

        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
