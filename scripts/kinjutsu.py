"""Pachecodes : Kinjutsu — root-relative Windows installation and lifecycle.
Only stdlib is imported until the isolated environment is provisioned.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CORE_REVISION = '7a131a3afadc8200120f67f9236311a2c48b7445'
PYTHON_VERSION = '3.12.10'
_CHILD_HANDLES = {}
READINESS_TIMEOUT = 180

def terminate_record(record):
    import psutil
    records=record.get('children',[])+[record]
    # Snapshot late-created FFmpeg/interpreter descendants only through verified owners.
    descendants=[]
    for identity in records:
        if is_owned(identity):
            try: descendants.extend(process_record(c.pid) for c in psutil.Process(identity['pid']).children(recursive=True))
            except psutil.Error: pass
    seen=set()
    for identity in reversed(records+descendants):
        key=(identity['pid'],identity['create_time'])
        if key in seen: continue
        seen.add(key)
        if not is_owned(identity): continue
        try:
            p=psutil.Process(identity['pid']); p.terminate()
            try: p.wait(timeout=15)
            except psutil.TimeoutExpired:
                if is_owned(identity): p.kill(); p.wait(timeout=5)
        except psutil.NoSuchProcess:
            # A verified owner can exit between the check and termination.
            # It is already stopped; do not hide AccessDenied or other errors.
            continue
    handle=_CHILD_HANDLES.pop(record['pid'],None)
    if handle: handle.wait(timeout=5)
    if any(is_owned(identity) for identity in records+descendants): raise RuntimeError('An owned process did not stop')

def safe_target(root, relative):
    if not isinstance(relative,str) or not relative or relative=='.': raise ValueError('Empty/invalid relative path')
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or ':' in relative or '\\' in relative:
        raise ValueError('Unsafe relative path: ' + relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes root: ' + relative)
    return path

def load_manifest(path, root):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    entries = data['models'] if isinstance(data, dict) else data
    seen = set()
    for entry in entries:
        for field in ('repo','path','revision','size','sha256','target','included'):
            if field not in entry: raise ValueError('Missing model field: ' + field)
        if not re.fullmatch(r'[0-9a-f]{40}', entry['revision']): raise ValueError('Model revision must be a commit SHA')
        if not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']): raise ValueError('Invalid model SHA256')
        if type(entry['size']) is not int or entry['size'] <= 0: raise ValueError('Invalid model size')
        if type(entry['included']) is not bool: raise ValueError('included must be boolean')
        safe_target(root, entry['target'])
        safe_target(root, entry['path'])
        if PurePosixPath(entry['target']).parts[0] not in ('diffusion_models','text_encoders','vae','loras'): raise ValueError('Unsupported Comfy model category')
        if entry['target'].casefold() in seen: raise ValueError('Duplicate model target')
        seen.add(entry['target'].casefold())
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', entry['repo']): raise ValueError('Invalid HF repository')
    return entries

def verify_file(path, size, sha256):
    path = Path(path)
    if not path.is_file() or path.stat().st_size != size: return False
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest() == sha256

def dependency_plan(root):
    return {'title':'Pachecodes : Kinjutsu', 'python':PYTHON_VERSION,
            'core_revision':CORE_REVISION, 'core_repository':'https://github.com/Comfy-Org/ComfyUI.git',
            'environment':'runtime/venv', 'constraints':'dependencies/constraints.txt',
            'listeners':{'comfy':'127.0.0.1:8218','studio':'127.0.0.1:8220'},
            'autostart':False, 'optional_trt':False}

def download_verified(url, target, size, sha256):
    target = Path(target)
    if verify_file(target, size, sha256): return
    if target.exists(): raise RuntimeError('Existing file has wrong digest; preserve and inspect manually: '+str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix+'.part')
    if part.exists() and part.stat().st_size > size:
        raise RuntimeError('Oversized partial download; inspect manually: '+str(part))
    if part.exists() and part.stat().st_size == size:
        if not verify_file(part,size,sha256): raise RuntimeError('Partial digest mismatch; remove .part manually after inspection')
        part.replace(target); return
    offset = part.stat().st_size if part.exists() else 0
    request=urllib.request.Request(url,headers={'User-Agent':'Kinjutsu-Installer/1','Range':'bytes=%d-'%offset})
    with urllib.request.urlopen(request, timeout=120) as response:
        append = response.status == 206 and offset > 0
        if response.status == 206 and not response.headers.get('Content-Range','').startswith('bytes %d-'%offset):
            raise RuntimeError('Server returned inconsistent Content-Range')
        with part.open('ab' if append else 'wb') as handle:
            while True:
                block=response.read(8*1024*1024)
                if not block: break
                handle.write(block)
                if handle.tell()>size: raise RuntimeError('Download exceeded declared size')
    if not verify_file(part,size,sha256): raise RuntimeError('Download digest/size mismatch: '+str(part))
    part.replace(target)

def verify_patch_payload(root):
    record=json.loads((root/'runtime/patches/provenance.json').read_text())
    for item in record['files']:
        p=safe_target(root,item['path'])
        if not verify_file(p,item['size'],item['sha256']): raise RuntimeError('Patch payload corrupted: '+item['path'])
    return record

def process_record(pid):
    import psutil
    p=psutil.Process(pid)
    return {'pid':pid,'create_time':p.create_time(),'exe':p.exe(),'cmdline':p.cmdline()}

def is_owned(record):
    import psutil
    try:
        actual=process_record(record['pid'])
        return all(actual[x]==record[x] for x in ('create_time','exe','cmdline'))
    except (psutil.Error,KeyError): return False

def run(args, cwd=None, capture=False):
    print('+', subprocess.list2cmdline([str(x) for x in args]), flush=True)
    return subprocess.run([str(x) for x in args],cwd=cwd,check=True,text=True,encoding='utf-8',
                          stdout=subprocess.PIPE if capture else None,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout

def tool(root, name):
    paths={'uv':root/'runtime/tools/uv/uv.exe','git':root/'runtime/tools/git/cmd/git.exe',
           'node':root/'runtime/tools/node/node.exe','npm':root/'runtime/tools/node/npm.cmd'}
    if paths[name].exists(): return str(paths[name])
    found=shutil.which(name)
    if not found: raise RuntimeError('Missing '+name+'; run Install-Kinjutsu.ps1 first')
    return found

def python_exe(root): return root/'runtime/venv/Scripts/python.exe'

def apply_core(root, core, check_only=False):
    git=tool(root,'git'); provenance=verify_patch_payload(root)
    for item in provenance['core_files']:
        actual=hashlib.sha256((core/item['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual not in (item['before_sha256'],item['after_sha256']):
            raise RuntimeError('Core file differs from audited pre/postimage; refusing overwrite: '+item['path'])
    head=run([git,'-C',core,'rev-parse','HEAD'],capture=True).strip()
    if head!=CORE_REVISION: raise RuntimeError('Refusing to patch unexpected Comfy revision: '+head)
    patch=root/'runtime/patches/h3-aligned-guide.patch'
    reverse=subprocess.run([git,'-C',str(core),'apply','--reverse','--check',str(patch)],capture_output=True)
    if reverse.returncode != 0:
        run([git,'-C',core,'apply','--check',patch])
        if not check_only: run([git,'-C',core,'apply',patch])
    if not check_only:
        src=root/'runtime/patches/ComfyUI-H3-AddGuide'; dst=core/'custom_nodes/ComfyUI-H3-AddGuide'
        dst.mkdir(parents=True,exist_ok=True)
        for p in src.iterdir():
            if p.is_file():
                target=dst/p.name
                if target.exists() and target.read_bytes()!=p.read_bytes(): raise RuntimeError('Existing AddGuide differs; refusing overwrite')
                if not target.exists(): shutil.copy2(p,target)

def existing_model(root,e):
    roots=[root/'models']
    cfg=root/'runtime/model-roots.json'
    if cfg.is_file():
        for raw in json.loads(cfg.read_text(encoding='utf-8-sig')).get('roots',[]):
            p=Path(raw)
            if not p.is_absolute() or not p.is_dir(): raise RuntimeError('Raiz de modelos autorizada inexistente o relativa')
            roots.append(p.resolve())
    for folder in roots:
        for p in (folder/e['target'],folder/PurePosixPath(e['target']).name):
            if p.resolve().is_relative_to(folder.resolve()) and verify_file(p,e['size'],e['sha256']): return p
    return None

def prerequisites(root, entries):
    if sys.platform!='win32': raise RuntimeError('Supported target is Windows 11 x64')
    needed=sum(e['size'] for e in entries if not existing_model(root,e))
    # 30GB runtime/cache allowance; additional output space is recommended.
    if shutil.disk_usage(root).free < needed+30_000_000_000: raise RuntimeError('Insufficient free space; allow base weights +30GB runtime/cache, 120GB recommended')
    smi=shutil.which('nvidia-smi')
    if not smi: raise RuntimeError('Install a current NVIDIA CUDA 13 compatible display driver first (nvidia-smi missing)')
    output=run([smi,'--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'],capture=True)
    print(output)
    if not any('4090' in line and int(line.split(',')[1].strip())>=23000 for line in output.splitlines()):
        raise RuntimeError('Approved hardware requires RTX 4090 24GB')

def managed_models(root):
    import importlib.util
    spec=importlib.util.spec_from_file_location('kinjutsu_models',root/'studio/backend/app/services/model_manager.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.ModelManager(root)

def model_files(root, entries, download=False):
    manager=managed_models(root)
    for i,e in enumerate(entries):
        if manager.discover(e): continue
        if not download: raise RuntimeError('Modelo ausente/corrupto: '+e['target'])
        job=manager.install(str(i),True)
        while job['status'] in ('queued','downloading','verifying'):
            time.sleep(1); job=manager.jobs[str(i)]
        if job['status']!='installed': raise RuntimeError(str(job))
    manager.write_mapping()

def verify_package(root):
    entries=load_manifest(root/'models/manifest.json',root/'models')
    verify_patch_payload(root)
    for e in entries:
        if e['included'] and not verify_file(root/'models'/e['target'],e['size'],e['sha256']):
            raise RuntimeError('Bundled weight missing/corrupt: '+e['target'])
    for p in ('dependencies/requirements.lock','studio/backend','studio/frontend/package-lock.json','workflows/approved-api.json'):
        if not (root/p).exists(): raise RuntimeError('Package component missing: '+p)
    return {'models':len(entries),'included':sum(e['included'] for e in entries),'base_bytes':sum(e['size'] for e in entries if not e['included']), 'patches':'verified'}

def ensure_workstation_profile(root):
    """Expose this verified managed installation to the local UI; never adopt externals."""
    root=Path(root).resolve(); target=root/'runtime/workstation.json'
    if target.exists():return False  # Never overwrite administrator authorization.
    receipt=root/'runtime/installed.json'
    if not receipt.is_file():return False
    info=json.loads(receipt.read_text(encoding='utf-8-sig'))
    if info.get('verified') is not True or Path(info.get('root','')).resolve()!=root:return False
    core=root/'runtime/ComfyUI'
    if not all((core/p).exists() for p in ('main.py','folder_paths.py','comfy')):return False
    service=service_commands(root)['comfy']
    if not Path(service['cmd'][0]).is_file():return False
    for folder in (root/'models',root/'models/loras',core/'output'):folder.mkdir(parents=True,exist_ok=True)
    roots=[root/'models']
    extra=root/'runtime/model-roots.json'
    if extra.is_file():
        for raw in json.loads(extra.read_text(encoding='utf-8-sig')).get('roots',[]):
            p=Path(raw)
            if p.is_absolute() and p.is_dir() and p.resolve() not in roots:roots.append(p.resolve())
    data={'version':1,'runtimes':[{'key':'managed','label':'Kinjutsu ComfyUI','approved':True,
          'root':str(core),'cwd':str(core),'port':8218,'executable':service['cmd'][0],'argv':service['cmd'][1:],
          'model_roots':[str(p) for p in roots],
          'folders':{'models':str(root/'models'),'loras':str(root/'models/loras'),'outputs':str(core/'output')}}]}
    tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');tmp.replace(target)
    return True

def install(root):
    entries=load_manifest(root/'models/manifest.json',root/'models')
    prerequisites(root,entries); verify_package(root)
    uv=tool(root,'uv'); git=tool(root,'git'); py=python_exe(root)
    envroot=root/'runtime/venv'
    if envroot.exists() and not py.exists(): raise RuntimeError('Existing incomplete venv; inspect manually, no destructive recreation')
    if not py.exists(): run([uv,'venv','--python',PYTHON_VERSION,'--managed-python',envroot])
    run([py,'-c',"import sys; assert sys.version_info[:3]==(3,12,10), sys.version; assert sys.prefix!=sys.base_prefix; assert not __import__('site').ENABLE_USER_SITE"])
    # Full transitive hash lock; no resolver is allowed to upgrade the audited torch override.
    run([uv,'pip','install','--python',py,'--no-deps','--require-hashes','--only-binary',':all:',
         '--index','https://download.pytorch.org/whl/cu130','--index-strategy','unsafe-best-match','-r',root/'dependencies/requirements.lock'])
    core=root/'runtime/ComfyUI'
    if not core.exists():
        run([git,'init',core]); run([git,'-C',core,'remote','add','origin','https://github.com/Comfy-Org/ComfyUI.git'])
        run([git,'-C',core,'fetch','--depth','1','origin',CORE_REVISION]); run([git,'-C',core,'checkout','--detach',CORE_REVISION])
    apply_core(root,core)
    # One central model tree avoids a second 44GB copy/hard-link assumption.
    config='kinjutsu:\n  base_path: '+json.dumps(str(root/'models'))+'\n  diffusion_models: diffusion_models\n  text_encoders: text_encoders\n  vae: vae\n  loras: loras\n'
    (root/'runtime/extra_model_paths.yaml').write_text(config,encoding='utf-8')
    model_files(root,entries,download=True)
    if not (root/'studio/frontend/dist/index.html').is_file(): raise RuntimeError('Falta interfaz compilada; vuelve a extraer el paquete completo')
    # Both binaries are mandatory; never accept the FFmpeg-only imageio wheel.
    pair=media_tools(root)
    (root/'runtime/tool-paths.json').write_text(json.dumps(pair),encoding='utf-8')
    verify_runtime(root)
    (root/'runtime/installed.json').write_text(json.dumps({'root':str(root),'configuration_sha256':configuration_digest(root),'lock_sha256':hashlib.sha256((root/'dependencies/requirements.lock').read_bytes()).hexdigest(),'verified':True}),encoding='utf-8')
    ensure_workstation_profile(root)
    print('Instalacion verificada. Ningun servicio iniciado.')

def verify_core_postimages(root):
    provenance=json.loads((root/'runtime/patches/provenance.json').read_text())
    core=root/'runtime/ComfyUI'
    for item in provenance['core_files']:
        actual=hashlib.sha256((core/item['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=item['after_sha256']: raise RuntimeError('Required core fix missing/changed: '+item['path'])
    bundled=root/'runtime/patches/ComfyUI-H3-AddGuide'
    if bundled.exists():
        for source in bundled.iterdir():
            if source.is_file():
                installed=core/'custom_nodes/ComfyUI-H3-AddGuide'/source.name
                if not installed.exists() or installed.read_bytes()!=source.read_bytes(): raise RuntimeError('Installed AddGuide missing/changed: '+source.name)

def verify_bootstrap_tools(root):
    pins=json.loads((root/'runtime/tools-manifest.json').read_text())['tools']
    for pin in pins:
        if pin['name']=='node': continue  # developer-only, not required by shipped dist
        folder=root/'runtime/tools'/pin['name']
        receipt=json.loads((folder/'bootstrap-receipt.json').read_text(encoding='utf-8-sig'))
        if receipt['archive_sha256']!=pin['sha256']: raise RuntimeError('Herramienta de otra version: '+pin['name'])
        if not receipt.get('files'): raise RuntimeError('Recibo de herramienta vacio')
        for item in receipt['files']:
            if not verify_file(safe_target(folder,item['path']),item['size'],item['sha256']):
                raise RuntimeError('Herramienta alterada: '+pin['name']+'/'+item['path'])

def verify_runtime(root):
    verify_bootstrap_tools(root)

    pins=dict(re.findall(r'^([A-Za-z0-9_-]+)==([^\s;]+)',(root/'dependencies/requirements.lock').read_text(),re.M))
    check="import importlib.metadata as m,json; pins=json.loads("+repr(json.dumps(pins))+"); bad=[n+' expected '+v+' got '+m.version(n) for n,v in pins.items() if m.version(n)!=v]; assert not bad, bad"
    run([python_exe(root),'-s','-c',check])
    environment=child_env(root)  # Fail closed on missing/stale ffmpeg + ffprobe receipt.
    for variable,name in (('H3_FFPROBE_PATH','ffprobe.exe'),('IMAGEIO_FFMPEG_EXE','ffmpeg.exe')):
        if Path(environment[variable]).resolve() != (root/'runtime/tools/ffmpeg/bin'/name).resolve():
            raise RuntimeError('El runtime requiere la pareja FFmpeg/ffprobe portable fijada de esta carpeta')
    entries=load_manifest(root/'models/manifest.json',root/'models'); model_files(root,entries)
    apply_core(root,root/'runtime/ComfyUI',check_only=True)
    verify_core_postimages(root)
    run([python_exe(root),'-c',"import sys,torch,torchaudio,torchvision,transformers,fastapi,uvicorn,psutil; assert sys.prefix!=sys.base_prefix; assert sys.version_info[:3]==(3,12,10); assert torch.__version__=='2.13.0+cu130'; assert torchaudio.functional.resample(torch.zeros(1,240),24000,16000).shape[-1]==160; assert torch.cuda.is_available(); print('GPU:',torch.cuda.get_device_name(0)); print('Imports/resample/CUDA available; no model generation performed')"])
    if not (root/'studio/frontend/dist/index.html').is_file(): raise RuntimeError('Frontend not built')

def validate_media_pair(pair):
    if not all(pair.get(name) for name in ('ffmpeg','ffprobe')):
        raise RuntimeError('Incomplete ffmpeg/ffprobe receipt; rerun Install-Kinjutsu.ps1')
    paths={name:Path(pair[name]) for name in ('ffmpeg','ffprobe')}
    if (not all(p.is_absolute() and p.is_file() for p in paths.values())
            or paths['ffmpeg'].parent != paths['ffprobe'].parent):
        raise RuntimeError('Missing/non-sibling media ffmpeg/ffprobe pair; rerun Install-Kinjutsu.ps1')
    for name,path in paths.items():
        output=run([path,'-version'],capture=True)
        if not output.startswith(name+' version '): raise RuntimeError('Invalid media executable: '+str(path))
    return {name:str(path.resolve()) for name,path in paths.items()}

def media_tools(root):
    """Resolve an executable sibling pair; imageio's FFmpeg-only wheel is insufficient."""
    portable = root/'runtime/tools/ffmpeg/bin'
    candidates = [portable]
    found = shutil.which('ffprobe')
    if found: candidates.append(Path(found).parent)
    for folder in candidates:
        pair = {name: folder/(name+'.exe') for name in ('ffmpeg','ffprobe')}
        if not all(path.is_file() for path in pair.values()): continue
        return validate_media_pair(pair)
    raise RuntimeError('Both ffmpeg.exe and sibling ffprobe.exe are required. Run Install-Kinjutsu.ps1 to automatically install the pinned portable pair in runtime/tools/ffmpeg.')

def child_env(root):
    env=os.environ.copy()
    for key in list(env):
        if key.upper().startswith('H3_') or key.upper() in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
            env.pop(key,None)
    cfg=json.loads((root/'runtime/studio-launch.json').read_text()) if (root/'runtime/studio-launch.json').exists() else {}
    env.update(cfg.get('environment', {}))
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1',
               H3_COMFY_URL='http://127.0.0.1:8218',H3_EXPERIMENTAL_COMFY_URL='http://127.0.0.1:8218',
               H3_DATA_DIR=str(root/'runtime/studio-data'),
               H3_FRONTEND_DIST=str(safe_target(root,cfg.get('frontend_dist','studio/frontend/dist'))),
               H3_DIRECTOR_ENABLED='false',H3_DIRECTOR_AUTOSTART_OLLAMA='false',H3_DIRECTOR_OPENAI_MANAGED_GPU='false',
               KINJUTSU_ROOT=str(root),HF_HOME=str(root/'runtime/cache/huggingface'))
    paths=json.loads((root/'runtime/tool-paths.json').read_text()) if (root/'runtime/tool-paths.json').exists() else media_tools(root)
    paths=validate_media_pair(paths)
    if paths.get('ffprobe'): env['H3_FFPROBE_PATH']=paths['ffprobe']
    if paths.get('ffmpeg'):
        env['IMAGEIO_FFMPEG_EXE']=paths['ffmpeg']; env['PATH']=str(Path(paths['ffmpeg']).parent)+os.pathsep+env.get('PATH','')
    return env

def service_commands(root):
    py=str(python_exe(root))
    cfg=json.loads((root/'runtime/studio-launch.json').read_text(encoding='utf-8')) if (root/'runtime/studio-launch.json').exists() else {}
    app=cfg.get('asgi_app','app.main:app')
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.]*:[a-zA-Z_][a-zA-Z0-9_]*',app): raise ValueError('Invalid ASGI entry point')
    studio_cwd=safe_target(root,cfg.get('working_directory','studio/backend'))
    return {'comfy': {'cmd':[py,'-s',str(root/'runtime/ComfyUI/main.py'),'--listen','127.0.0.1','--port','8218',
             '--disable-auto-launch','--use-pytorch-cross-attention','--extra-model-paths-config',str(root/'runtime/extra_model_paths.yaml')],
             'cwd':root/'runtime/ComfyUI','port':8218,'health':'/system_stats'},
            'studio':{'cmd':[py,'-s','-m','uvicorn',app,'--host','127.0.0.1','--port','8220'],
             'cwd':studio_cwd,'port':8220,'health':cfg.get('health_path','/api/health')}}

def valid_health(name, content_type, payload):
    """Never accept an HTML SPA as backend readiness."""
    if 'application/json' not in content_type.lower(): return False
    try: data = json.loads(payload)
    except (ValueError, UnicodeDecodeError): return False
    if not isinstance(data, dict): return False
    if name == 'studio':
        return (data.get('status') == 'ok' and data.get('comfy_online') is True
                and isinstance(data.get('version'), str) and type(data.get('active_jobs')) is int)
    return isinstance(data.get('system'), dict) and isinstance(data.get('devices'), list)

def port_free(port):
    with socket.socket() as s:
        try: s.bind(('127.0.0.1',port)); return True
        except OSError: return False

def health_ready(name, svc):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d%s'%(svc['port'],svc['health']),timeout=3) as response:
            return response.status==200 and valid_health(name,response.headers.get('Content-Type',''),response.read(1024*1024))
    except (OSError,ValueError): return False

def receipt_matches(root,name,record,svc):
    return (record.get('root')==str(root) and record.get('name')==name
            and record.get('service_command')==svc['cmd'] and record.get('cwd')==str(svc['cwd'])
            and record.get('configuration_sha256')==configuration_digest(root) and is_owned(record))

def configuration_digest(root):
    h=hashlib.sha256(str(root).encode())
    for rel in ('runtime/studio-launch.json','runtime/extra_model_paths.yaml','models/manifest.json','dependencies/requirements.lock'):
        h.update(rel.encode()); h.update((root/rel).read_bytes() if (root/rel).is_file() else b'<missing>')
    for folder in ('studio/backend/app','studio/frontend/dist'):
        for path in sorted((root/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                h.update(path.relative_to(root).as_posix().encode()); h.update(path.read_bytes())
    return h.hexdigest()

def start(root):
    import psutil
    ensure_workstation_profile(root)
    services=service_commands(root); state=root/'runtime/state'; state.mkdir(parents=True,exist_ok=True)
    logs=root/'runtime/logs'; logs.mkdir(parents=True,exist_ok=True)
    reused=set()
    for name, svc in services.items():
        receipt=state/(name+'.json')
        record=json.loads(receipt.read_text()) if receipt.exists() else {}
        if record and is_owned(record):
            if not receipt_matches(root,name,record,svc):
                raise RuntimeError(name+': configuracion distinta; usa DETENER antes de reiniciar. No se toca el proceso.')
            if health_ready(name,svc):
                reused.add(name); continue
            raise RuntimeError(name+': proceso propio sin salud; revisa el log y usa DETENER para reintentar')
        if not port_free(svc['port']):
            raise RuntimeError('Puerto ocupado por otro programa; no se adopta ni termina: '+str(svc['port']))
    created=[]
    try:
        for name,svc in services.items():
            if name in reused: continue
            with (logs/(name+'.log')).open('ab',buffering=0) as output:
                output.write(('\n--- Pachecodes : Kinjutsu '+time.strftime('%Y-%m-%dT%H:%M:%S')+' ---\n').encode('utf-8'))
                flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
                p=subprocess.Popen(svc['cmd'],cwd=svc['cwd'],env=child_env(root),stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,creationflags=flags)
            # Record all process-identity fields, not a PID alone.
            record=process_record(p.pid); record.update(name=name,root=str(root),service_command=svc['cmd'],cwd=str(svc['cwd']),configuration_sha256=configuration_digest(root))
            receipt=state/(name+'.json'); receipt.write_text(json.dumps(record),encoding='utf-8'); created.append((p,receipt))
            deadline=time.monotonic()+READINESS_TIMEOUT
            while time.monotonic()<deadline:
                if p.poll() is not None: raise RuntimeError(name+' exited; see runtime/logs/'+name+'.log')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:%d%s'%(svc['port'],svc['health']),timeout=2) as response:
                        if response.status==200 and valid_health(name, response.headers.get('Content-Type', ''), response.read(1024*1024)): break
                except (OSError,ValueError): pass
                time.sleep(1)
            else: raise RuntimeError(name+' readiness timed out')
            record['children']=[process_record(c.pid) for c in psutil.Process(p.pid).children(recursive=True)]
            owners={record['pid']} | {c['pid'] for c in record['children']}
            listeners=[c for c in psutil.net_connections(kind='tcp') if c.status==psutil.CONN_LISTEN and c.laddr.port==svc['port']]
            if not listeners or any(c.pid not in owners or c.laddr.ip!='127.0.0.1' for c in listeners):
                raise RuntimeError('Listener not exclusively owned/local: '+name)
            receipt.write_text(json.dumps(record),encoding='utf-8')
            _CHILD_HANDLES[p.pid]=p
        print('Servicios propios listos: http://127.0.0.1:8220')
    except Exception:
        for p,receipt in reversed(created):
            record=json.loads(receipt.read_text())
            terminate_record(record)
            p.wait(timeout=5)
            receipt.unlink(missing_ok=True)
        raise

def stop(root):
    import psutil
    for name in ('studio','comfy'):
        receipt=root/'runtime/state'/(name+'.json')
        if not receipt.exists(): print(name+': no owned process'); continue
        record=json.loads(receipt.read_text())
        if record.get('root')!=str(root) or record.get('name')!=name:
            raise RuntimeError(name+': receipt belongs to another installation; no process terminated')
        records=record.get('children',[])+[record]
        if not any(is_owned(identity) for identity in records):
            print(name+': stale receipt; no process terminated'); continue
        # Never use taskkill /IM or a port-based kill. Each identity is checked separately,
        # even if the venv launcher has exited and its PID has been reused.
        terminate_record(record)
        receipt.unlink(); print(name+': stopped identity-matched owned processes')

def main():
    parser=argparse.ArgumentParser(description='Pachecodes : Kinjutsu portable lifecycle')
    parser.add_argument('command',choices=('install','start','stop','verify','verify-package','plan','patch-check','launch'))
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--core',type=Path)
    args=parser.parse_args(); root=args.root.resolve()
    if args.command=='plan' or args.dry_run:
        plan=dependency_plan(root); plan['models']=load_manifest(root/'models/manifest.json',root/'models'); print(json.dumps(plan,indent=2)); return
    if args.command=='verify-package': print(json.dumps(verify_package(root),indent=2)); return
    if args.command=='patch-check': apply_core(root,args.core or root/'runtime/ComfyUI',check_only=True); return
    if args.command=='launch':
        verify_runtime(root); start(root)
        import webbrowser; webbrowser.open('http://127.0.0.1:8220'); return
    {'install':install,'start':start,'stop':stop,'verify':verify_runtime}[args.command](root)

if __name__=='__main__':
    try: main()
    except (RuntimeError,ValueError,OSError,subprocess.CalledProcessError) as error:
        print('ERROR: '+str(error),file=sys.stderr); sys.exit(1)

