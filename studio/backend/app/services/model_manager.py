"""Pinned local model catalog. No arbitrary URLs or client filesystem paths.
Roots are explicitly authorized by the local operator in runtime/model-roots.json.
Only exact manifest targets or flat exact basenames are inspected (no recursion).
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import time
import urllib.request
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict


class ModelManager:
    def __init__(self, root: Path, *, url_factory=None):
        self.root = root.resolve()
        self.manifest_path = self.root / 'models/manifest.json'
        self.entries = json.loads(self.manifest_path.read_text(encoding='utf-8-sig'))['models']
        self.manifest_sha256 = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.url_factory = url_factory  # test-only injection; HTTP never accepts URLs
        self.lock = threading.Lock()
        self.jobs = {}
        self.cancel_events = {}
        seen = set()
        for e in self.entries:
            if type(e.get('optional',False)) is not bool: raise ValueError('optional must be boolean')
            p = PurePosixPath(e['target'])
            if (p.is_absolute() or '..' in p.parts or ':' in e['target'] or '\\' in e['target']
                    or len(p.parts) != 2 or p.parts[0] not in ('loras','vae','diffusion_models','text_encoders')
                    or e['target'].casefold() in seen or not re.fullmatch('[0-9a-f]{64}',e['sha256'])
                    or not re.fullmatch('[0-9a-f]{40}',e['revision'])
                    or not re.fullmatch(r'[\w.-]+/[\w.-]+',e['repo'])
                    or PurePosixPath(e['path']).is_absolute() or '..' in PurePosixPath(e['path']).parts
                    or ':' in e['path'] or '\\' in e['path'] or type(e['size']) is not int or e['size'] <= 0):
                raise ValueError('Manifest de modelos invalido')
            seen.add(e['target'].casefold())

    @staticmethod
    def verified(path, e):
        if not path.is_file() or path.stat().st_size != e['size']:
            return False
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):
                h.update(block)
        return h.hexdigest() == e['sha256']

    def roots(self):
        result = [self.root/'models']
        cfg = self.root/'runtime/model-roots.json'
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding='utf-8-sig'))
            for raw in data.get('roots',[]):
                p = Path(raw)
                if not p.is_absolute() or not p.is_dir():
                    raise ValueError('Carpeta autorizada de modelos inexistente o no absoluta')
                if p.resolve() not in result:
                    result.append(p.resolve())
        return result

    def discover(self, e):
        for root in self.roots():
            for path in (root/e['target'],root/PurePosixPath(e['target']).name):
                # No symlink/junction traversal outside explicitly authorized root.
                if path.resolve().is_relative_to(root.resolve()) and self.verified(path,e):
                    return path.resolve()
        return None

    def catalog(self):
        rows=[]
        labels={
            'minimax_h3_ref2va_pruned_int8_convrot.safetensors':('MiniMax H3 Ref2VA INT8 ConvRot','video_model'),
            'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors':('Qwen3-VL 32B NVFP4 AWQ','text_encoder'),
            'minimax_h3_video_vae_fp16.safetensors':('MiniMax H3 Video VAE FP16','video_vae'),
            'minimax_h3_audio_vae_fp32.safetensors':('MiniMax H3 Audio VAE FP32','audio_vae'),
            'latest_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors':('Ref2VA Turbo8 v1.0','turbo_lora'),
            'minimax_h3_character_swap_v1.1_ref2va_fro.safetensors':('BFS Character Swap v1.1','task_lora'),
        }
        for i,e in enumerate(self.entries):
            found=self.discover(e)
            basename=PurePosixPath(e['target']).name
            label,role=labels.get(basename,(basename,PurePosixPath(e['target']).parts[0]))
            part=(self.root/'models'/e['target']).with_suffix(PurePosixPath(e['target']).suffix+'.part')
            safe_partial=part.resolve().is_relative_to((self.root/'models').resolve()) and part.is_file()
            partial_bytes=part.stat().st_size if safe_partial else 0
            required_by=(['character-swap-hd-turbo8'] if role=='turbo_lora' else ['character-swap-hd-turbo8','character-swap-v11']) if basename in labels else []
            if e.get('profile')=='fasth3-omni': label,role='FastH3 Omni 8-step INT8 ConvRot','video_model'
            if e.get('profile')=='fasth3-omni': required_by=['fasth3-omni-scenes']
            elif role in ('text_encoder','video_vae','audio_vae'): required_by += ['fasth3-omni-scenes']
            rows.append(dict(id=str(i),target=e['target'],size=e['size'],sha256=e['sha256'],
                optional=e.get('optional',False),profile=e.get('profile'),
                included=e['included'],installed=found is not None,verified=found is not None,
                reused=found is not None and not found.is_relative_to(self.root/'models'),
                revision=e['revision'],repo=e['repo'],label=label,role=role,required_by=required_by,
                partial_bytes=partial_bytes,partial_valid_size=partial_bytes<=e['size']))
        return dict(manifest_sha256=self.manifest_sha256,models=rows,
            free_bytes=shutil.disk_usage(self.root/'models').free,
            license_documents=['licenses/MINIMAX-H3-LICENSE.txt','licenses/BFS-CHARACTER-SWAP-LICENSE.md','licenses/BFS-ASSET-SCOPE.md'])

    def write_mapping(self, profile=None):
        if profile not in (None,'fasth3-omni'): raise ValueError('Unknown model mapping profile')
        lines=['# Generated from SHA256-verified catalog; restart Comfy after changes.']
        for i,e in enumerate(self.entries):
            if profile == 'fasth3-omni':
                if PurePosixPath(e['target']).parts[0] not in ('text_encoders','vae') and e.get('profile')!=profile: continue
            elif e.get('optional',False): continue
            found=self.discover(e)
            if found:
                category=PurePosixPath(e['target']).parts[0]
                lines += [f'catalog_{i}:', '  base_path: '+json.dumps(str(found.parent)),f'  {category}: .']
        runtime=self.root/'runtime'
        if profile: runtime=runtime/profile
        runtime.mkdir(parents=True,exist_ok=True)
        tmp=runtime/'extra_model_paths.yaml.tmp'
        tmp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        tmp.replace(runtime/'extra_model_paths.yaml')
        if profile is None and (self.root/'runtime/fasth3-omni').is_dir():
            self.write_mapping(profile='fasth3-omni')

    def install(self, model_id, acknowledge):
        if not acknowledge:
            raise ValueError('Lea y acepte las licencias antes de descargar')
        if model_id not in [str(i) for i in range(len(self.entries))]:
            raise ValueError('Modelo no incluido en el catalogo')
        with self.lock:
            if any(j['status'] in ('queued','downloading','verifying') for j in self.jobs.values()):
                raise ValueError('Ya hay una descarga activa; espere o cancele')
            e=self.entries[int(model_id)]
            # Validate roots before background work and never redownload a verified shared model.
            found=self.discover(e)
            if found:
                self.write_mapping()
                return dict(id=model_id,status='installed',bytes=e['size'],total=e['size'],reused=True)
            target=self.root/'models'/e['target']
            if target.exists():
                raise ValueError('Archivo final incorrecto: conservar e inspeccionar; no se sobrescribe')
            if not target.resolve().is_relative_to((self.root/'models').resolve()):
                raise ValueError('Destino fuera de models')
            target.parent.mkdir(parents=True,exist_ok=True)
            part=target.with_suffix(target.suffix+'.part')
            if not part.resolve().is_relative_to((self.root/'models').resolve()):
                raise ValueError('Parcial fuera de models')
            offset=part.stat().st_size if part.exists() else 0
            if offset>e['size']:
                raise ValueError('Archivo parcial excede el tamano fijado')
            if shutil.disk_usage(target.parent).free < e['size']-offset+1024*1024*1024:
                raise ValueError('Espacio insuficiente: modelo pendiente mas 1 GiB de margen')
            job=dict(id=model_id,status='queued',bytes=offset,total=e['size'],error=None)
            self.jobs[model_id]=job
            event=threading.Event(); self.cancel_events[model_id]=event
            threading.Thread(target=self._download,args=(e,target,part,job,event),daemon=True).start()
            return dict(job)

    def _download(self,e,target,part,job,event):
        try:
            offset=part.stat().st_size if part.exists() else 0
            url=(self.url_factory(e) if self.url_factory else
                 'https://huggingface.co/{repo}/resolve/{revision}/{path}'.format(**e))
            job['status']='downloading'
            if offset < e['size']:
                req=urllib.request.Request(url,headers={'Range':f'bytes={offset}-','User-Agent':'Kinjutsu/1'})
                with urllib.request.urlopen(req,timeout=30) as response:
                    append=response.status==206
                    if append and response.headers.get('Content-Range') != f"bytes {offset}-{e['size']-1}/{e['size']}":
                        raise ValueError('Content-Range inconsistente; parcial conservado')
                    if response.status not in (200,206):
                        raise ValueError('Respuesta HTTP inesperada')
                    with part.open('ab' if append else 'wb') as f:
                        while True:
                            if event.is_set():
                                job['status']='cancelled'; return
                            block=response.read(1024*1024)
                            if not block: break
                            if f.tell()+len(block)>e['size']:
                                raise ValueError('Descarga excede tamano fijado')
                            f.write(block); job['bytes']=f.tell()
            if event.is_set():
                job['status']='cancelled'; return
            job['status']='verifying'
            if not self.verified(part,e):
                raise ValueError('SHA256/tamano incorrecto; parcial conservado')
            if event.is_set():
                job['status']='cancelled'; return
            # Windows rename refuses an existing destination (no overwrite).
            part.rename(target)
            self.write_mapping()
            receipt=self.root/'runtime/download-receipts'; receipt.mkdir(parents=True,exist_ok=True)
            (receipt/(e['sha256']+'.json')).write_text(json.dumps(dict(target=e['target'],size=e['size'],sha256=e['sha256'],revision=e['revision'],url=url,verified_at=time.time(),license_acknowledged=True)),encoding='utf-8')
            job.update(status='installed',bytes=e['size'])
        except Exception as exc:
            job.update(status='error',error=str(exc))

    def cancel(self, model_id):
        if model_id not in self.cancel_events:
            raise ValueError('Descarga desconocida')
        self.cancel_events[model_id].set()
        return dict(id=model_id,cancel_requested=True)


_MANAGER_GATE=threading.Lock()
router=APIRouter(prefix='/models',tags=['managed models'])
class InstallRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    license_acknowledged: bool = False

def manager(request: Request):
    if request.method!='GET':
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403,'Origen externo rechazado')
        if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            raise HTTPException(403,'Solo acceso local')
    with _MANAGER_GATE:
        if not hasattr(request.app.state,'model_manager'):
            root=Path(os.environ.get('KINJUTSU_ROOT',Path(__file__).resolve().parents[4]))
            request.app.state.model_manager=ModelManager(root)
    return request.app.state.model_manager

@router.get('/catalog')
def catalog(request:Request):
    return manager(request).catalog()

@router.get('/licenses/{name}', response_class=PlainTextResponse)
def license_text(name:str,request:Request):
    allowed={'MINIMAX-H3-LICENSE.txt','BFS-CHARACTER-SWAP-LICENSE.md','BFS-ASSET-SCOPE.md'}
    if name not in allowed:
        raise HTTPException(404,'Licencia no incluida en el catalogo')
    folder=manager(request).root/'licenses'
    path=folder/name
    if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        raise HTTPException(404,'Documento de licencia no disponible')
    return PlainTextResponse(path.read_text(encoding='utf-8-sig'),headers={'X-Content-Type-Options':'nosniff'})

@router.get('/status')
def status(request:Request):
    m=manager(request)
    return dict(downloads=list(m.jobs.values()),restart_comfy_after_install=True)

@router.post('/{model_id}/install')
def install(model_id:str,body:InstallRequest,request:Request):
    try: return manager(request).install(model_id,body.license_acknowledged)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc

@router.post('/{model_id}/cancel')
def cancel(model_id:str,request:Request):
    try: return manager(request).cancel(model_id)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
