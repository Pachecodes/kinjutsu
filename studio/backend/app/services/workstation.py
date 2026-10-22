"""Local-only workstation control. HTTP never supplies paths, URLs or commands."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import threading
import subprocess
import time
import webbrowser
from typing import Literal
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


def process_record(pid):
    import psutil
    process=psutil.Process(pid)
    return dict(pid=pid,create_time=process.create_time(),exe=process.exe(),cmdline=process.cmdline(),cwd=process.cwd())


def record_alive(record):
    import psutil
    try: return process_record(record['pid'])==record
    except (psutil.Error,OSError,KeyError): return False


class WorkstationError(ValueError):
    pass


def opaque(kind, value):
    return kind+'_'+hashlib.sha256(str(value).casefold().encode()).hexdigest()[:24]


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(path)


def profile_installer():
    """Load only the packaged fixed lifecycle module, never a client-supplied path."""
    import importlib.util
    path=Path(__file__).resolve().parents[4]/'scripts/kinjutsu.py'
    spec=importlib.util.spec_from_file_location('kinjutsu_optional_runtime',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Workstation:
    def __init__(self, root: Path, *, standard_roots=None):
        self.root = root.resolve()
        self.standard_roots = standard_roots
        self.lock = threading.RLock()

    def config(self):
        path=self.root/'runtime/workstation.json'
        return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {'version':1,'runtimes':[]}

    @staticmethod
    def local_path(raw, *, directory=True):
        if not isinstance(raw,str) or not raw or '\x00' in raw or raw.startswith(('\\\\','//')):
            raise WorkstationError('Only explicit local absolute paths are allowed')
        path=Path(raw)
        if not path.is_absolute() or '..' in path.parts:
            raise WorkstationError('Only explicit local absolute paths are allowed')
        path=path.resolve()
        if not (path.is_dir() if directory else path.is_file()):
            raise WorkstationError('Configured local path is unavailable')
        return path

    def approved(self):
        result={}
        try:
            config=self.config()
            if set(config)-{'version','runtimes'} or config.get('version')!=1 or not isinstance(config.get('runtimes'),list) or len(config['runtimes'])>32:
                raise WorkstationError('Unsupported workstation config')
            for raw in config['runtimes']:
                item=dict(raw)
                if set(item)-{'key','label','approved','root','cwd','port','executable','argv','model_roots','folders'}:
                    raise WorkstationError('Unknown workstation config field')
                core=self.local_path(item['root'])
                if not all((core/p).exists() for p in ('main.py','folder_paths.py','comfy')):
                    raise WorkstationError('Configured root is not a Comfy installation')
                cwd=self.local_path(item['cwd'])
                if cwd != core: raise WorkstationError('Comfy cwd must match its root')
                executable=self.local_path(item['executable'],directory=False)
                if executable.name.lower() not in ('python.exe','pythonw.exe','python','python3'):
                    raise WorkstationError('Only a configured Python interpreter can start Comfy')
                port=item['port']
                if type(port) is not int or not 1024<=port<=65535: raise WorkstationError('Invalid local port')
                argv=item['argv']
                if not isinstance(argv,list) or not argv or len(argv)>128 or not all(isinstance(a,str) and '\x00' not in a for a in argv):
                    raise WorkstationError('Invalid fixed argument vector')
                prefix=0
                while prefix<len(argv):
                    if argv[prefix] in ('-s','-u'): prefix+=1
                    elif argv[prefix:prefix+2]==['-X','utf8']: prefix+=2
                    else: break
                if prefix>=len(argv) or not Path(argv[prefix]).is_absolute() or Path(argv[prefix]).resolve()!=core/'main.py':
                    raise WorkstationError('Interpreter must execute the exact configured main.py')
                tail=argv[prefix+1:]
                for flag,value in (('--listen','127.0.0.1'),('--port',str(port))):
                    if tail.count(flag)!=1 or any(a.startswith(flag+'=') for a in tail) or tail.index(flag)+1>=len(tail) or tail[tail.index(flag)+1]!=value:
                        raise WorkstationError('Startup must bind the exact configured IPv4 loopback port')
                if '--auto-launch' in tail: raise WorkstationError('Browser launch must be explicit')
                if item.get('key')=='fasth3-omni':
                    fixed=profile_installer().omni_service(self.root)
                    if (core!=fixed['cwd'] or str(executable)!=fixed['cmd'][0] or
                            argv!=fixed['cmd'][1:] or port!=8237):
                        raise WorkstationError('Omni requires the fixed isolated native PDD runtime command')
                roots=[str(self.local_path(p)) for p in item.get('model_roots',[])]
                if len(roots)>32: raise WorkstationError('Too many model roots')
                folders=item.get('folders',{})
                if set(folders)-{'models','loras','outputs'}: raise WorkstationError('Unknown folder target')
                item.update(root=str(core),cwd=str(cwd),executable=str(executable),model_roots=list(dict.fromkeys(roots)),
                            folders={k:str(self.local_path(p)) for k,p in folders.items()},id=opaque('comfy',core))
                if item['id'] in result: raise WorkstationError('Duplicate runtime root')
                result[item['id']]=item
        except (KeyError,TypeError,OSError,ValueError) as exc:
            if isinstance(exc,WorkstationError): raise
            raise WorkstationError('Invalid local workstation configuration') from exc
        return result

    def discover(self):
        deadline=time.monotonic()+2
        candidates=dict(self.approved())
        # Enumerate listeners once; inspect only an explicit main.py argument, never recurse.
        for port,owner in list(self.listeners().items())[:32]:
            if time.monotonic()>deadline: break
            argv=owner.get('cmdline',[])
            main=next((Path(a) for a in argv[1:] if Path(a).name=='main.py' and Path(a).is_absolute()),None)
            if main is None or not all((main.parent/p).exists() for p in ('main.py','folder_paths.py','comfy')): continue
            if not self.probe(port): continue
            core=main.parent.resolve(); identifier=opaque('comfy',core)
            candidates.setdefault(identifier,dict(id=identifier,root=str(core),label=core.name,approved=False,model_roots=[str(core/'models')]))
            candidates[identifier]['online']=True
        paths=self.standard_roots
        if paths is None:
            paths=[self.root/'runtime/ComfyUI',Path.home()/'ComfyUI',Path.home()/'ComfyUI_windows_portable/ComfyUI',
                   Path.home()/'Downloads/ComfyUI_windows_portable/ComfyUI',Path.home()/'Desktop/ComfyUI_windows_portable/ComfyUI']
            for variable in ('COMFYUI_PATH','COMFYUI_HOME'):
                if os.environ.get(variable): paths.append(Path(os.environ[variable]))
        for path in paths[:64]:
            if time.monotonic()>deadline: break
            path=Path(path).resolve()
            if all((path/p).exists() for p in ('main.py','folder_paths.py','comfy')):
                identifier=opaque('comfy',path)
                candidates.setdefault(identifier,dict(id=identifier,root=str(path),label=path.name,approved=False,model_roots=[str(path/'models')]))
        roots={}
        authorized=self.root/'runtime/model-roots.json'
        if authorized.is_file():
            try:
                for raw in json.loads(authorized.read_text(encoding='utf-8-sig')).get('roots',[])[:64]:
                    p=self.local_path(raw); identifier=opaque('root',p)
                    roots[identifier]=dict(id=identifier,label=p.name,location=str(p),approved=True,runtime_id=None)
            except (OSError,ValueError,TypeError) as exc: raise WorkstationError('Invalid model-roots configuration') from exc
        for item in candidates.values():
            for raw in item.get('model_roots',[])[:32]:
                p=Path(raw).resolve()
                if p.is_dir():
                    identifier=opaque('root',p)
                    roots.setdefault(identifier,dict(id=identifier,label=p.name,location=str(p),approved=item.get('approved',False),runtime_id=item['id']))
        return dict(runtimes=[dict(id=i['id'],label=i.get('label','ComfyUI'),location=i['root'],online=i.get('online',False),approved=i.get('approved',False),
                configuration_required=not i.get('approved',False)) for i in list(candidates.values())[:128]],roots=list(roots.values())[:128],
                limits=dict(max_roots=64,max_depth=0,max_results=128,budget_seconds=2),automatic_downloads=False)

    def selected(self, profile=None):
        if profile is not None:
            if profile!='fasth3-omni': raise WorkstationError('Unknown runtime profile')
            matches=[i for i in self.approved().values() if i.get('key')==profile and i.get('approved') is True]
            return matches[0] if len(matches)==1 else None
        path=self.root/'runtime/workstation-selection.json'
        selection=json.loads(path.read_text()) if path.is_file() else {}
        identifier=selection.get('selected_id')
        item=self.approved().get(identifier)
        return item if item and item.get('approved') is True and selection.get('configuration_sha256')==self.launch_digest(item) else None

    def select(self, identifier, acknowledge):
        with self.lock:
            item=self.approved().get(identifier)
            if not acknowledge or not item or item.get('approved') is not True:
                raise WorkstationError('Explicit selection and local administrator approval required')
            atomic_json(self.root/'runtime/workstation-selection.json',dict(selected_id=identifier,configuration_sha256=self.launch_digest(item)))
            return dict(selected_id=identifier,selected=True,generation_routing_changed=False)

    def select_root(self, identifier, acknowledge):
        from .model_manager import ModelManager
        with self.lock:
            item=self.selected()
            if not acknowledge or not item: raise WorkstationError('Select an approved runtime and confirm root adoption first')
            matches=[self.local_path(raw) for raw in item.get('model_roots',[]) if opaque('root',Path(raw).resolve())==identifier]
            if not matches: raise WorkstationError('Root is not authorized for the selected runtime')
            folder=matches[0]; manager=ModelManager(self.root); verified=0
            for entry in manager.entries:
                paths=list(dict.fromkeys([folder/entry['target'],folder/Path(entry['target']).name]))
                for path in paths:
                    if not path.exists(): continue
                    if not path.resolve().is_relative_to(folder) or not manager.verified(path,entry):
                        raise WorkstationError('Existing manifest model failed containment, size or SHA256 validation')
                    verified+=1; break
            if not verified: raise WorkstationError('No pinned manifest models verified in candidate root')
            roots=list(dict.fromkeys(str(p) for p in manager.roots()[1:]+[folder]))
            atomic_json(self.root/'runtime/model-roots.json',dict(roots=roots))
            manager.write_mapping()  # Only the package mapping; never change external Comfy config.
            return dict(root_id=identifier,verified_models=verified,reused=True,
                        external_comfy_mapping_changed=False,restart_required=True)

    @staticmethod
    def listeners():
        import psutil
        result={}
        try:
            for connection in psutil.net_connections(kind='tcp'):
                if connection.status!=psutil.CONN_LISTEN or not connection.laddr: continue
                if connection.laddr.ip not in ('127.0.0.1','::1','0.0.0.0','::'): continue
                port=connection.laddr.port
                try:
                    process=psutil.Process(connection.pid) if connection.pid else None
                    if process is None: raise psutil.AccessDenied()
                    result[port]=dict(pid=process.pid,create_time=process.create_time(),exe=process.exe(),cmdline=process.cmdline(),cwd=process.cwd())
                except (psutil.Error,OSError): result[port]={}
        except (psutil.Error,OSError): pass
        return result

    @staticmethod
    def probe(port):
        import urllib.request
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            with opener.open(f'http://127.0.0.1:{port}/system_stats',timeout=0.35) as response:
                if response.status!=200 or 'application/json' not in response.headers.get('Content-Type','').lower(): return False
                payload=response.read(262145)
                if len(payload)>262144: return False
                data=json.loads(payload)
                return isinstance(data,dict) and isinstance(data.get('system'),dict) and isinstance(data.get('devices'),list)
        except (OSError,ValueError): return False

    @staticmethod
    def port_free(port):
        import socket
        with socket.socket() as sock:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'): sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            try: sock.bind(('127.0.0.1',port)); return True
            except OSError: return False

    @staticmethod
    def identity_matches(item, owner):
        try:
            return (Path(owner['exe']).resolve()==Path(item['executable']) and
                    owner['cmdline']==[item['executable']]+item['argv'] and
                    Path(owner['cwd']).resolve()==Path(item['cwd']))
        except (KeyError,TypeError,OSError): return False

    def launch_digest(self,item):
        return hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()

    def receipt_path(self,item):
        name='workstation-fasth3-omni.json' if item.get('key')=='fasth3-omni' else 'workstation-comfy.json'
        return self.root/'runtime/state'/name

    @staticmethod
    def owned_descendants(record):
        import psutil
        if not record_alive(record): return []
        try:
            children=[process_record(p.pid) for p in psutil.Process(record['pid']).children(recursive=True)]
            return children if record_alive(record) else []
        except (psutil.Error,OSError,KeyError): return []

    def listener_owned(self,item,owner):
        if item.get('key')!='fasth3-omni': return self.identity_matches(item,owner)
        try:
            receipt=json.loads(self.receipt_path(item).read_text(encoding='utf-8'))
            parent=receipt['process']
            if (receipt.get('root')!=str(self.root) or receipt.get('profile')!='fasth3-omni' or
                    receipt.get('configuration_sha256')!=self.launch_digest(item) or
                    not self.identity_matches(item,parent) or not record_alive(parent)):
                return False
            # A Windows venv child has base-python.exe and a rewritten argv[0].
            # Trust only a full identity obtained through our still-verified launcher.
            candidates=[parent]+self.owned_descendants(parent)
            return (owner in candidates and owner.get('cmdline',[])[1:]==item['argv'] and
                    Path(owner.get('cwd','')).resolve()==Path(item['cwd']))
        except (OSError,ValueError,KeyError,TypeError): return False

    def omni_preflight(self):
        installer=profile_installer()
        receipt=self.root/'runtime/fasth3-omni/installed.json'
        try:
            data=json.loads(receipt.read_text(encoding='utf-8'))
            if (data.get('root')!=str(self.root) or data.get('verified') is not True or
                    data.get('lock_sha256')!=installer.omni_fingerprint(self.root)):
                raise ValueError('stale receipt')
            installer.verify_omni_runtime(self.root)
        except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
            raise WorkstationError('Omni preflight failed; explicitly install profile/models or inspect local runtime') from exc

    def pending(self,item):
        path=self.receipt_path(item)
        if not path.is_file(): return None
        try: receipt=json.loads(path.read_text())
        except (ValueError,OSError): raise WorkstationError('Unreadable process receipt; inspect locally')
        if receipt.get('launch_in_progress'):
            launch=getattr(self,'_omni_launch',None) if item.get('key')=='fasth3-omni' else None
            if launch and receipt==launch[0] and launch[1].poll() is not None:
                self.clear_omni_claim(item,launch[0])
                return None
            return 'launch_unverified'
        if not record_alive(receipt.get('process',{})): return None
        if receipt.get('configuration_sha256')!=self.launch_digest(item): return 'configuration_changed'
        return 'starting'

    def status(self, profile=None):
        item=self.selected(profile=profile)
        state='configuration_required'
        if item:
            owners=self.listeners(); owner=owners.get(item['port'])
            if owner is not None or not self.port_free(item['port']):
                state=('online' if self.probe(item['port']) else 'unhealthy') if self.listener_owned(item,owner or {}) else 'port_conflict'
            else: state=self.pending(item) or 'stopped'
        return dict(state=state,selected_id=item['id'] if item else None,label=item.get('label') if item else None,
                    url=f"http://127.0.0.1:{item['port']}" if item else None,
                    capabilities=dict(start=state=='stopped',open_comfy=state=='online',select=True,
                        folders={k:bool(item and item.get('folders',{}).get(k)) for k in ('models','loras','outputs')}),
                    automatic_downloads=False,stop_supported=False)

    def open_folder(self,kind):
        with self.lock:
            item=self.selected()
            if kind not in ('models','loras','outputs') or not item or kind not in item.get('folders',{}):
                raise WorkstationError('Folder target is not configured for the selected runtime')
            path=self.local_path(item['folders'][kind])
            explorer=Path(os.environ.get('SystemRoot','C:/Windows'))/'explorer.exe'
            subprocess.Popen([str(explorer),str(path)],shell=False,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return dict(kind=kind,requested=True)

    def open_comfy(self):
        with self.lock:
            state=self.status(); item=self.selected()
            if state['state']!='online' or not item: raise WorkstationError('Selected Comfy is not identity-verified and healthy')
            url=f"http://127.0.0.1:{item['port']}"
            if not webbrowser.open(url): raise WorkstationError('Default browser did not accept the request')
            return dict(requested=True,url=url)

    def clear_omni_claim(self,item,claim):
        path=self.receipt_path(item)
        try:
            current=json.loads(path.read_text(encoding='utf-8'))
            if all(current.get(k)==claim.get(k) for k in ('claim_id','root','profile','configuration_sha256')):
                path.unlink()
        except FileNotFoundError: pass

    def _start_omni(self,item,env,logs):
        import uuid
        claim=dict(launch_in_progress=True,claim_id=uuid.uuid4().hex,
                   root=str(self.root),profile='fasth3-omni',configuration_sha256=self.launch_digest(item))
        atomic_json(self.receipt_path(item),claim)
        child=None
        log='workstation-fasth3-omni.log'
        try:
            with (logs/log).open('ab',buffering=0) as output:
                child=subprocess.Popen([item['executable']]+item['argv'],cwd=item['cwd'],env=env,
                    shell=False,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self._omni_launch=(claim,child)
            if child.poll() is not None:
                raise WorkstationError('Omni spawn exited; inspect runtime/logs/'+log+' and retry')
            record=process_record(child.pid)
            if child.poll() is not None:
                raise WorkstationError('Omni spawn exited; inspect runtime/logs/'+log+' and retry')
            atomic_json(self.receipt_path(item),dict(claim,launch_in_progress=False,process=record,started_at=time.time()))
        except Exception as exc:
            # The retained Popen handle belongs only to this call (on Windows it
            # remains safe even if the numeric PID is reused). Never kill by port.
            if child is not None and child.poll() is None:
                try:
                    child.terminate()
                    child.wait(timeout=5)
                except (OSError,subprocess.TimeoutExpired): pass
            if child is None or child.poll() is not None:
                self.clear_omni_claim(item,claim)
            if isinstance(exc,WorkstationError): raise
            raise WorkstationError('Omni spawn/identity recording failed; inspect runtime/logs/'+log+' and profile status before retry') from exc
        return dict(state='starting',reused=False,log='runtime/logs/'+log)

    def start(self, profile=None):
        with self.lock:
            state=self.status(profile=profile)
            if state['state']=='online': return dict(state='online',reused=True)
            if state['state']=='starting': return dict(state='starting',reused=True)
            if state['state']!='stopped': raise WorkstationError('Runtime not safe to start: '+state['state'])
            item=self.selected(profile=profile)
            if not item or not self.port_free(item['port']): raise WorkstationError('Port is occupied; no process was changed')
            if item.get('key')=='fasth3-omni': self.omni_preflight()
            logs=self.root/'runtime/logs'; logs.mkdir(parents=True,exist_ok=True)
            env={k:v for k,v in os.environ.items() if k.upper() not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV') and not k.upper().startswith('H3_')}
            env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
            if item.get('key')=='fasth3-omni': return self._start_omni(item,env,logs)
            atomic_json(self.receipt_path(item),dict(launch_in_progress=True,
                        configuration_sha256=self.launch_digest(item)))
            log='workstation-fasth3-omni.log' if item.get('key')=='fasth3-omni' else 'workstation-comfy.log'
            with (logs/log).open('ab',buffering=0) as output:
                child=subprocess.Popen([item['executable']]+item['argv'],cwd=item['cwd'],env=env,
                    shell=False,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            # Keep handle alive and fail closed if recording fails. Never kill an unverified process.
            self.child=child
            try: record=process_record(child.pid)
            except Exception as exc: raise WorkstationError('Started process identity unavailable; inspect local log, do not retry blindly') from exc
            atomic_json(self.receipt_path(item),dict(process=record,root=str(self.root),profile=item.get('key'),
                        configuration_sha256=self.launch_digest(item),started_at=time.time()))
            return dict(state='starting',reused=False,log='runtime/logs/'+log)


class WorkstationCapabilities(BaseModel):
    start: bool
    open_comfy: bool
    select: bool
    folders: dict[Literal['models','loras','outputs'],bool]


class WorkstationStatus(BaseModel):
    state: Literal['configuration_required','online','unhealthy','port_conflict','stopped','starting','configuration_changed','launch_unverified']
    selected_id: str | None
    label: str | None
    url: str | None
    capabilities: WorkstationCapabilities
    automatic_downloads: bool = False
    stop_supported: bool = False
    generation_binding: Literal['not_selected','matches','different','unknown'] = 'unknown'


class SelectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_id: str = Field(min_length=1,max_length=80)
    acknowledge: bool = False


class ActionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')


_GATE=threading.Lock()

def workstation(request:Request):
    # Same peer + same-origin policy as model manager, tightened against Host rebinding.
    peer=request.client.host if request.client else None
    if peer not in ('127.0.0.1','::1','testclient'): raise HTTPException(403,'Only local workstation access is allowed')
    allowed=('127.0.0.1','localhost','::1')+ (('testserver',) if peer=='testclient' else ())
    if request.url.hostname not in allowed: raise HTTPException(403,'Non-local Host rejected')
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'): raise HTTPException(403,'External origin rejected')
    with _GATE:
        if not hasattr(request.app.state,'workstation'):
            root=Path(os.environ.get('KINJUTSU_ROOT',Path(__file__).resolve().parents[4]))
            request.app.state.workstation=Workstation(root)
    return request.app.state.workstation


def invoke(method,*args):
    try: return method(*args)
    except (WorkstationError,OSError,ValueError) as exc:
        # Never expose command lines or exception paths to clients.
        message=str(exc) if isinstance(exc,WorkstationError) else 'Local operation failed; inspect administrator configuration/logs'
        raise HTTPException(409,message) from exc


router=APIRouter(prefix='/workstation',tags=['local workstation'])

@router.get('/status',response_model=WorkstationStatus,summary='Read workstation state and UI action capabilities; never autostarts')
def status_api(request:Request,w:Workstation=Depends(workstation)):
    result=invoke(w.status)
    configured=getattr(getattr(request.app.state,'settings',None),'comfy_url',None)
    result['generation_binding']=('not_selected' if not result['selected_id'] else
        ('unknown' if not configured else ('matches' if configured.rstrip('/')==result['url'] else 'different')))
    return result

@router.get('/discover',summary='Bounded discovery; candidates require local administrator authorization')
def discover_api(w:Workstation=Depends(workstation)):
    return invoke(w.discover)

@router.get('/roots',summary='Read candidate roots; presence is not SHA256 verification')
def roots_api(w:Workstation=Depends(workstation)):
    result=invoke(w.discover)
    return dict(roots=result['roots'],configuration_required=not bool(invoke(w.selected)),verification_required=True)

@router.post('/select',summary='Explicitly select a locally approved runtime by opaque candidate ID')
def select_api(body:SelectionRequest,w:Workstation=Depends(workstation)):
    return invoke(w.select,body.candidate_id,body.acknowledge)

@router.post('/roots/select',summary='Hash-verify and reuse approved root; no model copying or downloads')
def select_root_api(body:SelectionRequest,w:Workstation=Depends(workstation)):
    return invoke(w.select_root,body.candidate_id,body.acknowledge)

@router.post('/comfy/start',summary='Start only fixed approved Comfy command; preserve existing listeners')
def start_api(body:ActionRequest=Body(default=ActionRequest()),w:Workstation=Depends(workstation)):
    return invoke(w.start)

@router.get('/profiles/{profile}/status',response_model=WorkstationStatus,summary='Read optional engine state; never install, download or start')
def profile_status_api(profile:Literal['fasth3-omni'],w:Workstation=Depends(workstation)):
    return invoke(w.status,profile)


@router.post('/profiles/{profile}/start',summary='Explicitly start an already installed isolated optional runtime')
def profile_start_api(profile:Literal['fasth3-omni'],body:ActionRequest=Body(default=ActionRequest()),w:Workstation=Depends(workstation)):
    return invoke(w.start,profile)


@router.post('/comfy/open',summary='Request server-desktop browser for selected verified loopback Comfy')
def open_api(body:ActionRequest=Body(default=ActionRequest()),w:Workstation=Depends(workstation)):
    return invoke(w.open_comfy)

@router.post('/folders/{kind}/open',summary='Request Explorer for allowlisted selected-runtime folder')
def folder_api(kind:Literal['models','loras','outputs'],body:ActionRequest=Body(default=ActionRequest()),w:Workstation=Depends(workstation)):
    return invoke(w.open_folder,kind)
