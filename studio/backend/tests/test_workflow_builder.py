"""Workflow builder: fixture contract tests, snapshots and node-contract safety.

The contract tests rebuild each shipped fixture from a GenerationRequest and
compare the graphs structurally (node ids normalised away). If the builder ever
invents an input name, drops the audio VAE, or rewires the sampler, these fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas import (
    ContinuityOptions,
    EasyCacheOptions,
    EncoderVariant,
    GenerationRequest,
    LoraInput,
    MethodId,
    Mode,
    RefKind,
    ReferenceInput,
    RefRole,
    WeightVariant,
)
from app.workflow import constants as C
from app.workflow.builder import WorkflowBuildError, build_workflow, make_filename_prefix, sanitize_prefix_component
from app.workflow.validation import ResolvedAsset
from tests.conftest import CONTRACT, load_fixture

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

AKITO = ResolvedAsset(id="a1", kind=RefKind.image, comfy_name="subject-one.png")
ALE = ResolvedAsset(id="a2", kind=RefKind.image, comfy_name="subject-two.png")
ZERK = ResolvedAsset(id="a3", kind=RefKind.image, comfy_name="subject-three.png")
PANDA_START = ResolvedAsset(id="i1", kind=RefKind.image, comfy_name="pachecodes-panda-start.png")
PANDA_END = ResolvedAsset(id="i2", kind=RefKind.image, comfy_name="pachecodes-panda-end.png")
MOTION = ResolvedAsset(
    id="v1",
    kind=RefKind.video,
    comfy_name="motion-guide.mp4",
    duration_seconds=5.0,
    has_audio=True,
)
VOICE = ResolvedAsset(
    id="s1", kind=RefKind.audio, comfy_name="pachecodes-panda-voice.wav", duration_seconds=4.2
)

ASSETS = {a.id: a for a in (AKITO, ALE, ZERK, PANDA_START, PANDA_END, MOTION, VOICE)}


# --- structural comparison helpers ---------------------------------------
def canonicalize(graph: dict[str, Any]) -> dict[str, Any]:
    """Relabel node ids by a deterministic walk so two graphs with the same
    shape compare equal regardless of how their ids were allocated.

    The shipped H3 fixtures predate the transport-only live-preview wrapper.
    Fold that wrapper away for fixture comparisons; dedicated preview tests
    assert its exact contract separately.
    """
    graph = json.loads(json.dumps(graph))
    preview_ids = {nid for nid, node in graph.items() if node.get("class_type") == "ModelPreviewOverrideKJ"}
    for preview_id in preview_ids:
        upstream = graph[preview_id]["inputs"]["model"]
        for node in graph.values():
            for key, value in list(node.get("inputs", {}).items()):
                if _is_link(value) and value[0] == preview_id:
                    node["inputs"][key] = upstream
        graph.pop(preview_id)

    order: list[str] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        inputs = graph[node_id].get("inputs", {})
        for key in sorted(inputs):
            value = inputs[key]
            if _is_link(value) and value[0] in graph:
                visit(str(value[0]))
        order.append(node_id)

    roots = sorted(nid for nid in graph if graph[nid].get("class_type") == C.NODE_SAVE_VIDEO)
    assert roots, "graph has no SaveVideo output node"
    for root in roots:
        visit(root)
    for node_id in sorted(graph):  # orphans, if any, still get named
        visit(node_id)

    mapping = {node_id: f"n{index:03d}" for index, node_id in enumerate(order)}
    result: dict[str, Any] = {}
    for node_id, name in mapping.items():
        node = graph[node_id]
        inputs = {}
        for key, value in node.get("inputs", {}).items():
            inputs[key] = [mapping[str(value[0])], value[1]] if _is_link(value) and str(value[0]) in mapping else value
        result[name] = {"class_type": node["class_type"], "inputs": inputs}
    return result


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


# --- fixture contract tests ----------------------------------------------
def test_text_to_video_matches_shipped_fixture() -> None:
    fixture = load_fixture("text-to-video.json")
    request = GenerationRequest(
        mode=Mode.text,
        prompt=fixture["5"]["inputs"]["prompt"],
        width=1024,
        height=576,
        length=209,
        steps=16,
        sampler_name="res_multistep",
        scheduler="simple",
        method=MethodId.baseline,
    )
    built = build_workflow(
        request,
        {},
        seed=3159072846,
        filename_prefix="video/MiniMax_H3_Original_Film_The_Last_Signal_T2VA",
    )
    assert canonicalize(built.prompt) == canonicalize(fixture)


def test_live_preview_wraps_the_final_guider_model_without_changing_scheduler() -> None:
    request = GenerationRequest(
        mode=Mode.text,
        prompt="A restrained preview fixture.",
        width=608,
        height=352,
        length=124,
        steps=20,
        method=MethodId.baseline,
    )

    built = build_workflow(request, {}, seed=7, filename_prefix="preview-test")

    assert built.prompt["101"] == {
        "class_type": "ModelPreviewOverrideKJ",
        "inputs": {
            "model": ["1", 0],
            "max_resolution": 1024,
            "jpeg_quality": 80,
            "suppress_default_preview": True,
            "preview_frames": 124,
            "preview_fps": 12,
            "tiny_vae": "taeh3.safetensors",
        },
    }
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]
    assert built.prompt["9"]["inputs"]["model"] == ["1", 0]


def test_ref2va_multi_image_matches_shipped_fixture() -> None:
    fixture = load_fixture("ref2va-multi-image.json")
    request = GenerationRequest(
        mode=Mode.ref2va,
        prompt=fixture["5"]["inputs"]["prompt"],
        width=1024,
        height=576,
        length=243,
        steps=20,
        scheduler="beta",
        ref_image_size="match",
        references=[
            ReferenceInput(asset_id="a1", kind=RefKind.image, role=RefRole.identity),
            ReferenceInput(asset_id="a2", kind=RefKind.image, role=RefRole.identity),
            ReferenceInput(asset_id="a3", kind=RefKind.image, role=RefRole.identity),
        ],
    )
    built = build_workflow(
        request, ASSETS, seed=8427601319, filename_prefix="video/MiniMax_H3_Example_Reference_Shot"
    )
    assert canonicalize(built.prompt) == canonicalize(fixture)


def test_performance_transfer_matches_shipped_fixture() -> None:
    fixture = load_fixture("performance-transfer.json")
    request = GenerationRequest(
        mode=Mode.performance,
        prompt=fixture["5"]["inputs"]["prompt"],
        width=576,
        height=1024,
        length=124,
        steps=12,
        scheduler="beta",
        ref_image_size="match",
        references=[
            ReferenceInput(asset_id="a1", kind=RefKind.image, role=RefRole.identity),
            ReferenceInput(asset_id="v1", kind=RefKind.video, role=RefRole.motion, include_audio=True),
        ],
    )
    built = build_workflow(
        request,
        ASSETS,
        seed=6290843175,
        filename_prefix="video/MiniMax_H3_Subject_Performance_Transfer_Optimized_5s",
    )
    assert canonicalize(built.prompt) == canonicalize(fixture)


# --- node contract safety -------------------------------------------------
def _all_requests() -> dict[str, GenerationRequest]:
    return {
        "text": GenerationRequest(mode=Mode.text, prompt="A quiet street at dawn.", length=124),
        "first_frame": GenerationRequest(
            mode=Mode.first_frame,
            prompt="The camera drifts forward.",
            length=124,
            references=[ReferenceInput(asset_id="i1", kind=RefKind.image, role=RefRole.first_frame)],
        ),
        "first_last": GenerationRequest(
            mode=Mode.first_last,
            prompt="Morning becomes night.",
            length=175,
            references=[
                ReferenceInput(asset_id="i1", kind=RefKind.image, role=RefRole.first_frame),
                ReferenceInput(asset_id="i2", kind=RefKind.image, role=RefRole.last_frame),
            ],
        ),
        "ref2va": GenerationRequest(
            mode=Mode.ref2va,
            prompt="<Picture 1> and <Picture 2> talk. <Audio 1> is the voice.",
            length=243,
            references=[
                ReferenceInput(asset_id="a1", kind=RefKind.image, role=RefRole.identity),
                ReferenceInput(asset_id="a2", kind=RefKind.image, role=RefRole.identity),
                ReferenceInput(asset_id="s1", kind=RefKind.audio, role=RefRole.voice),
            ],
        ),
        "performance": GenerationRequest(
            mode=Mode.performance,
            prompt="<Picture 1> performs <Video 1>.",
            length=124,
            references=[
                ReferenceInput(asset_id="a1", kind=RefKind.image, role=RefRole.identity),
                ReferenceInput(asset_id="v1", kind=RefKind.video, role=RefRole.motion, include_audio=True),
            ],
        ),
    }


def _contract_inputs(class_type: str) -> set[str]:
    spec = CONTRACT[class_type]["input"]
    names: set[str] = set()
    for section in ("required", "optional"):
        names.update(spec.get(section, {}))
    return names


@pytest.mark.parametrize("name", sorted(_all_requests()))
@pytest.mark.parametrize("method", list(MethodId))
def test_every_node_and_input_exists_in_the_live_contract(name: str, method: MethodId) -> None:
    if method in {MethodId.fast_h3_v2_8step, MethodId.taomate_3step}:
        pytest.skip("Isolated ComfyUI 0.36 profiles have dedicated exact-recipe and live-contract tests")
    if method in {MethodId.w4a8_lightx2v, MethodId.w4a8_lightx2v_trt, MethodId.w4a8_latent2x_refine3} and name in {
        "ref2va",
        "performance",
    }:
        pytest.skip("W4A8 methods are FL2VA-only")
    if method is MethodId.ref2va_vsa and name != "ref2va":
        pytest.skip("Ref2VA VSA is validated only for References mode")
    request = _all_requests()[name].model_copy(update={"method": method})
    if method is MethodId.ref2va_vsa:
        request = request.model_copy(
            update={"length": 124, "steps": 4, "sampler_name": "euler", "scheduler": "simple"}
        )
    built = build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")
    for node_id, node in built.prompt.items():
        class_type = node["class_type"]
        if class_type == "ModelPreviewOverrideKJ":
            assert node["inputs"]["tiny_vae"] == "taeh3.safetensors"
            continue
        if class_type == C.NODE_TRT_VAE_LOADER:
            assert node["inputs"] == {"decoder": C.TRT_VAE_DECODER, "encoder": C.TRT_VAE_ENCODER}
            continue
        assert class_type in CONTRACT, f"{class_type} is not in the node contract"
        allowed = _contract_inputs(class_type)
        for input_name in node["inputs"]:
            # Autogrow slots are `<socket>.<prefix><index>` in the API format.
            base = input_name.split(".", 1)[0]
            assert base in allowed, f"{class_type}.{input_name} (node {node_id}) is not a contract input"


@pytest.mark.parametrize("name", sorted(_all_requests()))
def test_graph_is_fully_connected_and_terminates_in_savevideo(name: str) -> None:
    built = build_workflow(_all_requests()[name], ASSETS, seed=7, filename_prefix="video/Test")
    graph = built.prompt
    for node in graph.values():
        for value in node["inputs"].values():
            if _is_link(value):
                assert value[0] in graph, f"dangling link to {value[0]}"
    save_nodes = [nid for nid, node in graph.items() if node["class_type"] == C.NODE_SAVE_VIDEO]
    assert save_nodes == [built.output_node_id]


def test_builder_is_pure_and_deterministic() -> None:
    request = _all_requests()["ref2va"]
    first = build_workflow(request, ASSETS, seed=42, filename_prefix="video/Test")
    second = build_workflow(request, ASSETS, seed=42, filename_prefix="video/Test")
    assert first.prompt == second.prompt
    assert json.dumps(first.prompt, sort_keys=True) == json.dumps(second.prompt, sort_keys=True)


# --- method profiles ------------------------------------------------------
def test_ref2va_vsa_is_a_public_method_id() -> None:
    assert MethodId("ref2va_vsa").value == "ref2va_vsa"


def test_baseline_has_no_patch_node() -> None:
    built = build_workflow(_all_requests()["text"], ASSETS, seed=1, filename_prefix="video/Test")
    classes = {node["class_type"] for node in built.prompt.values()}
    assert not classes & {C.NODE_EASYCACHE, C.NODE_SAGE_PATCH, C.NODE_SOL_PATCH}
    assert built.prompt["101"]["inputs"]["model"] == ["1", 0]
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]


def test_easycache_uses_the_documented_fast_preview_recipe() -> None:
    request = _all_requests()["text"].model_copy(
        update={"method": MethodId.easycache, "easycache": EasyCacheOptions()}
    )
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    patch = built.prompt["100"]
    assert patch["class_type"] == C.NODE_EASYCACHE
    assert patch["inputs"]["reuse_threshold"] == 0.3
    assert patch["inputs"]["start_percent"] == 0.2
    assert patch["inputs"]["end_percent"] == 0.9
    assert patch["inputs"]["model"] == ["1", 0]
    # Preview wraps the patched model, then the guider samples the wrapper.
    assert built.prompt["101"]["inputs"]["model"] == ["100", 0]
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]
    # ...but sigmas stay on the unpatched model so profiles stay comparable.
    assert built.prompt["9"]["inputs"]["model"] == ["1", 0]


@pytest.mark.parametrize(
    ("method", "class_type"),
    [(MethodId.sage, C.NODE_SAGE_PATCH), (MethodId.sol, C.NODE_SOL_PATCH)],
)
def test_experimental_patches_wire_into_the_guider(method: MethodId, class_type: str) -> None:
    request = _all_requests()["ref2va"].model_copy(update={"method": method})
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    assert built.prompt["100"]["class_type"] == class_type
    assert built.prompt["101"]["inputs"]["model"] == ["100", 0]
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]


def test_ref2va_vsa_uses_the_verified_four_step_convrot_graph() -> None:
    request = _all_requests()["ref2va"].model_copy(
        update={
            "method": MethodId.ref2va_vsa,
            "length": 124,
            "steps": 4,
            "sampler_name": "euler",
            "scheduler": "simple",
        }
    )
    built = build_workflow(request, ASSETS, seed=981445682258077, filename_prefix="video/Test")

    assert built.checkpoint == "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
    assert built.prompt["109"]["inputs"] == {
        "model": ["1", 0],
        "lora_name": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
        "strength_model": 1.0,
    }
    assert built.prompt["100"] == {
        "class_type": "Ref2VAVSAGatePatch",
        "inputs": {
            "model": ["109", 0],
            "gate_file": "fasth3_vsa_gate.safetensors",
            "sparsity": 0.75,
        },
    }
    assert built.prompt["103"] == {
        "class_type": "MiniMaxH3SigmaShift",
        "inputs": {"model": ["100", 0], "shift_video": 12, "shift_audio": 3},
    }
    assert built.prompt["101"]["inputs"]["model"] == ["103", 0]
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]
    assert built.prompt["8"]["inputs"]["sampler_name"] == "euler"
    assert built.prompt["9"]["inputs"] == {
        "model": ["103", 0],
        "scheduler": "simple",
        "steps": 4,
        "denoise": 1.0,
    }


def test_ref2va_vsa_refuses_non_reference_modes_but_accepts_extra_loras() -> None:
    wrong_mode = _all_requests()["text"].model_copy(
        update={"method": MethodId.ref2va_vsa, "length": 124, "steps": 4, "sampler_name": "euler", "scheduler": "simple"}
    )
    with pytest.raises(WorkflowBuildError, match="References mode"):
        build_workflow(wrong_mode, ASSETS, seed=1, filename_prefix="video/Test")

    with_lora = _all_requests()["ref2va"].model_copy(
        update={
            "method": MethodId.ref2va_vsa,
            "length": 124,
            "steps": 4,
            "sampler_name": "euler",
            "scheduler": "simple",
            "lora_chain": [LoraInput(name="MysticXXX_MMH3-V3.safetensors", strength=0.7)],
        }
    )
    built = build_workflow(with_lora, ASSETS, seed=1, filename_prefix="video/Test")
    assert built.prompt["110"]["inputs"]["model"] == ["109", 0]
    assert built.prompt["100"]["inputs"]["model"] == ["110", 0]


def test_ref2va_vsa_continuity_keeps_turbo_loras_gate_and_sigma_shift() -> None:
    request = _all_requests()["ref2va"].model_copy(
        update={
            "method": MethodId.ref2va_vsa,
            "length": 270,
            "steps": 4,
            "sampler_name": "euler",
            "scheduler": "simple",
            "weights": WeightVariant.gguf_q3km,
            "encoder": EncoderVariant.heretic,
            "lora_chain": [LoraInput(name="MysticXXX_MMH3-V3.safetensors", strength=0.7)],
            "continuity": ContinuityOptions(auto_split=True, window="124", pin_frames="22"),
        }
    )

    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")

    assert built.prompt["1"]["class_type"] == C.NODE_UNET_LOADER_GGUF
    assert built.prompt["2"]["inputs"]["clip_name"] == C.HERETIC_CLIP_NAME
    assert built.prompt["109"]["inputs"]["lora_name"] == C.REF2VA_TURBO_4STEP_LORA
    assert built.prompt["110"]["inputs"]["model"] == ["109", 0]
    assert built.prompt["100"]["inputs"]["model"] == ["110", 0]
    assert built.prompt["103"]["inputs"]["model"] == ["100", 0]
    assert built.prompt["300"]["inputs"]["model"] == ["103", 0]


def test_w4a8_lightx2v_uses_the_verified_four_step_graph() -> None:
    request = _all_requests()["first_frame"].model_copy(
        update={
            "method": MethodId.w4a8_lightx2v,
            "steps": 4,
            "sampler_name": "er_sde",
            "scheduler": "simple",
        }
    )
    built = build_workflow(request, ASSETS, seed=3159072846, filename_prefix="video/Test")
    assert built.prompt["1"]["inputs"]["unet_name"] == C.FL2VA_W4A8
    assert built.prompt["3"]["inputs"]["vae_name"] == C.W4A8_VIDEO_VAE
    assert built.prompt["109"]["inputs"] == {
        "model": ["1", 0],
        "lora_name": C.LIGHTX2V_4STEP_LORA,
        "strength_model": 0.75,
    }
    assert built.prompt["101"]["inputs"]["model"] == ["109", 0]
    assert built.prompt["6"]["inputs"]["model"] == ["101", 0]
    assert built.prompt["8"]["inputs"]["sampler_name"] == "er_sde"
    assert built.prompt["9"]["inputs"] == {
        "model": ["109", 0],
        "scheduler": "simple",
        "steps": 4,
        "denoise": 1.0,
    }


def test_fast_final_trt_uses_standard_conditioning_and_trt_decode_only() -> None:
    request = _all_requests()["first_frame"].model_copy(
        update={
            "method": MethodId.w4a8_lightx2v_trt,
            "steps": 4,
            "sampler_name": "res_multistep",
            "scheduler": "simple",
        }
    )
    built = build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")

    assert built.checkpoint == C.FL2VA_W4A8
    assert built.prompt["3"] == {
        "class_type": C.NODE_VAE_LOADER,
        "inputs": {"vae_name": C.W4A8_VIDEO_VAE},
    }
    assert built.prompt["5"]["inputs"]["vae"] == ["3", 0]
    assert built.prompt["102"] == {
        "class_type": C.NODE_TRT_VAE_LOADER,
        "inputs": {"decoder": C.TRT_VAE_DECODER, "encoder": C.TRT_VAE_ENCODER},
    }
    assert built.prompt["11"]["inputs"]["vae"] == ["102", 0]
    assert built.prompt["12"]["inputs"]["vae"] == ["4", 0]
    assert built.prompt["109"]["inputs"]["lora_name"] == C.FAST_FINAL_4STEP_LORA
    assert built.prompt["109"]["inputs"]["strength_model"] == 1.0
    assert built.prompt["8"]["inputs"]["sampler_name"] == "res_multistep"
    assert built.prompt["9"]["inputs"]["scheduler"] == "simple"


def test_erosmax_checkpoint_is_selectable_for_reference_modes() -> None:
    request = _all_requests()["ref2va"].model_copy(update={"weights": WeightVariant.erosmax_beta4})
    built = build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")
    assert built.checkpoint == C.EROSMAX_BETA4
    assert built.prompt["1"]["inputs"]["unet_name"] == C.EROSMAX_BETA4


def test_erosmax_checkpoint_refuses_frame_modes() -> None:
    request = _all_requests()["first_frame"].model_copy(update={"weights": WeightVariant.erosmax_beta4})
    with pytest.raises(WorkflowBuildError, match="custom Ref2VA"):
        build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")


def test_erosmax_beta5_checkpoint_is_selectable_for_reference_modes() -> None:
    request = _all_requests()["ref2va"].model_copy(update={"weights": WeightVariant.erosmax_beta5})
    built = build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")
    assert built.checkpoint == C.EROSMAX_BETA5
    assert built.prompt["1"]["inputs"]["unet_name"] == C.EROSMAX_BETA5


def test_erosmax_beta5_checkpoint_is_selectable_for_frame_modes() -> None:
    request = _all_requests()["first_frame"].model_copy(update={"weights": WeightVariant.erosmax_beta5})
    built = build_workflow(request, ASSETS, seed=7, filename_prefix="video/Test")
    assert built.checkpoint == C.EROSMAX_BETA5
    assert built.prompt["1"]["inputs"]["unet_name"] == C.EROSMAX_BETA5


def test_premium_latent2x_refine3_matches_the_verified_robot_recipe() -> None:
    request = _all_requests()["first_frame"].model_copy(
        update={
            "method": MethodId.w4a8_latent2x_refine3,
            "width": 640,
            "height": 1152,
            "length": 124,
            "steps": 4,
            "sampler_name": "er_sde",
            "scheduler": "simple",
        }
    )
    built = build_workflow(request, ASSETS, seed=2564026427703801401, filename_prefix="video/Test")

    assert built.prompt["1"]["inputs"]["unet_name"] == C.FL2VA_W4A8
    assert built.prompt["3"]["inputs"]["vae_name"] == C.W4A8_VIDEO_VAE
    assert built.prompt["109"]["inputs"]["strength_model"] == 0.75
    assert built.prompt["5"]["inputs"]["width"] == 320
    assert built.prompt["5"]["inputs"]["height"] == 576
    assert built.prompt["5"]["inputs"]["length"] == 124
    assert built.prompt["200"] == {
        "class_type": C.NODE_SEPARATE_AV_LATENT,
        "inputs": {"av_latent": ["10", 0]},
    }
    assert built.prompt["201"] == {
        "class_type": C.NODE_H3_LATENT_UPSCALER_3D,
        "inputs": {
            "latent": ["200", 0],
            "model_name": C.H3_LATENT_UPSCALER_3D,
            "precision": "bf16",
            "mode": "scale by multiplier",
            "mode.scale": 2.0,
            "device": "cuda",
            "enable_chunking": True,
            "align": 32,
        },
    }
    assert built.prompt["202"] == {
        "class_type": C.NODE_CONCAT_AV_LATENT,
        "inputs": {"video_latent": ["201", 0], "audio_latent": ["200", 1]},
    }
    assert built.prompt["203"]["class_type"] == C.NODE_IMAGE_TO_VIDEO
    assert built.prompt["203"]["inputs"]["width"] == 640
    assert built.prompt["203"]["inputs"]["height"] == 1152
    assert built.prompt["203"]["inputs"]["length"] == 124
    assert built.prompt["204"]["inputs"] == {"model": ["109", 0], "conditioning": ["203", 0]}
    assert built.prompt["205"]["inputs"] == {"sampler_name": "euler"}
    assert built.prompt["206"]["inputs"] == {"sigmas": "0.9035, 0.6316, 0.3158, 0.0000"}
    assert built.prompt["207"]["inputs"] == {
        "noise": ["7", 0],
        "guider": ["204", 0],
        "sampler": ["205", 0],
        "sigmas": ["206", 0],
        "latent_image": ["202", 0],
    }
    assert built.prompt["11"]["inputs"]["samples"] == ["207", 0]
    assert built.prompt["12"]["inputs"]["samples"] == ["207", 0]


def test_premium_latent2x_refine3_keeps_user_loras_after_lightx2v_for_both_passes() -> None:
    request = _all_requests()["first_frame"].model_copy(
        update={
            "method": MethodId.w4a8_latent2x_refine3,
            "width": 640,
            "height": 1152,
            "steps": 4,
            "sampler_name": "er_sde",
            "scheduler": "simple",
            "lora_chain": [LoraInput(name="MysticXXX_MMH3-V3.safetensors", strength=0.7)],
        }
    )
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    assert built.prompt["110"]["inputs"]["model"] == ["109", 0]
    assert built.prompt["9"]["inputs"]["model"] == ["110", 0]
    assert built.prompt["204"]["inputs"]["model"] == ["110", 0]


def test_w4a8_lightx2v_refuses_reference_modes() -> None:
    request = _all_requests()["ref2va"].model_copy(update={"method": MethodId.w4a8_lightx2v})
    with pytest.raises(WorkflowBuildError, match="FL2VA-only"):
        build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")


def test_sol_defaults_match_the_node_contract() -> None:
    request = _all_requests()["ref2va"].model_copy(update={"method": MethodId.sol})
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    inputs = built.prompt["100"]["inputs"]
    contract = CONTRACT[C.NODE_SOL_PATCH]["input"]["required"]
    for key, spec in contract.items():
        if key == "model":
            continue
        assert inputs[key] == spec[1]["default"], f"Sol default drifted for {key}"


# --- reference wiring -----------------------------------------------------
def test_reference_slots_are_indexed_from_zero_and_tagged_from_one() -> None:
    built = build_workflow(_all_requests()["ref2va"], ASSETS, seed=1, filename_prefix="video/Test")
    inputs = built.prompt["5"]["inputs"]
    assert "ref_images.ref_image_0" in inputs
    assert "ref_images.ref_image_1" in inputs
    assert "ref_audios.ref_audio_0" in inputs
    assert built.reference_tags == ["<Picture 1>", "<Picture 2>", "<Audio 1>"]


def test_video_soundtrack_is_only_wired_when_requested() -> None:
    with_audio = build_workflow(_all_requests()["performance"], ASSETS, seed=1, filename_prefix="video/Test")
    assert "ref_video_audios.ref_video_audio_0" in with_audio.prompt["5"]["inputs"]

    silent = _all_requests()["performance"]
    silent = silent.model_copy(
        update={
            "references": [
                silent.references[0],
                silent.references[1].model_copy(update={"include_audio": False}),
            ]
        }
    )
    built = build_workflow(silent, ASSETS, seed=1, filename_prefix="video/Test")
    assert "ref_video_audios.ref_video_audio_0" not in built.prompt["5"]["inputs"]
    assert "ref_videos.ref_video_0" in built.prompt["5"]["inputs"]


def test_video_reference_goes_through_get_video_components() -> None:
    built = build_workflow(_all_requests()["performance"], ASSETS, seed=1, filename_prefix="video/Test")
    link = built.prompt["5"]["inputs"]["ref_videos.ref_video_0"]
    components = built.prompt[link[0]]
    assert components["class_type"] == C.NODE_GET_VIDEO_COMPONENTS
    assert link[1] == 0  # IMAGE output
    audio_link = built.prompt["5"]["inputs"]["ref_video_audios.ref_video_audio_0"]
    assert audio_link == [link[0], 1]  # AUDIO output of the same node


def test_frame_modes_use_the_image_to_video_node_only() -> None:
    for name in ("text", "first_frame", "first_last"):
        built = build_workflow(_all_requests()[name], ASSETS, seed=1, filename_prefix="video/Test")
        node = built.prompt["5"]
        assert node["class_type"] == C.NODE_IMAGE_TO_VIDEO
        assert "audio_vae" not in node["inputs"], "ImageToVideo has no audio_vae input in the contract"
        assert "ref_image_size" not in node["inputs"]
    assert "first_frame" in build_workflow(
        _all_requests()["first_frame"], ASSETS, seed=1, filename_prefix="video/Test"
    ).prompt["5"]["inputs"]


def test_text_mode_omits_frame_inputs_entirely() -> None:
    built = build_workflow(_all_requests()["text"], ASSETS, seed=1, filename_prefix="video/Test")
    assert "first_frame" not in built.prompt["5"]["inputs"]
    assert "last_frame" not in built.prompt["5"]["inputs"]


# --- checkpoint selection -------------------------------------------------
def test_frame_modes_use_fl2va_and_reference_modes_use_ref2va() -> None:
    frame = build_workflow(_all_requests()["text"], ASSETS, seed=1, filename_prefix="video/Test")
    assert frame.prompt["1"]["inputs"]["unet_name"] == C.FL2VA_INT8
    reference = build_workflow(_all_requests()["ref2va"], ASSETS, seed=1, filename_prefix="video/Test")
    assert reference.prompt["1"]["inputs"]["unet_name"] == C.REF2VA_INT8


def test_gguf_uses_the_gguf_loader_without_weight_dtype() -> None:
    request = _all_requests()["ref2va"].model_copy(update={"weights": WeightVariant.gguf_q3km})
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    loader = built.prompt["1"]
    assert loader["class_type"] == C.NODE_UNET_LOADER_GGUF
    assert loader["inputs"] == {"unet_name": C.REF2VA_GGUF_Q3KM}


def test_gguf_is_refused_for_frame_modes() -> None:
    request = _all_requests()["text"].model_copy(update={"weights": WeightVariant.gguf_q3km})
    with pytest.raises(WorkflowBuildError, match="GGUF"):
        build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")


def test_pink_cherry_uses_the_installed_fl2va_checkpoint() -> None:
    request = _all_requests()["text"].model_copy(update={"weights": WeightVariant.pinkcherry_v03})
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")
    loader = built.prompt["1"]
    assert loader["class_type"] == C.NODE_UNET_LOADER
    assert loader["inputs"] == {
        "unet_name": C.PINKCHERRY_FL2VA_INT8_V03,
        "weight_dtype": "default",
    }


# --- automatic long-take continuity --------------------------------------
def test_long_take_uses_raw_latent_context_and_exact_duration_trim() -> None:
    request = GenerationRequest(
        mode=Mode.text,
        prompt="One continuous tracking shot; keep motion and sound flowing.",
        width=1024,
        height=576,
        length=362,
        steps=20,
        continuity={"auto_split": True},
    )

    built = build_workflow(request, {}, seed=77, filename_prefix="video/continuity")
    graph = built.prompt
    memory = next(node for node in graph.values() if node["class_type"] == "H3MultishotMemorySampler")
    assert memory["inputs"]["continuity"] == "context_pin"
    assert memory["inputs"]["frames_per_shot"] == 141
    assert memory["inputs"]["shot_count"] == 3
    assert memory["inputs"]["pin_frames"] == "22"
    assert memory["inputs"]["preview_first_shot"] is False
    assert memory["inputs"]["save_every_shot"] is False
    assert memory["inputs"]["pin_renorm"] is True
    image_trim = next(node for node in graph.values() if node["class_type"] == "GetImageRangeFromBatch")
    audio_trim = next(node for node in graph.values() if node["class_type"] == "TrimAudioDuration")
    assert image_trim["inputs"]["num_frames"] == 362
    assert audio_trim["inputs"]["duration"] == pytest.approx(362 / 24)
    assert graph[built.output_node_id]["class_type"] == C.NODE_SAVE_VIDEO


def test_continuity_plain_section_headers_are_not_misread_as_json() -> None:
    request = GenerationRequest(
        mode=Mode.text,
        prompt="[REFERENCE USE]\nKeep Picture 1 consistent.\n\n[SCENE]\nA continuous camera move.",
        width=1024,
        height=576,
        length=362,
        continuity=ContinuityOptions(auto_split=True),
    )
    built = build_workflow(request, {}, seed=123, filename_prefix="video/section-header")
    script = built.prompt["300"]["inputs"]["script"]
    assert script.startswith("H3 prompt sections:\n[REFERENCE USE]")


def test_continuity_maps_studio_reference_size_to_sampler_contract() -> None:
    request = GenerationRequest(
        mode=Mode.ref2va,
        prompt="Keep the subject consistent.",
        width=1024,
        height=576,
        length=362,
        ref_image_size="max",
        continuity=ContinuityOptions(auto_split=True),
        references=[ReferenceInput(asset_id="img", kind=RefKind.image, role=RefRole.identity)],
    )
    built = build_workflow(
        request,
        {"img": ResolvedAsset(id="img", kind=RefKind.image, comfy_name="ref.png", duration_seconds=None)},
        seed=123,
        filename_prefix="h3-studio/test-ref-continuity",
    )
    assert built.prompt["300"]["inputs"]["reference_image_size"] == "model_default"


# --- misuse ---------------------------------------------------------------
def test_missing_asset_is_refused() -> None:
    with pytest.raises(WorkflowBuildError, match="not available"):
        build_workflow(_all_requests()["ref2va"], {}, seed=1, filename_prefix="video/Test")


def test_frame_role_in_reference_mode_is_refused() -> None:
    request = GenerationRequest(
        mode=Mode.ref2va,
        prompt="x",
        references=[ReferenceInput(asset_id="i1", kind=RefKind.image, role=RefRole.first_frame)],
    )
    with pytest.raises(WorkflowBuildError, match="Frame roles"):
        build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")


def test_reference_role_in_frame_mode_is_refused() -> None:
    request = GenerationRequest(
        mode=Mode.first_frame,
        prompt="x",
        references=[ReferenceInput(asset_id="a1", kind=RefKind.image, role=RefRole.identity)],
    )
    with pytest.raises(WorkflowBuildError, match="does not accept"):
        build_workflow(request, ASSETS, seed=1, filename_prefix="video/Test")


# --- filename safety ------------------------------------------------------
@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "..\\..\\windows\\system32", "a/b/c", "  ", "%date:yyyy%", "C:\\weights\\model"],
)
def test_filename_prefix_never_escapes_the_output_folder(hostile: str) -> None:
    prefix = make_filename_prefix("deadbeefcafe", hostile)
    assert prefix.startswith("video/H3Studio_")
    tail = prefix.removeprefix("video/")
    assert "/" not in tail and "\\" not in tail and ".." not in tail


def test_sanitize_prefix_component_falls_back() -> None:
    assert sanitize_prefix_component("", fallback="Take") == "Take"
    assert sanitize_prefix_component("Night Drive #2") == "Night_Drive_2"


def test_heretic_encoder_changes_only_the_clip_loader() -> None:
    standard = GenerationRequest(mode=Mode.text, prompt="A quiet studio scene.")
    heretic = standard.model_copy(update={"encoder": EncoderVariant.heretic})
    standard_graph = build_workflow(standard, {}, seed=42, filename_prefix="video/standard").prompt
    heretic_graph = build_workflow(heretic, {}, seed=42, filename_prefix="video/heretic").prompt

    assert standard_graph["2"]["inputs"]["clip_name"] == C.CLIP_NAME
    assert heretic_graph["2"]["inputs"]["clip_name"] == C.HERETIC_CLIP_NAME
    standard_graph["2"] = heretic_graph["2"]
    standard_graph["14"]["inputs"]["filename_prefix"] = "video/heretic"
    assert standard_graph == heretic_graph


# --- snapshots ------------------------------------------------------------
SNAPSHOT_CASES = {
    "text-baseline": ("text", MethodId.baseline),
    "text-easycache": ("text", MethodId.easycache),
    "first-frame-baseline": ("first_frame", MethodId.baseline),
    "first-last-baseline": ("first_last", MethodId.baseline),
    "ref2va-baseline": ("ref2va", MethodId.baseline),
    "ref2va-sage": ("ref2va", MethodId.sage),
    "performance-baseline": ("performance", MethodId.baseline),
    "performance-sol": ("performance", MethodId.sol),
}


@pytest.mark.parametrize("case", sorted(SNAPSHOT_CASES))
def test_workflow_snapshots(case: str) -> None:
    """Every product mode x representative method profile, frozen on disk.

    Regenerate deliberately with `H3_UPDATE_SNAPSHOTS=1 pytest`.
    """
    import os

    mode_key, method = SNAPSHOT_CASES[case]
    request = _all_requests()[mode_key].model_copy(update={"method": method})
    built = build_workflow(request, ASSETS, seed=1234567, filename_prefix="video/H3Studio_Snapshot_test0001")
    payload = json.dumps(built.prompt, indent=2, sort_keys=True) + "\n"

    path = SNAPSHOT_DIR / f"{case}.json"
    if os.environ.get("H3_UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    assert path.is_file(), f"missing snapshot {path.name}; run with H3_UPDATE_SNAPSHOTS=1"
    assert json.loads(path.read_text("utf-8")) == built.prompt
