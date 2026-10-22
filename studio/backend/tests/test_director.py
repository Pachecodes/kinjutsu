from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import subprocess

import pytest

from app.db import Database, utcnow
from app.main import create_app
from app.schemas import DirectorRequest, Mode, PromptChatRequest, ReferenceInput
from app.services.director import (
    H3_PROMPTING_GUIDE,
    DirectorError,
    DirectorService,
    OllamaDirectorClient,
    ManagedOpenAIDirectorClient,
    build_h3_director_prompt,
)


@pytest.fixture(autouse=True)
def enable_fake_director(settings):
    # Explicit test opt-in only; no local model process is started by this fixture.
    settings.director_enabled = True
    settings.director_openai_managed_gpu = True

class FakeOllama:
    def __init__(self) -> None:
        self.model = "local-test-model"
        self.calls: list[dict] = []

    async def chat(self, *, system: str, prompt: str, images: list[str] | None = None) -> str:
        self.calls.append({"system": system, "prompt": prompt, "images": images or []})
        if images:
            return "A young astronaut in a white suit, lit from camera left."
        if "ZERO media references" in prompt or "ZERO reference assets" in system:
            return "[SCENE]\nThe astronaut walks through a quiet lunar base."
        return "[REFERENCE USE]\n<Picture 1> defines the astronaut identity only.\n\n[SCENE]\nThe astronaut walks through a quiet lunar base."


class RetryOllama(FakeOllama):
    async def chat(self, *, system: str, prompt: str, images: list[str] | None = None) -> str:
        self.calls.append({"system": system, "prompt": prompt, "images": images or []})
        if len(self.calls) == 1:
            return "[REFERENCE USE]\n<Video 1> is the primary visual track.\n[SCENE]\nA lunar base."
        return "[SCENE]\nA solitary astronaut finds a glowing flower inside a lunar base."


class RefusalThenPromptOllama(FakeOllama):
    async def chat(self, *, system: str, prompt: str, images: list[str] | None = None) -> str:
        self.calls.append({"system": system, "prompt": prompt, "images": images or []})
        if len(self.calls) == 1:
            return "I'm sorry, I can't assist with that request."
        return "[SCENE]\nAn adult fashion model undergoes the requested fictional transformation."


class MultimodalConversationWriter(FakeOllama):
    async def conversation(self, **kwargs):
        self.calls.append(kwargs)
        return "[REFERENCE USE]\n<Picture 1> defines the subject.\n\n[SCENE]\nThe visible subject turns toward camera."


class RepairingMultimodalWriter(FakeOllama):
    async def conversation(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return "[SCENE]\n[specify what is visible]"
        return "[REFERENCE USE]\n<Picture 1> defines the subject.\n\n[SCENE]\nA corrected visible subject."


class BrokenRepairMultimodalWriter(RepairingMultimodalWriter):
    async def conversation(self, **kwargs):
        self.calls.append(kwargs)
        return "[SCENE]\n[specify what is visible]"


class LowercaseReferenceWriter(FakeOllama):
    async def conversation(self, **kwargs):
        self.calls.append(kwargs)
        return "[REFERENCE USE]\n<picture 1> defines the subject.\n\n[SCENE]\nThe subject turns toward camera."


def insert_asset(db: Database, uploads: Path, *, asset_id: str = "asset-1") -> None:
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "safe.png").write_bytes(b"real-image-bytes")
    db.insert_asset(
        {
            "id": asset_id,
            "kind": "image",
            "original_name": "astronaut.png",
            "stored_name": "safe.png",
            "mime": "image/png",
            "size_bytes": 16,
            "width": 1,
            "height": 1,
            "duration_seconds": None,
            "has_audio": None,
            "comfy_name": None,
            "created_at": utcnow(),
        }
    )


def test_director_prompt_uses_studio_reference_tokens_and_duration() -> None:
    request = DirectorRequest(
        mode=Mode.ref2va,
        prompt="Haz una escena emotiva en la luna",
        length=124,
        references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
    )

    prompt = build_h3_director_prompt(request, ["A young astronaut in a white suit."])

    assert "<Picture 1>" in prompt
    assert "Image1" not in prompt
    assert "5.17 seconds" in prompt
    assert "identity" in prompt
    assert "Haz una escena emotiva en la luna" in prompt


def test_text_prompt_forbids_reference_examples_when_no_media_is_attached() -> None:
    request = DirectorRequest(mode=Mode.text, prompt="A lunar discovery", length=124, references=[])
    prompt = build_h3_director_prompt(request, [])

    assert "ZERO media references" in prompt
    assert "Omit [REFERENCE USE]" in prompt
    assert "<Picture" not in prompt
    assert "<Video" not in prompt
    assert "<Audio" not in prompt


@pytest.mark.asyncio
async def test_director_retries_a_writer_that_invents_unattached_references(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    writer = RetryOllama()
    service = DirectorService(db=db, uploads_dir=tmp_path / "uploads", ollama=FakeOllama(), prompt_ollama=writer)

    response = await service.enhance(DirectorRequest(mode=Mode.text, prompt="A lunar discovery", references=[]))

    assert len(writer.calls) == 2
    assert "<Video 1>" not in response.enhanced_prompt
    assert "CORRECTION REQUIRED" in writer.calls[1]["prompt"]
    db.close()


@pytest.mark.asyncio
async def test_director_analyzes_once_then_reuses_cached_asset_analysis(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    ollama = FakeOllama()
    service = DirectorService(db=db, uploads_dir=uploads, ollama=ollama)
    request = DirectorRequest(
        mode=Mode.ref2va,
        prompt="Astronaut walks through a lunar base",
        length=124,
        references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
    )

    first = await service.enhance(request)
    second = await service.enhance(request)

    assert first.cached_analyses == 0
    assert second.cached_analyses == 1
    assert first.enhanced_prompt.startswith("[REFERENCE USE]")
    assert len(ollama.calls) == 3  # one visual analysis, two prompt generations
    db.close()


@pytest.mark.asyncio
async def test_director_uses_separate_vision_and_prompt_models(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    vision = FakeOllama()
    vision.model = "vision-model"
    writer = FakeOllama()
    writer.model = "writer-model"
    service = DirectorService(db=db, uploads_dir=uploads, ollama=vision, prompt_ollama=writer)
    request = DirectorRequest(
        mode=Mode.ref2va,
        prompt="Astronaut walks through a lunar base",
        references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
    )

    response = await service.enhance(request)

    assert len(vision.calls) == 1
    assert len(writer.calls) == 1
    assert response.model == "writer-model"
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_receives_studio_context_and_h3_guide(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    writer = FakeOllama()
    writer.model = "gemma4-e2b-h3-prompts"
    service = DirectorService(db=db, uploads_dir=tmp_path / "uploads", ollama=FakeOllama(), prompt_ollama=writer)

    response = await service.chat(
        PromptChatRequest(
            mode=Mode.first_frame,
            current_prompt="A restrained identity-preserving transformation",
            length=124,
            messages=[{"role": "user", "content": "Write the final prompt."}],
        )
    )

    assert response.model == "gemma4-e2b-h3-prompts"
    assert "5.17 seconds" in writer.calls[0]["system"]
    assert "production H3 prompting guide" in H3_PROMPTING_GUIDE
    assert "A restrained identity-preserving transformation" in writer.calls[0]["system"]
    assert "Write the final prompt" in writer.calls[0]["prompt"]
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_sends_attached_image_pixels_to_multimodal_gemma(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    writer = MultimodalConversationWriter()
    writer.model = "gemma4-e2b-h3-prompts-gpu"
    service = DirectorService(db=db, uploads_dir=uploads, ollama=FakeOllama(), prompt_ollama=writer)

    response = await service.chat(
        PromptChatRequest(
            mode=Mode.ref2va,
            current_prompt="Keep the attached subject recognizable.",
            references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
            messages=[{"role": "user", "content": "Write the final prompt from what you see."}],
        )
    )

    parts = writer.calls[0]["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "<Picture 1> — assigned role: identity"}
    assert parts[1]["type"] == "image_url"
    image_url = parts[1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert base64.b64decode(image_url.split(",", 1)[1]) == b"real-image-bytes"
    assert writer.calls[0]["messages"][-1] == {
        "role": "user",
        "content": "Write the final prompt from what you see.",
    }
    assert response.visual_references == 1
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_canonicalizes_reference_token_case_without_a_repair_pass(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    writer = LowercaseReferenceWriter()
    service = DirectorService(db=db, uploads_dir=uploads, ollama=FakeOllama(), prompt_ollama=writer)

    response = await service.chat(
        PromptChatRequest(
            mode=Mode.ref2va,
            references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
            messages=[{"role": "user", "content": "Write the final prompt."}],
        )
    )

    assert "<Picture 1>" in response.message
    assert "<picture 1>" not in response.message
    assert len(writer.calls) == 1
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_rejects_an_unknown_visual_asset(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    service = DirectorService(
        db=db,
        uploads_dir=tmp_path / "uploads",
        ollama=FakeOllama(),
        prompt_ollama=MultimodalConversationWriter(),
    )

    with pytest.raises(DirectorError, match="Reference not found"):
        await service.chat(
            PromptChatRequest(
                mode=Mode.ref2va,
                references=[ReferenceInput(asset_id="missing", kind="image", role="identity")],
                messages=[{"role": "user", "content": "Describe what you see."}],
            )
        )
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_rejects_unknown_or_mismatched_metadata_only_assets(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    service = DirectorService(
        db=db,
        uploads_dir=uploads,
        ollama=FakeOllama(),
        prompt_ollama=MultimodalConversationWriter(),
    )

    with pytest.raises(DirectorError, match="Reference not found"):
        await service.chat(
            PromptChatRequest(
                mode=Mode.ref2va,
                references=[ReferenceInput(asset_id="missing", kind="video", role="motion")],
                messages=[{"role": "user", "content": "Use the clip role."}],
            )
        )
    with pytest.raises(DirectorError, match="kind does not match"):
        await service.chat(
            PromptChatRequest(
                mode=Mode.ref2va,
                references=[ReferenceInput(asset_id="asset-1", kind="video", role="motion")],
                messages=[{"role": "user", "content": "Use the clip role."}],
            )
        )
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_rejects_excessive_aggregate_image_bytes(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    with (uploads / "safe.png").open("r+b") as stream:
        stream.truncate(65 * 1024 * 1024)
    service = DirectorService(
        db=db,
        uploads_dir=uploads,
        ollama=FakeOllama(),
        prompt_ollama=MultimodalConversationWriter(),
    )

    with pytest.raises(DirectorError, match="64 MB"):
        await service.chat(
            PromptChatRequest(
                mode=Mode.ref2va,
                references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
                messages=[{"role": "user", "content": "Inspect this image."}],
            )
        )
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_reattaches_images_during_repair_and_revalidates(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    writer = RepairingMultimodalWriter()
    service = DirectorService(db=db, uploads_dir=uploads, ollama=FakeOllama(), prompt_ollama=writer)
    request = PromptChatRequest(
        mode=Mode.ref2va,
        references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
        messages=[{"role": "user", "content": "Write the final prompt."}],
    )

    response = await service.chat(request)

    assert len(writer.calls) == 2
    repair_parts = writer.calls[1]["messages"][0]["content"]
    assert any(part.get("type") == "image_url" for part in repair_parts)
    assert "corrected visible subject" in response.message
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_rejects_an_invalid_multimodal_repair(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    uploads = tmp_path / "uploads"
    insert_asset(db, uploads)
    service = DirectorService(
        db=db,
        uploads_dir=uploads,
        ollama=FakeOllama(),
        prompt_ollama=BrokenRepairMultimodalWriter(),
    )

    with pytest.raises(DirectorError, match="could not obey"):
        await service.chat(
            PromptChatRequest(
                mode=Mode.ref2va,
                references=[ReferenceInput(asset_id="asset-1", kind="image", role="identity")],
                messages=[{"role": "user", "content": "Write the final prompt."}],
            )
        )
    db.close()


@pytest.mark.asyncio
async def test_prompt_chat_repairs_an_unnecessary_refusal(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    writer = RefusalThenPromptOllama()
    service = DirectorService(db=db, uploads_dir=tmp_path / "uploads", ollama=FakeOllama(), prompt_ollama=writer)

    response = await service.chat(
        PromptChatRequest(
            mode=Mode.text,
            messages=[
                {
                    "role": "user",
                    "content": "Write an H3 prompt for a fictional adult fashion transformation.",
                }
            ],
        )
    )

    assert len(writer.calls) == 2
    assert "unnecessary refusal" in writer.calls[1]["prompt"]
    assert not response.message.startswith("I'm sorry")
    assert "adult fashion model" in response.message
    db.close()


@pytest.mark.asyncio
async def test_director_rejects_unknown_assets_without_reading_arbitrary_paths(tmp_path: Path) -> None:
    db = Database(tmp_path / "studio.sqlite3")
    service = DirectorService(db=db, uploads_dir=tmp_path / "uploads", ollama=FakeOllama())
    request = DirectorRequest(
        mode=Mode.ref2va,
        prompt="A scene",
        references=[ReferenceInput(asset_id="missing", kind="image", role="identity")],
    )

    with pytest.raises(DirectorError, match="Reference not found"):
        await service.enhance(request)
    db.close()


def test_director_api_returns_preview_without_mutating_the_prompt(client, app) -> None:
    class FakeDirector:
        async def enhance(self, request):
            from app.schemas import DirectorResponse

            return DirectorResponse(
                original_prompt=request.prompt,
                enhanced_prompt="[SCENE]\nA stronger prompt.",
                analyses=[],
                cached_analyses=0,
                model="local-test-model",
            )

    app.state.director = FakeDirector()
    response = client.post(
        "/api/director/enhance",
        json={"mode": "text", "prompt": "simple idea", "length": 124, "references": []},
    )

    assert response.status_code == 200
    assert response.json()["original_prompt"] == "simple idea"
    assert response.json()["enhanced_prompt"] == "[SCENE]\nA stronger prompt."


def test_prompt_chat_api_returns_local_gemma_response(client, app) -> None:
    class FakeDirector:
        async def chat(self, request):
            from app.schemas import PromptChatResponse

            assert request.messages[-1].content == "Write a final H3 prompt"
            return PromptChatResponse(message="[SCENE]\nA controlled final shot.", model="gemma4-e2b-h3-prompts")

    app.state.director = FakeDirector()
    response = client.post(
        "/api/director/chat",
        json={
            "mode": "text",
            "current_prompt": "",
            "length": 124,
            "references": [],
            "messages": [{"role": "user", "content": "Write a final H3 prompt"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "[SCENE]\nA controlled final shot.",
        "model": "gemma4-e2b-h3-prompts",
        "visual_references": 0,
    }


def test_director_api_refuses_to_compete_with_an_active_render(client, app, comfy) -> None:
    client.post("/api/jobs", json={"mode": "text", "prompt": "rendering", "length": 124})
    response = client.post(
        "/api/director/enhance",
        json={"mode": "text", "prompt": "simple idea", "length": 124, "references": []},
    )
    assert response.status_code == 409
    assert "render" in response.json()["detail"].lower()


def test_prompt_chat_api_refuses_to_compete_with_an_active_render(client, app) -> None:
    class ShouldNotRunDirector:
        async def chat(self, request):
            raise AssertionError("Prompt Chat must not run during an H3 render")

    app.state.director = ShouldNotRunDirector()
    client.post("/api/jobs", json={"mode": "text", "prompt": "rendering", "length": 124})
    response = client.post(
        "/api/director/chat",
        json={
            "mode": "text",
            "current_prompt": "",
            "length": 124,
            "references": [],
            "messages": [{"role": "user", "content": "Write a final H3 prompt"}],
        },
    )
    assert response.status_code == 409
    assert "render" in response.json()["detail"].lower()


def test_creating_a_job_releases_prompt_gpu_first(client, app) -> None:
    class ReleasingDirector:
        def __init__(self) -> None:
            self.released = False

        async def release_prompt_model(self) -> None:
            self.released = True

    director = ReleasingDirector()
    app.state.director = director

    response = client.post("/api/jobs", json={"mode": "text", "prompt": "rendering", "length": 124})

    assert response.status_code == 201
    assert director.released is True


@pytest.mark.asyncio
async def test_ollama_autostart_uses_the_configured_model_store(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}
    readiness = iter([False, True])
    client = OllamaDirectorClient(
        base_url="http://127.0.0.1:11434",
        model="vision-model",
        timeout=30,
        autostart=True,
        executable="ollama.exe",
        models_dir=str(tmp_path / "models"),
    )

    async def ready() -> bool:
        return next(readiness)

    def popen(argv, **kwargs):
        captured.update({"argv": argv, **kwargs})
        return object()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(client, "_ready", ready)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr("app.services.director.asyncio.sleep", no_sleep)

    await client._ensure_ready()

    assert captured["env"]["OLLAMA_MODELS"] == str(tmp_path / "models")


@pytest.mark.asyncio
async def test_managed_prompt_client_starts_cuda_server_and_releases_it(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}
    readiness = iter([False, False, True, False])

    class Process:
        def __init__(self) -> None:
            self.terminated = False

        def poll(self):
            return None if not self.terminated else 0

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout=None) -> int:
            assert timeout == 10
            return 0

    process = Process()
    executable = tmp_path / "llama-server.exe"
    model_path = tmp_path / "gemma.gguf"
    mmproj_path = tmp_path / "mmproj.gguf"
    executable.write_bytes(b"exe")
    model_path.write_bytes(b"gguf")
    mmproj_path.write_bytes(b"projector")
    client = ManagedOpenAIDirectorClient(
        base_url="http://127.0.0.1:8083/v1",
        model="gemma4-e2b-h3-prompts-gpu",
        timeout=30,
        executable=str(executable),
        model_path=str(model_path),
        mmproj_path=str(mmproj_path),
        context_size=8192,
        gpu_layers=99,
        idle_seconds=180,
    )

    async def ready() -> bool:
        return next(readiness)

    def popen(argv, **kwargs):
        captured.update({"argv": argv, **kwargs})
        return process

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(client, "_ready", ready)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr("app.services.director.asyncio.sleep", no_sleep)

    await client._ensure_ready()

    assert captured["argv"][0] == str(tmp_path / "llama-server.exe")
    assert captured["argv"][captured["argv"].index("--gpu-layers") + 1] == "99"
    assert captured["argv"][captured["argv"].index("--ctx-size") + 1] == "8192"
    assert captured["argv"][captured["argv"].index("-m") + 1] == str(tmp_path / "gemma.gguf")
    assert captured["argv"][captured["argv"].index("--mmproj") + 1] == str(tmp_path / "mmproj.gguf")

    await client.release()

    assert process.terminated is True


@pytest.mark.asyncio
async def test_managed_prompt_client_requires_a_multimodal_projector(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "llama-server.exe"
    model_path = tmp_path / "gemma.gguf"
    executable.write_bytes(b"exe")
    model_path.write_bytes(b"gguf")
    client = ManagedOpenAIDirectorClient(
        base_url="http://127.0.0.1:8083/v1",
        model="gemma4-e2b-h3-prompts-gpu",
        timeout=30,
        executable=str(executable),
        model_path=str(model_path),
        mmproj_path="   ",
    )

    async def not_ready() -> bool:
        return False

    monkeypatch.setattr(client, "_ready", not_ready)
    with pytest.raises(DirectorError, match="projector"):
        await client._ensure_ready()


@pytest.mark.asyncio
async def test_managed_prompt_client_refuses_to_reuse_an_unowned_ready_server(monkeypatch, tmp_path: Path) -> None:
    client = ManagedOpenAIDirectorClient(
        base_url="http://127.0.0.1:8083/v1",
        model="gemma4-e2b-h3-prompts-gpu",
        timeout=30,
        executable=str(tmp_path / "llama-server.exe"),
        model_path=str(tmp_path / "gemma.gguf"),
        mmproj_path=str(tmp_path / "mmproj.gguf"),
    )

    async def ready() -> bool:
        return True

    monkeypatch.setattr(client, "_ready", ready)
    with pytest.raises(DirectorError, match="not owned"):
        await client._ensure_ready()


def test_studio_builds_the_prompt_writer_as_a_managed_gpu_client(settings, comfy) -> None:
    app = create_app(settings, comfy_client=comfy)

    assert isinstance(app.state.director.prompt_ollama, ManagedOpenAIDirectorClient)
    assert app.state.director.prompt_ollama.model == "gemma4-e2b-h3-prompts-gpu"
    assert app.state.director.prompt_ollama.idle_seconds == 180
    assert app.state.director.prompt_ollama.mmproj_path.endswith(
        "optional-mmproj.gguf"
    )


@pytest.mark.asyncio
async def test_managed_prompt_client_releases_after_idle_timeout(monkeypatch, tmp_path: Path) -> None:
    client = ManagedOpenAIDirectorClient(
        base_url="http://127.0.0.1:8083/v1",
        model="gemma4-e2b-h3-prompts-gpu",
        timeout=30,
        executable=str(tmp_path / "llama-server.exe"),
        model_path=str(tmp_path / "gemma.gguf"),
        mmproj_path=str(tmp_path / "mmproj.gguf"),
        idle_seconds=0.01,
    )
    released = asyncio.Event()

    async def release() -> None:
        released.set()

    monkeypatch.setattr(client, "release", release)

    await client.unload()
    await asyncio.wait_for(released.wait(), timeout=1)

    assert released.is_set()
