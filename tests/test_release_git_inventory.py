import pathlib,subprocess,sys,tempfile,unittest,os
ROOT=pathlib.Path(__file__).resolve().parents[1]

class GitInventoryTests(unittest.TestCase):
 def test_git_inventory_excludes_private_ignored_runtime(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
   root=pathlib.Path(tmp)
   (root/'safe.py').write_text('print(1)\n')
   (root/'.gitignore').write_text('runtime/\n')
   (root/'SHA256SUMS.txt').write_text('')
   (root/'runtime').mkdir();(root/'runtime/workstation.json').write_text('private-local-only')
   subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
   subprocess.run(['git','-C',str(root),'add','.'],check=True,capture_output=True)
   r=subprocess.run([sys.executable,str(ROOT/'scripts/release_gate.py'),'--root',str(root),'--git-tracked','--write-inventory','--verify-inventory'],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   inventory=(root/'SHA256SUMS.txt').read_text()
   self.assertIn('safe.py',inventory);self.assertNotIn('workstation.json',inventory)
   self.assertEqual((root/'runtime/workstation.json').read_text(),'private-local-only')

if __name__=='__main__':unittest.main()
