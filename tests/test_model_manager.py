"""Small real HTTP range fixtures; never downloads production weights."""
import hashlib
import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('models_test',ROOT/'studio/backend/app/services/model_manager.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PAYLOAD=b'known-model-fixture'*131072

class ManagerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='Kinjutsu root with spaces ',dir=os.environ.get('TMPDIR'));self.root=Path(self.tmp.name)
  (self.root/'models').mkdir(); (self.root/'runtime').mkdir()
  self.entry=dict(repo='test/fixture',revision='a'*40,path='model.safetensors',target='vae/model.safetensors',size=len(PAYLOAD),sha256=hashlib.sha256(PAYLOAD).hexdigest(),included=False)
  (self.root/'models/manifest.json').write_text(json.dumps({'models':[self.entry]}))
  self.requests=[]; requests=self.requests
  class Handler(BaseHTTPRequestHandler):
   def do_GET(s):
    offset=int(s.headers['Range'].split('=')[1].split('-')[0]);requests.append(offset)
    s.send_response(206);s.send_header('Content-Range',f'bytes {offset}-{len(PAYLOAD)-1}/{len(PAYLOAD)}');s.end_headers()
    try:
     for start in range(offset,len(PAYLOAD),16384):
      s.wfile.write(PAYLOAD[start:start+16384]);time.sleep(.002)
    except (ConnectionError,OSError):pass
   def log_message(*args):pass
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.manager=m.ModelManager(self.root,url_factory=lambda e:f'http://127.0.0.1:{self.server.server_port}/fixture')
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def wait(self):
  deadline=time.monotonic()+10
  while self.manager.jobs['0']['status'] in ('queued','downloading','verifying'):
   if time.monotonic()>deadline:self.fail('download timeout')
   time.sleep(.02)
  return self.manager.jobs['0']
 def test_real_range_resume_sha_receipt_and_mapping(self):
  part=self.root/'models/vae/model.safetensors.part';part.parent.mkdir();part.write_bytes(PAYLOAD[:123])
  self.manager.install('0',True);self.assertEqual(self.wait()['status'],'installed')
  self.assertEqual(self.requests,[123]);self.assertFalse(part.exists())
  self.assertTrue(self.manager.catalog()['models'][0]['verified'])
  receipt=json.loads(next((self.root/'runtime/download-receipts').glob('*.json')).read_text())
  self.assertEqual(receipt['sha256'],self.entry['sha256']);self.assertTrue(receipt['license_acknowledged'])
  self.assertIn('vae: .',(self.root/'runtime/extra_model_paths.yaml').read_text())
 def test_reuse_explicit_root_no_copy_and_size_not_enough(self):
  shared=self.root/'shared';shared.mkdir();weight=shared/'model.safetensors';weight.write_bytes(b'x'*len(PAYLOAD))
  (self.root/'runtime/model-roots.json').write_text(json.dumps({'roots':[str(shared)]}))
  self.assertFalse(self.manager.catalog()['models'][0]['installed'])
  weight.write_bytes(PAYLOAD);result=self.manager.install('0',True)
  self.assertTrue(result['reused']);self.assertFalse((self.root/'models/vae/model.safetensors').exists());self.assertEqual(self.requests,[])
 def test_license_unknown_and_wrong_final_fail_closed(self):
  with self.assertRaises(ValueError):self.manager.install('0',False)
  with self.assertRaises(ValueError):self.manager.install('../evil',True)
  p=self.root/'models/vae/model.safetensors';p.parent.mkdir();p.write_bytes(b'wrong')
  with self.assertRaises(ValueError):self.manager.install('0',True)
  self.assertEqual(p.read_bytes(),b'wrong')
 def test_cancel_preserves_partial_then_resume(self):
  self.manager.install('0',True)
  while self.manager.jobs['0']['bytes']==0:time.sleep(.01)
  self.manager.cancel('0');self.assertEqual(self.wait()['status'],'cancelled')
  self.manager.install('0',True);self.assertEqual(self.wait()['status'],'installed')
 def test_bad_hash_never_promoted(self):
  self.manager.entries[0]['sha256']='0'*64
  self.manager.install('0',True);self.assertEqual(self.wait()['status'],'error')
  self.assertFalse((self.root/'models/vae/model.safetensors').exists())
  self.assertFalse((self.root/'runtime/download-receipts').exists())

 def test_api_contract_rejects_external_origin_extra_paths_and_allows_catalog(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  app=FastAPI();app.state.model_manager=self.manager;app.include_router(m.router,prefix='/api')
  with TestClient(app) as client:
   result=client.get('/api/models/catalog');self.assertEqual(result.status_code,200)
   self.assertFalse(result.json()['models'][0]['verified'])
   self.assertEqual(client.post('/api/models/0/install',json={'license_acknowledged':False}).status_code,409)
   self.assertEqual(client.post('/api/models/0/install',json={'license_acknowledged':True,'url':'http://invalid'}).status_code,422)
   self.assertEqual(client.post('/api/models/0/install',headers={'Origin':'https://foreign.invalid'},json={'license_acknowledged':True}).status_code,403)
   result=client.post('/api/models/0/install',json={'license_acknowledged':True});self.assertEqual(result.status_code,200)
   self.assertEqual(self.wait()['status'],'installed')
   self.assertEqual(client.get('/api/models/status').json()['downloads'][0]['status'],'installed')

 def test_catalog_reports_free_disk_partial_and_readable_identity(self):
  part=self.root/'models/vae/model.safetensors.part';part.parent.mkdir();part.write_bytes(PAYLOAD[:123])
  result=self.manager.catalog();row=result['models'][0]
  self.assertGreater(result['free_bytes'],0)
  self.assertEqual(row['partial_bytes'],123)
  self.assertTrue(row['label']);self.assertEqual(row['role'],'vae');self.assertIsInstance(row['required_by'],list)
  self.assertFalse(row['installed'])

 def test_license_http_serves_only_allowlisted_documents(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  folder=self.root/'licenses';folder.mkdir();(folder/'MINIMAX-H3-LICENSE.txt').write_text('Fixture model license',encoding='utf8')
  app=FastAPI();app.state.model_manager=self.manager;app.include_router(m.router,prefix='/api')
  with TestClient(app) as client:
   r=client.get('/api/models/licenses/MINIMAX-H3-LICENSE.txt');self.assertEqual(r.status_code,200);self.assertEqual(r.text,'Fixture model license')
   self.assertTrue(r.headers['content-type'].startswith('text/plain'))
   self.assertEqual(client.get('/api/models/licenses/manifest.json').status_code,404)
   self.assertEqual(client.get('/api/models/licenses/..%2fmodels%2fmanifest.json').status_code,404)

if __name__=='__main__':unittest.main()
