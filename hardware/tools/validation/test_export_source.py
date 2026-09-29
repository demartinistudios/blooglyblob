"""Offline guards only; no test opens, saves or certifies live Fusion geometry."""
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter = load('cad_export', TOOLS / 'cad/export.py')
source = load('render_source', TOOLS / 'rendering/source.py')


class ExportRequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.request = dict(cloud_file_id='permanent-id', cloud_version=18,
                            part_ids=['FB01', 'FB41'], include_hidden=True,
                            output=str(Path(self.tmp.name) / 'new'))

    def test_valid_request_does_not_create_or_connect(self):
        output = exporter.validate_request(self.request)
        self.assertFalse(output.exists())

    def test_explicit_identity_selection_and_new_output_required(self):
        for key, value in [('cloud_file_id', ''), ('cloud_version', True),
                           ('cloud_version', 0), ('part_ids', []),
                           ('part_ids', ['FB01', 'FB01']), ('part_ids', [{}]),
                           ('include_hidden', None), ('output', self.tmp.name)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    exporter.validate_request(dict(self.request, **{key: value}))


class NativeRenderSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.native = dict(path='FB41:1', vertices_cm=[0, 0, 0],
                           triangles=[0, 0, 0], transform=[1, 0, 0, 0])
        (self.root / 'native.json').write_text(json.dumps([self.native]))
        registry = self.root / 'hardware/cad/design-control/registry.json'
        registry.parent.mkdir(parents=True)
        registry.write_text('{}')
        self.row = dict(self.native)
        self.row['faces'] = self.row.pop('triangles')
        self.lock = {'roles': {'mesh': 'mesh.gz', 'native_meshes': 'native.json'}}
        for target, value in [('ROOT', self.root), ('inside', lambda p: self.root / p),
                              ('selected', lambda: (self.lock, {}))]:
            patcher = patch.object(source, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def check(self):
        (self.root / 'mesh.gz').write_bytes(gzip.compress(json.dumps([self.row]).encode()))
        return source.checked_source()

    def test_matching_native_export_passes(self):
        self.assertEqual(self.check()[0], self.root / 'mesh.gz')

    def test_changed_placement_fails_even_with_same_vertices(self):
        self.row['transform'] = [1, 0, 0, 2]
        with self.assertRaisesRegex(ValueError, 'transform'):
            self.check()

    def test_changed_geometry_fails(self):
        self.row['vertices_cm'] = [1, 0, 0]
        with self.assertRaisesRegex(ValueError, 'vertices_cm'):
            self.check()


if __name__ == '__main__':
    unittest.main()
