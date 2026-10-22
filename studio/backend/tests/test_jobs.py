"""Job lifecycle: submission, progress, output harvesting and - above all -
cancellation ownership. The Studio must never interrupt a prompt it does not own.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.capabilities import CapabilityService
from app.db import Database
from app.schemas import GenerationRequest, JobStatus, Mode, RefKind
from app.services.assets import AssetService
from app.services.jobs import JobConflict, JobNotFound, JobService
from app.services.progress import handle_message
from tests.conftest import FakeComfy

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def service(tmp_path: Path, comfy: FakeComfy) -> JobService:
    db = Database(tmp_path / "studio.sqlite3")
    assets = AssetService(
        db,
        uploads_dir=tmp_path / "uploads",
        max_bytes={RefKind.image: 10**7, RefKind.video: 10**8, RefKind.audio: 10**7},
        ffprobe_path=None,
    )
    capabilities = CapabilityService(comfy, comfy_url=comfy.base_url, ttl=0.0)
    return JobService(
        db=db,
        comfy=comfy,
        assets=assets,
        capabilities=capabilities,
        outputs_dir=tmp_path / "outputs",
        poll_interval=0.01,
    )


def text_request(**kwargs) -> GenerationRequest:
    return GenerationRequest(mode=Mode.text, prompt="a lighthouse in fog", length=124, **kwargs)


async def wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition never became true")


# --- submission -----------------------------------------------------------
async def test_create_submits_to_comfy_and_stores_the_recipe(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request(seed=99, title="Lighthouse"))
    assert job.status is JobStatus.queued
    assert job.seed == 99
    assert job.comfy_prompt_id == "prompt-1"
    assert job.estimate_seconds and job.estimate_seconds > 0
    assert comfy.submitted[0]["client_id"] == service.client_id
    assert job.request is not None and job.request.prompt == "a lighthouse in fog"
    graph = comfy.submitted[0]["prompt"]
    assert graph["14"]["inputs"]["filename_prefix"].startswith("video/H3Studio_Lighthouse_")
    await service.stop()


async def test_seed_is_generated_when_omitted(service: JobService) -> None:
    job = await service.create(text_request())
    assert job.seed > 0
    await service.stop()


async def test_invalid_requests_never_reach_comfy(service: JobService, comfy: FakeComfy) -> None:
    from app.services.jobs import JobRejected

    bad = GenerationRequest(mode=Mode.ref2va, prompt="no refs at all")
    with pytest.raises(JobRejected) as excinfo:
        await service.create(bad)
    assert {issue.code for issue in excinfo.value.issues} & {"references_required"}
    assert comfy.submitted == []


async def test_a_comfy_rejection_fails_the_job_instead_of_raising(service: JobService, comfy: FakeComfy) -> None:
    comfy.submit_error = "value not in list: unet_name"
    job = await service.create(text_request())
    assert job.status is JobStatus.failed
    assert job.error and "value not in list" in job.error
    # The take is still recorded, so the creator can see what was attempted.
    assert service.get(job.id).request is not None


async def test_an_offline_comfy_is_reported_as_such(service: JobService, comfy: FakeComfy) -> None:
    from app.services.jobs import JobRejected

    comfy.online = False
    with pytest.raises(JobRejected) as excinfo:
        await service.create(text_request())
    assert [issue.code for issue in excinfo.value.issues] == ["comfy_offline"]


async def test_checkpoint_switch_frees_vram_only_when_comfy_is_idle(
    service: JobService, comfy: FakeComfy
) -> None:
    first = await service.create(text_request(weights="int8"))
    comfy.complete("prompt-1")
    await wait_for(lambda: service.get(first.id).status is JobStatus.completed)

    await service.create(text_request(weights="pinkcherry_v03"))

    assert comfy.free_memory_calls == 1
    await service.stop()


async def test_checkpoint_switch_never_frees_vram_while_any_job_is_active(
    service: JobService, comfy: FakeComfy
) -> None:
    await service.create(text_request(weights="int8"))
    second = await service.create(text_request(weights="pinkcherry_v03"))

    assert comfy.free_memory_calls == 0
    assert comfy.interrupt_calls == 0
    assert any("without forced unload" in event["message"] for event in service.events(second.id))
    await service.stop()


# --- watcher --------------------------------------------------------------
async def test_completion_downloads_and_stores_the_output(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.complete("prompt-1", content=b"rendered-bytes")
    await wait_for(lambda: service.get(job.id).status is JobStatus.completed)

    done = service.get(job.id)
    assert done.progress == 1.0
    assert len(done.outputs) == 1
    output = done.outputs[0]
    assert output.kind == "video"
    assert output.size_bytes == len(b"rendered-bytes")
    stored = service.resolve_output(service.db.get_output(output.id)["stored_name"])
    assert stored is not None and stored.read_bytes() == b"rendered-bytes"
    await service.stop()


async def test_execution_errors_surface_the_comfy_message(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.fail("prompt-1", "CUDA out of memory")
    await wait_for(lambda: service.get(job.id).status is JobStatus.failed)
    assert "CUDA out of memory" in (service.get(job.id).error or "")
    await service.stop()


async def test_queue_position_is_tracked(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.pending = ["someone-else", "prompt-1"]
    await wait_for(lambda: service.get(job.id).queue_position == 2)
    comfy.pending = []
    comfy.running = ["prompt-1"]
    await wait_for(lambda: service.get(job.id).status is JobStatus.running)
    await service.stop()


# --- cancellation ownership ----------------------------------------------
async def test_cancel_deletes_a_queued_prompt_without_interrupting(
    service: JobService, comfy: FakeComfy
) -> None:
    job = await service.create(text_request())
    comfy.pending = ["prompt-1"]

    canceled = await service.cancel(job.id)

    assert canceled.status is JobStatus.canceled
    assert comfy.deleted == ["prompt-1"]
    assert comfy.interrupt_calls == 0
    await service.stop()


async def test_cancel_interrupts_only_when_our_prompt_is_the_running_one(
    service: JobService, comfy: FakeComfy
) -> None:
    job = await service.create(text_request())
    comfy.pending = []
    comfy.running = ["prompt-1"]

    canceled = await service.cancel(job.id)

    assert canceled.status is JobStatus.canceled
    assert comfy.interrupt_calls == 1
    await service.stop()


async def test_cancel_never_interrupts_a_prompt_owned_by_someone_else(
    service: JobService, comfy: FakeComfy
) -> None:
    """The load-bearing safety test: another tool owns the GPU, we back off."""
    job = await service.create(text_request())
    comfy.pending = []
    comfy.running = ["a-prompt-from-the-comfy-ui"]

    canceled = await service.cancel(job.id)

    assert canceled.status is JobStatus.canceled
    assert comfy.interrupt_calls == 0, "interrupted a render the Studio does not own"
    assert comfy.deleted == []
    messages = [event["message"] for event in service.events(job.id)]
    assert any("without interrupting" in message for message in messages)
    await service.stop()


async def test_cancel_before_submission_is_local_only(service: JobService, comfy: FakeComfy) -> None:
    comfy.submit_error = "queue is full"
    job = await service.create(text_request())  # fails, never gets a prompt id
    assert job.comfy_prompt_id is None
    service.db.update_job(job.id, status=JobStatus.queued.value, error=None)
    canceled = await service.cancel(job.id)
    assert canceled.status is JobStatus.canceled
    assert comfy.interrupt_calls == 0


async def test_cancelling_a_finished_take_is_a_conflict(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.complete("prompt-1")
    await wait_for(lambda: service.get(job.id).status is JobStatus.completed)
    with pytest.raises(JobConflict):
        await service.cancel(job.id)
    await service.stop()


async def test_cancelling_an_unknown_take_is_not_found(service: JobService) -> None:
    with pytest.raises(JobNotFound):
        await service.cancel("does-not-exist")


async def test_cancel_refuses_when_comfy_is_unreachable(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.online = False
    with pytest.raises(JobConflict, match="Cannot reach ComfyUI"):
        await service.cancel(job.id)
    assert comfy.interrupt_calls == 0
    await service.stop()


async def test_an_interrupted_history_marks_the_take_canceled(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.histories["prompt-1"] = {
        "status": {"status_str": "success", "completed": False, "messages": [["execution_interrupted", {}]]},
        "outputs": {},
    }
    await wait_for(lambda: service.get(job.id).status is JobStatus.canceled)
    await service.stop()


# --- websocket progress ---------------------------------------------------
async def test_progress_messages_move_the_bar(service: JobService) -> None:
    job = await service.create(text_request())
    handle_message(service, {"type": "progress", "data": {"prompt_id": "prompt-1", "value": 8, "max": 20}})
    updated = service.get(job.id)
    assert updated.progress == pytest.approx(0.4)
    assert updated.status is JobStatus.running
    await service.stop()


async def test_executing_messages_translate_nodes_into_creator_stages(service: JobService) -> None:
    job = await service.create(text_request())
    handle_message(service, {"type": "executing", "data": {"prompt_id": "prompt-1", "node": "10"}})
    assert service.get(job.id).stage == "Rendering"
    handle_message(service, {"type": "executing", "data": {"prompt_id": "prompt-1", "node": "13"}})
    assert service.get(job.id).stage == "Muxing video and sound"
    await service.stop()


async def test_progress_for_an_unknown_prompt_is_ignored(service: JobService) -> None:
    handle_message(service, {"type": "progress", "data": {"prompt_id": "not-ours", "value": 5, "max": 10}})
    jobs, total = service.list()
    assert total == 0 and jobs == []


async def test_execution_error_messages_fail_the_take(service: JobService) -> None:
    job = await service.create(text_request())
    handle_message(
        service,
        {
            "type": "execution_error",
            "data": {"prompt_id": "prompt-1", "node_type": "UNETLoader", "exception_message": "bad weights"},
        },
    )
    failed = service.get(job.id)
    assert failed.status is JobStatus.failed
    assert "bad weights" in (failed.error or "")
    await service.stop()


async def test_malformed_websocket_frames_are_ignored(service: JobService) -> None:
    for payload in ({}, {"type": "progress"}, {"type": "progress", "data": {}}, {"data": {"prompt_id": "x"}}):
        handle_message(service, payload)  # must not raise


# --- history management ---------------------------------------------------
async def test_hide_unhide_and_listing(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.complete("prompt-1")
    await wait_for(lambda: service.get(job.id).status is JobStatus.completed)

    service.set_hidden(job.id, True)
    visible, total = service.list()
    assert total == 0 and visible == []

    hidden, total = service.list(include_hidden=True)
    assert total == 1 and hidden[0].hidden is True

    service.set_hidden(job.id, False)
    visible, total = service.list()
    assert total == 1
    await service.stop()


async def test_delete_removes_the_row_and_the_file(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    comfy.complete("prompt-1")
    await wait_for(lambda: service.get(job.id).status is JobStatus.completed)
    output = service.get(job.id).outputs[0]
    path = service.resolve_output(service.db.get_output(output.id)["stored_name"])
    assert path is not None and path.is_file()

    service.delete(job.id)

    assert not path.exists()
    with pytest.raises(JobNotFound):
        service.get(job.id)
    await service.stop()


async def test_running_takes_cannot_be_deleted(service: JobService, comfy: FakeComfy) -> None:
    job = await service.create(text_request())
    with pytest.raises(JobConflict, match="Cancel this take"):
        service.delete(job.id)
    await service.stop()


@pytest.mark.parametrize("hostile", ["../../etc/passwd", "..\\evil", "sub/dir.mp4", ""])
async def test_output_resolution_refuses_traversal(service: JobService, hostile: str) -> None:
    assert service.resolve_output(hostile) is None
