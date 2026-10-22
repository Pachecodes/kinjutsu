"""Best-effort progress feed from the ComfyUI websocket.

Completion is always decided by the polling watcher in `jobs.py`; this listener
only makes the progress bar honest while a render is running. If the socket
never connects the UI falls back to elapsed-versus-estimate, which is why
nothing here is allowed to raise into the app.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

logger = logging.getLogger("h3studio.progress")

RECONNECT_MIN = 2.0
RECONNECT_MAX = 30.0


def handle_message(service: Any, payload: dict[str, Any]) -> None:
    """Route one decoded Comfy websocket message onto the job service."""
    message_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(data, dict):
        return

    if message_type == "kj_preview_override":
        image = data.get("image")
        mime = data.get("mime")
        if not isinstance(image, str) or not image or not isinstance(mime, str):
            return
        service.apply_preview(
            str(data.get("node_id") or ""),
            image,
            mime,
            int(data.get("w") or 0),
            int(data.get("h") or 0),
            int(data.get("step") or 0),
            int(data.get("total") or 0),
        )
        return

    prompt_id = data.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        return

    if message_type == "progress":
        try:
            value = float(data.get("value", 0))
            maximum = float(data.get("max", 0))
        except (TypeError, ValueError):
            return
        service.apply_progress(prompt_id, value, maximum)
    elif message_type == "executing":
        node = data.get("node")
        service.apply_executing(prompt_id, str(node) if node is not None else None)
    elif message_type == "execution_error":
        detail = data.get("exception_message") or data.get("exception_type") or "ComfyUI execution error"
        node = data.get("node_type")
        service.apply_error(prompt_id, f"{node}: {detail}" if node else str(detail))


async def run_progress_listener(service: Any, ws_url: str, client_id: str) -> None:
    """Keep a websocket open to Comfy, reconnecting with backoff, forever."""
    try:
        import websockets
    except ImportError:  # pragma: no cover - websockets is a declared dependency
        logger.info("websockets is not installed; progress will fall back to estimates")
        return

    url = f"{ws_url}?clientId={client_id}"
    delay = RECONNECT_MIN
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, max_size=8 * 1024 * 1024) as socket:
                logger.info("progress websocket connected")
                delay = RECONNECT_MIN
                async for raw in socket:
                    if not isinstance(raw, str):
                        continue  # binary previews are not used by the Studio
                    try:
                        payload = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(payload, dict):
                        with contextlib.suppress(Exception):
                            handle_message(service, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never let the socket kill the app
            logger.debug("progress websocket unavailable (%s); retrying in %.0fs", exc, delay)
        await asyncio.sleep(delay)
        delay = min(RECONNECT_MAX, delay * 2)
