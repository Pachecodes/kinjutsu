from copy import deepcopy
import pytest
from app.schemas import GenerationRequest, RefKind
from app.workflow.validation import ResolvedAsset, validate_request
from app.workflow.builder import build_workflow
from app.capabilities import build_capabilities
from tests.conftest import CONTRACT

NAME = 'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors'

def request():
    return GenerationRequest.model_validate(dict(mode='ref2va', prompt='body_swap: Replace the main subject with <Picture 1>. Preserve guide scene and motion.', width=576, height=1024, length=124, steps=20, method='baseline', weights='int8', sampler_name='res_multistep', scheduler='beta', continuity={'auto_split':False}, lora_chain=[{'name':NAME,'strength':1.0}], references=[{'asset_id':'portrait','kind':'image','role':'identity'},{'asset_id':'guide','kind':'video','role':'aligned_guide'}]))

def assets(**changes):
    return {'portrait':ResolvedAsset(id='portrait',kind=RefKind.image,comfy_name='h3studio/portrait.png'), 'guide':ResolvedAsset(id='guide',kind=RefKind.video,comfy_name='h3studio/guide.mp4',duration_seconds=124/24, width=576,height=1024,frame_count=124,fps=24, **changes)}

def test_aligned_guide_is_keyframe_conditioning_not_a_video_reference():
    req = request()
    normalized, issues = validate_request(req, assets(), aligned_guides_available=True)
    assert not [i for i in issues if i.severity.value=='error']
    graph = build_workflow(normalized,assets(),seed=1,filename_prefix='no-submit').prompt
    guides = [(key,node) for key,node in graph.items() if node['class_type']=='MiniMaxH3AddGuide']
    assert len(guides)==1
    key,node=guides[0]
    assert node['inputs']=={'positive':['5',0], 'latent':['5',1], 'vae':['3',0], 'image':['17',0], 'frame_idx':0}
    assert graph['6']['inputs']['conditioning']==[key,0]
    assert graph['10']['inputs']['latent_image']==['5',1]
    assert not any(k.startswith('ref_videos') for k in graph['5']['inputs'])
    assert graph['9']['inputs']['model']==['1',0]

@pytest.mark.parametrize('field,value,code', [('fps',30,'guide_alignment'),('frame_count',123,'guide_alignment'),('width',608,'guide_alignment'),('height',None,'guide_metadata_missing')])
def test_alignment_fails_closed(field,value,code):
    data=assets(); from dataclasses import replace
    data['guide']=replace(data['guide'], **{field:value})
    _, issues=validate_request(request(),data,aligned_guides_available=True)
    assert code in [i.code for i in issues if i.severity.value=='error']

def test_live_node_capability_is_required():
    _,issues=validate_request(request(),assets(),aligned_guides_available=False)
    assert 'guide_unavailable' in [i.code for i in issues]

def test_character_swap_requires_guide_and_trigger():
    req=request(); req.references=req.references[:1]; req.prompt='A person <Picture 1>'
    _,issues=validate_request(req,assets(),aligned_guides_available=True)
    assert {'character_swap_guide_required','character_swap_trigger'} <= {i.code for i in issues}

def test_real_aligned_synthetic_guide_is_probed_without_gpu(synthetic_guide):
    from app.services.assets import probe_aligned_video
    from pathlib import Path
    metadata = probe_aligned_video(synthetic_guide[1], synthetic_guide[0]/'guide-124f-576x1024-24fps.mp4')
    assert metadata == {'width':576,'height':1024,'frame_count':124,'fps':24.0}


def test_character_swap_preset_is_fail_closed():
    from app.api import _presets_with_availability
    info=deepcopy(CONTRACT)
    caps=build_capabilities(info,comfy_url='test',comfy_online=True,source='live')
    preset=next(p for p in _presets_with_availability(caps) if p['id']=='character-swap-v11')
    assert preset['available'] is False
    info['LoraLoaderModelOnly']['input']['required']['lora_name'][0].append(NAME)
    info['MiniMaxH3AddGuide']={'input':{'required':{'positive':['CONDITIONING'],'latent':['LATENT'],'frame_idx':['INT']},'optional':{'vae':['VAE'],'image':['IMAGE']}}}
    caps=build_capabilities(info,comfy_url='test',comfy_online=True,source='live')
    assert caps.aligned_guides
    preset=next(p for p in _presets_with_availability(caps) if p['id']=='character-swap-v11')
    assert preset['available']
    assert preset['patch']['lora_chain']==[{'name':NAME,'strength':1.0}]
    assert preset['patch']['method']=='baseline'
    assert preset['patch']['steps']==20
    assert not preset['patch']['continuity']['auto_split']


def test_api_upload_validate_and_build_owned_guide_without_gpu(client, app, comfy, monkeypatch, synthetic_guide):
    from pathlib import Path
    info=deepcopy(CONTRACT)
    info['LoraLoaderModelOnly']['input']['required']['lora_name'][0].append(NAME)
    info['MiniMaxH3AddGuide']={'input':{'required':{'positive':['CONDITIONING'],'latent':['LATENT'],'frame_idx':['INT']},'optional':{'vae':['VAE'],'image':['IMAGE']}}}
    async def object_info(): return info
    monkeypatch.setattr(comfy,'object_info',object_info)
    app.state.assets.ffprobe_path=synthetic_guide[1]
    root=synthetic_guide[0]
    image=client.post('/api/assets',files={'file':('portrait.jpg',(root/'Picture1.jpg').read_bytes(),'image/jpeg')})
    guide=client.post('/api/assets',files={'file':('guide.mp4',(root/'guide-124f-576x1024-24fps.mp4').read_bytes(),'video/mp4')})
    assert image.status_code==201, image.text
    assert guide.status_code==201, guide.text
    req=request().model_dump(mode='json')
    req['references'][0]['asset_id']=image.json()['id']
    req['references'][1]['asset_id']=guide.json()['id']
    result=client.post('/api/validate',json=req)
    assert result.status_code==200, result.text
    assert result.json()['ok'],result.text
    req['length']=141
    invalid=client.post('/api/jobs',json=req)
    assert invalid.status_code==422,invalid.text
    assert not comfy.submitted
    req['length']=124
    created=client.post('/api/jobs',json=req)  # in-memory FakeComfy only, no real service
    assert created.status_code==201,created.text
    graph=comfy.submitted[0]['prompt']
    assert graph['106']['class_type']=='MiniMaxH3AddGuide'
    assert graph['6']['inputs']['conditioning']==['106',0]
    assert graph['5']['inputs']['ref_images.ref_image_0']
    assert not any(k.startswith('ref_videos') for k in graph['5']['inputs'])
    assert created.json()['job']['request']['references'][1]['role']=='aligned_guide'


def test_builder_rejects_split_guides_before_continuity_can_drop_them():
    from app.schemas import ContinuityOptions
    from app.workflow.builder import WorkflowBuildError
    req=request().model_copy(update={'length':498,'continuity':ContinuityOptions(auto_split=True)})
    with pytest.raises(WorkflowBuildError,match='continuity'):
        build_workflow(req,assets(),seed=1,filename_prefix='no-submit')


@pytest.mark.parametrize('flag', ['offline','fallback','bad_schema'])
def test_guide_capability_rejects_untrusted_contract(flag):
    info=deepcopy(CONTRACT)
    info['MiniMaxH3AddGuide']={} if flag=='bad_schema' else {'input':{'required':{'positive':['CONDITIONING'],'latent':['LATENT'],'frame_idx':['INT']},'optional':{'vae':['VAE'],'image':['IMAGE']}}}
    caps=build_capabilities(info,comfy_url='test',comfy_online=flag!='offline',source='contract-fallback' if flag=='fallback' else 'live')
    assert not caps.aligned_guides


@pytest.mark.parametrize('schema_name',['DirectorRequest','PromptChatRequest'])
def test_prompt_ai_does_not_reinterpret_guide_as_an_ordinary_video(schema_name):
    from app import schemas
    from pydantic import ValidationError
    data={'mode':'ref2va','references':[{'asset_id':'guide','kind':'video','role':'aligned_guide'}]}
    data.update({'prompt':'body_swap: <Picture 1>'} if schema_name=='DirectorRequest' else {'messages':[{'role':'user','content':'Help'}]})
    with pytest.raises(ValidationError, match='manual prompt'):
        getattr(schemas,schema_name).model_validate(data)


def test_guides_not_advertised_offline_or_without_node():
    caps=build_capabilities(CONTRACT,comfy_url='test',comfy_online=True,source='live')
    assert not caps.aligned_guides

@pytest.fixture
def synthetic_guide(tmp_path):
    import shutil, subprocess
    from pathlib import Path
    ffmpeg=shutil.which('ffmpeg'); ffprobe=shutil.which('ffprobe')
    if not ffmpeg or not ffprobe: pytest.skip('Synthetic media test requires ffmpeg + ffprobe')
    subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=blue:s=576x1024:r=24','-frames:v','124','-c:v','libx264','-pix_fmt','yuv420p',str(tmp_path/'guide-124f-576x1024-24fps.mp4')],check=True,capture_output=True)
    subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=red:s=64x64','-frames:v','1',str(tmp_path/'Picture1.jpg')],check=True,capture_output=True)
    return tmp_path,ffprobe
