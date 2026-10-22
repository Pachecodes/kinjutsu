"""Real CPU-only Studio HTTP smoke; never launches ComfyUI or a GPU process.
Run with the locked backend environment. KINJUTSU_TEST_FFMPEG_DIR optionally
selects an extracted portable bin directory. All generated data is isolated.
"""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kinjutsu_install', ROOT/'scripts/kinjutsu.py')
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)

class StudioCpuIntegration(unittest.TestCase):
    def test_real_studio_health_openapi_environment_and_video_probe(self):
        import httpx
        with tempfile.TemporaryDirectory(prefix='kinjutsu-studio-', dir=os.environ.get('TMPDIR')) as tmp:
            isolated = Path(tmp)
            (isolated/'runtime').mkdir()
            (isolated/'runtime/studio-launch.json').write_bytes((ROOT/'runtime/studio-launch.json').read_bytes())
            folder = os.environ.get('KINJUTSU_TEST_FFMPEG_DIR')
            pair = {name:str(Path(folder)/(name+'.exe')) for name in ('ffmpeg','ffprobe')} if folder else k.media_tools(isolated)
            for name, path in pair.items():
                result = subprocess.run([path,'-version'],capture_output=True,text=True,check=True)
                self.assertTrue(result.stdout.startswith(name+' version '))
            (isolated/'runtime/tool-paths.json').write_text(json.dumps(pair))
            env = k.child_env(isolated)
            env['H3_FRONTEND_DIST'] = str(ROOT/'studio/frontend/dist')
            # Reserve a deliberately unavailable Comfy port. Its absence must be
            # surfaced as degraded health, never mistaken for full readiness.
            with socket.socket() as offline, socket.socket() as available:
                offline.bind(('127.0.0.1',0))
                comfy = 'http://127.0.0.1:%d' % offline.getsockname()[1]
                available.bind(('127.0.0.1',0)); port=available.getsockname()[1]
                available.close()
                env.update(H3_COMFY_URL=comfy,H3_EXPERIMENTAL_COMFY_URL=comfy,H3_COMFY_TIMEOUT_SECONDS='0.2',CUDA_VISIBLE_DEVICES='-1')
                config = subprocess.run([sys.executable,'-s','-c',
                    'from app.config import Settings; import json; s=Settings(); print(json.dumps(dict(ffprobe=s.resolve_ffprobe(), comfy=s.comfy_url, data=str(s.data_dir), managed=s.director_openai_managed_gpu, autostart=s.director_autostart_ollama)))'],
                    cwd=ROOT/'studio/backend',env=env,capture_output=True,text=True,check=True)
                settings=json.loads(config.stdout)
                self.assertEqual(settings['ffprobe'],pair['ffprobe'])
                self.assertEqual(settings['comfy'],comfy)
                self.assertEqual(settings['data'],str(isolated/'runtime/studio-data'))
                self.assertFalse(settings['managed']); self.assertFalse(settings['autostart'])
                log=isolated/'studio.log'
                with log.open('wb') as out:
                    child=subprocess.Popen([sys.executable,'-s','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT/'studio/backend',env=env,stdout=out,stderr=subprocess.STDOUT)
                try:
                    url='http://127.0.0.1:%d' % port
                    deadline=time.monotonic()+30
                    with httpx.Client(base_url=url,trust_env=False,timeout=3) as client:
                        while True:
                            self.assertIsNone(child.poll(),log.read_text(errors='replace'))
                            try:
                                response=client.get('/api/health')
                                if response.status_code == 200: break
                            except httpx.TransportError: pass
                            if time.monotonic()>deadline: self.fail(log.read_text(errors='replace'))
                            time.sleep(0.1)
                        health=response.json()
                        self.assertEqual(health['status'],'degraded')
                        self.assertIs(health['comfy_online'],False)
                        self.assertEqual(health['comfy_url'],comfy)
                        self.assertFalse(k.valid_health('studio',response.headers['content-type'],response.content))
                        schema=client.get('/api/openapi.json')
                        self.assertEqual(schema.status_code,200)
                        self.assertIn('/api/health',schema.json()['paths'])
                        spa=client.get('/openapi.json')
                        self.assertFalse(k.valid_health('studio',spa.headers.get('content-type',''),spa.content))
                        clip=isolated/'synthetic.mp4'
                        subprocess.run([pair['ffmpeg'],'-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=4','-t','3.0','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],check=True,capture_output=True)
                        with clip.open('rb') as media:
                            upload=client.post('/api/assets',files={'file':('synthetic.mp4',media,'video/mp4')})
                        self.assertEqual(upload.status_code,201,upload.text)
                        asset=upload.json()
                        self.assertEqual(asset['width'],64)
                        self.assertEqual(asset['height'],64)
                        self.assertGreater(asset['duration_seconds'],0)
                        prepared=client.post('/api/assets/'+asset['id']+'/prepare-guide',json=dict(width=320,height=320,length=22,fit='pad',start_seconds=0.0),timeout=30)
                        self.assertEqual(prepared.status_code,201,prepared.text)
                        guide=prepared.json()
                        self.assertEqual(guide['verified']['frame_count'],22)
                        self.assertEqual(guide['asset']['guide_provenance']['source_asset_id'],asset['id'])
                        # Lengthen a derivative using original source provenance, never frozen frames.
                        longer=client.post('/api/assets/'+guide['asset']['id']+'/prepare-guide',json=dict(width=320,height=320,length=39,fit='crop',start_seconds=0.25),timeout=30)
                        self.assertEqual(longer.status_code,201,longer.text)
                        self.assertEqual(longer.json()['verified']['frame_count'],39)
                        self.assertEqual(longer.json()['asset']['guide_provenance']['source_asset_id'],asset['id'])
                        print('CPU prepare-guide: 22 then 39 frames; original-source provenance verified; custom duration grid exercised')
                        print(json.dumps({'cpu_studio_health':health['status'],'comfy_online':False,'openapi':schema.status_code,'spa_rejected':True,'video_probe':{key:asset[key] for key in ('width','height','duration_seconds')},'ffprobe_env_resolved':True}))
                finally:
                    # Windows venv's launcher has a real interpreter descendant;
                    # waiting on the launcher alone does not release SQLite files.
                    import psutil
                    if child.poll() is None:
                        record=k.process_record(child.pid)
                        record['children']=[k.process_record(p.pid) for p in psutil.Process(child.pid).children(recursive=True)]
                        k.terminate_record(record)
                    child.wait(timeout=15)
                self.assertIsNotNone(child.returncode)

if __name__ == '__main__': unittest.main()
