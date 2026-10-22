import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
class BootstrapTests(unittest.TestCase):
 def test_powershell_real_range_resume_hash_extract_receipt_and_reuse(self):
  archive=io.BytesIO()
  with zipfile.ZipFile(archive,'w') as z:z.writestr('hello.txt','fixture only; not executable')
  payload=archive.getvalue();requests=[]
  class Handler(BaseHTTPRequestHandler):
   def do_GET(s):
    offset=int(s.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);requests.append(offset)
    s.send_response(206);s.send_header('Content-Range',f'bytes {offset}-{len(payload)-1}/{len(payload)}');s.end_headers();s.wfile.write(payload[offset:])
   def log_message(*a):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with tempfile.TemporaryDirectory(prefix='Bootstrap root with spaces ',dir=os.environ.get('TMPDIR')) as tmp:
    root=Path(tmp);cache=root/'runtime/cache/bootstrap';cache.mkdir(parents=True)
    (cache/'fixture.zip.part').write_bytes(payload[:13])
    digest=hashlib.sha256(payload).hexdigest();url=f'http://127.0.0.1:{server.server_port}/fixture.zip'
    (root/'runtime/tools-manifest.json').write_text(json.dumps({'tools':[dict(name='fixture',url=url,sha256=digest,size=len(payload))]}))
    script=root/'test.ps1'
    script.write_text(". '"+str(ROOT/'scripts/Common-Kinjutsu.ps1')+"'\nInstall-PinnedZip '"+str(root)+"' 'fixture' '"+url+"' '"+digest+"' 'hello.txt'\n",encoding='utf-8')
    for _ in range(2):
     result=subprocess.run(['powershell.exe','-NoProfile','-File',str(script)],capture_output=True,text=True)
     self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertEqual(requests,[13]);receipt=json.loads((root/'runtime/tools/fixture/bootstrap-receipt.json').read_text(encoding='utf-8-sig'))
    self.assertEqual(receipt['archive_sha256'],digest)
    (root/'runtime/tools/fixture/hello.txt').write_text('tampered')
    result=subprocess.run(['powershell.exe','-NoProfile','-File',str(script)],capture_output=True,text=True)
    self.assertNotEqual(result.returncode,0)
  finally:
   server.shutdown();server.server_close();thread.join()
