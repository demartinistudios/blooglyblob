"""Small adversarial fixtures for the portable 3MF contract."""
import copy
import struct
import tempfile
import unittest
from pathlib import Path
import semantics as s


class SolidMeshTests(unittest.TestCase):
    def setUp(self):
        self.vertices = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)]
        self.faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]

    def test_closed_solid_and_exact_duplicate_coordinates_pass(self):
        s.check_closed_mesh((self.vertices, self.faces))
        vertices = [self.vertices[i] for f in self.faces for i in f]
        s.check_closed_mesh((vertices, [(i, i+1, i+2) for i in range(0, 12, 3)]))

    def test_serialized_near_zero_seam_is_not_welded_by_rounding(self):
        # Same failure mechanism as P08: float32 preserves a tiny near-zero
        # split that a rounded-coordinate edge audit mistakenly closes.
        vertices = self.vertices + [(1e-15, 0., 0.)]
        faces = [(4, 2, 1)] + self.faces[1:]
        raw = bytes(80) + struct.pack('<I', len(faces))
        for f in faces:
            raw += struct.pack('<12fH', 0, 0, 0, *(x for i in f for x in vertices[i]), 0)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'seam.stl'; p.write_bytes(raw)
            mesh = s.read_stl(p)
            before = p.read_bytes()
            with self.assertRaisesRegex(ValueError, '4 boundary'):
                s.check_closed_mesh(mesh)
            self.assertEqual(before, p.read_bytes())
            rounded = [tuple(round(x, 5) for x in v) for v in mesh[0]]
            s.check_closed_mesh((rounded, mesh[1]))

    def test_open_duplicate_reversed_and_degenerate_faces_fail(self):
        for faces, message in [
            (self.faces[:-1], 'boundary'),
            (self.faces + [self.faces[0]], 'nonmanifold'),
            ([self.faces[0][::-1]] + self.faces[1:], 'winding'),
            (self.faces + [(0, 0, 1)], 'Degenerate'),
            ([], 'Empty'),
        ]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                s.check_closed_mesh((self.vertices, faces))


class ContractTests(unittest.TestCase):
    def test_renumbering_and_repeated_labels_use_explicit_instance_map(self):
        a = {'objects': {'2': {'printable': True, 'plate': '1', 'label': 'same', 'parts': [], 'settings': {}, 'build': s.IDENTITY}}, 'settings': {}, 'plates': {'1': {}}}
        b = copy.deepcopy(a)
        b['objects']['900'] = b['objects'].pop('2')
        s.compare(a, b, {'stable': '2'}, {'stable': '900'})
        with self.assertRaisesRegex(ValueError, 'bijection'):
            s.compare(a, b, {'a': '2', 'b': '2'}, {'a': '900', 'b': '900'})

    def test_reindexed_faces_match_but_corrupt_triangle_fails(self):
        v = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]
        s.compare_mesh((v, [(0, 1, 2)]), ([v[2], v[0], v[1]], [(1, 2, 0)]))
        with self.assertRaises(ValueError):
            s.compare_mesh((v, [(0, 1, 2)]), (v, [(0, 2, 1)]))
        with self.assertRaises(ValueError):
            s.compare_mesh((v, [(0, 1, 2)]), (v, [(0, 1, 2), (0, 1, 2)]))

    def test_declared_frame_applies_rotation_and_translation(self):
        v = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]
        t = [0, 1, 0, -1, 0, 0, 0, 0, 1, 5, 6, 7]
        w = s.transform(v, t)
        s.compare_mesh((w, [(0, 1, 2)]), ([(5, 6, 7), (5, 7, 7), (4, 6, 7)], [(0, 1, 2)]))
        with self.assertRaises(ValueError):
            s.compare_mesh((v, [(0, 1, 2)]), (w, [(0, 1, 2)]))

    def test_quantity_and_plate_corruption_fail(self):
        catalog = {'parts': [{'part_id': 'P', 'quantity': 1}], 'optional_parts': []}
        manifest = {'objects': [{'recipe_instance_id': 'stable', 'part': 'P', 'plate_id': 'A'}], 'plates': [{'id': 'A', 'parts': {'P': 1}, 'piece_count': 1}]}
        s.check_manifest(manifest, catalog)
        bad = copy.deepcopy(manifest); bad['objects'] *= 2
        with self.assertRaises(ValueError): s.check_manifest(bad, catalog)
        bad = copy.deepcopy(manifest); bad['objects'][0]['plate_id'] = 'B'
        with self.assertRaises(ValueError): s.check_manifest(bad, catalog)

    def test_optional_is_replacement_not_added_demand(self):
        catalog = {'parts': [{'part_id': 'P', 'quantity': 1}], 'optional_parts': [{'part_id': 'ALT', 'quantity': 0, 'alternative_quantity': 1, 'replaces': 'P'}]}
        s.check_alternative({'part': 'ALT', 'replaces': 'P', 'quantity': 1}, catalog)
        with self.assertRaises(ValueError): s.check_alternative({'part': 'ALT', 'replaces': 'P', 'quantity': 2}, catalog)


class MeshCoordinateTests(unittest.TestCase):
    # First ambiguous AR02 coordinate in the accepted R23 recipe, compared with
    # its selected STL at the independently proposed proper rigid frame. These
    # two source vertices are distinct despite sharing the tolerance cube.
    def arm_patch(self):
        vertices = [
            (4.7261749821985894, -2.6349491030189567, 6.560579292090738),
            (4.726180584716082, -2.634953319813342, 6.560550681861246),
            (5., -2., 7.),
            (4., -3., 6.),
        ]
        candidate = vertices[:]
        candidate[0] = (4.72617531, -2.63494921, 6.5605793)
        candidate[1] = tuple(x + 1e-7 for x in vertices[1])
        return vertices, candidate, [(0, 2, 3), (1, 3, 2)]

    def test_arm_roundtrip_uses_unique_nearest_and_all_oriented_triangles(self):
        vertices, candidate, faces = self.arm_patch()
        # Reindex both arrays, cyclically rotate faces, and repeat an identical
        # candidate coordinate to exercise exact welding without losing counts.
        reordered = [candidate[3], candidate[1], candidate[0], candidate[2], candidate[0]]
        s.compare_mesh((vertices, faces), (reordered, [(0, 3, 1), (3, 0, 4)]))
        s.compare_mesh((reordered, [(0, 3, 1), (3, 0, 4)]), (vertices, faces))

    def test_nearest_does_not_hide_winding_or_topology_changes(self):
        vertices, candidate, faces = self.arm_patch()
        # The last case could match only by swapping the two close vertices;
        # searching for a farther correspondence must not mask the wrong faces.
        for wrong in ([(0, 3, 2), faces[1]], [faces[0], (0, 3, 2)],
                      [(1, 2, 3), (0, 3, 2)]):
            with self.subTest(faces=wrong), self.assertRaisesRegex(ValueError, 'topology/winding'):
                s.compare_mesh((vertices, faces), (candidate, wrong))

    def test_duplicate_triangle_multiplicity_is_preserved(self):
        vertices, candidate, faces = self.arm_patch()
        s.compare_mesh((vertices, faces + [faces[0]]), (candidate, [faces[0]] + faces))
        with self.assertRaisesRegex(ValueError, 'topology/winding'):
            s.compare_mesh((vertices, faces + [faces[0]]), (candidate, faces + [faces[1]]))

    def test_equidistant_and_numerically_tied_candidates_fail_closed(self):
        vertices = [(-2e-5, 0., 0.), (2e-5, 0., 0.), (0., 1., 0.), (0., 0., 1.)]
        faces = [(0, 2, 3), (1, 3, 2)]
        for displacement in (0., 1e-18):
            candidate = vertices[:]
            candidate[0] = (displacement, 0., 0.)
            with self.subTest(displacement=displacement), self.assertRaisesRegex(ValueError, 'ambiguous'):
                s.compare_mesh((vertices, faces), (candidate, faces))

    def test_nearest_match_still_requires_coordinate_tolerance(self):
        vertices, candidate, faces = self.arm_patch()
        candidate[2] = (5., -2., 7. + 2*s.TOLERANCE_MM)
        with self.assertRaisesRegex(ValueError, 'coordinates differ'):
            s.compare_mesh((vertices, faces), (candidate, faces))

    def test_tolerance_remains_per_coordinate_not_euclidean_radius(self):
        vertices = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)]
        candidate = [tuple(x + 0.9*s.TOLERANCE_MM for x in v) for v in vertices]
        s.compare_mesh((vertices, [(0, 1, 2)]), (candidate, [(0, 1, 2)]))

    def test_close_vertices_cannot_be_collapsed(self):
        vertices, candidate, faces = self.arm_patch()
        candidate[1] = candidate[0]
        with self.assertRaisesRegex(ValueError, 'topology/winding'):
            s.compare_mesh((vertices, faces), (candidate, faces))

    def test_mesh_comparison_does_not_infer_scale_reflection_or_placement(self):
        vertices = [(1., 0., 0.), (0., 2., 0.), (0., 0., 3.)]
        faces = [(0, 1, 2)]
        for frame in ([2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0],
                      [-1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                      s.IDENTITY[:9] + [1, 2, 3]):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                s.compare_mesh((vertices, faces), (s.transform(vertices, frame), faces))


class ArchiveTests(unittest.TestCase):
    def write_project(self, path, *, duplicate_part=False, duplicate_zip=False, transform=None, printable="1"):
        import zipfile
        component = '<component objectid="1" p:path="/3D/Objects/mesh.model"/>'
        model = f'<model xmlns="{s.N[1:-1]}" xmlns:p="{s.P[1:-1]}" unit="millimeter"><resources><object id="2"><components>{component}</components></object></resources><build><item objectid="2" printable="{printable}" transform="{transform or "1 0 0 0 1 0 0 0 1 0 0 0"}"/></build></model>'
        mesh = f'<model xmlns="{s.N[1:-1]}"><resources><object id="1"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object></resources></model>'
        part = '<part id="1" subtype="normal_part"><metadata key="name" value="same"/></part>'
        config = '<config><object id="2"><metadata key="name" value="same"/>'+part*(2 if duplicate_part else 1)+'</object><plate><metadata key="plater_id" value="1"/><model_instance><metadata key="object_id" value="2"/><metadata key="instance_id" value="0"/></model_instance></plate></config>'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('3D/3dmodel.model', model); z.writestr('3D/Objects/mesh.model', mesh)
            z.writestr('Metadata/model_settings.config', config); z.writestr('Metadata/project_settings.config', '{}')
            if duplicate_zip:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore'); z.writestr('Metadata/project_settings.config', '{}')

    def test_duplicate_archive_members_and_components_fail(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'a.3mf'
            self.write_project(p); self.assertEqual(len(s.load(p)['objects']), 1)
            self.write_project(p, duplicate_part=True)
            with self.assertRaisesRegex(ValueError, 'duplicate part'): s.load(p)
            self.write_project(p, duplicate_zip=True)
            with self.assertRaisesRegex(ValueError, 'duplicate ZIP'): s.load(p)

    def test_build_orientation_and_modifier_drift_fail(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'a.3mf'; q = Path(td)/'b.3mf'
            self.write_project(p); self.write_project(q, transform='0 1 0 -1 0 0 0 0 1 0 0 0')
            a, b = s.load(p), s.load(q)
            with self.assertRaises(ValueError): s.compare(a, b, {'stable': '2'}, {'stable': '2'})
            b = copy.deepcopy(a); b['objects']['2']['parts'][0]['type'] = 'support_blocker'
            with self.assertRaisesRegex(ValueError, 'modifier'): s.compare(a, b, {'stable': '2'}, {'stable': '2'})
            b = copy.deepcopy(a); b['settings']['support_enable'] = True
            with self.assertRaisesRegex(ValueError, 'Global settings'): s.compare(a, b, {'stable': '2'}, {'stable': '2'})

    def test_disabled_print_instance_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td)/'a.3mf'; b = Path(td)/'b.3mf'
            self.write_project(a); self.write_project(b, printable='0')
            loaded_a, loaded_b = s.load(a), s.load(b)
            with self.assertRaisesRegex(ValueError, 'printability'):
                s.compare(loaded_a, loaded_b, {'stable': '2'}, {'stable': '2'})
            self.assertNotEqual(s.object_contract(loaded_a['objects']['2']),
                                s.object_contract(loaded_b['objects']['2']))

    def test_plate_renumbering_and_duplicate_labels(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'a.3mf'; self.write_project(p); a = s.load(p)
            a['objects']['4'] = copy.deepcopy(a['objects']['2']); a['objects']['4']['plate'] = '2'; a['plates']['2'] = {}
            b = copy.deepcopy(a); b['plates'] = {'9': {}, '10': {}}
            b['objects']['2']['plate'] = '9'; b['objects']['4']['plate'] = '10'
            s.compare(a, b, {'first': '2', 'second': '4'}, {'first': '2', 'second': '4'}, {'A': '1', 'B': '2'}, {'A': '9', 'B': '10'})
            with self.assertRaises(ValueError):
                s.compare(a, b, {'first': '2', 'second': '4'}, {'first': '4', 'second': '2'}, {'A': '1', 'B': '2'}, {'A': '9', 'B': '10'})

class ReceiptTests(unittest.TestCase):
    def test_input_bound_estimates_and_selected_stl_reject_staleness(self):
        import hashlib
        import struct
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); stl = root/'part.stl'
            vertices = [(0.,0.,0.), (1.,0.,0.), (0.,1.,0.), (0.,0.,1.)]
            faces = [(0,2,1), (0,1,3), (0,3,2), (1,2,3)]
            raw = bytes(80) + struct.pack('<I', len(faces))
            for face in faces:
                raw += struct.pack('<12fH', 0,0,0, *(x for i in face for x in vertices[i]), 0)
            stl.write_bytes(raw)
            digest = hashlib.sha256(stl.read_bytes()).hexdigest()
            obj = {'printable': True, 'plate': '1', 'build': s.IDENTITY, 'settings': {'extruder': '1'}, 'parts': [{'type': 'normal_part', 'settings': {}, 'vertices': vertices, 'faces': faces, 'transform': s.IDENTITY}]}
            loaded = {'objects': {'2': obj}, 'settings': {}, 'plates': {'1': {}}}
            catalog = {'parts': [{'part_id': 'P', 'quantity': 1, 'geometry_path': 'part.stl', 'geometry_sha256': digest}], 'optional_parts': []}
            manifest = {'master_project': 'project.3mf', 'objects': [{'part': 'P', 'object_id': '2', 'plate_id': 'A', 'plate': 1, 'settings': {}, 'filament_index': 1}], 'plates': [{'id': 'A', 'parts': {'P': 1}, 'piece_count': 1, 'estimated_seconds': 60, 'estimated_grams': 1.2}]}
            contract = {'projects': [{'path': 'hardware/printing/current/project.3mf', 'project_sha256': 'accepted', 'role': 'required', 'global_settings_sha256': s.signature({}), 'plate_settings_sha256': s.signature({'1': {}}), 'instances': [{'recipe_instance_id': 'stable', 'object_id': '2', 'part': 'P', 'plate_number': 1, 'plate_id': 'A', 'source_sha256': digest, 'source_status': 'verified_triangle_geometry', 'stl_to_mesh': s.IDENTITY, 'invariants': s.object_contract(obj)}]}], 'review_evidence': {'files': [], 'estimates_sha256': s.signature([{'id': 'A', 'estimated_seconds': 60, 'estimated_grams': 1.2}])}}
            lock = {'projects': [{'path': 'hardware/printing/current/project.3mf', 'sha256': 'accepted'}]}
            contract['review_evidence']['inputs'] = s.reviewed_inputs(contract)
            with patch.object(s, 'load', return_value=loaded):
                self.assertEqual(s.validate_current(root, lock, manifest, catalog, contract), [])
                seam = bytearray(raw)
                struct.pack_into('<f', seam, 96, 1e-15)
                stl.write_bytes(seam)
                seam_digest = hashlib.sha256(seam).hexdigest()
                catalog['parts'][0]['geometry_sha256'] = seam_digest
                contract['projects'][0]['instances'][0]['source_sha256'] = seam_digest
                with self.assertRaisesRegex(ValueError, 'P: Exact mesh edges: 4 boundary'):
                    s.validate_current(root, lock, manifest, catalog, contract)
                stl.write_bytes(raw)
                catalog['parts'][0]['geometry_sha256'] = digest
                contract['projects'][0]['instances'][0]['source_sha256'] = digest
                bad = copy.deepcopy(manifest); bad['master_project'] = 'unchecked.3mf'
                with self.assertRaisesRegex(ValueError, 'unchecked project'):
                    s.validate_current(root, lock, bad, catalog, contract)
                contract['review_evidence']['inputs'][contract['projects'][0]['path']]['project_sha256'] = 'old-process'
                self.assertTrue(s.validate_current(root, lock, manifest, catalog, contract))
                contract['review_evidence']['inputs'] = s.reviewed_inputs(contract)
                manifest['plates'][0]['estimated_seconds'] = 61
                with self.assertRaisesRegex(ValueError, 'Estimates changed'): s.validate_current(root, lock, manifest, catalog, contract)
                manifest['plates'][0]['estimated_seconds'] = 60
                stl.write_bytes(stl.read_bytes()+b'corrupt')
                with self.assertRaisesRegex(ValueError, 'STL hash mismatch'): s.validate_current(root, lock, manifest, catalog, contract)


class ManualSourceReviewTests(unittest.TestCase):
    def test_only_complete_hash_bound_equivalence_evidence_is_accepted(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); directory = root/'hardware/printing/recipes/reviews'
            directory.mkdir(parents=True)
            evidence = directory/'frame-notes.md'; evidence.write_text('Source and recipe frames compared; test fixture only.')
            receipt = directory/'source-review.json'
            row = {'recipe_instance_id': 'stable', 'source_sha256': 'source-hash'}
            project = {'project_sha256': 'project-hash'}
            review = {'schema_version': 1, 'reviewer': 'Fixture reviewer',
                      'method': 'Independent surface comparison in declared frames',
                      'result': 'equivalent', 'project_sha256': 'project-hash',
                      'source_sha256': 'source-hash', 'recipe_instance_id': 'stable',
                      'frame_evidence': {'description': 'Source bed frame to raw component frame; see notes.',
                                         'artifacts': [{'path': str(evidence.relative_to(root)), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}]},
                      'limitations': ['Geometry equivalence only; no support or physical-fit qualification.']}
            def bind(value):
                receipt.write_text(json.dumps(value))
                row['source_review'] = {'path': str(receipt.relative_to(root)), 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}
            bind(review)
            s.validate_source_review(root, project, row)
            for key, value in [('project_sha256', 'stale'), ('source_sha256', 'stale'),
                               ('recipe_instance_id', 'another'), ('result', 'failed'),
                               ('reviewer', ''), ('method', ''), ('frame_evidence', {}), ('limitations', [])]:
                bad = copy.deepcopy(review); bad[key] = value; bind(bad)
                with self.subTest(key=key), self.assertRaises(ValueError): s.validate_source_review(root, project, row)
            bind(review); receipt.write_text(receipt.read_text()+' ')
            with self.assertRaisesRegex(ValueError, 'hash'): s.validate_source_review(root, project, row)
            bind(review); evidence.write_text('Changed after review')
            with self.assertRaisesRegex(ValueError, 'hash'): s.validate_source_review(root, project, row)
            receipt.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'): s.validate_source_review(root, project, row)
            bind(review); row['source_review']['path'] = str(receipt)
            with self.assertRaisesRegex(ValueError, 'relative'): s.validate_source_review(root, project, row)
            outside = root/'outside.json'; outside.write_text(receipt.read_text())
            receipt.unlink(); receipt.symlink_to(outside)
            row['source_review']['path'] = str(receipt.relative_to(root))
            with self.assertRaisesRegex(ValueError, 'recipes/reviews'): s.validate_source_review(root, project, row)


if __name__ == '__main__': unittest.main()
