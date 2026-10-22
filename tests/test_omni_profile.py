"""CPU-only isolated optional runtime contracts."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer_omni',ROOT/'scripts/kinjutsu.py')
k=importlib.util.module_from_spec(spec); spec.loader.exec_module(k)


def test_explicit_profile_plan_is_independent_and_never_autostarts():
    base=k.dependency_plan(ROOT)
    omni=k.dependency_plan(ROOT,profile='fasth3-omni')
    assert base['core_revision']==k.CORE_REVISION
    assert base['environment']=='runtime/venv'
    assert omni['core_revision']=='b1a247c9cf9dbfda4b2c0a0c1d50950667eeaa0c'
    assert omni['environment']=='runtime/fasth3-omni/venv'
    assert omni['core']=='runtime/fasth3-omni/ComfyUI'
    assert omni['autostart'] is False and omni['automatic_downloads'] is False
    command=k.omni_service(ROOT)['cmd']
    for flag in ('--normalvram','--disable-dynamic-vram','--disable-async-offload','--disable-cuda-malloc','--disable-all-custom-nodes'):
        assert flag in command
    assert command[command.index('--reserve-vram')+1]=='6'
    assert command[command.index('--port')+1]=='8237'
    assert command[command.index('--listen')+1]=='127.0.0.1'
    assert 'fasth3-omni' not in k.service_commands(ROOT)


def test_default_model_iteration_skips_optional_without_losing_catalog_ids(tmp_path,monkeypatch):
    entries=[dict(target='vae/a',optional=False),dict(target='diffusion_models/omni',optional=True)]
    manager=Mock()
    manager.entries=entries
    manager.discover.return_value=None
    manager.install.return_value={'status':'installed'}
    monkeypatch.setattr(k,'managed_models',lambda root:manager)
    k.model_files(tmp_path,entries,download=True)
    manager.install.assert_called_once_with('0',True)


def test_omni_models_require_verified_shared_and_only_download_missing_omni(tmp_path,monkeypatch):
    entries=[dict(target='diffusion_models/base'),dict(target='text_encoders/shared'),dict(target='vae/video'),dict(target='vae/audio'),dict(target='loras/not-for-omni'),dict(target='diffusion_models/omni',optional=True,profile='fasth3-omni')]
    manager=Mock();manager.entries=entries
    manager.discover.side_effect=lambda e: None if e.get('optional') else tmp_path/e['target']
    manager.install.return_value={'status':'installed'}
    monkeypatch.setattr(k,'managed_models',lambda root:manager)
    k.omni_models(tmp_path,download=True)
    manager.install.assert_called_once_with('5',True)
    manager.write_mapping.assert_called_with(profile='fasth3-omni')
    manager.reset_mock();manager.discover.return_value=None;manager.discover.side_effect=None
    import pytest
    with pytest.raises(RuntimeError,match='shared'): k.omni_models(tmp_path,download=True)
    manager.install.assert_not_called()


def test_isolated_install_provisions_without_models_or_start(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(k,'tool',lambda root,name:name)
    monkeypatch.setattr(k,'prerequisites',lambda *a:None)
    monkeypatch.setattr(k,'verify_omni_runtime',lambda *a,**kw:None,raising=False)
    monkeypatch.setattr(k,'register_omni_workstation',lambda root:calls.append('register'),raising=False)
    monkeypatch.setattr(k,'omni_models',lambda *a,**kw:calls.append(kw))
    def run(args,**kwargs):
        calls.append([str(a) for a in args])
        if args[:2]==['uv','venv']:
            py=tmp_path/'runtime/fasth3-omni/venv/Scripts/python.exe'
            py.parent.mkdir(parents=True);py.write_text('fixture')
        return ''
    monkeypatch.setattr(k,'run',run)
    (tmp_path/'dependencies').mkdir()
    (tmp_path/'dependencies/fasth3-omni.lock').write_bytes((ROOT/'dependencies/fasth3-omni.lock').read_bytes())
    k.install_omni(tmp_path)
    flattened=json.dumps(calls)
    assert 'fasth3-omni.lock' in flattened
    assert '--require-hashes' in flattened and '--no-deps' in flattened
    assert '7a131' not in flattened and 'h3-aligned-guide' not in flattened
    assert not (tmp_path/'runtime/venv').exists()
    assert not (tmp_path/'runtime/installed.json').exists()
    assert dict(download=False,require_all=False) in calls
    assert 'register' in calls
    receipt=json.loads((tmp_path/'runtime/fasth3-omni/installed.json').read_text())
    assert receipt['verified'] is True and receipt['profile']=='fasth3-omni'


def test_cli_explicit_profile_plan_has_no_side_effects(tmp_path,monkeypatch,capsys):
    import sys
    monkeypatch.setattr(sys,'argv',['kinjutsu.py','install','--profile','fasth3-omni','--root',str(ROOT),'--dry-run'])
    k.main()
    plan=json.loads(capsys.readouterr().out)
    assert plan['profile']=='fasth3-omni'
    assert all(e.get('profile')=='fasth3-omni' or e['target'].startswith(('vae/','text_encoders/')) for e in plan['models'])
    assert plan['automatic_downloads'] is False


def test_omni_stop_only_terminates_receipt_owned_identity(tmp_path,monkeypatch):
    state=tmp_path/'runtime/state';state.mkdir(parents=True)
    record=dict(pid=12,create_time=4,exe='python.exe',cmdline=['python.exe','private/main.py'],cwd='private')
    path=state/'workstation-fasth3-omni.json'
    path.write_text(json.dumps(dict(process=record,root=str(tmp_path),profile='fasth3-omni')))
    calls=[]
    monkeypatch.setattr(k,'is_owned',lambda r:False)
    monkeypatch.setattr(k,'terminate_record',lambda r:calls.append(r))
    k.stop_omni(tmp_path)
    assert not calls
    monkeypatch.setattr(k,'is_owned',lambda r:r==record)
    k.stop_omni(tmp_path)
    assert calls==[record] and not path.exists()


def test_omni_lock_is_standalone_hash_pinned_and_default_lock_unchanged():
    import re,hashlib
    base=(ROOT/'dependencies/requirements.lock').read_text()
    lock=(ROOT/'dependencies/fasth3-omni.lock').read_text()
    evidence=json.loads((ROOT/'dependencies/fasth3-omni-provenance.json').read_text())
    assert evidence['base_lock_normalized_lf_sha256']==hashlib.sha256(base.encode()).hexdigest()
    assert 'comfy-kitchen==0.2.33' in base and 'comfy-aimdo==0.4.13' in base
    assert 'comfy-kitchen==0.2.39' in lock and 'comfy-aimdo==0.5.6' in lock
    assert 'comfyui-frontend-package==1.55.18' in lock
    for change in evidence['updates']:
        assert change['metadata_url'].startswith('https://pypi.org/pypi/')
        for wheel in change['wheels']: assert '--hash=sha256:'+wheel['sha256'] in lock
    pins=dict(re.findall(r'^([\w-]+)==([^\s]+)',lock,re.M))
    assert not any('tensorrt' in name or 'sageattention' in name or 'triton' in name for name in pins)
    assert all('--hash=sha256:' in block for block in re.split(r'(?m)^(?=[\w-]+==)',lock)[1:])


def test_omni_manifest_pinned_optional_and_default_counts_unchanged():
    entries=k.load_manifest(ROOT/'models/manifest.json',ROOT/'models')
    required=[e for e in entries if not e.get('optional',False)]
    optional=[e for e in entries if e.get('optional',False)]
    assert len(required)==6 and len(optional)==1
    omni=optional[0]
    assert omni['included'] is False and omni['size']==22213723064
    assert omni['revision']=='82eff2a6eee6c962846879f4bab52610a4df24d3'
    assert omni['sha256']=='851b2dc9670ed864b7f1e951ac9da047d83b1c04ded9bfcc1a9e5bba0ee33f80'


def test_private_model_mapping_has_no_loras_and_default_omits_omni(tmp_path):
    import sys,hashlib
    sys.path.insert(0,str(ROOT/'studio/backend'))
    from app.services.model_manager import ModelManager
    entries=[]
    for target,profile in [('text_encoders/shared',None),('vae/video',None),('vae/audio',None),('loras/task',None),('diffusion_models/base',None),('diffusion_models/omni','fasth3-omni')]:
        path=tmp_path/'models'/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(target.encode())
        entry=dict(target=target,path=target,size=len(target.encode()),sha256=hashlib.sha256(target.encode()).hexdigest(),revision='a'*40,repo='test/test',included=False)
        if profile:entry.update(profile=profile,optional=True)
        entries.append(entry)
    (tmp_path/'models/manifest.json').write_text(json.dumps(dict(models=entries)))
    m=ModelManager(tmp_path);m.write_mapping();m.write_mapping(profile='fasth3-omni')
    private=(tmp_path/'runtime/fasth3-omni/extra_model_paths.yaml').read_text()
    assert 'loras' not in private and 'catalog_4:' not in private
    assert 'catalog_5:' in private and 'catalog_0:' in private
    assert 'catalog_5:' not in (tmp_path/'runtime/extra_model_paths.yaml').read_text()
    row=m.catalog()['models'][5]
    assert row['optional'] is True and row['required_by']==['fasth3-omni-scenes']
