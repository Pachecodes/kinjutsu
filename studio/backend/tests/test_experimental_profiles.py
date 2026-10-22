from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from app.capabilities import build_capabilities
from app.main import create_app
from app.schemas import GenerationRequest, MethodId, Mode
from app.workflow import constants as C
from app.workflow.builder import build_workflow
from tests.conftest import CONTRACT, FakeComfy


def _add_combo(info: dict, node: str, input_name: str, value: str) -> None:
    entry = info[node]["input"]["required"][input_name]
    if isinstance(entry[0], list):
        entry[0].append(value)
    else:
        entry[1].setdefault("options", []).append(value)


def experimental_contract() -> dict:
    info = deepcopy(CONTRACT)
    for node in ("ModelAttentionBackend", "BlockSparseAttention", "MiniMaxH3SigmaShift"):
        info.setdefault(node, {"input": {"required": {}}})
    _add_combo(info, "UNETLoader", "unet_name", C.FASTH3_V2)
    _add_combo(info, "LoraLoaderModelOnly", "lora_name", C.TAOMATE_3STEP_LORA)
    return info


class ExperimentalFake(FakeComfy):
    base_url = "http://127.0.0.1:8226"
    ws_url = "ws://127.0.0.1:8226/ws"

    async def object_info(self) -> dict:
        self._guard()
        return experimental_contract()


def test_experimental_profiles_are_capability_gated_by_exact_nodes_and_files() -> None:
    caps = build_capabilities(
        experimental_contract(),
        comfy_url="http://127.0.0.1:8226",
        comfy_online=True,
        source="live",
    )
    methods = {method.id: method for method in caps.methods}
    assert methods[MethodId.fast_h3_v2_8step.value].available is True
    assert methods[MethodId.taomate_3step.value].available is True

    missing = experimental_contract()
    del missing["BlockSparseAttention"]
    gated = build_capabilities(missing, comfy_url="http://127.0.0.1:8226", comfy_online=True, source="live")
    methods = {method.id: method for method in gated.methods}
    assert methods[MethodId.fast_h3_v2_8step.value].available is False
    assert "BlockSparseAttention" in (methods[MethodId.fast_h3_v2_8step.value].unavailable_reason or "")


def test_fast_h3_v2_workflow_uses_official_atomic_recipe() -> None:
    request = GenerationRequest(
        mode=Mode.text,
        prompt="A calm portrait with subtle motion and synchronized room tone.",
        width=1344,
        height=768,
        length=124,
        steps=8,
        sampler_name="res_multistep",
        scheduler="simple",
        method=MethodId.fast_h3_v2_8step,
    )
    graph = build_workflow(request, {}, seed=42, filename_prefix="test").prompt
    assert graph["1"]["inputs"]["unet_name"] == C.FASTH3_V2
    assert graph["103"] == {
        "class_type": "MiniMaxH3SigmaShift",
        "inputs": {"model": ["1", 0], "shift_video": 10, "shift_audio": 3},
    }
    assert graph["104"]["class_type"] == "ModelAttentionBackend"
    assert graph["104"]["inputs"]["attention"] == "comfy kitchen attention"
    assert graph["105"]["class_type"] == "BlockSparseAttention"
    assert graph["105"]["inputs"] == {
        "model": ["104", 0],
        "selection": "vsa",
        "selection.keep_percent": 10,
        "start_percent": 0.2,
        "end_percent": 1.0,
        "dense_blocks": "",
        "min_tokens": 12288,
        "extra_tokens": 256,
        "sink_conditioning": "exact_kv_and_rows",
        "verbose": False,
    }
    assert graph["8"]["inputs"]["sampler_name"] == "res_multistep"
    assert graph["9"]["inputs"]["scheduler"] == "simple"
    assert graph["9"]["inputs"]["steps"] == 8
    assert "101" not in graph  # no stable custom preview node in isolated core runtime


def test_taomate_workflow_uses_official_atomic_recipe() -> None:
    request = GenerationRequest(
        mode=Mode.text,
        prompt="A static camera portrait with subtle hand motion and clean dialogue.",
        width=1024,
        height=576,
        length=124,
        steps=3,
        sampler_name="euler",
        scheduler="simple",
        method=MethodId.taomate_3step,
    )
    graph = build_workflow(request, {}, seed=42, filename_prefix="test").prompt
    assert graph["1"]["inputs"]["unet_name"] == C.FL2VA_INT8
    assert graph["109"] == {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"model": ["1", 0], "lora_name": C.TAOMATE_3STEP_LORA, "strength_model": 1.0},
    }
    assert graph["8"]["inputs"]["sampler_name"] == "euler"
    assert graph["9"]["inputs"]["scheduler"] == "simple"
    assert graph["9"]["inputs"]["steps"] == 3
    assert graph["6"]["inputs"]["model"] == ["109", 0]
    assert "101" not in graph


def test_config_lists_gated_experimental_presets_without_changing_default(settings, comfy: FakeComfy) -> None:
    experimental = ExperimentalFake()
    app = create_app(settings, comfy_client=comfy, experimental_comfy_client=experimental)
    with TestClient(app) as client:
        payload = client.get("/api/config").json()
    assert payload["defaults"]["method"] == "baseline"
    presets = {preset["label"]: preset for preset in payload["presets"]}
    assert presets["FastH3 V2 8-Step (Experimental)"]["available"] is True
    assert presets["FastH3 V2 8-Step (Experimental)"]["estimate_seconds"] is None
    assert presets["TaoMate H3 3-Step (Draft/Experimental)"]["available"] is True
    assert "not validated" in " ".join(presets["FastH3 V2 8-Step (Experimental)"]["caveats"]).lower()
    assert presets["FastH3 V2 8-Step (Experimental)"]["recommended_duration_seconds"] == 5.167


def test_experimental_presets_are_disabled_when_exact_live_artifacts_are_missing(
    settings, comfy: FakeComfy
) -> None:
    class MissingExperimental(ExperimentalFake):
        async def object_info(self) -> dict:
            info = experimental_contract()
            info["UNETLoader"]["input"]["required"]["unet_name"][0].remove(C.FASTH3_V2)
            info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0].remove(
                C.TAOMATE_3STEP_LORA
            )
            return info

    app = create_app(settings, comfy_client=comfy, experimental_comfy_client=MissingExperimental())
    with TestClient(app) as client:
        payload = client.get("/api/config").json()
    presets = {preset["label"]: preset for preset in payload["presets"]}
    fast = presets["FastH3 V2 8-Step (Experimental)"]
    tao = presets["TaoMate H3 3-Step (Draft/Experimental)"]
    assert fast["available"] is False
    assert C.FASTH3_V2 in fast["unavailable_reason"]
    assert tao["available"] is False
    assert C.TAOMATE_3STEP_LORA in tao["unavailable_reason"]


def test_experimental_method_submits_only_to_experimental_backend(settings, comfy: FakeComfy) -> None:
    experimental = ExperimentalFake()
    app = create_app(settings, comfy_client=comfy, experimental_comfy_client=experimental)
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            json={
                "mode": "text",
                "prompt": "A calm portrait with synchronized room tone.",
                "width": 1344,
                "height": 768,
                "length": 124,
                "steps": 8,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "method": "fast_h3_v2_8step",
            },
        )
    assert response.status_code == 201, response.text
    assert len(experimental.submitted) == 1
    assert comfy.submitted == []


def test_experimental_method_rejects_encoder_missing_from_isolated_runtime(
    settings, comfy: FakeComfy
) -> None:
    experimental = ExperimentalFake()
    app = create_app(settings, comfy_client=comfy, experimental_comfy_client=experimental)
    with TestClient(app) as client:
        response = client.post(
            "/api/validate",
            json={
                "mode": "text",
                "prompt": "A calm portrait with synchronized room tone.",
                "width": 1024,
                "height": 576,
                "length": 124,
                "steps": 3,
                "sampler_name": "euler",
                "scheduler": "simple",
                "method": "taomate_3step",
                "encoder": "heretic",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "experimental_encoder_unavailable" in {issue["code"] for issue in body["issues"]}


def test_experimental_asset_is_uploaded_even_when_it_has_a_stable_backend_name(
    settings, comfy: FakeComfy, png_bytes: bytes
) -> None:
    experimental = ExperimentalFake()
    app = create_app(settings, comfy_client=comfy, experimental_comfy_client=experimental)
    with TestClient(app) as client:
        asset = client.post(
            "/api/assets",
            files={"file": ("first-frame.png", png_bytes, "image/png")},
        ).json()
        app.state.db.set_asset_comfy_name(asset["id"], f"h3studio/{asset['stored_name']}")

        response = client.post(
            "/api/jobs",
            json={
                "mode": "first_frame",
                "prompt": "A slow controlled camera push with synchronized room tone.",
                "width": 1024,
                "height": 576,
                "length": 124,
                "steps": 3,
                "sampler_name": "euler",
                "scheduler": "simple",
                "method": "taomate_3step",
                "encoder": "standard",
                "references": [
                    {
                        "asset_id": asset["id"],
                        "kind": "image",
                        "role": "first_frame",
                    }
                ],
            },
        )

    assert response.status_code == 201, response.text
    assert experimental.uploaded == [
        {
            "filename": asset["stored_name"],
            "content_type": "image/png",
            "subfolder": "h3studio",
        }
    ]
