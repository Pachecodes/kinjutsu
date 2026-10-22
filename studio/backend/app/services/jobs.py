"""Owned-job orchestration: submit, watch, progress, cancel, harvest outputs.

Ownership is the load-bearing idea. A job only exists here if the Studio
created it, and the Studio will only ever interrupt ComfyUI when the prompt id
Comfy reports as *running* is one of ours. Anything else - another tab, another
tool, a hand-run workflow in the Comfy UI - is left completely alone.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..capabilities import CapabilityService
from ..comfy import ComfyClientProtocol, ComfyError
from ..db import Database, dumps, loads, utcnow
from ..schemas import (
    GenerationRequest,
    Issue,
    JobOut,
    JobStatus,
    MethodId,
    Mode,
    OutputOut,
    RefKind,
)
from ..workflow.builder import WorkflowBuildError, build_workflow, make_filename_prefix
from ..workflow.estimate import estimate_seconds
from ..workflow.continuity import plan_continuity
from ..workflow.validation import ResolvedAsset, has_errors, validate_request
from .assets import AssetService

logger = logging.getLogger("h3studio.jobs")

TERMINAL = {JobStatus.completed, JobStatus.failed, JobStatus.canceled}
OUTPUT_EXTENSIONS = {
    ".mp4": "video",
    ".webm": "video",
    ".mov": "video",
    ".gif": "video",
    ".wav": "audio",
    ".mp3": "audio",
    ".flac": "audio",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}

#: Friendly stage names for the graph nodes the creator actually waits on.
STAGE_LABELS = {
    "UNETLoader": "Loading H3 weights",
    "UnetLoaderGGUF": "Loading H3 weights",
    "CLIPLoader": "Loading text encoder",
    "LoraLoaderModelOnly": "Applying LoRAs",
    "VAELoader": "Loading VAE",
    "LoadImage": "Reading references",
    "LoadVideo": "Reading references",
    "LoadAudio": "Reading references",
    "GetVideoComponents": "Unpacking motion clip",
    "MiniMaxH3ImageToVideo": "Understanding the prompt",
    "MiniMaxH3ReferenceToVideo": "Understanding references",
    "EasyCache": "Preparing fast preview",
    "MiniMaxH3MemoryEfficientSageAttentionPatch": "Patching attention",
    "SolAttnPatch": "Patching attention",
    "BasicScheduler": "Building the schedule",
    "SamplerCustomAdvanced": "Rendering",
    "VAEDecode": "Decoding video",
    "VAEDecodeAudio": "Decoding audio",
    "CreateVideo": "Muxing video and sound",
    "SaveVideo": "Saving take",
}

#: Consecutive polls where Comfy knows nothing about our prompt before we give up.
MISSING_POLL_LIMIT = 8


class JobRejected(ValueError):
    """The request did not pass validation; carries the issue list for the UI."""

    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("The request is not valid for this H3 install.")
        self.issues = issues


class JobNotFound(LookupError):
    pass


class JobConflict(RuntimeError):
    pass


def _asset_to_resolved(record: dict[str, Any]) -> ResolvedAsset:
    has_audio = record.get("has_audio")
    return ResolvedAsset(
        id=record["id"],
        kind=RefKind(record["kind"]),
        comfy_name=record.get("comfy_name") or "",
        duration_seconds=record.get("duration_seconds"),
        has_audio=None if has_audio is None else bool(has_audio),
        width=record.get("width"), height=record.get("height"),
        frame_count=record.get("frame_count"), fps=record.get("fps"),
    )


class JobService:
    def __init__(
        self,
        *,
        db: Database,
        comfy: ComfyClientProtocol,
        assets: AssetService,
        capabilities: CapabilityService,
        outputs_dir: Path,
        experimental_comfy: ComfyClientProtocol | None = None,
        omni_comfy: ComfyClientProtocol | None = None,
        poll_interval: float = 1.0,
        comfy_subfolder: str = "h3studio",
    ) -> None:
        self.db = db
        self.comfy = comfy
        self.experimental_comfy = experimental_comfy or comfy
        self.omni_comfy = omni_comfy
        self.assets = assets
        self.capabilities = capabilities
        self.outputs_dir = outputs_dir.resolve()
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.poll_interval = poll_interval
        self.comfy_subfolder = comfy_subfolder
        self.client_id = uuid.uuid4().hex
        self._watchers: dict[str, asyncio.Task[None]] = {}
        self._progress_task: asyncio.Task[None] | None = None
        self._preview: dict[str, Any] | None = None
        self._stopping = False
        self._checkpoint_lock = asyncio.Lock()
        self._submitted_checkpoints: dict[str, str | None] = {"stable": None, "experimental": None, "omni": None}

    def _backend_for_method(self, method: MethodId) -> str:
        if method is MethodId.fast_h3_omni_8step:
            return "omni"
        return "experimental" if method in {MethodId.fast_h3_v2_8step, MethodId.taomate_3step} else "stable"

    def _client_for_method(self, method: MethodId) -> ComfyClientProtocol:
        if method is MethodId.fast_h3_omni_8step:
            if self.omni_comfy is None:
                raise ComfyError("Backend Omni independiente no configurado.")
            return self.omni_comfy
        return self.experimental_comfy if self._backend_for_method(method) == "experimental" else self.comfy

    def _client_for_row(self, row: dict[str, Any]) -> ComfyClientProtocol:
        return self._client_for_method(MethodId(row["method"]))

    # -- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        """Re-attach watchers to anything left running across a restart."""
        self._stopping = False
        for row in self.db.active_jobs():
            if row["comfy_prompt_id"]:
                self._spawn_watcher(row["id"])
            else:
                self._finish(row["id"], JobStatus.failed, error="Studio restarted before this take was queued.")

    async def stop(self) -> None:
        self._stopping = True
        tasks = list(self._watchers.values())
        if self._progress_task is not None:
            tasks.append(self._progress_task)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._watchers.clear()
        self._progress_task = None

    def attach_progress_listener(self, task: asyncio.Task[None]) -> None:
        self._progress_task = task

    @property
    def active_count(self) -> int:
        return len(self.db.active_jobs())

    # -- asset mirroring ---------------------------------------------------
    async def _mirror_asset(self, record: dict[str, Any], client: ComfyClientProtocol) -> str:
        """Ensure the file exists in Comfy's input folder, return its combo name."""
        # `comfy_name` is only a relative name, not proof that every isolated
        # backend has the file. Upload with overwrite so the selected runtime
        # owns the exact Studio asset before its workflow is submitted.
        path = self.assets.resolve_stored(record["stored_name"])
        content = await asyncio.to_thread(path.read_bytes)
        comfy_name = await client.upload_input(
            filename=record["stored_name"],
            content=content,
            content_type=record["mime"],
            subfolder=self.comfy_subfolder,
        )
        self.db.set_asset_comfy_name(record["id"], comfy_name)
        return comfy_name

    async def _resolve_assets(
        self,
        request: GenerationRequest,
        *,
        mirror: bool,
        client: ComfyClientProtocol | None = None,
    ) -> dict[str, ResolvedAsset]:
        ids = [ref.asset_id for ref in request.references]
        records = self.db.get_assets(ids)
        resolved: dict[str, ResolvedAsset] = {}
        guide_ids = {r.asset_id for r in request.references if r.role.value == "aligned_guide"}
        for asset_id, record in records.items():
            if asset_id in guide_ids:
                from .assets import probe_aligned_video
                metadata = await asyncio.to_thread(probe_aligned_video, self.assets.ffprobe_path, self.assets.resolve_stored(record["stored_name"]))
                record = {**record, **metadata}
            if mirror:
                try:
                    comfy_name = await self._mirror_asset(record, client or self.comfy)
                except ComfyError:
                    # A normal-backend name is never proof of an Omni upload.
                    comfy_name = "" if request.method is MethodId.fast_h3_omni_8step else record.get("comfy_name") or ""
                record = {**record, "comfy_name": comfy_name}
            resolved[asset_id] = _asset_to_resolved(record)
        return resolved

    # -- validation --------------------------------------------------------
    async def validate(self, request: GenerationRequest) -> tuple[GenerationRequest, list[Issue]]:
        assets = await self._resolve_assets(request, mirror=False)
        capabilities = await self.capabilities.get()
        available = {method.id for method in capabilities.methods if method.available}
        available_loras = {lora.name: lora.checkpoint for lora in capabilities.loras}
        normalized, issues = validate_request(
            request,
            assets,
            available_methods=available,
            available_loras=available_loras,
            aligned_guides_available=capabilities.aligned_guides,
        )
        if request.weights.value == "erosmax_beta5":
            if not capabilities.comfy_online:
                issues.append(Issue(code="comfy_offline", message="H3 runtime offline; checkpoint availability unknown.", field="weights"))
            elif not capabilities.weights.get("erosmax_beta5"):
                issues.append(Issue(code="checkpoint_missing", message="10Eros-Max Beta 5 is missing from the live UNETLoader. No fallback.", field="weights"))
        if request.custom_sigmas is not None and not capabilities.manual_sigmas:
            issues.append(Issue(code="manual_sigmas_unavailable", message="Live ManualSigmas node is unavailable.", field="custom_sigmas"))
        if request.method is not MethodId.fast_h3_omni_8step and capabilities.comfy_online and request.sampler_name not in capabilities.samplers:
            issues.append(Issue(code="sampler_unavailable", message="Selected sampler is unavailable in the live runtime.", field="sampler_name"))
        return normalized, issues

    # -- creation ----------------------------------------------------------
    async def create(self, request: GenerationRequest) -> JobOut:
        capabilities = await self.capabilities.get()
        if request.method is not MethodId.fast_h3_omni_8step and not capabilities.comfy_online:
            # Say the real reason instead of cascading into "every method is
            # unavailable", which is technically true and completely unhelpful.
            raise JobRejected(
                [
                    Issue(
                        code="comfy_offline",
                        message=f"H3 Lab ComfyUI at {capabilities.comfy_url} is not responding.",
                    )
                ]
            )

        normalized, issues = await self.validate(request)
        if has_errors(issues):
            raise JobRejected(issues)

        target_client = self._client_for_method(normalized.method)
        target_backend = self._backend_for_method(normalized.method)
        for active in self.db.active_jobs():
            active_backend = self._backend_for_method(MethodId(active["method"]))
            if active_backend != target_backend:
                raise JobRejected(
                    [
                        Issue(
                            code="backend_busy",
                            message="Another H3 runtime owns the GPU. Wait for that take to finish before switching backends.",
                            field="method",
                        )
                    ]
                )

        mode_info = next((m for m in capabilities.modes if m.id == normalized.mode), None)
        if normalized.method is not MethodId.fast_h3_omni_8step and mode_info is not None and not mode_info.available:
            raise JobRejected(
                [
                    Issue(
                        code="mode_unavailable",
                        message=mode_info.unavailable_reason or "This mode is unavailable right now.",
                        field="mode",
                    )
                ]
            )

        assets = await self._resolve_assets(normalized, mirror=True, client=target_client)
        unmirrored = [
            ref.asset_id
            for ref in normalized.references
            if not (assets.get(ref.asset_id) and assets[ref.asset_id].comfy_name)
        ]
        if unmirrored:
            raise JobRejected(
                [
                    Issue(
                        code="asset_upload_failed",
                        message="References could not be copied to ComfyUI. Is the H3 lab instance running?",
                        field="references",
                    )
                ]
            )

        job_id = uuid.uuid4().hex
        seed = normalized.seed if normalized.seed is not None else secrets.randbits(63)
        prefix = make_filename_prefix(job_id, normalized.title)

        try:
            built = build_workflow(normalized, assets, seed=seed, filename_prefix=prefix)
        except WorkflowBuildError as exc:
            raise JobRejected([Issue(code="workflow_build_failed", message=str(exc))]) from exc

        continuity_plan = plan_continuity(normalized)
        estimate = estimate_seconds(
            method=normalized.method.value,
            width=normalized.width,
            height=normalized.height,
            length=continuity_plan.sampled_frames,
            steps=normalized.steps,
        )

        record = {
            "id": job_id,
            "status": JobStatus.queued.value,
            "mode": normalized.mode.value,
            "method": normalized.method.value,
            "title": normalized.title,
            "prompt": normalized.prompt,
            "width": normalized.width,
            "height": normalized.height,
            "length": normalized.length,
            "seed": seed,
            "steps": normalized.steps,
            "request_json": dumps(normalized.model_dump(mode="json")),
            "workflow_json": dumps(built.prompt),
            "comfy_prompt_id": None,
            "comfy_client_id": self.client_id,
            "progress": 0.0,
            "stage": "Queued",
            "queue_position": None,
            "error": None,
            "hidden": 0,
            "estimate_seconds": estimate,
            "created_at": utcnow(),
            "started_at": None,
            "finished_at": None,
        }
        self.db.insert_job(record)
        self.db.add_event(job_id, "info", f"Queued {normalized.mode.value} take, {built.checkpoint}.")

        try:
            async with self._checkpoint_lock:
                await self._unload_for_checkpoint_switch(
                    job_id,
                    built.checkpoint,
                    target_client,
                    target_backend,
                )
                prompt_id = await target_client.submit(built.prompt, self.client_id)
                self._submitted_checkpoints[target_backend] = built.checkpoint
        except ComfyError as exc:
            self._finish(job_id, JobStatus.failed, error=str(exc))
            self.db.add_event(job_id, "error", str(exc))
            return self.get(job_id)

        self.db.update_job(job_id, comfy_prompt_id=prompt_id)
        self.db.add_event(job_id, "info", f"ComfyUI accepted the workflow (prompt {prompt_id}).")
        self._spawn_watcher(job_id)
        return self.get(job_id)

    async def _unload_for_checkpoint_switch(
        self,
        job_id: str,
        checkpoint: str,
        client: ComfyClientProtocol,
        backend: str,
    ) -> None:
        """Free cached VRAM before a safe checkpoint switch.

        `/free` is never called while Comfy has running or pending work, so this
        cannot interrupt this Studio or another Comfy client. Busy switches are
        delegated to Comfy's own model manager.
        """
        previous = self._submitted_checkpoints[backend]
        if previous is None or previous == checkpoint:
            return
        snapshot = await client.queue()
        if snapshot.running or snapshot.pending:
            self.db.add_event(
                job_id,
                "info",
                "Checkpoint switch queued without forced unload because ComfyUI is busy; its model manager will switch safely.",
            )
            return
        try:
            await client.free_memory()
        except ComfyError as exc:
            self.db.add_event(
                job_id,
                "warning",
                f"ComfyUI could not explicitly unload cached VRAM ({exc}); its model manager will switch safely.",
            )
            return
        self.db.add_event(
            job_id,
            "info",
            f"Released cached VRAM before switching checkpoints ({previous} → {checkpoint}).",
        )

    # -- watching ----------------------------------------------------------
    def _spawn_watcher(self, job_id: str) -> None:
        if job_id in self._watchers and not self._watchers[job_id].done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - only outside an event loop
            return
        task = loop.create_task(self._watch(job_id), name=f"h3-watch-{job_id}")
        self._watchers[job_id] = task
        task.add_done_callback(lambda _t, jid=job_id: self._watchers.pop(jid, None))

    async def _watch(self, job_id: str) -> None:
        missing_polls = 0
        try:
            while not self._stopping:
                await asyncio.sleep(self.poll_interval)
                row = self.db.get_job(job_id)
                if row is None or JobStatus(row["status"]) in TERMINAL:
                    return
                prompt_id = row["comfy_prompt_id"]
                if not prompt_id:
                    return

                client = self._client_for_row(row)
                try:
                    history = await client.history(prompt_id)
                except ComfyError as exc:
                    logger.debug("history poll failed for %s: %s", job_id, exc)
                    history = None
                    missing_polls += 1
                    if missing_polls >= MISSING_POLL_LIMIT:
                        self._finish(job_id, JobStatus.failed, error=str(exc))
                        return
                    continue

                if history:
                    await self._complete_from_history(job_id, history, client)
                    return

                try:
                    snapshot = await client.queue()
                except ComfyError:
                    continue

                position = snapshot.position_of(prompt_id)
                if position == 0:
                    fresh = self.db.get_job(job_id)
                    if fresh and fresh["status"] == JobStatus.queued.value:
                        self.db.update_job(
                            job_id,
                            status=JobStatus.running.value,
                            started_at=utcnow(),
                            queue_position=0,
                            stage="Rendering",
                        )
                    else:
                        self.db.update_job(job_id, queue_position=0)
                    missing_polls = 0
                elif position is not None:
                    self.db.update_job(job_id, queue_position=position)
                    missing_polls = 0
                else:
                    missing_polls += 1
                    if missing_polls >= MISSING_POLL_LIMIT:
                        self._finish(
                            job_id,
                            JobStatus.failed,
                            error="ComfyUI no longer knows about this take. It may have been cleared elsewhere.",
                        )
                        return
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("watcher for %s crashed", job_id)
            self._finish(job_id, JobStatus.failed, error=f"Studio watcher error: {exc}")

    async def _complete_from_history(
        self,
        job_id: str,
        history: dict[str, Any],
        client: ComfyClientProtocol,
    ) -> None:
        status = history.get("status") or {}
        status_str = str(status.get("status_str") or "")
        completed = bool(status.get("completed"))

        messages = status.get("messages") or []
        interrupted = any(
            isinstance(entry, (list, tuple)) and entry and entry[0] == "execution_interrupted"
            for entry in messages
        )

        if interrupted:
            self._finish(job_id, JobStatus.canceled, error=None)
            self.db.add_event(job_id, "info", "Render interrupted.")
            return

        if status_str == "error" or (not completed and status_str):
            detail = _extract_error(messages) or "ComfyUI reported an execution error."
            self._finish(job_id, JobStatus.failed, error=detail)
            self.db.add_event(job_id, "error", detail)
            return

        stored = await self._store_outputs(job_id, history.get("outputs") or {}, client)
        if not stored:
            self._finish(job_id, JobStatus.failed, error="The render finished but produced no file.")
            return
        self._finish(job_id, JobStatus.completed, error=None)
        self.db.add_event(job_id, "info", f"Saved {stored} file(s).")

    async def _store_outputs(
        self,
        job_id: str,
        outputs: dict[str, Any],
        client: ComfyClientProtocol,
    ) -> int:
        stored = 0
        for node_outputs in outputs.values():
            if not isinstance(node_outputs, dict):
                continue
            for key in ("videos", "gifs", "images", "audio"):
                for item in node_outputs.get(key) or []:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not isinstance(filename, str) or not filename:
                        continue
                    subfolder = str(item.get("subfolder") or "")
                    folder_type = str(item.get("type") or "output")
                    if folder_type != "output":
                        continue
                    try:
                        content = await client.download_output(
                            filename=filename, subfolder=subfolder, folder_type=folder_type
                        )
                    except ComfyError as exc:
                        self.db.add_event(job_id, "error", f"Could not fetch {filename}: {exc}")
                        continue
                    extension = Path(filename).suffix.lower()
                    kind = OUTPUT_EXTENSIONS.get(extension)
                    if kind is None:
                        continue
                    stored_name = f"{uuid.uuid4().hex}{extension}"
                    destination = self.outputs_dir / stored_name
                    await asyncio.to_thread(destination.write_bytes, content)
                    self.db.insert_output(
                        {
                            "id": uuid.uuid4().hex,
                            "job_id": job_id,
                            "kind": kind,
                            "filename": Path(filename).name,
                            "stored_name": stored_name,
                            "size_bytes": len(content),
                            "created_at": utcnow(),
                        }
                    )
                    stored += 1
        return stored

    def _finish(self, job_id: str, status: JobStatus, *, error: str | None) -> None:
        fields: dict[str, Any] = {
            "status": status.value,
            "finished_at": utcnow(),
            "queue_position": None,
            "error": error,
        }
        if status is JobStatus.completed:
            fields["progress"] = 1.0
            fields["stage"] = "Done"
        elif status is JobStatus.canceled:
            fields["stage"] = "Canceled"
        else:
            fields["stage"] = "Failed"
        self.db.update_job(job_id, **fields)

    # -- progress from the Comfy websocket ---------------------------------
    def apply_preview(
        self,
        node_id: str,
        image: str,
        mime: str,
        width: int,
        height: int,
        step: int,
        total: int,
    ) -> None:
        """Keep only the newest tiny-VAE preview; never persist render frames."""
        if node_id != "101" or not image or not mime.startswith(("image/", "video/")):
            return
        self._preview = {
            "data_url": f"data:{mime};base64,{image}",
            "width": width,
            "height": height,
            "step": step,
            "total": total,
        }

    def latest_preview(self) -> dict[str, Any] | None:
        return self._preview

    def apply_progress(self, prompt_id: str, value: float, maximum: float) -> None:
        row = self.db.get_job_by_prompt_id(prompt_id)
        if row is None or JobStatus(row["status"]) in TERMINAL:
            return
        fraction = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
        updates: dict[str, Any] = {"progress": round(fraction, 4)}
        if row["status"] == JobStatus.queued.value:
            updates["status"] = JobStatus.running.value
            updates["started_at"] = row["started_at"] or utcnow()
            updates["queue_position"] = 0
        self.db.update_job(row["id"], **updates)

    def apply_executing(self, prompt_id: str, node_id: str | None) -> None:
        row = self.db.get_job_by_prompt_id(prompt_id)
        if row is None or JobStatus(row["status"]) in TERMINAL:
            return
        stage = "Rendering"
        if node_id:
            workflow = loads(row["workflow_json"]) or {}
            node = workflow.get(str(node_id)) or {}
            stage = STAGE_LABELS.get(str(node.get("class_type")), "Rendering")
        updates: dict[str, Any] = {"stage": stage}
        if row["status"] == JobStatus.queued.value:
            updates["status"] = JobStatus.running.value
            updates["started_at"] = row["started_at"] or utcnow()
            updates["queue_position"] = 0
        self.db.update_job(row["id"], **updates)

    def apply_error(self, prompt_id: str, message: str) -> None:
        row = self.db.get_job_by_prompt_id(prompt_id)
        if row is None or JobStatus(row["status"]) in TERMINAL:
            return
        self._finish(row["id"], JobStatus.failed, error=message)
        self.db.add_event(row["id"], "error", message)

    # -- cancellation ------------------------------------------------------
    async def cancel(self, job_id: str) -> JobOut:
        """Cancel a take. Only ever interrupts Comfy when *our* prompt is running."""
        row = self.db.get_job(job_id)
        if row is None:
            raise JobNotFound(job_id)
        if JobStatus(row["status"]) in TERMINAL:
            raise JobConflict("This take already finished.")

        client = self._client_for_row(row)
        prompt_id = row["comfy_prompt_id"]
        if not prompt_id:
            self._finish(job_id, JobStatus.canceled, error=None)
            self.db.add_event(job_id, "info", "Canceled before ComfyUI accepted it.")
            return self.get(job_id)

        try:
            snapshot = await client.queue()
        except ComfyError as exc:
            raise JobConflict(f"Cannot reach ComfyUI to cancel safely: {exc}") from exc

        if prompt_id in snapshot.pending:
            await client.delete_queued(prompt_id)
            self.db.add_event(job_id, "info", "Removed from the ComfyUI queue.")
        elif prompt_id in snapshot.running:
            # Ours, and it is the prompt actually executing: safe to interrupt.
            await client.interrupt()
            self.db.add_event(job_id, "info", "Interrupted the running render.")
        else:
            # Something else owns the GPU right now. Never interrupt that.
            self.db.add_event(
                job_id,
                "info",
                "ComfyUI is not running this take; marked canceled locally without interrupting anything.",
            )

        self._finish(job_id, JobStatus.canceled, error=None)
        return self.get(job_id)

    # -- reads / mutations -------------------------------------------------
    def get(self, job_id: str) -> JobOut:
        row = self.db.get_job(job_id)
        if row is None:
            raise JobNotFound(job_id)
        return self.to_out(row, self.db.list_outputs(job_id))

    def list(
        self,
        *,
        include_hidden: bool = False,
        statuses: list[str] | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> tuple[list[JobOut], int]:
        rows, total = self.db.list_jobs(
            include_hidden=include_hidden, statuses=statuses, limit=limit, offset=offset
        )
        grouped = self.db.outputs_for_jobs([row["id"] for row in rows])
        return [self.to_out(row, grouped.get(row["id"], [])) for row in rows], total

    def set_hidden(self, job_id: str, hidden: bool) -> JobOut:
        if self.db.get_job(job_id) is None:
            raise JobNotFound(job_id)
        self.db.update_job(job_id, hidden=1 if hidden else 0)
        return self.get(job_id)

    def delete(self, job_id: str) -> None:
        row = self.db.get_job(job_id)
        if row is None:
            raise JobNotFound(job_id)
        if JobStatus(row["status"]) not in TERMINAL:
            raise JobConflict("Cancel this take before deleting it.")
        outputs = self.db.delete_job(job_id)
        for output in outputs:
            path = self.resolve_output(output["stored_name"])
            if path is not None:
                path.unlink(missing_ok=True)

    def resolve_output(self, stored_name: str) -> Path | None:
        """Resolve a generated output name inside the outputs dir, or None."""
        if not stored_name or "/" in stored_name or "\\" in stored_name or ".." in stored_name:
            return None
        candidate = (self.outputs_dir / stored_name).resolve()
        if candidate.parent != self.outputs_dir:
            return None
        return candidate

    def events(self, job_id: str) -> list[dict[str, Any]]:
        if self.db.get_job(job_id) is None:
            raise JobNotFound(job_id)
        return self.db.list_events(job_id)

    def to_out(self, row: dict[str, Any], outputs: list[dict[str, Any]]) -> JobOut:
        request: GenerationRequest | None = None
        raw = loads(row["request_json"])
        if isinstance(raw, dict):
            try:
                request = GenerationRequest.model_validate(raw)
            except Exception:  # pragma: no cover - a stored request should always parse
                request = None

        duration: float | None = None
        if row["started_at"] and row["finished_at"]:
            try:
                started = datetime.fromisoformat(row["started_at"])
                finished = datetime.fromisoformat(row["finished_at"])
                duration = round((finished - started).total_seconds(), 1)
            except ValueError:  # pragma: no cover
                duration = None

        return JobOut(
            id=row["id"],
            status=JobStatus(row["status"]),
            mode=Mode(row["mode"]),
            method=MethodId(row["method"]),
            title=row["title"],
            prompt=row["prompt"],
            width=row["width"],
            height=row["height"],
            length=row["length"],
            seed=row["seed"],
            steps=row["steps"],
            progress=float(row["progress"] or 0.0),
            stage=row["stage"],
            queue_position=row["queue_position"],
            error=row["error"],
            hidden=bool(row["hidden"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_seconds=duration,
            estimate_seconds=row["estimate_seconds"],
            comfy_prompt_id=row["comfy_prompt_id"],
            outputs=[
                OutputOut(
                    id=output["id"],
                    job_id=output["job_id"],
                    kind=output["kind"],
                    filename=output["filename"],
                    size_bytes=output["size_bytes"],
                    url=f"/api/outputs/{output['id']}/file",
                    created_at=output["created_at"],
                )
                for output in outputs
            ],
            request=request,
        )


def _extract_error(messages: Any) -> str | None:
    for entry in messages or []:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[0] == "execution_error":
            payload = entry[1]
            if isinstance(payload, dict):
                node = payload.get("node_type") or payload.get("node_id")
                detail = payload.get("exception_message") or payload.get("exception_type")
                if detail:
                    return f"{node}: {detail}" if node else str(detail)
    return None


def workflow_json(row: dict[str, Any]) -> dict[str, Any]:
    parsed = loads(row.get("workflow_json"))
    return parsed if isinstance(parsed, dict) else {}


__all__ = [
    "JobConflict",
    "JobNotFound",
    "JobRejected",
    "JobService",
    "workflow_json",
]
