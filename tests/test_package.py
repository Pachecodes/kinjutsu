import hashlib,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class PackageTests(unittest.TestCase):
 def setUp(self):
  for name in ['models/manifest.json','workflows/approved-api.json','workflows/character-swap-turbo8-api.json']:
   self.assertTrue((ROOT/name).is_file(),'Missing required package artifact: '+name)
 def test_model_manifest_pinned_and_complete(self):
  data=json.loads((ROOT/'models/manifest.json').read_text(encoding='utf-8'))
  self.assertEqual(len(data['models']),6)
  self.assertEqual(sum(bool(m['included']) for m in data['models']),0)
  for m in data['models']:
   self.assertRegex(m['revision'],r'^[0-9a-f]{40}$')
   self.assertRegex(m['sha256'],r'^[0-9a-f]{64}$')
   self.assertGreater(m['size'],0)
   self.assertNotIn('main/',m['url'])
   self.assertFalse(pathlib.PurePosixPath(m['target']).is_absolute())
 def test_api_workflow_whole_and_reference_safe(self):
  graph=json.loads((ROOT/'workflows/character-swap-turbo8-api.json').read_text(encoding='utf-8'))
  self.assertFalse(any(n['class_type']=='ModelPreviewOverrideKJ' for n in graph.values()))
  for n in graph.values():
   for v in n['inputs'].values():
    if isinstance(v,list) and len(v)==2 and isinstance(v[0],str) and isinstance(v[1],int):self.assertIn(v[0],graph)
  by={n['class_type']:n['inputs'] for n in graph.values()}
  self.assertEqual(by['MiniMaxH3AddGuide']['frame_idx'],0)
  self.assertEqual(by['BasicScheduler']['steps'],8)
  self.assertEqual(by['KSamplerSelect']['sampler_name'],'euler')
  self.assertEqual(by['MiniMaxH3ReferenceToVideo']['length'],124)
  self.assertIn('CreateVideo',by)
  self.assertIn('SaveVideo',by)
  self.assertEqual(graph['111']['inputs']['model'],['110',0])
  self.assertEqual(by['BasicGuider']['model'],['111',0])
 def test_template_is_generic(self):
  data=json.loads((ROOT/'workflows/approved-api.json').read_text(encoding='utf-8'))
  self.assertEqual(data['steps'],8)
  self.assertEqual(data['references'][0]['asset_id'],'REPLACE_WITH_UPLOADED_IDENTITY_ASSET_ID')
  self.assertEqual(data['references'][1]['role'],'aligned_guide')
  text=json.dumps(data).lower()
  self.assertNotRegex(text,r'[a-z]:[/\\\\]')
  self.assertNotIn('h3studio/',text)
 def test_bundled_weights_match(self):
  data=json.loads((ROOT/'models/manifest.json').read_text(encoding='utf-8'))
  for m in data['models']:
   p=ROOT/'models'/m['target']
   if not m['included']:
    self.assertFalse(p.exists())
    continue
   self.assertEqual(p.stat().st_size,m['size'])
   with p.open('rb') as f:self.assertEqual(hashlib.file_digest(f,'sha256').hexdigest(),m['sha256'])
if __name__=='__main__':unittest.main()
