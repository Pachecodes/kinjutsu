"""A process exiting between identity check and terminate is already stopped."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import psutil
spec=importlib.util.spec_from_file_location('kinjutsu_race',Path(__file__).resolve().parents[1]/'scripts/kinjutsu.py')
k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
class ExitRaceTests(unittest.TestCase):
 def test_verified_owner_exiting_during_terminate_is_success(self):
  identity={'pid':999999,'create_time':1.0,'exe':'python.exe','cmdline':['python.exe']}
  process=Mock();process.children.return_value=[];process.terminate.side_effect=psutil.NoSuchProcess(identity['pid'])
  with patch.object(k,'is_owned',side_effect=[True,True,False]),patch('psutil.Process',return_value=process):
   k.terminate_record(identity)
  process.terminate.assert_called_once()
if __name__=='__main__':unittest.main()
