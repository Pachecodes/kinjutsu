"""Thin async client for the H3 lab ComfyUI instance.

Only the endpoints the Studio actually needs. Every call is scoped to the
configured `comfy_url`, which `Settings` refuses to point at the stable
service on :8215.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class ComfyError(RuntimeError):
    """Comfy rejected a request or is unreachable."""


@dataclass(frozen=True)
class QueueSnapshot:
    running: list[str]
    pending: list[str]

    def position_of(self, prompt_id: str) -> int | None:
        if prompt_id in self.running:
            return 0
        if prompt_id in self.pending:
            return self.pending.index(prompt_id) + 1
        return None

    def contains(self, prompt_id: str) -> bool:
        return prompt_id in self.running or prompt_id in self.pending


class ComfyClientProtocol(Protocol):
    """Interface the worker depends on, so tests can substitute a fake."""

    base_url: str

    async def object_info(self) -> dict[str, Any]: ...
    async def system_stats(self) -> dict[str, Any]: ...
    async def queue(self) -> QueueSnapshot: ...
    async def submit(self, prompt: dict[str, Any], client_id: str) -> str: ...
    async def history(self, prompt_id: str) -> dict[str, Any] | None: ...
    async def interrupt(self) -> None: ...
    async def delete_queued(self, prompt_id: str) -> None: ...
    async def free_memory(self) -> None: ...
    async def upload_input(
        self, *, filename: str, content: bytes, content_type: str, subfolder: str
    ) -> str: ...
    async def download_output(self, *, filename: str, subfolder: str, folder_type: str) -> bytes: ...
    async def aclose(self) -> None: ...


def _prompt_ids(entries: Any) -> list[str]:
    ids: list[str] = []
    if not isinstance(entries, list):
        return ids
    for entry in entries:
        # Comfy queue entries are [number, prompt_id, prompt, extra_data, outputs]
        if isinstance(entry, list) and len(entry) >= 2 and isinstance(entry[1], str):
            ids.append(entry[1])
    return ids


class ComfyClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    @property
    def ws_url(self) -> str:
        scheme = "wss" if self.base_url.startswith("https") else "ws"
        host = self.base_url.split("://", 1)[-1]
        return f"{scheme}://{host}/ws"

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.get(path, **kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise ComfyError(f"ComfyUI unreachable at {self.base_url}: {exc}") from exc
        return response

    async def _post(self, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.post(path, **kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise ComfyError(f"ComfyUI unreachable at {self.base_url}: {exc}") from exc
        return response

    async def object_info(self) -> dict[str, Any]:
        response = await self._get("/object_info")
        if response.status_code != 200:
            raise ComfyError(f"/object_info returned HTTP {response.status_code}")
        return response.json()

    async def system_stats(self) -> dict[str, Any]:
        response = await self._get("/system_stats")
        if response.status_code != 200:
            raise ComfyError(f"/system_stats returned HTTP {response.status_code}")
        return response.json()

    async def queue(self) -> QueueSnapshot:
        response = await self._get("/queue")
        if response.status_code != 200:
            raise ComfyError(f"/queue returned HTTP {response.status_code}")
        payload = response.json()
        return QueueSnapshot(
            running=_prompt_ids(payload.get("queue_running")),
            pending=_prompt_ids(payload.get("queue_pending")),
        )

    async def submit(self, prompt: dict[str, Any], client_id: str) -> str:
        response = await self._post("/prompt", json={"prompt": prompt, "client_id": client_id})
        if response.status_code != 200:
            detail = response.text[:600]
            try:
                payload = response.json()
                detail = json.dumps(payload.get("error", payload))[:600]
            except ValueError:
                pass
            raise ComfyError(f"ComfyUI rejected the workflow: {detail}")
        payload = response.json()
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str):
            raise ComfyError("ComfyUI did not return a prompt_id")
        return prompt_id

    async def history(self, prompt_id: str) -> dict[str, Any] | None:
        response = await self._get(f"/history/{prompt_id}")
        if response.status_code != 200:
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        return payload.get(prompt_id)

    async def interrupt(self) -> None:
        response = await self._post("/interrupt")
        if response.status_code not in (200, 204):
            raise ComfyError(f"/interrupt returned HTTP {response.status_code}")

    async def delete_queued(self, prompt_id: str) -> None:
        response = await self._post("/queue", json={"delete": [prompt_id]})
        if response.status_code not in (200, 204):
            raise ComfyError(f"/queue delete returned HTTP {response.status_code}")

    async def free_memory(self) -> None:
        """Unload cached models and release VRAM without interrupting work."""
        response = await self._post("/free", json={"unload_models": True, "free_memory": True})
        if response.status_code not in (200, 204):
            raise ComfyError(f"/free returned HTTP {response.status_code}")

    async def upload_input(self, *, filename: str, content: bytes, content_type: str, subfolder: str) -> str:
        """Mirror a Studio upload into the Comfy input folder.

        Returns the name Comfy expects in LoadImage/LoadVideo/LoadAudio, which
        includes the subfolder when one is used.
        """
        files = {"image": (filename, content, content_type)}
        data = {"type": "input", "overwrite": "true", "subfolder": subfolder}
        response = await self._post("/upload/image", files=files, data=data)
        if response.status_code not in (200, 201):
            raise ComfyError(f"ComfyUI rejected the upload ({response.status_code}): {response.text[:300]}")
        payload = response.json()
        name = payload.get("name") or filename
        returned_subfolder = payload.get("subfolder") or ""
        return f"{returned_subfolder}/{name}" if returned_subfolder else name

    async def download_output(self, *, filename: str, subfolder: str, folder_type: str) -> bytes:
        response = await self._get(
            "/view", params={"filename": filename, "subfolder": subfolder, "type": folder_type}
        )
        if response.status_code != 200:
            raise ComfyError(f"Could not fetch output {filename} (HTTP {response.status_code})")
        return response.content
