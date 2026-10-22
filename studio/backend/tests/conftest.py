from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.comfy import ComfyError, QueueSnapshot
from app.config import REPO_ROOT, Settings, settings_from_env
from app.main import create_app

CONTRACT = json.loads((REPO_ROOT / "docs" / "contracts" / "h3-node-contracts.json").read_text("utf-8-sig"))
FIXTURES_DIR = REPO_ROOT / "docs" / "fixtures"

# Nodes the Studio requires that the shipped contract does not enumerate,
# because the capture only covered the H3-relevant subset.
EXTRA_LIVE_NODES = {"PreviewImage": {"input": {"required": {}}}}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text("utf-8-sig"))


class FakeComfy:
    """In-memory stand-in for the H3 lab Comfy instance."""

    base_url = "http://127.0.0.1:8216"
    ws_url = "ws://127.0.0.1:8216/ws"

    def __init__(self, *, online: bool = True) -> None:
        self.online = online
        self.running: list[str] = []
        self.pending: list[str] = []
        self.histories: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}
        self.submitted: list[dict[str, Any]] = []
        self.uploaded: list[dict[str, Any]] = []
        self.interrupt_calls = 0
        self.free_memory_calls = 0
        self.deleted: list[str] = []
        self.next_prompt_id = "prompt-1"
        self.closed = False
        #: When set, /prompt rejects the workflow with this message.
        self.submit_error: str | None = None

    def _guard(self) -> None:
        if not self.online:
            raise ComfyError("ComfyUI unreachable at http://127.0.0.1:8216")

    async def object_info(self) -> dict[str, Any]:
        self._guard()
        return {**CONTRACT, **EXTRA_LIVE_NODES}

    async def queue(self) -> QueueSnapshot:
        self._guard()
        return QueueSnapshot(running=list(self.running), pending=list(self.pending))

    async def submit(self, prompt: dict[str, Any], client_id: str) -> str:
        self._guard()
        if self.submit_error:
            raise ComfyError(f"ComfyUI rejected the workflow: {self.submit_error}")
        self.submitted.append({"prompt": prompt, "client_id": client_id})
        prompt_id = self.next_prompt_id
        self.pending.append(prompt_id)
        return prompt_id

    async def history(self, prompt_id: str) -> dict[str, Any] | None:
        self._guard()
        return self.histories.get(prompt_id)

    async def interrupt(self) -> None:
        self._guard()
        self.interrupt_calls += 1
        self.running.clear()

    async def delete_queued(self, prompt_id: str) -> None:
        self._guard()
        self.deleted.append(prompt_id)
        if prompt_id in self.pending:
            self.pending.remove(prompt_id)

    async def free_memory(self) -> None:
        self._guard()
        self.free_memory_calls += 1

    async def upload_input(self, *, filename: str, content: bytes, content_type: str, subfolder: str) -> str:
        self._guard()
        self.uploaded.append({"filename": filename, "content_type": content_type, "subfolder": subfolder})
        return f"{subfolder}/{filename}" if subfolder else filename

    async def download_output(self, *, filename: str, subfolder: str, folder_type: str) -> bytes:
        self._guard()
        key = f"{subfolder}/{filename}" if subfolder else filename
        if key not in self.files:
            raise ComfyError(f"missing output {key}")
        return self.files[key]

    async def aclose(self) -> None:
        self.closed = True

    # -- helpers used by tests --------------------------------------------
    def complete(self, prompt_id: str, *, filename: str = "take_00001.mp4", content: bytes = b"fake-mp4") -> None:
        self.files[filename] = content
        if prompt_id in self.pending:
            self.pending.remove(prompt_id)
        if prompt_id in self.running:
            self.running.remove(prompt_id)
        self.histories[prompt_id] = {
            "status": {"status_str": "success", "completed": True, "messages": []},
            "outputs": {"14": {"videos": [{"filename": filename, "subfolder": "", "type": "output"}]}},
        }

    def fail(self, prompt_id: str, message: str = "CUDA out of memory") -> None:
        self.histories[prompt_id] = {
            "status": {
                "status_str": "error",
                "completed": False,
                "messages": [
                    ["execution_error", {"node_type": "SamplerCustomAdvanced", "exception_message": message}]
                ],
            },
            "outputs": {},
        }


@pytest.fixture
def comfy() -> FakeComfy:
    return FakeComfy()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_from_env(
        data_dir=tmp_path / "data",
        frontend_dist=tmp_path / "dist",
        comfy_url="http://127.0.0.1:8216",
        poll_interval=0.05,
        capability_ttl=0.0,
        dev_origins="",
    )


@pytest.fixture
def app(settings: Settings, comfy: FakeComfy):
    return create_app(settings, comfy_client=comfy)


@pytest.fixture
def client(app) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def png_bytes() -> bytes:
    """A real 1x1 PNG so magic-byte sniffing passes."""
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
