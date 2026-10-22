"""HTTP surface: health, capability honesty, uploads, jobs, outputs, SPA fallback."""

from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings_from_env
from app.main import create_app
from app.workflow.constants import FL2VA_INT8, NODE_EASYCACHE, NODE_SOL_PATCH
from tests.conftest import CONTRACT, FakeComfy

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def wait_until(fn, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("condition never became true")


# --- health / config ------------------------------------------------------
def test_health_reports_ok_when_comfy_answers(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["comfy_online"] is True
    assert body["comfy_url"] == "http://127.0.0.1:8216"
    assert body["active_jobs"] == 0
    assert body["version"]


def test_active_take_preview_endpoint_returns_latest_tiny_vae_frame(client: TestClient, app) -> None:
    app.state.jobs.apply_preview("101", "YWJj", "image/jpeg", 352, 640, 3, 20)
    response = client.get("/api/preview")
    assert response.status_code == 200
    assert response.json() == {
        "data_url": "data:image/jpeg;base64,YWJj",
        "width": 352,
        "height": 640,
        "step": 3,
        "total": 20,
    }


def test_health_is_degraded_but_answers_when_comfy_is_down(app, comfy: FakeComfy) -> None:
    comfy.online = False
    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["comfy_online"] is False


def test_config_exposes_presets_defaults_and_measured_basis(client: TestClient) -> None:
    body = client.get("/api/config").json()
    preset_ids = [preset["id"] for preset in body["presets"]]
    assert preset_ids == [
        "fasth3-omni-scenes",
        "character-swap-playground",
        "character-swap-hd-turbo8",
        "character-swap-v11",
        "10eros-motion6", "10eros-sde6", "10eros-custom7",
        "fasth3-v2-8step-experimental",
        "taomate-h3-3step-experimental",
        "fast-preview-5s",
        "balanced-10s",
        "fast-final-trt-5s",
        "lightx2v8-creator-5s",
        "identity-locked",
        "lip-sync",
        "performance-transfer",
        "premium-vertical-5s",
        "final-15s",
    ]
    assert body["defaults"]["length"] == 124
    assert "608x352" in body["estimate_basis"]
    assert body["method_profiles"]["easycache"]["measured_ssim"] == 0.914
    assert body["upload_limits"]["image_mb"] == 32
    lightx2v8 = next(preset for preset in body["presets"] if preset["id"] == "lightx2v8-creator-5s")
    assert lightx2v8["patch"]["steps"] == 8
    assert lightx2v8["patch"]["sampler_name"] == "er_sde"
    assert lightx2v8["patch"]["scheduler"] == "beta"
    assert lightx2v8["patch"]["weights"] == "int8"
    assert lightx2v8["patch"]["lora_chain"] == [
        {
            "name": "minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors",
            "strength": 1.0,
        }
    ]


def test_every_preset_patch_is_a_valid_partial_request(client: TestClient) -> None:
    from app.schemas import GenerationRequest

    for preset in client.get("/api/presets").json()["presets"]:
        request = GenerationRequest.model_validate({"mode": preset["suggests_mode"] or "text", "prompt": "x", **preset["patch"]})
        assert request.length > 0
        if preset["id"].startswith("10eros-") or preset["patch"]["method"] in {"fast_h3_v2_8step", "taomate_3step", "fast_h3_omni_8step"}:
            assert preset["estimate_seconds"] is None
        else:
            assert preset["estimate_seconds"] > 0
        assert preset["recipe"] and preset["caveats"]


# --- capabilities ---------------------------------------------------------
def test_capabilities_are_live_when_comfy_answers(client: TestClient) -> None:
    body = client.get("/api/capabilities").json()
    assert body["source"] == "live"
    assert body["comfy_online"] is True
    assert all(mode["available"] for mode in body["modes"]), body["modes"]
    assert {method["id"] for method in body["methods"] if method["available"]} == {
        "baseline",
        "easycache",
        "w4a8_lightx2v",
        "w4a8_latent2x_refine3",
        "ref2va_vsa",
        "sage",
        "sol",
    }
    exposed_loras = {lora["name"] for lora in body["loras"]}
    assert "fasth3_vsa_gate.safetensors" not in exposed_loras
    assert "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors" not in exposed_loras
    assert body["weights"] == {"int8": True, "gguf_q3km": True, "pinkcherry_v03": True, "erosmax_beta4": False, "erosmax_beta5": False}
    assert next(
        lora for lora in body["loras"]
        if lora["name"] == "minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors"
    ) == {
        "name": "minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors",
        "label": "LightX2V Turbo 4-step v1.1 (768p)",
        "recommended_strength": 1.0,
        "checkpoint": "fl2va",
        "note": "Official FL2VA four-step acceleration LoRA. Select Quality, set 4 steps and use the simple scheduler.",
    }
    assert [option["frames"] for option in body["preferred_lengths"]] == [124, 175, 192, 243, 362]
    assert body["limits"]["max_ref_total"] == 12


def test_capabilities_fall_back_honestly_when_comfy_is_offline(app, comfy: FakeComfy) -> None:
    comfy.online = False
    with TestClient(app) as client:
        body = client.get("/api/capabilities").json()
    assert body["source"] == "contract-fallback"
    assert body["comfy_online"] is False
    assert body["error"]
    assert not any(mode["available"] for mode in body["modes"])
    assert not any(method["available"] for method in body["methods"])
    assert body["weights"] == {"int8": False, "gguf_q3km": False, "pinkcherry_v03": False, "erosmax_beta4": False, "erosmax_beta5": False}


def test_live_capabilities_expose_erosmax_beta5_when_unetloader_lists_it(app, comfy: FakeComfy) -> None:
    enriched = {name: spec for name, spec in CONTRACT.items()}
    unet = enriched["UNETLoader"]
    options = [*unet["input"]["required"]["unet_name"][0], "h3ErosMax_beta5.safetensors"]
    enriched["UNETLoader"] = {
        **unet,
        "input": {"required": {**unet["input"]["required"], "unet_name": [options]}},
    }

    async def object_info():
        return enriched

    comfy.object_info = object_info  # type: ignore[assignment]
    with TestClient(app) as client:
        weights = client.get("/api/capabilities?refresh=true").json()["weights"]
    assert weights["erosmax_beta5"] is True


def test_a_missing_patch_node_disables_only_that_method(app, comfy: FakeComfy) -> None:
    stripped = {name: spec for name, spec in CONTRACT.items() if name != NODE_EASYCACHE}

    async def object_info():
        return stripped

    comfy.object_info = object_info  # type: ignore[assignment]
    with TestClient(app) as client:
        methods = {m["id"]: m for m in client.get("/api/capabilities").json()["methods"]}
    assert methods["easycache"]["available"] is False
    assert NODE_EASYCACHE in methods["easycache"]["unavailable_reason"]
    assert methods["baseline"]["available"] is True
    assert methods["sol"]["available"] is True


def test_missing_sol_node_is_reported(app, comfy: FakeComfy) -> None:
    stripped = {name: spec for name, spec in CONTRACT.items() if name != NODE_SOL_PATCH}

    async def object_info():
        return stripped

    comfy.object_info = object_info  # type: ignore[assignment]
    with TestClient(app) as client:
        methods = {m["id"]: m for m in client.get("/api/capabilities").json()["methods"]}
    assert methods["sol"]["available"] is False
    assert methods["easycache"]["available"] is True


def test_a_missing_checkpoint_disables_the_frame_modes(app, comfy: FakeComfy) -> None:
    trimmed = {name: spec for name, spec in CONTRACT.items()}
    unet = trimmed["UNETLoader"]
    options = [n for n in unet["input"]["required"]["unet_name"][0] if n != FL2VA_INT8]
    trimmed["UNETLoader"] = {
        **unet,
        "input": {"required": {**unet["input"]["required"], "unet_name": [options]}},
    }

    async def object_info():
        return trimmed

    comfy.object_info = object_info  # type: ignore[assignment]
    with TestClient(app) as client:
        modes = {m["id"]: m for m in client.get("/api/capabilities").json()["modes"]}
    assert modes["text"]["available"] is False
    assert "FL2VA" in modes["text"]["unavailable_reason"]
    assert modes["ref2va"]["available"] is True


# --- validation endpoint --------------------------------------------------
def test_validate_normalizes_and_estimates(client: TestClient) -> None:
    body = client.post(
        "/api/validate",
        json={"mode": "text", "prompt": "a beach", "length": 200, "width": 1000, "height": 570},
    ).json()
    assert body["ok"] is True
    assert body["normalized"]["length"] == 192
    assert body["normalized"]["width"] == 992
    assert body["estimate_seconds"] > 0
    assert "608x352" in body["estimate_basis"]
    assert {issue["code"] for issue in body["issues"]} >= {"length_snapped", "dimensions_snapped"}


def test_validate_reports_auto_continuity_plan(client: TestClient) -> None:
    body = client.post(
        "/api/validate",
        json={
            "mode": "text",
            "prompt": "one long continuous shot",
            "length": 362,
            "width": 1024,
            "height": 576,
            "continuity": {"auto_split": True, "window": "auto", "pin_frames": "22"},
        },
    ).json()
    assert body["ok"] is True
    assert body["continuity_plan"]["split"] is True
    assert body["continuity_plan"]["window_count"] == 3
    assert body["continuity_plan"]["delivered_frames"] == 362


def test_validate_prices_the_extra_overlap_frames(client: TestClient) -> None:
    base_request = {
        "mode": "text",
        "prompt": "one long continuous shot",
        "length": 362,
        "width": 1024,
        "height": 576,
    }
    single = client.post("/api/validate", json={**base_request, "continuity": {"auto_split": False}}).json()
    chained = client.post("/api/validate", json={**base_request, "continuity": {"auto_split": True}}).json()
    assert chained["estimate_seconds"] > single["estimate_seconds"]


def test_validate_reports_errors_without_creating_anything(client: TestClient) -> None:
    body = client.post("/api/validate", json={"mode": "ref2va", "prompt": "nothing"}).json()
    assert body["ok"] is False
    assert "references_required" in {issue["code"] for issue in body["issues"]}
    assert client.get("/api/jobs").json()["total"] == 0


# --- uploads --------------------------------------------------------------
def test_upload_returns_a_uuid_name_and_lists(client: TestClient, png_bytes: bytes) -> None:
    response = client.post("/api/assets", files={"file": ("shot.png", png_bytes, "image/png")})
    assert response.status_code == 201
    asset = response.json()
    assert asset["kind"] == "image"
    assert asset["original_name"] == "shot.png"
    assert asset["stored_name"] != "shot.png"
    assert asset["url"] == f"/api/assets/{asset['id']}/file"

    listed = client.get("/api/assets").json()
    assert [item["id"] for item in listed] == [asset["id"]]


def test_upload_rejects_a_disguised_file(client: TestClient) -> None:
    response = client.post("/api/assets", files={"file": ("evil.png", b"<script>", "image/png")})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mime_mismatch"


def test_upload_rejects_an_unsupported_type(client: TestClient) -> None:
    response = client.post("/api/assets", files={"file": ("run.exe", b"MZ\x90\x00", "application/exe")})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "extension_not_allowed"


def test_upload_size_cap_is_enforced_by_the_api(tmp_path: Path, comfy: FakeComfy, png_bytes: bytes) -> None:
    settings = settings_from_env(
        data_dir=tmp_path / "data", frontend_dist=tmp_path / "dist", max_image_mb=0, dev_origins=""
    )
    with TestClient(create_app(settings, comfy_client=comfy)) as client:
        response = client.post("/api/assets", files={"file": ("shot.png", png_bytes, "image/png")})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "file_too_large"


def test_asset_file_is_served_and_deleted(client: TestClient, png_bytes: bytes) -> None:
    asset = client.post("/api/assets", files={"file": ("shot.png", png_bytes, "image/png")}).json()
    served = client.get(asset["url"])
    assert served.status_code == 200
    assert served.content == png_bytes

    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert client.get(asset["url"]).status_code == 404
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 404


def test_unknown_asset_is_404(client: TestClient) -> None:
    assert client.get("/api/assets/deadbeef/file").status_code == 404


# --- jobs end to end ------------------------------------------------------
def test_full_take_lifecycle(client: TestClient, comfy: FakeComfy) -> None:
    created = client.post(
        "/api/jobs",
        json={"mode": "text", "prompt": "a lighthouse", "length": 124, "seed": 7, "title": "Lighthouse"},
    )
    assert created.status_code == 201
    job = created.json()["job"]
    assert job["status"] == "queued"
    assert job["seed"] == 7

    comfy.complete("prompt-1", content=b"MP4DATA")
    finished = wait_until(
        lambda: (lambda body: body if body["status"] == "completed" else None)(
            client.get(f"/api/jobs/{job['id']}").json()
        )
    )
    assert finished["progress"] == 1.0
    output = finished["outputs"][0]

    played = client.get(output["url"])
    assert played.status_code == 200
    assert played.content == b"MP4DATA"
    assert played.headers["content-type"] == "video/mp4"

    downloaded = client.get(f"/api/outputs/{output['id']}/download")
    assert downloaded.status_code == 200
    assert "attachment" in downloaded.headers["content-disposition"]


def test_reuse_returns_the_exact_recipe(client: TestClient, comfy: FakeComfy) -> None:
    created = client.post(
        "/api/jobs",
        json={"mode": "text", "prompt": "a lighthouse", "length": 175, "seed": 4242, "steps": 18},
    ).json()["job"]

    same_seed = client.post(f"/api/jobs/{created['id']}/reuse", json={"keep_seed": True}).json()
    assert same_seed["seed"] == 4242
    assert same_seed["length"] == 175
    assert same_seed["steps"] == 18

    reroll = client.post(f"/api/jobs/{created['id']}/reuse", json={"keep_seed": False}).json()
    assert reroll["seed"] is None
    assert reroll["prompt"] == "a lighthouse"


def test_invalid_job_returns_422_with_issues(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"mode": "ref2va", "prompt": "no references"})
    assert response.status_code == 422
    codes = {issue["code"] for issue in response.json()["issues"]}
    assert "references_required" in codes


def test_cancel_endpoint_reports_conflict_for_finished_takes(client: TestClient, comfy: FakeComfy) -> None:
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    comfy.complete("prompt-1")
    wait_until(lambda: client.get(f"/api/jobs/{job['id']}").json()["status"] == "completed")
    response = client.post(f"/api/jobs/{job['id']}/cancel")
    assert response.status_code == 409


def test_cancel_endpoint_cancels_a_queued_take(client: TestClient, comfy: FakeComfy) -> None:
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    comfy.pending = ["prompt-1"]
    response = client.post(f"/api/jobs/{job['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert comfy.interrupt_calls == 0


def test_hide_unhide_and_delete_via_the_api(client: TestClient, comfy: FakeComfy) -> None:
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    comfy.complete("prompt-1")
    wait_until(lambda: client.get(f"/api/jobs/{job['id']}").json()["status"] == "completed")

    assert client.patch(f"/api/jobs/{job['id']}", json={"hidden": True}).json()["hidden"] is True
    assert client.get("/api/jobs").json()["total"] == 0
    assert client.get("/api/jobs", params={"include_hidden": True}).json()["total"] == 1

    assert client.patch(f"/api/jobs/{job['id']}", json={"hidden": False}).json()["hidden"] is False
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_running_take_cannot_be_deleted_via_the_api(client: TestClient) -> None:
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 409


def test_events_and_workflow_are_available_for_the_advanced_drawer(client: TestClient) -> None:
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    events = client.get(f"/api/jobs/{job['id']}/events").json()["events"]
    assert any("Queued" in event["message"] for event in events)

    workflow = client.get(f"/api/jobs/{job['id']}/workflow").json()["workflow"]
    assert workflow["1"]["class_type"] == "UNETLoader"
    assert workflow["14"]["class_type"] == "SaveVideo"


def test_events_use_the_same_created_at_key_as_every_other_model(client: TestClient) -> None:
    """The activity panel timestamps events by `created_at`; `ts` is storage-only."""
    job = client.post("/api/jobs", json={"mode": "text", "prompt": "x", "length": 124}).json()["job"]
    events = client.get(f"/api/jobs/{job['id']}/events").json()["events"]
    assert events
    for event in events:
        assert set(event) == {"id", "job_id", "level", "message", "created_at"}
        assert event["created_at"]


def test_unknown_job_routes_are_404(client: TestClient) -> None:
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.post("/api/jobs/nope/cancel").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404
    assert client.get("/api/jobs/nope/workflow").status_code == 404
    assert client.get("/api/outputs/nope/file").status_code == 404


# --- references through the API ------------------------------------------
def test_reference_upload_is_mirrored_into_comfy_on_submit(
    client: TestClient, comfy: FakeComfy, png_bytes: bytes
) -> None:
    asset = client.post("/api/assets", files={"file": ("akito.png", png_bytes, "image/png")}).json()
    created = client.post(
        "/api/jobs",
        json={
            "mode": "ref2va",
            "prompt": "<Picture 1> waves at the camera",
            "length": 124,
            "references": [{"asset_id": asset["id"], "kind": "image", "role": "identity"}],
        },
    )
    assert created.status_code == 201, created.text
    assert comfy.uploaded[0]["subfolder"] == "h3studio"
    assert comfy.uploaded[0]["filename"] == asset["stored_name"]
    graph = comfy.submitted[0]["prompt"]
    load_image = next(node for node in graph.values() if node["class_type"] == "LoadImage")
    assert load_image["inputs"]["image"] == f"h3studio/{asset['stored_name']}"


def test_audio_only_reference_is_refused_by_the_api(client: TestClient) -> None:
    response = client.post(
        "/api/validate",
        json={
            "mode": "ref2va",
            "prompt": "a voice",
            "references": [{"asset_id": "missing", "kind": "audio", "role": "voice"}],
        },
    )
    codes = {issue["code"] for issue in response.json()["issues"]}
    assert "audio_needs_visual" in codes


# --- SPA ------------------------------------------------------------------
def test_spa_reports_a_missing_build_instead_of_crashing(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 503
    assert "has not been built" in response.json()["detail"]


def test_spa_fallback_serves_index_for_deep_links(tmp_path: Path, comfy: FakeComfy) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>H3 Studio</title>", encoding="utf-8")
    (dist / "assets" / "main.js").write_text("console.log('hi')", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")

    settings: Settings = settings_from_env(data_dir=tmp_path / "data", frontend_dist=dist, dev_origins="")
    with TestClient(create_app(settings, comfy_client=comfy)) as client:
        assert "H3 Studio" in client.get("/").text
        assert "H3 Studio" in client.get("/gallery").text
        assert "H3 Studio" in client.get("/some/deep/link").text
        assert client.get("/assets/main.js").text == "console.log('hi')"
        assert client.get("/favicon.svg").text == "<svg/>"
        # API 404s stay API 404s - the SPA fallback must never swallow them.
        assert client.get("/api/not-a-route").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_spa_fallback_cannot_serve_files_outside_dist(tmp_path: Path, comfy: FakeComfy) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>H3 Studio</title>", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me", encoding="utf-8")

    settings = settings_from_env(data_dir=tmp_path / "data", frontend_dist=dist, dev_origins="")
    with TestClient(create_app(settings, comfy_client=comfy)) as client:
        for hostile in ("../secret.txt", "..%2fsecret.txt", "a/../../secret.txt"):
            response = client.get(f"/{hostile}")
            assert "do not serve me" not in response.text


# --- configuration safety -------------------------------------------------
def test_the_stable_comfy_service_can_never_be_targeted() -> None:
    with pytest.raises(ValueError, match="8215"):
        settings_from_env(comfy_url="http://127.0.0.1:8215")


def test_openapi_document_builds(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()
    assert schema["info"]["title"] == "MiniMax H3 Studio"
    assert "/api/jobs" in schema["paths"]
