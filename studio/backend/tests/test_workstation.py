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
