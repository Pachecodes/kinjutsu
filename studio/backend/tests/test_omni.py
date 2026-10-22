import pytest
from copy import deepcopy
from fastapi.testclient import TestClient
from app.main import create_app
from app.capabilities import CapabilityService
from app.comfy import ComfyError
from tests.conftest import FakeComfy, CONTRACT
from app.workflow.validation import validate_request, has_errors
from app.schemas import GenerationRequest
from app.workflow.builder import build_workflow
from app.workflow.validation import ResolvedAsset, normalize_request
from app.schemas import RefKind


def omni_request(**overrides):
    return GenerationRequest.model_validate(dict(mode='ref2va', prompt='<Picture 1> in a quiet kitchen.',
        method='fast_h3_omni_8step', width=512, height=640,
        references=[dict(asset_id='image', kind='image', role='identity')], **overrides))


@pytest.mark.parametrize('override', [dict(mode='text'), dict(mode='first_frame'), dict(mode='performance'),
    dict(weights='gguf_q3km'), dict(encoder='heretic'), dict(steps=20), dict(sampler_name='er_sde'),
    dict(scheduler='beta'), dict(custom_sigmas=[1.,0.]), dict(lora_chain=[dict(name='swap.safetensors')]),
    dict(continuity=dict(auto_split=True)), dict(length=243), dict(width=1536, height=1536),
    dict(references=[dict(asset_id='guide',kind='video',role='aligned_guide')])])
def test_omni_rejects_method_mixing_and_unmeasured_bounds(override):
    payload = normalize_request(omni_request())[0].model_dump(mode='json')
    payload.update(override)
    _, issues = validate_request(GenerationRequest.model_validate(payload), {'image': ResolvedAsset(id='image',kind=RefKind.image,comfy_name='img.png')})
    assert any(i.code.startswith('omni_') and i.severity.value == 'error' for i in issues)


class OmniFake(FakeComfy):
    base_url = 'http://127.0.0.1:8237'
    ws_url = 'ws://127.0.0.1:8237/ws'
    version = '0.42.0'

    async def system_stats(self):
        self._guard()
        return {'system': {'comfyui_version': self.version}}

    async def object_info(self):
        self._guard()
        info = deepcopy(CONTRACT)
        info['UNETLoader']['input']['required']['unet_name'][0].append('fasth3_omniref_8step_pruned_int8_convrot.safetensors')
        info['MiniMaxH3SigmaShift'] = {'python_module':'comfy_extras.nodes_minimax_h3', 'input': {'required': {'model':['MODEL'], 'shift_video':['FLOAT'], 'shift_audio':['FLOAT']}}}
        return info


def test_omni_independent_backend_submission_and_cancel(settings, comfy, png_bytes):
    omni = OmniFake()
    app = create_app(settings, comfy_client=comfy, omni_comfy_client=omni)
    with TestClient(app) as client:
        asset = client.post('/api/assets', files={'file': ('image.png', png_bytes, 'image/png')}).json()
        app.state.db.set_asset_comfy_name(asset['id'], 'normal-only.png')
        preset = next(p for p in client.get('/api/presets').json()['presets'] if p['id']=='fasth3-omni-scenes')
        assert preset['available'] is True
        payload = omni_request().model_dump(mode='json')
        payload.update(preset['patch'])
        payload['references'] = [dict(asset_id=asset['id'],kind='image',role='identity')]
        response = client.post('/api/jobs', json=payload)
        assert response.status_code == 201, response.text
        job = response.json()['job']
        assert omni.uploaded and not comfy.uploaded
        assert omni.submitted and not comfy.submitted
        assert client.post('/api/jobs/'+job['id']+'/cancel').status_code == 200
        assert omni.deleted == [job['comfy_prompt_id']]
        assert not comfy.deleted


def test_omni_pdd_gate_fails_closed_on_legacy_core(settings, comfy):
    omni = OmniFake()
    omni.version = '0.36.0'
    app = create_app(settings, comfy_client=comfy, omni_comfy_client=omni)
    with TestClient(app) as client:
        method = next(m for m in client.get('/api/capabilities').json()['methods'] if m['id']=='fast_h3_omni_8step')
        assert not method['available']
        assert 'PDD' in method['unavailable_reason']


@pytest.mark.parametrize('fault', ['checkpoint','node','signature','native','autogrow','version','stats','offline'])
def test_omni_capability_fails_closed(settings, comfy, fault):
    class BrokenOmni(OmniFake):
        async def object_info(self):
            info = await super().object_info()
            if fault == 'checkpoint':
                info['UNETLoader']['input']['required']['unet_name'][0].remove('fasth3_omniref_8step_pruned_int8_convrot.safetensors')
            if fault == 'node':
                del info['LoadVideo']
            if fault == 'signature':
                info['MiniMaxH3SigmaShift']['input']['required']['shift_video'] = ['STRING']
            if fault == 'native':
                info['MiniMaxH3SigmaShift']['python_module'] = 'custom_nodes.backport'
            if fault == 'autogrow':
                del info['MiniMaxH3ReferenceToVideo']['input']['optional']['ref_videos']
            return info
        async def system_stats(self):
            if fault == 'stats':
                raise ComfyError('no stats')
            return {'system': {'comfyui_version': 'unknown' if fault == 'version' else self.version}}
    omni = BrokenOmni(online=fault != 'offline')
    app = create_app(settings, comfy_client=comfy, omni_comfy_client=omni)
    with TestClient(app) as client:
        method = next(m for m in client.get('/api/capabilities').json()['methods'] if m['id']=='fast_h3_omni_8step')
        assert not method['available']
        assert method['unavailable_reason']


def test_omni_upload_failure_never_reuses_other_backend_name(settings, comfy, png_bytes):
    class UploadFailure(OmniFake):
        async def upload_input(self, **kwargs):
            raise ComfyError('upload refused')
    omni = UploadFailure()
    app = create_app(settings, comfy_client=comfy, omni_comfy_client=omni)
    with TestClient(app) as client:
        asset = client.post('/api/assets', files={'file': ('image.png', png_bytes, 'image/png')}).json()
        app.state.db.set_asset_comfy_name(asset['id'], 'normal-only.png')
        payload = normalize_request(omni_request())[0].model_dump(mode='json')
        payload['references'][0]['asset_id'] = asset['id']
        response = client.post('/api/jobs', json=payload)
        assert response.status_code == 422, response.text
        assert 'asset_upload_failed' in response.text
        assert not omni.submitted


def test_omni_history_and_output_use_own_backend_with_main_offline(settings, png_bytes):
    import time
    normal = FakeComfy(online=False)
    omni = OmniFake()
    app = create_app(settings, comfy_client=normal, omni_comfy_client=omni)
    with TestClient(app) as client:
        asset = client.post('/api/assets', files={'file': ('image.png', png_bytes, 'image/png')}).json()
        payload = normalize_request(omni_request())[0].model_dump(mode='json')
        payload['references'][0]['asset_id'] = asset['id']
        validated = client.post('/api/validate', json=payload).json()
        assert validated['ok'], validated
        assert validated['estimate_seconds'] is None
        assert 'Solo se midió una imagen' in validated['estimate_basis']
        response = client.post('/api/jobs', json=payload)
        assert response.status_code == 201, response.text
        job = response.json()['job']
        omni.complete(job['comfy_prompt_id'], content=b'omni-test-output')
        for _ in range(100):
            done = client.get('/api/jobs/'+job['id']).json()
            if done['status'] == 'completed':
                break
            time.sleep(.02)
        assert done['status'] == 'completed', done
        assert client.get(done['outputs'][0]['url']).content == b'omni-test-output'
        assert client.get('/api/jobs').json()['total'] == 1
        assert done['request']['method'] == 'fast_h3_omni_8step'


def test_omni_running_cancel_interrupts_only_owned_runtime(settings, comfy, png_bytes):
    omni = OmniFake()
    app = create_app(settings, comfy_client=comfy, omni_comfy_client=omni)
    with TestClient(app) as client:
        asset = client.post('/api/assets', files={'file': ('image.png', png_bytes, 'image/png')}).json()
        payload = normalize_request(omni_request())[0].model_dump(mode='json')
        payload['references'][0]['asset_id'] = asset['id']
        job = client.post('/api/jobs', json=payload).json()['job']
        omni.pending.clear()
        omni.running.append(job['comfy_prompt_id'])
        assert client.post('/api/jobs/'+job['id']+'/cancel').status_code == 200
        assert omni.interrupt_calls == 1
        assert comfy.interrupt_calls == 0


def test_omni_native_graph_inputs_match_probed_contract():
    import asyncio
    request = normalize_request(omni_request())[0]
    info = asyncio.run(OmniFake().object_info())
    graph = build_workflow(request, {'image': ResolvedAsset(id='image',kind=RefKind.image,comfy_name='ref.png')}, seed=0, filename_prefix='test').prompt
    for node in graph.values():
        schema = info[node['class_type']]['input']
        allowed = {**schema.get('required',{}), **schema.get('optional',{})}
        assert all(name.split('.')[0] in allowed for name in node['inputs'])


def test_omni_normal_video_and_audio_references_are_wired():
    payload = normalize_request(omni_request())[0].model_dump(mode='json')
    payload['references'] += [dict(asset_id='video',kind='video',role='motion',include_audio=True), dict(asset_id='audio',kind='audio',role='voice')]
    assets = {'image': ResolvedAsset(id='image',kind=RefKind.image,comfy_name='image.png'),
              'video': ResolvedAsset(id='video',kind=RefKind.video,comfy_name='video.mp4',duration_seconds=5,has_audio=True),
              'audio': ResolvedAsset(id='audio',kind=RefKind.audio,comfy_name='audio.wav',duration_seconds=5)}
    request, issues = validate_request(GenerationRequest.model_validate(payload), assets)
    assert not has_errors(issues), issues
    graph = build_workflow(request, assets, seed=0, filename_prefix='test').prompt
    assert graph['5']['inputs']['ref_videos.ref_video_0'] == ['17',0]
    assert graph['5']['inputs']['ref_video_audios.ref_video_audio_0'] == ['17',1]
    assert graph['5']['inputs']['ref_audios.ref_audio_0'] == ['18',0]
    assert not any(v['class_type']=='MiniMaxH3AddGuide' for v in graph.values())


@pytest.mark.parametrize('dimensions, expected', [
    pytest.param(dict(height=639), (512, 640), id='omitted-width-snapped-height'),
    pytest.param(dict(width=511), (512, 640), id='snapped-width-omitted-height'),
    pytest.param({}, (512, 640), id='both-omitted'),
    pytest.param(dict(width=832, height=480), (832, 480), id='explicit-valid-canvas'),
])
def test_omni_canvas_snaps_after_method_defaults(dimensions, expected):
    request = GenerationRequest(mode='ref2va', method='fast_h3_omni_8step',
        prompt='<Picture 1> in a quiet kitchen.',
        references=[dict(asset_id='image', kind='image', role='identity')], **dimensions)
    normalized, issues = validate_request(request, {
        'image': ResolvedAsset(id='image', kind=RefKind.image, comfy_name='image.png'),
    })
    assert (normalized.width, normalized.height) == expected
    assert not any(issue.code == 'omni_dimensions' for issue in issues)
    assert not has_errors(issues), issues


def test_omni_omitted_canvas_uses_measured_short_clip_defaults():
    request = GenerationRequest(mode='ref2va',method='fast_h3_omni_8step',prompt='scene',references=[dict(asset_id='image',kind='image',role='identity')])
    normalized, _ = normalize_request(request)
    assert (normalized.width, normalized.height, normalized.length) == (512,640,124)


def test_omni_graph_matches_measured_scene_recipe():
    request = GenerationRequest(mode='ref2va', prompt='<Picture 1> in a quiet kitchen.',
        method='fast_h3_omni_8step', width=512, height=640,
        references=[dict(asset_id='image', kind='image', role='identity')])
    request, _ = normalize_request(request)
    assert (request.steps, request.sampler_name, request.scheduler, request.ref_image_size) == (8, 'euler', 'simple', 'max')
    graph = build_workflow(request, {'image': ResolvedAsset(id='image', kind=RefKind.image, comfy_name='omni/image.png')}, seed=0, filename_prefix='test').prompt
    assert graph['1']['inputs']['unet_name'] == 'fasth3_omniref_8step_pruned_int8_convrot.safetensors'
    shift = next(k for k,v in graph.items() if v['class_type'] == 'MiniMaxH3SigmaShift')
    assert graph[shift]['inputs'] == dict(model=['1',0], shift_video=12, shift_audio=3)
    assert graph['6']['inputs']['model'] == graph['9']['inputs']['model'] == [shift,0]
    assert graph['5']['inputs']['ref_images.ref_image_0'] == ['15',0]
    assert graph['15']['inputs']['image'] == 'omni/image.png'
    assert '101' not in graph
    assert not any('Lora' in node['class_type'] or 'Attention' in node['class_type'] for node in graph.values())
