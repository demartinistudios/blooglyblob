"""Candidate replacement checks use synthetic projects; accepted assets are never written."""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

import semantics as s
import replace_meshes as r


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'baseline.3mf'
        self.source = self.root / 'part.stl'
        self.review = self.root / 'review.json'
        self.output = self.root / 'candidate'
        # Duplicate oriented triangles must survive, as must precision after a rotation.
        triangle = struct.pack('<12fH', 0, 0, 1, 12345.125, .25, 0, 12346.125, .25, 0, 12345.125, 1.25, 0, 0)
        self.source.write_bytes(bytes(80) + struct.pack('<I', 2) + triangle * 2)
        mesh = '<mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh>'
        self.untouched = '<object id="9" type="model">\n<!-- unrelated bytes -->' + mesh + '</object>'
        self.members = {
            '3D/3dmodel.model': f'<model xmlns="{s.N[1:-1]}" xmlns:p="{s.P[1:-1]}"><resources><object id="2"><components><component objectid="1" p:path="/3D/Objects/mesh.model" transform="1 0 0 0 1 0 0 0 1 3 4 5"/><component objectid="5" p:path="/3D/Objects/mesh.model"/></components></object><object id="4"><components><component objectid="3" p:path="/3D/Objects/mesh.model"/></components></object></resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 10 20 0"/><item objectid="4"/></build></model>',
            '3D/Objects/mesh.model': f'<model xmlns="{s.N[1:-1]}"><resources><object id="1" type="model">{mesh}</object><object id="3">{mesh}</object><object id="5">{mesh}</object>{self.untouched}</resources></model>',
            'Metadata/model_settings.config': '<config><!-- keep formatting --><object id="2"><metadata key="name" value="same"/><metadata face_count="1"/><part id="1" subtype="normal_part"><metadata key="extruder" value="1"/><mesh_stat face_count="1" edges_fixed="0"/></part><part id="5" subtype="support_blocker"><mesh_stat face_count="1"/></part></object><object id="4"><metadata key="name" value="same"/><metadata face_count="1"/><part id="3" subtype="normal_part"><mesh_stat face_count="1"/></part></object><plate><metadata key="plater_id" value="1"/><metadata key="thumbnail_file" value="Metadata/plate_1.png"/><model_instance><metadata key="object_id" value="2"/><metadata key="instance_id" value="0"/></model_instance></plate><plate><metadata key="plater_id" value="2"/><model_instance><metadata key="object_id" value="4"/><metadata key="instance_id" value="0"/></model_instance></plate></config>',
            'Metadata/project_settings.config': '{"layer_height":"0.16"}',
            'Metadata/plate_1.png': 'stale', 'Metadata/plate_1_small.png': 'stale small', 'Metadata/plate_2.png': 'keep',
            'Metadata/other.png': 'keep', 'Metadata/slice_info.config': '<config/>',
        }
        self.write_project()
        self.record = {'schema_version': 1, 'reviewer': 'Fixture independent reviewer',
                       'method': 'Fixture frame review, separate from replacement verification',
                       'project_sha256': digest(self.project),
                       'instance_map': {'stable-a': '2', 'stable-b': '4'},
                       'replacements': [{'recipe_instance_id': 'stable-a',
                                         'source': {'path': 'part.stl', 'sha256': digest(self.source)},
                                         'stl_to_mesh': [.6, .8, 0, -.8, .6, 0, 0, 0, 1, .123456789012345, 2, 3]}]}
        self.bind()

    def write_project(self, duplicate=False):
        with zipfile.ZipFile(self.project, 'w') as archive:
            archive.comment = b'preserve archive comment'
            for name, data in self.members.items():
                archive.writestr(name, data)
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    archive.writestr('Metadata/other.png', 'duplicate')

    def bind(self):
        self.review.write_text(json.dumps(self.record))
        self.review_hash = digest(self.review)

    def run_helper(self):
        return r.replace_meshes(self.project, self.review, self.review_hash, self.output)

    def assert_rejected(self, pattern):
        before = (self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes())
        with self.assertRaisesRegex(ValueError, pattern):
            self.run_helper()
        self.assertFalse(self.output.exists())
        self.assertEqual(before, (self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()))

    def test_candidate_preserves_other_bytes_settings_modifiers_and_precision(self):
        original = self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()
        receipt = self.run_helper()
        candidate = self.output / 'candidate.3mf'
        self.assertEqual(original, (self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()))
        before, after = s.load(self.project), s.load(candidate)
        self.assertEqual(before['objects']['4'], after['objects']['4'])
        self.assertEqual(before['objects']['2']['parts'][1], after['objects']['2']['parts'][1])
        expected, faces = s.read_stl(self.source)
        expected = s.transform(expected, self.record['replacements'][0]['stl_to_mesh'])
        self.assertEqual(expected, after['objects']['2']['parts'][0]['vertices'])
        self.assertEqual(faces, after['objects']['2']['parts'][0]['faces'])
        with zipfile.ZipFile(candidate) as archive:
            self.assertEqual(archive.comment, b'preserve archive comment')
            self.assertIn(self.untouched.encode(), archive.read('3D/Objects/mesh.model'))
            for name in self.members.keys() - {'3D/Objects/mesh.model', 'Metadata/model_settings.config', 'Metadata/plate_1.png', 'Metadata/plate_1_small.png', 'Metadata/slice_info.config'}:
                self.assertEqual(self.members[name].encode(), archive.read(name))
            self.assertNotIn('Metadata/plate_1.png', archive.namelist())
            self.assertNotIn('Metadata/slice_info.config', archive.namelist())
            config = archive.read('Metadata/model_settings.config').decode()
            self.assertEqual(config, self.members['Metadata/model_settings.config'].replace('face_count="1"', 'face_count="2"', 2))
        self.assertEqual(receipt, json.loads((self.output / 'receipt.json').read_text()))
        self.assertEqual(set(receipt['removed_members']), {'Metadata/plate_1.png', 'Metadata/plate_1_small.png', 'Metadata/slice_info.config'})
        self.assertEqual(receipt['candidate_sha256'], digest(candidate))
        self.output = self.root / 'repeat'
        self.run_helper()
        self.assertEqual(after, s.load(self.output / 'candidate.3mf'))

    def test_repeated_instances_use_distinct_reviewed_frames(self):
        second = copy.deepcopy(self.record['replacements'][0])
        second['recipe_instance_id'] = 'stable-b'
        second['stl_to_mesh'] = s.IDENTITY[:9] + [100, 200, 300]
        self.record['replacements'].append(second)
        self.bind()
        self.run_helper()
        candidate = s.load(self.output / 'candidate.3mf')
        vertices, faces = s.read_stl(self.source)
        for row in self.record['replacements']:
            actual = candidate['objects'][self.record['instance_map'][row['recipe_instance_id']]]['parts'][0]
            s.compare_mesh((s.transform(vertices, row['stl_to_mesh']), faces), (actual['vertices'], actual['faces']))

    def test_stale_project_source_review_and_edited_frame_are_rejected(self):
        for kind in ('project', 'source', 'review', 'frame'):
            with self.subTest(kind=kind):
                project, source, review = self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()
                if kind == 'project': self.project.write_bytes(project + b'changed')
                elif kind == 'source': self.source.write_bytes(source + b'changed')
                elif kind == 'review': self.review.write_bytes(review + b' ')
                else:
                    changed = copy.deepcopy(self.record); changed['replacements'][0]['stl_to_mesh'][9] += 1
                    self.review.write_text(json.dumps(changed))
                self.assert_rejected('hash')
                self.project.write_bytes(project); self.source.write_bytes(source); self.review.write_bytes(review)

    def test_reflection_scale_and_nonfinite_frames_are_rejected(self):
        for value in (-1, 2, float('nan')):
            self.record['replacements'][0]['stl_to_mesh'] = s.IDENTITY[:]
            self.record['replacements'][0]['stl_to_mesh'][0] = value
            self.bind()
            self.assert_rejected('frame|transform')

    def test_duplicate_or_incomplete_mapping_and_duplicate_replacements_fail(self):
        original = copy.deepcopy(self.record)
        for mapping in ({'a': '2', 'b': '2'}, {'a': '2'}, {'a': '2', 'b': '4', 'c': '8'}):
            self.record['instance_map'] = mapping; self.bind()
            self.assert_rejected('map')
        self.record = original
        self.record['replacements'] *= 2; self.bind()
        self.assert_rejected('duplicate')

    def test_duplicate_json_keys_and_zip_members_fail(self):
        self.review.write_text(self.review.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        self.review_hash = digest(self.review)
        self.assert_rejected('duplicate')
        self.bind(); self.write_project(duplicate=True)
        self.record['project_sha256'] = digest(self.project); self.bind()
        self.assert_rejected('duplicate|Duplicate')

    def test_target_annotations_and_unknown_mesh_structure_fail_closed(self):
        original = self.members['3D/Objects/mesh.model']
        for old, new in [('<mesh>', '<mesh custom="paint">'),
                         ('<vertex x=', '<vertex custom="paint" x='),
                         ('<triangle v1=', '<triangle paint_color="1" v1='),
                         ('</mesh>', '<extension/></mesh>'),
                         ('<object id="1" type="model">', '<object id="1" type="model" pid="3">')]:
            with self.subTest(change=new):
                self.members['3D/Objects/mesh.model'] = original.replace(old, new, 1)
                self.write_project(); self.record['project_sha256'] = digest(self.project); self.bind()
                self.assert_rejected('Unsupported|annotation')

    def test_shared_mesh_and_presliced_project_fail(self):
        self.members['3D/3dmodel.model'] = self.members['3D/3dmodel.model'].replace('objectid="3" p:path=', 'objectid="1" p:path=')
        self.members['Metadata/model_settings.config'] = self.members['Metadata/model_settings.config'].replace('part id="3"', 'part id="1"')
        self.write_project(); self.record['project_sha256'] = digest(self.project); self.bind()
        self.assert_rejected('shared|Shared')
        self.members['Metadata/plate_1.gcode'] = 'G1 X0'
        self.write_project(); self.record['project_sha256'] = digest(self.project); self.bind()
        self.assert_rejected('sliced|gcode')

    def test_corruption_of_a_blocker_during_writing_is_detected(self):
        write_member = zipfile.ZipFile.writestr

        def corrupt(archive, info, data, *args, **kwargs):
            if info.filename == '3D/Objects/mesh.model':
                old = b'<object id="5"><mesh><vertices><vertex x="0"'
                self.assertIn(old, data)
                data = data.replace(old, b'<object id="5"><mesh><vertices><vertex x="42"')
            return write_member(archive, info, data, *args, **kwargs)

        with patch.object(zipfile.ZipFile, 'writestr', corrupt):
            self.assert_rejected('modifier')

    def test_nonzero_repair_counters_and_counter_annotations_are_rejected(self):
        original = self.members['Metadata/model_settings.config']
        for change in ('edges_fixed="1"/>', 'unknown_counter="0"/>', 'edges_fixed="0"><annotation/></mesh_stat>'):
            with self.subTest(change=change):
                self.members['Metadata/model_settings.config'] = original.replace('edges_fixed="0"/>', change, 1)
                self.write_project(); self.record['project_sha256'] = digest(self.project); self.bind()
                self.assert_rejected('repair counters|annotations')

    def test_existing_output_is_never_touched(self):
        self.output.mkdir(); marker = self.output / 'mine'; marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'exist'):
            self.run_helper()
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(list(self.output.iterdir()), [marker])

    def test_failed_output_write_cleans_up_and_allows_retry(self):
        before = self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()
        original_open = Path.open
        for filename in ('candidate.3mf', 'receipt.json'):
            with self.subTest(filename=filename):
                @contextmanager
                def failing_open(path, *args, **kwargs):
                    with original_open(path, *args, **kwargs) as stream:
                        if path == self.output / filename:
                            def fail_write(data):
                                stream.write(data[:10])
                                raise OSError('injected output failure')
                            yield SimpleNamespace(write=fail_write)
                        else:
                            yield stream
                with patch.object(Path, 'open', failing_open):
                    with self.assertRaisesRegex(OSError, 'injected output failure'):
                        self.run_helper()
                self.assertFalse(self.output.exists())
                self.assertEqual(before, (self.project.read_bytes(), self.source.read_bytes(), self.review.read_bytes()))
        self.run_helper()
        self.assertTrue((self.output / 'candidate.3mf').is_file())
        self.assertTrue((self.output / 'receipt.json').is_file())


if __name__ == '__main__':
    unittest.main()
