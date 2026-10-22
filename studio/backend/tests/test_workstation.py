"""CPU-only workstation contract; never launches GPU, browsers or Explorer."""
import hashlib
import json
from pathlib import Path
import pytest


def test_first_run_status_is_read_only(tmp_path):
    from app.services.workstation import Workstation
    w = Workstation(tmp_path, standard_roots=[])
    status = w.status()
    assert status['state'] == 'configuration_required'
    assert status['capabilities']['start'] is False
    assert not (tmp_path/'runtime').exists()


def test_discovery_stable_deduplicated_and_requires_admin_approval(tmp_path):
    from app.services.workstation import Workstation, WorkstationError
    cfg=configured(tmp_path)
    w=Workstation(tmp_path, standard_roots=[Path(cfg['runtimes'][0]['root'])]*3)
    first=w.discover()
    assert len(first['runtimes']) == 1
    row=first['runtimes'][0]
    assert row['id'] == w.discover()['runtimes'][0]['id']
    assert row['approved'] is True
    assert 'executable' not in row and 'argv' not in row
    assert len(first['roots']) == 1
    with pytest.raises(WorkstationError): w.select(row['id'], False)
    selected=w.select(row['id'], True)
    assert selected['selected_id'] == row['id']
    assert json.loads((tmp_path/'runtime/workstation-selection.json').read_text())['selected_id']==row['id']
    cfg['runtimes'][0]['approved']=False
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(cfg))
    with pytest.raises(WorkstationError): w.select(row['id'],True)


@pytest.mark.parametrize('change',[
    {'root':'relative'}, {'port':0}, {'port':True}, {'executable':'cmd.exe'},
    {'argv':['/c','evil']}, {'argv':['main.py','--listen','0.0.0.0','--port','8188']},
    {'cwd':'relative'}, {'url':'https://evil.invalid'},
    {'model_roots':['relative']}, {'folders':{'models':'relative'}},
])
def test_reject_invalid_admin_config(tmp_path,change):
    from app.services.workstation import Workstation, WorkstationError
    cfg=configured(tmp_path); cfg['runtimes'][0].update(change)
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(cfg))
    with pytest.raises(WorkstationError): Workstation(tmp_path,standard_roots=[]).discover()


@pytest.fixture
def comfy_server():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class Handler(BaseHTTPRequestHandler):
        payload={'system':{'comfyui_version':'fixture'},'devices':[]}
        def do_GET(self):
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps(self.payload).encode())
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    yield server,Handler
    server.shutdown(); server.server_close(); thread.join()


def selected_station(tmp_path, monkeypatch, port=8188):
    from app.services.workstation import Workstation
    cfg=configured(tmp_path,port=port)
    w=Workstation(tmp_path,standard_roots=[])
    monkeypatch.setattr(w,'listeners',lambda: {})
    identifier=w.discover()['runtimes'][0]['id']; w.select(identifier,True)
    return w,cfg['runtimes'][0]


def test_real_loopback_health_requires_exact_listener_identity(tmp_path,monkeypatch,comfy_server):
    server,_=comfy_server
    w,item=selected_station(tmp_path,monkeypatch,server.server_port)
    assert w.probe(item['port']) is True
    assert w.status()['state']=='port_conflict'  # healthy HTTP alone is not identity
    owner={'pid':123,'create_time':10,'exe':item['executable'],'cmdline':[item['executable']]+item['argv'],'cwd':item['cwd']}
    monkeypatch.setattr(w,'listeners',lambda:{item['port']:owner})
    assert w.status()['state']=='online'
    assert w.start()['reused'] is True
    owner['cmdline']=['foreign']
    assert w.status()['state']=='port_conflict'
    from app.services.workstation import WorkstationError
    with pytest.raises(WorkstationError): w.start()


def test_probe_rejects_non_comfy_and_redirects(tmp_path,comfy_server):
    from app.services.workstation import Workstation
    server,handler=comfy_server; handler.payload={'not':'comfy'}
    w=Workstation(tmp_path,standard_roots=[])
    assert w.probe(server.server_port) is False


def test_start_fixed_command_once_no_autostart_or_restart(tmp_path,monkeypatch):
    import app.services.workstation as module
    w,item=selected_station(tmp_path,monkeypatch)
    monkeypatch.setattr(w,'port_free',lambda port:True)
    calls=[]
    class Child:
        pid=123
        def poll(self): return None
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw: calls.append((a,kw)) or Child())
    owner=dict(pid=123,create_time=42,exe=item['executable'],cmdline=[item['executable']]+item['argv'],cwd=item['cwd'])
    monkeypatch.setattr(module,'process_record',lambda pid:owner)
    monkeypatch.setattr(module,'record_alive',lambda record:record==owner)
    assert w.status()['state']=='stopped' and not calls
    assert w.start()['state']=='starting'
    assert w.start()['state']=='starting'
    assert len(calls)==1
    args,kwargs=calls[0]
    assert args[0]==[item['executable']]+item['argv']
    assert kwargs['shell'] is False and kwargs['cwd']==item['cwd']
    assert kwargs['creationflags']==getattr(module.subprocess,'CREATE_NO_WINDOW',0)
    assert 'PYTHONPATH' not in kwargs['env']
    receipt=json.loads((tmp_path/'runtime/state/workstation-comfy.json').read_text())
    assert receipt['process']==owner
    assert 'cmdline' not in json.dumps(w.status())


@pytest.fixture(autouse=True)
def no_real_listener_discovery(monkeypatch):
    from app.services.workstation import Workstation
    monkeypatch.setattr(Workstation,'listeners',staticmethod(lambda:{}))


def test_discover_running_candidate_is_not_automatically_approved(tmp_path,monkeypatch):
    from app.services.workstation import Workstation
    cfg=configured(tmp_path)
    item=cfg['runtimes'][0]
    (tmp_path/'runtime/workstation.json').unlink()
    w=Workstation(tmp_path,standard_roots=[])
    owner=dict(pid=1,exe=item['executable'],cmdline=[item['executable']]+item['argv'],cwd=item['cwd'])
    monkeypatch.setattr(w,'listeners',lambda:{item['port']:owner})
    monkeypatch.setattr(w,'probe',lambda port:True)
    discovered=w.discover()
    assert len(discovered['runtimes'])==1
    assert discovered['runtimes'][0]['approved'] is False
    assert discovered['runtimes'][0]['online'] is True
    assert w.status()['state']=='configuration_required'


def test_adopt_root_verifies_manifest_before_any_write(tmp_path,monkeypatch):
    from app.services.workstation import WorkstationError
    w,item=selected_station(tmp_path,monkeypatch)
    models=Path(item['model_roots'][0]); target=models/'loras/a.safetensors'; target.write_bytes(b'abc')
    package_models=tmp_path/'models'; package_models.mkdir()
    entry=dict(repo='test/test',path='a.safetensors',revision='a'*40,size=3,
        sha256=hashlib.sha256(b'abc').hexdigest(),target='loras/a.safetensors',included=False)
    (package_models/'manifest.json').write_text(json.dumps({'models':[entry]}))
    candidate=w.discover()['roots'][0]['id']
    assert w.select_root(candidate,True)['verified_models']==1
    assert json.loads((tmp_path/'runtime/model-roots.json').read_text())['roots']==[str(models)]
    assert 'loras' in (tmp_path/'runtime/extra_model_paths.yaml').read_text()
    before=(tmp_path/'runtime/model-roots.json').read_bytes()
    target.write_bytes(b'bad')
    with pytest.raises(WorkstationError): w.select_root(candidate,True)
    assert (tmp_path/'runtime/model-roots.json').read_bytes()==before
    assert target.read_bytes()==b'bad'  # never repair/copy/download
    with pytest.raises(WorkstationError): w.select_root('../escape',True)


def test_open_actions_only_selected_allowlisted_targets(tmp_path,monkeypatch):
    import app.services.workstation as module
    w,item=selected_station(tmp_path,monkeypatch)
    calls=[]; browser=[]
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:calls.append((a,kw)))
    monkeypatch.setattr(module.webbrowser,'open',lambda url:browser.append(url) or True)
    assert w.open_folder('models')['requested'] is True
    assert calls[0][0][0][1]==item['folders']['models']
    assert calls[0][1]['shell'] is False
    with pytest.raises(module.WorkstationError): w.open_folder('../escape')
    with pytest.raises(module.WorkstationError): w.open_comfy()
    monkeypatch.setattr(w,'status',lambda:dict(state='online',url=f"http://127.0.0.1:{item['port']}"))
    assert w.open_comfy()['requested'] is True
    assert browser==[f"http://127.0.0.1:{item['port']}"]


def test_http_contract_local_origin_and_payload_restrictions(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.services.workstation import router
    w,item=selected_station(tmp_path,monkeypatch)
    app=FastAPI(); app.include_router(router,prefix='/api'); app.state.workstation=w
    client=TestClient(app)
    assert client.get('/api/workstation/status').status_code==200
    assert client.get('/api/workstation/discover').status_code==200
    assert client.get('/api/workstation/roots').status_code==200
    assert client.post('/api/workstation/comfy/start',json={'executable':'evil'}).status_code==422
    assert client.post('/api/workstation/comfy/open',json={'url':'https://evil.invalid'}).status_code==422
    assert client.post('/api/workstation/folders/unknown/open',json={}).status_code==422
    assert client.post('/api/workstation/select',json={'candidate_id':'../escape','acknowledge':True}).status_code==409
    assert client.post('/api/workstation/comfy/open',json={},headers={'Origin':'https://evil.invalid'}).status_code==403
    assert client.get('/api/workstation/status',headers={'Host':'evil.invalid'}).status_code==403
    remote=TestClient(app,client=('192.0.2.1',1234))
    assert remote.post('/api/workstation/comfy/open',json={}).status_code==403
    assert 'FolderKind' in str(app.openapi()) or 'outputs' in str(app.openapi())


def test_changed_config_requires_reselection(tmp_path,monkeypatch):
    w,item=selected_station(tmp_path,monkeypatch)
    cfg=json.loads((tmp_path/'runtime/workstation.json').read_text()); cfg['runtimes'][0]['label']='Changed'
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(cfg))
    assert w.status()['state']=='configuration_required'


def test_failed_identity_recording_never_duplicates_child(tmp_path,monkeypatch):
    import app.services.workstation as module
    w,item=selected_station(tmp_path,monkeypatch)
    monkeypatch.setattr(w,'port_free',lambda port:True)
    calls=[]
    class Child:
        pid=123
        def poll(self): return None
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:calls.append(a) or Child())
    def unavailable(pid): raise OSError('unavailable')
    monkeypatch.setattr(module,'process_record',unavailable)
    with pytest.raises(module.WorkstationError): w.start()
    with pytest.raises(module.WorkstationError): w.start()
    assert len(calls)==1


def test_openapi_exposes_ui_capability_fields():
    from fastapi import FastAPI
    from app.services.workstation import router
    app=FastAPI(); app.include_router(router,prefix='/api')
    schema=app.openapi()
    response=schema['paths']['/api/workstation/status']['get']['responses']['200']['content']['application/json']['schema']
    assert response['$ref'].endswith('/WorkstationStatus')
    assert 'capabilities' in schema['components']['schemas']['WorkstationStatus']['properties']
    assert 'generation_binding' in schema['components']['schemas']['WorkstationStatus']['properties']


def test_bounded_discovery_does_not_recurse_or_inspect_beyond_cap(tmp_path,monkeypatch):
    from app.services.workstation import Workstation
    cfg=configured(tmp_path); core=Path(cfg['runtimes'][0]['root'])
    (tmp_path/'runtime/workstation.json').unlink()
    paths=[tmp_path/f'nonexistent-{i}' for i in range(64)]+[core]
    assert Workstation(tmp_path,standard_roots=paths).discover()['runtimes']==[]
    assert Workstation(tmp_path,standard_roots=[tmp_path]).discover()['runtimes']==[]


def test_probe_timeout_redirect_and_nonlocal_port_validation(tmp_path,comfy_server):
    from app.services.workstation import Workstation
    server,handler=comfy_server
    def redirect(self):
        self.send_response(302); self.send_header('Location','https://example.invalid/'); self.end_headers()
    handler.do_GET=redirect
    assert Workstation(tmp_path,standard_roots=[]).probe(server.server_port) is False


def test_real_cpu_process_receipt_rejects_pid_reuse():
    import os
    from app.services.workstation import process_record,record_alive
    record=process_record(os.getpid())
    assert record_alive(record) is True
    assert record_alive(dict(record,create_time=record['create_time']-1)) is False
    assert record_alive(dict(record,cmdline=['foreign'])) is False


def test_registered_on_studio_api():
    from fastapi import FastAPI
    from app.api import router
    app=FastAPI(); app.include_router(router)
    assert '/api/workstation/status' in app.openapi()['paths']


def test_support_hidden_utf8_portable_interpreter_prefix(tmp_path):
    from app.services.workstation import Workstation
    cfg=configured(tmp_path); argv=cfg['runtimes'][0]['argv']
    cfg['runtimes'][0]['argv']=['-X','utf8']+argv
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(cfg))
    assert Workstation(tmp_path,standard_roots=[]).discover()['runtimes'][0]['approved'] is True


def test_probe_read_timeout_is_bounded(tmp_path,comfy_server):
    import time
    from app.services.workstation import Workstation
    server,handler=comfy_server
    def delayed(self):
        time.sleep(0.8)
    handler.do_GET=delayed
    start=time.monotonic()
    assert Workstation(tmp_path,standard_roots=[]).probe(server.server_port) is False
    assert time.monotonic()-start < 1.5


def test_omni_start_is_explicit_fixed_and_receipt_scoped(tmp_path,monkeypatch):
    import importlib.util
    import app.services.workstation as module
    root=Path(__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('profile_fixture',root/'scripts/kinjutsu.py')
    k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
    service=k.omni_service(tmp_path);core=service['cwd'];core.mkdir(parents=True)
    (core/'main.py').write_text('# fixture');(core/'folder_paths.py').write_text('# fixture');(core/'comfy').mkdir()
    py=Path(service['cmd'][0]);py.parent.mkdir(parents=True);py.write_text('fixture')
    private=tmp_path/'runtime/fasth3-omni'
    (tmp_path/'dependencies').mkdir();(tmp_path/'dependencies/fasth3-omni.lock').write_text('fixture')
    (private/'installed.json').write_text(json.dumps(dict(root=str(tmp_path),verified=True,lock_sha256=k.omni_fingerprint(tmp_path))))
    k.register_omni_workstation(tmp_path)
    w=module.Workstation(tmp_path,standard_roots=[])
    assert w.status()['state']=='configuration_required'  # install is NOT select/start
    assert w.status(profile='fasth3-omni')['state']=='stopped'
    calls=[];preflight=[]
    monkeypatch.setattr(w,'port_free',lambda port:True)
    monkeypatch.setattr(w,'omni_preflight',lambda:preflight.append(True))
    class Child:
        pid=321
        def poll(self): return None
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:calls.append((a,kw)) or Child())
    item=w.selected(profile='fasth3-omni')
    owner=dict(pid=321,create_time=1,exe=item['executable'],cmdline=[item['executable']]+item['argv'],cwd=item['cwd'])
    monkeypatch.setattr(module,'process_record',lambda pid:owner)
    monkeypatch.setattr(module,'record_alive',lambda record:record==owner)
    monkeypatch.setenv('H3_COMFY_URL','http://foreign')
    assert w.start(profile='fasth3-omni')['state']=='starting'
    assert w.start(profile='fasth3-omni')['reused'] is True
    assert len(calls)==1 and len(preflight)==1
    assert calls[0][0][0]==service['cmd']
    assert 'H3_COMFY_URL' not in calls[0][1]['env']
    assert (tmp_path/'runtime/state/workstation-fasth3-omni.json').is_file()
    assert not (tmp_path/'runtime/state/workstation-comfy.json').exists()
    # Windows venv launcher remains owned, but its listening child uses base Python.
    listener=dict(owner,pid=322,exe='C:/Python312/python.exe',cmdline=['C:/Python312/python.exe']+item['argv'])
    monkeypatch.setattr(w,'listeners',lambda:{8237:listener})
    monkeypatch.setattr(w,'owned_descendants',lambda record:[listener] if record==owner else [])
    monkeypatch.setattr(w,'probe',lambda port:True)
    assert w.status(profile='fasth3-omni')['state']=='online'
    listener['create_time']=999  # receipt/lineage must match full identity, not PID/port
    monkeypatch.setattr(w,'owned_descendants',lambda record:[])
    assert w.status(profile='fasth3-omni')['state']=='port_conflict'
    cfg=json.loads((tmp_path/'runtime/workstation.json').read_text())
    cfg['runtimes'][0]['argv'].append('--highvram')
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(cfg))
    with pytest.raises(module.WorkstationError,match='fixed'): w.approved()


@pytest.fixture
def omni_failure_station(tmp_path,monkeypatch):
    import app.services.workstation as module
    w,item=selected_station(tmp_path,monkeypatch)
    item.update(key='fasth3-omni',port=8237,id='omni-fixture')
    monkeypatch.setattr(w,'selected',lambda profile=None:item)
    monkeypatch.setattr(w,'port_free',lambda port:True)
    monkeypatch.setattr(w,'omni_preflight',lambda:None)
    return w,item,module


def test_omni_spawn_failure_rolls_back_only_own_claim(omni_failure_station,monkeypatch):
    w,item,module=omni_failure_station
    claims=[]
    def fail(*args,**kwargs):
        claims.append(json.loads(w.receipt_path(item).read_text()))
        raise OSError('simulated spawn failure')
    monkeypatch.setattr(module.subprocess,'Popen',fail)
    for _ in range(2):
        with pytest.raises((OSError,module.WorkstationError),match='spawn'):
            w.start(profile='fasth3-omni')
        assert not w.receipt_path(item).exists()
        assert w.status(profile='fasth3-omni')['state']=='stopped'
    assert claims[0]['root']==str(w.root)
    assert claims[0]['profile']=='fasth3-omni'
    assert claims[0]['configuration_sha256']==w.launch_digest(item)
    assert claims[0]['claim_id']!=claims[1]['claim_id']
    installer=module.profile_installer()
    monkeypatch.setattr(installer,'terminate_record',lambda record:pytest.fail('foreign process killed'))
    installer.stop_omni(w.root)
    monkeypatch.setattr(w,'listeners',lambda:{8237:dict(pid=999,cmdline=['foreign'])})
    assert w.status(profile='fasth3-omni')['state']=='port_conflict'
    with pytest.raises(module.WorkstationError,match='port_conflict'): w.start(profile='fasth3-omni')


@pytest.mark.parametrize('death_at',[0,1])
def test_omni_dead_spawn_is_not_starting_and_can_retry(omni_failure_station,monkeypatch,death_at):
    w,item,module=omni_failure_station
    class Child:
        pid=123
        polls=0
        def poll(self):
            self.polls+=1
            return 1 if self.polls>death_at else None
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:Child())
    owner=dict(pid=123,create_time=42,exe=item['executable'],cmdline=[item['executable']]+item['argv'],cwd=item['cwd'])
    monkeypatch.setattr(module,'process_record',lambda pid:owner)
    monkeypatch.setattr(module,'record_alive',lambda record:False)
    for _ in range(2):
        with pytest.raises(module.WorkstationError,match='exited.*log'):
            w.start(profile='fasth3-omni')
        assert not w.receipt_path(item).exists()
        assert w.status(profile='fasth3-omni')['state']=='stopped'


def test_omni_failed_recording_recovers_when_created_child_dies(omni_failure_station,monkeypatch):
    w,item,module=omni_failure_station
    class Child:
        pid=123
        exitcode=None
        def poll(self): return self.exitcode
        def terminate(self): raise OSError('simulated handle access failure')
    child=Child();calls=[]
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:calls.append(True) or child)
    def unavailable(pid): raise OSError('identity unavailable')
    monkeypatch.setattr(module,'process_record',unavailable)
    with pytest.raises(module.WorkstationError,match='log'): w.start(profile='fasth3-omni')
    assert w.status(profile='fasth3-omni')['state']=='launch_unverified'
    installer=module.profile_installer()
    monkeypatch.setattr(installer,'is_owned',lambda r:False)
    monkeypatch.setattr(installer,'terminate_record',lambda r:pytest.fail('unverified/foreign kill'))
    installer.stop_omni(w.root)  # own pending metadata must not be rejected
    with pytest.raises(module.WorkstationError): w.start(profile='fasth3-omni')
    assert len(calls)==1
    child.exitcode=1
    assert w.status(profile='fasth3-omni')['state']=='stopped'
    assert not w.receipt_path(item).exists()
    with pytest.raises(module.WorkstationError): w.start(profile='fasth3-omni')
    assert len(calls)==2


def test_omni_spawn_rollback_preserves_replaced_claim(omni_failure_station,monkeypatch):
    w,item,module=omni_failure_station
    replacement=dict(root=str(w.root),profile='fasth3-omni',claim_id='another-caller',
                     configuration_sha256=w.launch_digest(item),launch_in_progress=True)
    def fail(*args,**kwargs):
        module.atomic_json(w.receipt_path(item),replacement)
        raise OSError('spawn failed')
    monkeypatch.setattr(module.subprocess,'Popen',fail)
    with pytest.raises(module.WorkstationError): w.start(profile='fasth3-omni')
    assert json.loads(w.receipt_path(item).read_text())==replacement


def test_omni_identity_failure_rolls_back_created_child_handle(omni_failure_station,monkeypatch):
    w,item,module=omni_failure_station
    calls=[]
    class Child:
        pid=123
        exitcode=None
        def poll(self): return self.exitcode
        def terminate(self):
            calls.append('terminate-own-handle')
            self.exitcode=1
        def wait(self,timeout):
            calls.append('wait-own-handle')
            return self.exitcode
    monkeypatch.setattr(module.subprocess,'Popen',lambda *a,**kw:Child())
    def unavailable(pid): raise OSError('identity unavailable')
    monkeypatch.setattr(module,'process_record',unavailable)
    for _ in range(2):
        with pytest.raises(module.WorkstationError,match='log'): w.start(profile='fasth3-omni')
        assert not w.receipt_path(item).exists()
        assert w.status(profile='fasth3-omni')['state']=='stopped'
    assert calls==['terminate-own-handle','wait-own-handle']*2


def test_optional_profile_api_never_installs_or_downloads(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.services.workstation import Workstation,router
    app=FastAPI();app.include_router(router,prefix='/api')
    app.state.workstation=Workstation(tmp_path,standard_roots=[])
    client=TestClient(app)
    url='/api/workstation/profiles/fasth3-omni'
    assert client.get(url+'/status').json()['state']=='configuration_required'
    assert client.get(url+'/status').json()['automatic_downloads'] is False
    assert client.post(url+'/start',json={}).status_code==409
    assert not (tmp_path/'runtime').exists()
    assert client.post(url+'/start',json={'command':'evil'}).status_code==422
    assert client.get('/api/workstation/profiles/not-approved/status').status_code==422


def configured(tmp_path, *, port=8188):
    core=tmp_path/'existing-comfy'; core.mkdir()
    (core/'main.py').write_text('# fixture')
    (core/'folder_paths.py').write_text('# fixture')
    (core/'comfy').mkdir()
    models=core/'models'; models.mkdir()
    (models/'loras').mkdir(); (core/'output').mkdir()
    executable=tmp_path/'python.exe'; executable.write_bytes(b'fixture')
    config={'version':1, 'runtimes':[{'key':'fixture', 'label':'Existing Comfy', 'approved':True,
        'root':str(core), 'cwd':str(core), 'port':port, 'executable':str(executable),
        'argv':['-s',str(core/'main.py'),'--listen','127.0.0.1','--port',str(port),'--disable-auto-launch'],
        'model_roots':[str(models)], 'folders':{'models':str(models),'loras':str(models/'loras'),'outputs':str(core/'output')}}]}
    (tmp_path/'runtime').mkdir()
    (tmp_path/'runtime/workstation.json').write_text(json.dumps(config))
    return config
