"""Local-only workstation control. HTTP never supplies paths, URLs or commands."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import threading
import subprocess
import time


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
                while prefix<len(argv) and argv[prefix] in ('-s','-u'): prefix+=1
                if prefix>=len(argv) or not Path(argv[prefix]).is_absolute() or Path(argv[prefix]).resolve()!=core/'main.py':
                    raise WorkstationError('Interpreter must execute the exact configured main.py')
                tail=argv[prefix+1:]
                for flag,value in (('--listen','127.0.0.1'),('--port',str(port))):
                    if tail.count(flag)!=1 or any(a.startswith(flag+'=') for a in tail) or tail.index(flag)+1>=len(tail) or tail[tail.index(flag)+1]!=value:
                        raise WorkstationError('Startup must bind the exact configured IPv4 loopback port')
                if '--auto-launch' in tail: raise WorkstationError('Browser launch must be explicit')
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

    def selected(self):
        path=self.root/'runtime/workstation-selection.json'
        identifier=json.loads(path.read_text()).get('selected_id') if path.is_file() else None
        item=self.approved().get(identifier)
        return item if item and item.get('approved') is True else None

    def select(self, identifier, acknowledge):
        with self.lock:
            item=self.approved().get(identifier)
            if not acknowledge or not item or item.get('approved') is not True:
                raise WorkstationError('Explicit selection and local administrator approval required')
            atomic_json(self.root/'runtime/workstation-selection.json',dict(selected_id=identifier))
            return dict(selected_id=identifier,selected=True)

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

    def pending(self,item):
        path=self.root/'runtime/state/workstation-comfy.json'
        if not path.is_file(): return None
        try: receipt=json.loads(path.read_text())
        except (ValueError,OSError): raise WorkstationError('Unreadable process receipt; inspect locally')
        if not record_alive(receipt.get('process',{})): return None
        if receipt.get('configuration_sha256')!=self.launch_digest(item): return 'configuration_changed'
        return 'starting'

    def status(self):
        item=self.selected()
        state='configuration_required'
        if item:
            owners=self.listeners(); owner=owners.get(item['port'])
            if owner is not None or not self.port_free(item['port']):
                state=('online' if self.probe(item['port']) else 'unhealthy') if self.identity_matches(item,owner or {}) else 'port_conflict'
            else: state=self.pending(item) or 'stopped'
        return dict(state=state,selected_id=item['id'] if item else None,label=item.get('label') if item else None,
                    url=f"http://127.0.0.1:{item['port']}" if item else None,
                    capabilities=dict(start=state=='stopped',open_comfy=state=='online',select=True,
                        folders={k:bool(item and item.get('folders',{}).get(k)) for k in ('models','loras','outputs')}),
                    automatic_downloads=False,stop_supported=False)

    def start(self):
        with self.lock:
            state=self.status()
            if state['state']=='online': return dict(state='online',reused=True)
            if state['state']=='starting': return dict(state='starting',reused=True)
            if state['state']!='stopped': raise WorkstationError('Runtime not safe to start: '+state['state'])
            item=self.selected()
            if not item or not self.port_free(item['port']): raise WorkstationError('Port is occupied; no process was changed')
            logs=self.root/'runtime/logs'; logs.mkdir(parents=True,exist_ok=True)
            env={k:v for k,v in os.environ.items() if k.upper() not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')}
            env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
            with (logs/'workstation-comfy.log').open('ab',buffering=0) as output:
                child=subprocess.Popen([item['executable']]+item['argv'],cwd=item['cwd'],env=env,
                    shell=False,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            # Keep handle alive and fail closed if recording fails. Never kill an unverified process.
            self.child=child
            try: record=process_record(child.pid)
            except Exception as exc: raise WorkstationError('Started process identity unavailable; inspect local log, do not retry blindly') from exc
            atomic_json(self.root/'runtime/state/workstation-comfy.json',dict(process=record,
                        configuration_sha256=self.launch_digest(item),started_at=time.time()))
            return dict(state='starting',reused=False,log='runtime/logs/workstation-comfy.log')
