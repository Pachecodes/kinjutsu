import pytest
from app.schemas import GenerationRequest
from app.workflow.builder import build_workflow
from app.presets import PRESETS
from app.api import _presets_with_availability
from app.capabilities import build_capabilities
from tests.conftest import CONTRACT
from tests.test_jobs import service, anyio_backend
from app.services.jobs import JobRejected


@pytest.mark.anyio
async def test_missing_10eros_fails_before_queue_without_fallback(service):
    request = GenerationRequest(mode='text', prompt='Robot', weights='erosmax_beta5')
    with pytest.raises(JobRejected) as error:
        await service.create(request)
    assert any(issue.code == 'checkpoint_missing' for issue in error.value.issues)
    assert service.db.active_jobs() == []



import pytest
from app.workflow.validation import validate_request


@pytest.mark.parametrize('sigmas', [[1.,.5,.6,0.], [1.,.5,.1], [float('nan'),.5,0.], [1.,-.1,0.]])
def test_invalid_custom_sigmas_fail_validation(sigmas):
    request = GenerationRequest(mode='text', prompt='Robot', custom_sigmas=sigmas, steps=len(sigmas)-1)
    _, issues = validate_request(request, {})
    assert any(i.code == 'custom_sigmas_invalid' for i in issues)


def test_10eros_rejects_method_that_would_override_checkpoint():
    request = GenerationRequest(mode='text', prompt='Robot', weights='erosmax_beta5', method='w4a8_lightx2v')
    _, issues = validate_request(request, {})
    assert any(i.code == 'checkpoint_method_conflict' for i in issues)


def test_missing_manual_sigmas_disables_preferred_recipe():
    import copy
    info = copy.deepcopy(CONTRACT)
    info.pop('ManualSigmas', None)
    info['UNETLoader']['input']['required']['unet_name'][0].append('h3ErosMax_beta5.safetensors')
    caps = build_capabilities(info, comfy_url='http://127.0.0.1:8218', comfy_online=True, source='live')
    recipe = next(p for p in _presets_with_availability(caps) if p['id'] == '10eros-custom7')
    assert recipe['available'] is False
    assert 'ManualSigmas' in recipe['unavailable_reason']


def test_10eros_missing_checkpoint_disables_recipes():
    caps = build_capabilities(CONTRACT, comfy_url='http://127.0.0.1:8218', comfy_online=True, source='live')
    caps.weights['erosmax_beta5'] = False
    recipes = _presets_with_availability(caps)
    recipe = next(p for p in recipes if p['id'] == '10eros-custom7')
    assert recipe['available'] is False
    assert 'checkpoint' in recipe['unavailable_reason'].lower()



def test_10eros_presets_do_not_reuse_base_checkpoint_timing():
    assert all(p['estimate_seconds'] is None for p in PRESETS if p['id'].startswith('10eros-'))


def test_10eros_offline_is_not_reported_as_missing():
    caps = build_capabilities(CONTRACT, comfy_url='http://127.0.0.1:8218', comfy_online=False, source='contract-fallback')
    recipe = next(p for p in _presets_with_availability(caps) if p['id'] == '10eros-custom7')
    assert recipe['available'] is False
    assert 'offline' in recipe['unavailable_reason']
    assert 'missing' not in recipe['unavailable_reason']


def test_10eros_presets_load_checkpoint_without_changing_existing_profiles():
    recipes = {p['id']: p for p in PRESETS}
    assert recipes['10eros-motion6']['patch']['sampler_name'] == 'res_multistep'
    assert recipes['10eros-sde6']['patch']['sampler_name'] == 'er_sde'
    preferred = recipes['10eros-custom7']['patch']
    assert preferred['custom_sigmas'] == [1., .94, .83, .72, .55, .30, .10, 0.]
    assert preferred['weights'] == 'erosmax_beta5'
    assert preferred['method'] == 'baseline'
    assert preferred['lora_chain'] == []


def test_10eros_custom_sigmas_reach_native_sampler():
    request = GenerationRequest(mode='text', prompt='A red robot waves.', weights='erosmax_beta5', steps=7, sampler_name='er_sde', scheduler='simple', custom_sigmas=[1.0, .94, .83, .72, .55, .30, .10, 0.0])
    built = build_workflow(request, {}, seed=123, filename_prefix='eros-smoke')
    assert built.prompt['9']['class_type'] == 'ManualSigmas'
    assert built.prompt['9']['inputs']['sigmas'] == '1.0, 0.94, 0.83, 0.72, 0.55, 0.3, 0.1, 0.0'
    assert built.prompt['10']['inputs']['sigmas'] == ['9', 0]
    assert built.checkpoint == 'h3ErosMax_beta5.safetensors'
