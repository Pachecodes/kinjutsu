"""CPU-only installer contract tests. No GPU services or large downloads."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kinjutsu_install', ROOT / 'scripts/kinjutsu.py')
k = importlib.util.module_from_spec(spec)
if spec.loader:
    spec.loader.exec_module(k)

class ManifestTests(unittest.TestCase):
    def test_rejects_unpinned_or_escaping_entry(self):
        good = dict(repo='org/model', path='weight.bin', revision='a'*40,
                    size=3, sha256='b'*64, target='vae/weight.bin', included=False)
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root = Path(t)
            p = root/'manifest.json'
            p.write_text(json.dumps({'models':[good]}))
            self.assertEqual(k.load_manifest(p, root)[0]['size'], 3)
            for field, value in [('target','../escape'),('revision','main'),('sha256','bad'),('included','false')]:
                p.write_text(json.dumps({'models':[{**good,field:value}]}))
                with self.assertRaises(ValueError): k.load_manifest(p, root)
    def test_hash_mismatch_does_not_overwrite_final(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            p=Path(t)/'model'; p.write_bytes(b'abc')
            self.assertFalse(k.verify_file(p, 3, '0'*64))
            self.assertEqual(p.read_bytes(), b'abc')
    def test_dependency_plan_is_pinned_local_and_read_only(self):
        plan=k.dependency_plan(ROOT)
        self.assertEqual(plan['core_revision'], '7a131a3afadc8200120f67f9236311a2c48b7445')
        self.assertEqual(plan['listeners'], {'comfy':'127.0.0.1:8218','studio':'127.0.0.1:8220'})
        self.assertIn('3.12.10', plan['python'])

class OperationalTests(unittest.TestCase):
    def test_incomplete_media_receipt_cannot_start_studio(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root=Path(t); (root/'runtime').mkdir()
            (root/'runtime/tool-paths.json').write_text(json.dumps({'ffmpeg':'missing/ffmpeg.exe','ffprobe':'missing/ffprobe.exe'}))
            with self.assertRaisesRegex(RuntimeError, 'media|ffprobe'):
                k.child_env(root)

    def test_child_env_isolates_h3_settings_and_exposes_ffprobe_pair(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root = Path(t); (root/'runtime').mkdir()
            pair = k.media_tools(root)
            (root/'runtime/tool-paths.json').write_text(json.dumps(pair))
            with patch.dict(os.environ, {'H3_COMFY_URL': 'http://127.0.0.1:9999', 'H3_DATA_DIR': 'private', 'H3_DIRECTOR_OPENAI_MANAGED_GPU': 'true'}):
                env = k.child_env(root)
            self.assertEqual(env['H3_COMFY_URL'], 'http://127.0.0.1:8218')
            self.assertEqual(env['H3_EXPERIMENTAL_COMFY_URL'], env['H3_COMFY_URL'])
            self.assertEqual(env['H3_FFPROBE_PATH'], pair['ffprobe'])
            self.assertEqual(env['H3_DATA_DIR'], str(root/'runtime/studio-data'))
            self.assertEqual(env['H3_DIRECTOR_OPENAI_MANAGED_GPU'], 'false')
            self.assertEqual(env['IMAGEIO_FFMPEG_EXE'], pair['ffmpeg'])

    def test_ffmpeg_only_is_not_a_complete_media_toolchain(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root = Path(t)
            with patch.object(k.shutil, 'which', return_value=None):
                with self.assertRaisesRegex(RuntimeError, 'ffmpeg.*ffprobe'):
                    k.media_tools(root)

    def test_backend_direct_requirements_are_satisfied_by_lock(self):
        from packaging.requirements import Requirement
        locked = {}
        import re
        for name, version in re.findall(r'^([\w-]+)==([^\s;]+)', (ROOT/'dependencies/requirements.lock').read_text(), re.M):
            locked[name.lower().replace('_','-')] = version
        for line in (ROOT/'studio/backend/requirements.txt').read_text().splitlines():
            if not line.strip() or line.startswith('#'): continue
            req=Requirement(line)
            self.assertIn(req.name.lower(),locked)
            self.assertIn(locked[req.name.lower()],req.specifier, str(req))
        self.assertIn('httptools',locked)
        self.assertIn('watchfiles',locked)

    def test_studio_readiness_rejects_spa_and_degraded_backend(self):
        self.assertEqual(k.service_commands(ROOT)['studio']['health'], '/api/health')
        self.assertFalse(k.valid_health('studio', 'text/html', b'<html>SPA</html>'))
        self.assertFalse(k.valid_health('studio', 'application/json', b'{"status":"degraded","comfy_online":false}'))
        self.assertTrue(k.valid_health('studio', 'application/json', b'{"status":"ok","comfy_online":true,"version":"1","active_jobs":0}'))

    def test_download_resume_and_range_ignored_restart(self):
        import http.server, threading
        payload=b'0123456789'*100
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self,*args): pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
                p=Path(t)/'model.bin'; p.with_suffix('.bin.part').write_bytes(payload[:150])
                k.download_verified('http://127.0.0.1:%s/file'%server.server_port,p,len(payload),k.hashlib.sha256(payload).hexdigest())
                self.assertEqual(p.read_bytes(),payload)
                self.assertFalse(p.with_suffix('.bin.part').exists())
                with self.assertRaises(RuntimeError): k.download_verified('http://127.0.0.1:%s/file'%server.server_port,p,len(payload),'0'*64)
                self.assertEqual(p.read_bytes(),payload)
        finally: server.shutdown(); server.server_close(); thread.join()
    def test_ephemeral_lifecycle_does_not_kill_unrelated(self):
        import socket, subprocess, sys
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root=Path(t)
            unrelated=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
            old=k.service_commands
            def commands(r):
                with socket.socket() as s: s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
                script=root/'health_server.py'
                script.write_text("from http.server import BaseHTTPRequestHandler,HTTPServer\nimport sys\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b'{\"system\":{},\"devices\":[]}')\nHTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()\n")
                return {'comfy':{'cmd':[sys.executable,str(script),str(port)],'cwd':r,'port':port,'health':'/system_stats'}}
            k.service_commands=commands
            try:
                k.start(root)
                record=json.loads((root/'runtime/state/comfy.json').read_text())
                self.assertIn('children', record)
                k.stop(root)
                self.assertFalse(k.is_owned(record))
                self.assertIsNone(unrelated.poll())
            finally:
                k.service_commands=old
                unrelated.terminate(); unrelated.wait()
                if (root/'runtime/state/comfy.json').exists(): k.stop(root)

    def test_local_studio_contract_and_no_preview_trt_dependency(self):
        commands=k.service_commands(ROOT)
        self.assertEqual(commands['studio']['cwd'], ROOT/'studio/backend')
        self.assertIn('app.main:app',commands['studio']['cmd'])
        self.assertEqual(commands['studio']['port'],8220)
        self.assertNotIn('--enable-cors-header',commands['comfy']['cmd'])
        self.assertNotIn('trt',json.dumps(commands,default=str).lower())
    def test_safe_target_rejects_empty_windows_and_symlink_escape(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            for value in ('','C:/escape','/absolute','a\\\\b','../x'):
                with self.assertRaises(ValueError): k.safe_target(Path(t),value)

    def test_stop_handles_exited_launcher_without_touching_reused_pid(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root=Path(t); state=root/'runtime/state'; state.mkdir(parents=True)
            child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
            unrelated=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
            record=k.process_record(unrelated.pid)
            record.update(create_time=record['create_time']-100,root=str(root),name='comfy',children=[k.process_record(child.pid)])
            (state/'comfy.json').write_text(json.dumps(record))
            try:
                k.stop(root)
                self.assertIsNotNone(child.poll())
                self.assertIsNone(unrelated.poll())
            finally:
                if child.poll() is None: child.terminate()
                child.wait(); unrelated.terminate(); unrelated.wait()

    def test_failed_start_rolls_back_descendant_process(self):
        self.assertTrue(hasattr(k,'READINESS_TIMEOUT'))
        import sys,psutil
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root=Path(t); marker=root/'child.pid'
            script=root/'spawn.py'
            script.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\nPath('child.pid').write_text(str(p.pid))\ntime.sleep(30)\n")
            old=k.service_commands; old_timeout=getattr(k,'READINESS_TIMEOUT',180)
            k.READINESS_TIMEOUT=0.3
            k.service_commands=lambda r:{'comfy':{'cmd':[sys.executable,str(script)],'cwd':r,'port':0,'health':'/'}}
            try:
                with self.assertRaises(RuntimeError): k.start(root)
                self.assertTrue(marker.exists())
                self.assertFalse(psutil.pid_exists(int(marker.read_text())))
            finally:
                k.service_commands=old; k.READINESS_TIMEOUT=old_timeout
                if marker.exists() and psutil.pid_exists(int(marker.read_text())):
                    psutil.Process(int(marker.read_text())).terminate()

    def test_runtime_source_verifier_requires_postimage_and_addguide(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
            root=Path(t); payload=root/'runtime/patches'; payload.mkdir(parents=True)
            core=root/'runtime/ComfyUI'; core.mkdir(parents=True)
            file=core/'file.py'; file.write_bytes(b'patched\n')
            record={'core_files':[{'path':'file.py','after_sha256':k.hashlib.sha256(b'patched\n').hexdigest()}]}
            (payload/'provenance.json').write_text(json.dumps(record))
            k.verify_core_postimages(root)
            file.write_bytes(b'unpatched\n')
            with self.assertRaises(RuntimeError): k.verify_core_postimages(root)

    def test_patch_payload_integrity(self):
        k.verify_patch_payload(ROOT)
    def test_owned_process_rejects_forged_creation_time(self):
        import subprocess,sys
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
        try:
            record=k.process_record(child.pid)
            self.assertTrue(k.is_owned(record))
            self.assertFalse(k.is_owned({**record,'create_time':record['create_time']-10}))
            self.assertFalse(k.is_owned({**record,'cmdline':['unrelated']}))
        finally: child.terminate(); child.wait()

if __name__ == '__main__': unittest.main()
