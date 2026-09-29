"""Authority rejection occurs before candidate outputs can be created."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SPEC=importlib.util.spec_from_file_location('authority',Path(__file__).resolve().parents[1]/'authority.py');a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)
class AuthorityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();p=patch.object(a,'ROOT',self.root);p.start();self.addCleanup(p.stop)
  self.control=self.root/'hardware/cad/design-control';self.control.mkdir(parents=True)
  (self.root/'release.json').write_text('{}');self.main={'design_revision':'R22','cloud_file_id':'lineage','cloud_version':17,'release_manifest':'release.json','release_manifest_sha256':a.digest(self.root/'release.json')};self.registry={'main':self.main};self.lock={'cad':dict(self.main)};self.path=self.root/'lock.json';self.path.write_text(json.dumps(self.lock));self.write()
 def write(self):(self.control/'registry.json').write_text(json.dumps(self.registry))
 def test_candidate_can_build_without_delivery(self):a.validate_input_authority(self.lock,self.path)
 def test_different_cad_rejected(self):
  self.main['cloud_version']=18;self.write()
  with self.assertRaisesRegex(ValueError,'exact accepted CAD'):a.validate_input_authority(self.lock,self.path)
 def test_stale_manifest_rejected(self):
  (self.root/'release.json').write_text('{"changed":1}')
  with self.assertRaisesRegex(ValueError,'manifest changed'):a.validate_input_authority(self.lock,self.path)
 def test_release_requires_delivery(self):
  with self.assertRaisesRegex(ValueError,'selected delivery'):a.validate_input_authority(self.lock,self.path,True)
 def test_release_requires_lock_binding(self):
  d={'cad':{k:self.main[k] for k in ['design_revision','cloud_file_id','cloud_version']},'release_manifest':self.main['release_manifest'],'release_manifest_sha256':self.main['release_manifest_sha256'],'files':[]};p=self.root/'delivery.json';p.write_text(json.dumps(d));self.registry['delivery']={'path':'delivery.json','sha256':a.digest(p)};self.write()
  with self.assertRaisesRegex(ValueError,'not bound'):a.validate_input_authority(self.lock,self.path,True)
if __name__=='__main__':unittest.main()
