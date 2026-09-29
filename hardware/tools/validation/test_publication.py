"""Interrupted publication keeps readers closed and can restore exact prior bytes."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('publish',Path(__file__).resolve().parents[1]/'cad/publish.py')
p=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(p)

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.root=self.base/'repo';self.root.mkdir()
        self.candidate=self.base/'candidate';self.output=self.base/'journal'
        dc=p.control(self.root)
        def put(path,data):
            file=self.root/path;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode())
            return {'path':path,'sha256':dc.digest(file)}
        self.put=put
        native=put('hardware/cad/current/assembly.f3d',b'native')
        main={'cloud_name':'MAIN','project':'Project','design_revision':'R1','cloud_file_id':'id','cloud_version':1}
        release=dict(main,artifacts=[dict(native,path='old.f3d')],summary='Accepted')
        manifest=put('hardware/cad/design-control/releases/R1.json',release)
        self.inputs='hardware/cad/design-control/current-inputs.json'
        inputs=put(self.inputs,{'files':[native]})
        self.r={'schema_version':3,'main':dict(main,release_manifest=manifest['path'],release_manifest_sha256=manifest['sha256']), 'accepted_native':dict(native,original_path='old.f3d'),'current_inputs':inputs}
        put(p.REGISTRY,self.r);put(p.PAGE,dc.render(self.r,release).encode())
        put(p.LOCK,{'owner':'owner','registry_sha256':dc.digest(self.root/p.REGISTRY)})
        shutil.copytree(self.root,self.candidate)
        asset='hardware/cad/current/extra.json';f=self.candidate/asset;f.write_text('{}')
        data={'files':[native,{'path':asset,'sha256':dc.digest(f)}]}
        (self.candidate/self.inputs).write_text(json.dumps(data))
        self.r['current_inputs']['sha256']=dc.digest(self.candidate/self.inputs)
        (self.candidate/p.REGISTRY).write_text(json.dumps(self.r))
        (self.candidate/p.PAGE).write_text(dc.render(self.r,release))
        self.paths=[asset,self.inputs,p.PAGE,p.REGISTRY]
    def stage(self):return p.stage(self.root,self.candidate,self.output,'owner',self.paths)
    def test_stage_is_read_only_for_checkout(self):
        before=(self.root/p.REGISTRY).read_bytes();self.stage()
        self.assertEqual((self.root/p.REGISTRY).read_bytes(),before)
        self.assertFalse((self.root/self.paths[0]).exists())
    def test_install_preserves_native_and_passes(self):
        self.stage();p.install(self.root,self.output,'owner')
        dc=p.control(self.root);self.assertEqual(dc.validate(json.loads((self.root/p.REGISTRY).read_text()))[1],2)
        self.assertFalse((self.root/p.MARKER).exists())
    def test_interruption_recovery_restores_before_bytes(self):
        before=(self.root/p.REGISTRY).read_bytes();self.stage();original=p.save
        def fail(path,data):
            if path==self.root/self.inputs:raise OSError('interrupted')
            original(path,data)
        with patch.object(p,'save',side_effect=fail):
            with self.assertRaises(OSError):p.install(self.root,self.output,'owner')
        with self.assertRaisesRegex(ValueError,'publication'):
            p.control(self.root).validate(json.loads((self.root/p.REGISTRY).read_text()))
        p.install(self.root,self.output,'owner',recover=True)
        self.assertEqual((self.root/p.REGISTRY).read_bytes(),before)
        self.assertFalse((self.root/self.paths[0]).exists())
    def test_concurrent_edit_blocks_install(self):
        self.stage();(self.root/p.PAGE).write_text('other owner edit')
        with self.assertRaisesRegex(ValueError,'Concurrent edit'):p.install(self.root,self.output,'owner')
        self.assertFalse((self.root/p.MARKER).exists())
    def test_failed_temporary_write_does_not_prevent_recovery(self):
        self.stage()
        with patch.object(p.os, 'fsync', side_effect=OSError('write interrupted')):
            with self.assertRaises(OSError):
                p.install(self.root, self.output, 'owner')
        self.assertFalse((self.root/p.MARKER).exists())
        p.install(self.root, self.output, 'owner')
        self.assertFalse((self.root/p.MARKER).exists())
        self.assertTrue((self.root/self.paths[0]).exists())
    def test_wrong_owner_rejected(self):
        self.stage()
        with self.assertRaisesRegex(ValueError,'owner'):p.install(self.root,self.output,'other')
    def test_recovery_bytes_tamper_rejected(self):
        self.stage();(self.output/'after'/self.paths[0]).write_text('changed')
        with self.assertRaisesRegex(ValueError,'bytes changed'):p.install(self.root,self.output,'owner')
    def test_escape_rejected_before_journal_creation(self):
        with self.assertRaises(ValueError):p.stage(self.root,self.candidate,self.output,'owner',self.paths+['../escape'])
        self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
