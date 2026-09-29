"""Check failure behavior using disposable records, never real CAD files."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('design_control', Path(__file__).parents[1] / 'design_control.py')
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.root = root
        for name, value in {'ROOT': root, 'CAD': root, 'CONTROL': root,
                            'REGISTRY': root / 'registry.json', 'LOCK': root / 'lock.json'}.items():
            p = patch.object(dc, name, value)
            p.start()
            self.addCleanup(p.stop)
        (root / 'assembly.f3d').write_bytes(b'preserved test artifact')
        native = {'path': 'assembly.f3d', 'sha256': dc.digest(root / 'assembly.f3d')}
        self.release = {'design_revision': 'R6', 'cloud_file_id': 'main-id', 'cloud_version': 1,
                        'summary': 'test release', 'artifacts': [native]}
        (root / 'R6.json').write_text(json.dumps(self.release))
        (root / 'current-inputs.json').write_text(json.dumps({'files': [native]}))
        self.registry = {'schema_version': 3, 'main': {'design_revision': 'R6',
                         'cloud_file_id': 'main-id', 'cloud_version': 1, 'cloud_name': 'MAIN',
                         'project': 'Test', 'release_manifest': 'R6.json',
                         'release_manifest_sha256': dc.digest(root / 'R6.json')},
                         'accepted_native': dict(native, original_path='assembly.f3d'),
                         'current_inputs': {'path': 'current-inputs.json',
                             'sha256': dc.digest(root / 'current-inputs.json')}}
        dc.REGISTRY.write_text(json.dumps(self.registry))

    def command(self, *args):
        with patch.object(sys, 'argv', ['design_control.py', *args]):
            dc.main()

    def test_artifact_tampering_is_detected(self):
        dc.validate(self.registry)
        (self.root / 'assembly.f3d').write_bytes(b'overwritten')
        with self.assertRaisesRegex(ValueError, 'Missing or changed'):
            dc.validate(self.registry)

    def test_manifest_tampering_is_detected(self):
        (self.root / 'R6.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Missing or changed artifact: R6.json'):
            dc.validate(self.registry)

    def test_cloud_baseline_mismatch_is_detected(self):
        self.registry['main']['cloud_version'] = 2
        with self.assertRaisesRegex(ValueError, 'disagree'):
            dc.validate(self.registry)

    def test_current_input_lock_tampering_is_detected(self):
        (self.root / 'current-inputs.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Missing or changed artifact: current-inputs.json'):
            dc.validate(self.registry)

    def test_promotion_lock_records_exact_baseline(self):
        self.command('lock', '--owner', 'first')
        lock = dc.read(dc.LOCK)
        self.assertEqual(lock['baseline'], self.registry['main'])
        self.assertEqual(lock['registry_sha256'], dc.digest(dc.REGISTRY))

    def test_owner_can_unlock_after_interrupted_publication(self):
        self.command('lock', '--owner', 'first')
        (self.root / 'publication-in-progress.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Incomplete publication'):
            self.command('check')
        self.command('unlock', '--owner', 'first')
        self.assertFalse(dc.LOCK.exists())

    def test_conflicting_owner_cannot_take_or_release_lock(self):
        self.command('lock', '--owner', 'first')
        before = dc.LOCK.read_bytes()
        with self.assertRaises(FileExistsError):
            self.command('lock', '--owner', 'second')
        with self.assertRaisesRegex(ValueError, 'recorded promotion owner'):
            self.command('unlock', '--owner', 'second')
        self.assertEqual(before, dc.LOCK.read_bytes())
        self.command('unlock', '--owner', 'first')
        self.assertFalse(dc.LOCK.exists())

    def test_stale_current_page_is_detected(self):
        self.command('render')
        self.command('check')
        (self.root / 'CURRENT-DESIGN.md').write_text('outdated')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.command('check')


if __name__ == '__main__':
    unittest.main()
