import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lifecycle_reuse',ROOT/'scripts/kinjutsu.py')
k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
class ReuseTests(unittest.TestCase):
 def test_reuses_only_healthy_same_root_same_config_and_stops_exact_identity(self):
  with tempfile.TemporaryDirectory(prefix='Lifecycle root with spaces ',dir=os.environ.get('TMPDIR')) as tmp:
   root=Path(tmp)
   server=root/'health.py'
   server.write_text("from http.server import BaseHTTPRequestHandler,HTTPServer\nimport sys\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{\"system\":{},\"devices\":[]}')\nHTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()\n")
   with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   services={'comfy':dict(cmd=[sys.executable,str(server),str(port)],cwd=root,port=port,health='/system_stats')}
   with patch.object(k,'service_commands',return_value=services),patch.object(k,'child_env',return_value=os.environ.copy()):
    try:
     k.start(root);receipt=root/'runtime/state/comfy.json';first=json.loads(receipt.read_text())
     k.start(root);self.assertEqual(json.loads(receipt.read_text())['pid'],first['pid'])
     (root/'runtime/studio-launch.json').write_text('{"changed":true}')
     with self.assertRaisesRegex(RuntimeError,'configuracion'):k.start(root)
     self.assertTrue(k.is_owned(first))
    finally:k.stop(root)
    self.assertFalse(k.is_owned(first));self.assertTrue(k.port_free(port))
