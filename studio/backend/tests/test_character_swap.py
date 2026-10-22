from copy import deepcopy

from app.capabilities import build_capabilities
from tests.conftest import CONTRACT

NAME = "minimax_h3_character_swap_v1.1_ref2va_fro.safetensors"


def test_character_swap_v11_live_catalog_has_reviewed_ref2va_metadata():
    info = deepcopy(CONTRACT)
    info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0].append(NAME)
    caps = build_capabilities(info, comfy_url="http://127.0.0.1:8218", comfy_online=True, source="live")
    lora = next(item for item in caps.loras if item.name == NAME)
    assert lora.label == "Character Swap v1.1 (experimental)"
    assert lora.checkpoint == "ref2va"
    assert lora.recommended_strength == 1.0
    assert "body_swap:" in lora.note
    assert "guide-latent" in lora.note
    assert "not" in lora.note


def test_character_swap_exact_filename_is_preserved_after_vsa_turbo():
    from app.schemas import LoraInput, MethodId
    from app.workflow.builder import build_workflow
    from tests.test_workflow_builder import ASSETS, _all_requests

    request = _all_requests()["ref2va"].model_copy(update={
        "method": MethodId.ref2va_vsa, "steps": 4,
        "sampler_name": "euler", "scheduler": "simple",
        "lora_chain": [LoraInput(name=NAME, strength=1.0)],
    })
    built = build_workflow(request, ASSETS, seed=1, filename_prefix="test/no-submit")
    assert built.prompt["110"]["inputs"] == {
        "model": ["109", 0], "lora_name": NAME, "strength_model": 1.0,
    }
    assert built.prompt["100"]["inputs"]["model"] == ["110", 0]


def test_character_swap_is_not_offered_when_absent_from_live_catalog():
    caps = build_capabilities(CONTRACT, comfy_url="http://127.0.0.1:8218", comfy_online=True, source="live")
    assert NAME not in [item.name for item in caps.loras]
