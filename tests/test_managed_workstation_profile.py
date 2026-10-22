import importlib.util,json,os,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kinjutsu_managed_profile',ROOT/'scripts/kinjutsu.py')
k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)

class ManagedProfileTests(unittest.TestCase):
 def test_verified_install_creates_selectable_profile_without_launch(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
   root=pathlib.Path(tmp).resolve();core=root/'runtime/ComfyUI';core.mkdir(parents=True)
   for name in ('main.py','folder_paths.py'):(core/name).write_text('# fixture')
   (core/'comfy').mkdir();py=root/'runtime/venv/Scripts/python.exe';py.parent.mkdir(parents=True);py.write_text('fixture')
   (root/'models').mkdir()
   (root/'runtime/installed.json').write_text(json.dumps({'verified':True,'root':str(root)}))
   self.assertTrue(k.ensure_workstation_profile(root))
   profile=json.loads((root/'runtime/workstation.json').read_text())['runtimes'][0]
   self.assertTrue(profile['approved']);self.assertEqual(profile['executable'],str(py));self.assertEqual(profile['port'],8218)
   self.assertEqual(profile['argv'][1],str(core/'main.py'));self.assertTrue(pathlib.Path(profile['folders']['outputs']).is_dir())
   original=(root/'runtime/workstation.json').read_bytes()
   self.assertFalse(k.ensure_workstation_profile(root));self.assertEqual(original,(root/'runtime/workstation.json').read_bytes())

 def test_unverified_install_does_not_authorize_runtime(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
   root=pathlib.Path(tmp);self.assertFalse(k.ensure_workstation_profile(root));self.assertFalse((root/'runtime/workstation.json').exists())

if __name__=='__main__':unittest.main()
