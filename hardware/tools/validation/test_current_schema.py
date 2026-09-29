"""Portable current authority rejects stale bytes and unaccepted inputs."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('current_dc', Path(__file__).resolve().parents[3] / 'hardware/cad/design_control.py')
dc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dc)

class CurrentSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        for name, path in [('ROOT', self.root), ('CONTROL', self.root/'hardware/cad/design-control')]:
            p = patch.object(dc, name, path); p.start(); self.addCleanup(p.stop)
        self.main = dict(design_revision='R1', cloud_file_id='lineage', cloud_version=1)
        native = self.put('hardware/cad/current/assembly.f3d', b'accepted')
        release = self.put('hardware/cad/design-control/releases/R1.json', dict(self.main, artifacts=[dict(native, path='original.f3d')]))
        inputs = self.put('hardware/cad/design-control/current-inputs.json', {'files':[native]})
        self.registry = {'schema_version':3, 'main':dict(self.main, release_manifest=release['path'], release_manifest_sha256=release['sha256']), 'accepted_native':dict(native, original_path='original.f3d'), 'current_inputs':inputs}
    def put(self, name, data):
        path=self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
        return {'path':name, 'sha256':dc.digest(path)}
    def test_current_set_is_self_contained(self):
        self.assertEqual(dc.validate(self.registry)[1], 1)
    def test_only_current_schema_is_supported(self):
        for version in (1, 2, 99):
            with self.subTest(version=version):
                self.registry['schema_version'] = version
                with self.assertRaisesRegex(ValueError, 'Unsupported registry schema'):
                    dc.validate(self.registry)
    def test_native_required_without_delivery(self):
        self.registry['current_inputs']=self.put('hardware/cad/design-control/current-inputs.json', {'files':[]})
        with self.assertRaisesRegex(ValueError, 'Empty|native'):dc.validate(self.registry)
    def test_scratch_input_rejected(self):
        row=self.put('hardware/.work/mesh.stl', b'scratch')
        self.registry['current_inputs']=self.put('hardware/cad/design-control/current-inputs.json', {'files':[row]})
        with self.assertRaisesRegex(ValueError,'current input'):dc.validate(self.registry)
    def test_symlink_into_scratch_rejected(self):
        source=self.put('hardware/.work/native.f3d', b'accepted')
        p=self.root/'hardware/cad/current/assembly.f3d';p.unlink();p.symlink_to(self.root/source['path'])
        with self.assertRaisesRegex(ValueError,'current input'):dc.validate(self.registry)
    def test_duplicate_input_rejected(self):
        row=self.registry['accepted_native'];self.registry['current_inputs']=self.put('hardware/cad/design-control/current-inputs.json', {'files':[row,row]})
        with self.assertRaisesRegex(ValueError,'Duplicate'):dc.validate(self.registry)
    def test_native_must_match_accepted_release(self):
        row=self.put('hardware/cad/current/assembly.f3d',b'other')
        self.registry['accepted_native'].update(row)
        self.registry['current_inputs']=self.put('hardware/cad/design-control/current-inputs.json',{'files':[row]})
        with self.assertRaisesRegex(ValueError,'accepted native'):dc.validate(self.registry)
    def test_interrupted_publication_fails_closed(self):
        self.put('hardware/cad/design-control/publication-in-progress.json', {'owner':'test'})
        with self.assertRaisesRegex(ValueError,'publication'):dc.validate(self.registry)
    def test_delivery_cannot_claim_wrong_design(self):
        d=self.put('hardware/cad/design-control/deliveries/d.json',{'cad':dict(self.main,cloud_version=9), 'release_manifest':self.registry['main']['release_manifest'],'release_manifest_sha256':self.registry['main']['release_manifest_sha256'],'files':[]})
        self.registry['delivery']=d
        with self.assertRaisesRegex(ValueError,'Delivery'):dc.validate(self.registry)

    def test_delivery_must_bind_exact_manifest(self):
        self.registry['delivery'] = self.put('hardware/cad/design-control/deliveries/d.json', {
            'cad': self.main,
            'release_manifest': self.registry['main']['release_manifest'],
            'release_manifest_sha256': '0' * 64,
            'files': [],
        })
        with self.assertRaisesRegex(ValueError, 'exact accepted manifest'):
            dc.validate(self.registry)

    def test_delivery_input_must_be_in_current_set(self):
        extra = self.put('hardware/printing/extra.3mf', b'extra')
        self.registry['delivery'] = self.put('hardware/cad/design-control/deliveries/d.json', {
            'cad': self.main,
            'release_manifest': self.registry['main']['release_manifest'],
            'release_manifest_sha256': self.registry['main']['release_manifest_sha256'],
            'files': [extra],
        })
        with self.assertRaisesRegex(ValueError, 'absent from current set'):
            dc.validate(self.registry)

if __name__=='__main__': unittest.main()
