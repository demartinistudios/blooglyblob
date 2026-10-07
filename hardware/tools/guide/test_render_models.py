"""The unchanged stand may be reused without relabeling its original CAD export."""
import copy
import gzip
import importlib.util
import json
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('render_models', ROOT / 'hardware/tools/guide/render_models.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StandReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = json.loads((ROOT / 'hardware/rendering/r23-service-stand-provenance.json').read_text())
        cls.registry = json.loads((ROOT / 'hardware/cad/design-control/registry.json').read_text())
        cls.accepted = {r['path']: r for r in json.loads((ROOT / 'hardware/cad/current/release-assembly.json').read_text())['occurrences']}
        with gzip.open(ROOT / cls.provenance['mesh']['path'], 'rt') as stream:
            cls.rows = json.load(stream)

    def verify(self, accepted=None, provenance=None, rows=None, registry=None):
        module.verify_stand_reuse(provenance or self.provenance, registry or self.registry, accepted or self.accepted, rows or self.rows)

    def test_retains_original_export_identity(self):
        original = copy.deepcopy(self.provenance)
        self.verify()
        self.assertEqual(self.provenance, original)

    def test_rejects_changed_fixture_geometry_or_frame(self):
        key = self.rows[0]['path']
        for field in ('transform', 'volume', 'bounds'):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.accepted)
                if field == 'transform':
                    changed[key]['transform'][3] += 0.1
                elif field == 'volume':
                    changed[key]['bodies'][0]['volume'] += 0.1
                else:
                    changed[key]['bodies'][0]['bounds'][0][0] += 0.1
                with self.assertRaises(ValueError):
                    self.verify(accepted=changed)

    def test_rejects_missing_fixture(self):
        with self.assertRaises(ValueError):
            self.verify(rows=self.rows[:-1])

    def test_rejects_unrelated_lineage(self):
        changed = copy.deepcopy(self.registry)
        changed['main']['cloud_file_id'] = 'different-main'
        with self.assertRaises(ValueError):
            self.verify(registry=changed)

    def test_rejects_unbound_original_native(self):
        changed = copy.deepcopy(self.provenance)
        changed['native_source']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.verify(provenance=changed)


class ReferenceIdentityTests(unittest.TestCase):
    def test_missing_or_misidentified_reference_fails_before_render(self):
        rows = [{'root': 'FBREF Fuse F2:1', 'id': 'E07'},
                {'root': 'FBREF Capacitor C1:1', 'id': 'E08'},
                {'root': 'FBREF Capacitor C2:1', 'id': 'E08'}]
        module.verify_reference_identities(rows)
        for index in range(len(rows)):
            with self.subTest(missing=rows[index]['root']):
                with self.assertRaises(ValueError):
                    module.verify_reference_identities(rows[:index] + rows[index + 1:])
        wrong = copy.deepcopy(rows)
        wrong[0]['id'] = 'E08'
        with self.assertRaises(ValueError):
            module.verify_reference_identities(wrong)
        with self.assertRaises(ValueError):
            module.verify_reference_identities(rows + [{'root': 'FBREF Fuse F1:1', 'id': 'E07'}])


class BoardMountSceneTests(unittest.TestCase):
    def test_feet_do_not_imply_old_stock_size_or_cover_installation(self):
        library=json.loads((ROOT/'hardware/rendering/scenes/views.json').read_text())
        for version in ('r16','r17','r21'):
            view=library[f'{version}/base-feet']['view']
            self.assertEqual(view['select'],['FB01'])
            self.assertEqual(len(view['feature_labels']),4)
            self.assertEqual({m['point'][2] for m in view['feature_labels']},{-69})


class CloseupReadabilityTests(unittest.TestCase):
    def test_closeups_keep_phone_labels_at_readable_size(self):
        directory = ROOT / 'hardware/build-guide/src/assets/community'
        names = [
            'eye-film-insertion', 'eye-foam-insertion', 'eye-housing-nuts',
            'eye-board-nuts', 'eye-board-fastening', 'eye-cassette-fastening',
            'eye-installed-inside', 'horn-drill-pair', 'horn-side-orientation',
        ]
        for name in names:
            with self.subTest(name=name):
                svg = ET.parse(directory / (name + '.svg')).getroot()
                self.assertEqual(float(svg.attrib['viewBox'].split()[2]), 420)
                labels = list(svg.iter('{http://www.w3.org/2000/svg}text'))
                self.assertTrue(all(float(t.attrib['font-size']) >= 22 for t in labels))
                # No drawn title: the guide caption gives the view; text only labels the picture.
                self.assertEqual(float(svg.attrib['viewBox'].split()[1]), 50)
                self.assertTrue(all(float(t.attrib['y']) > 60 for t in labels))

    def test_compact_audio_labels_preserve_phone_readability(self):
        directory = ROOT / 'hardware/build-guide/src/assets/community'
        for name in ['audio-cradle-lid-nuts', 'audio-cradle-base-mount',
                     'audio-module-seating', 'audio-tape-back', 'audio-tape-contact',
                     'audio-module-connections', 'audio-lid-fastening',
                     'frame-uprights-fastening', 'shoulder-servo-insertion',
                     'shoulder-servo-fastening', 'shoulder-carrier-front',
                     'shoulder-carrier-rear', 'head-servo-fastening',
                     'upper-collar-fastening']:
            with self.subTest(name=name):
                svg = ET.parse(directory / (name + '.svg')).getroot()
                _, _, width, height = map(float, svg.attrib['viewBox'].split())
                self.assertEqual((width, height), (600, 420))
                labels = list(svg.iter('{http://www.w3.org/2000/svg}text'))
                self.assertTrue(labels)
                # Preserve the older 22/420 label-to-image ratio on phones.
                self.assertTrue(all(float(t.attrib['font-size']) / width >= 22 / 420 for t in labels))



if __name__ == '__main__':
    unittest.main()


class NutPocketOrientationTests(unittest.TestCase):
    def test_nut_flats_fit_accepted_hex_pockets(self):
        # Test all six nut corners against the accepted pocket's six walls.
        for axis, dimensions in [([0,0,1], (0,1)), ([0,1,0], (0,2))]:
            matrix = module.nut_axis_transform(axis)
            self.assertEqual([row[2] for row in matrix[:3]], axis)
            for af, pocket_af in [(4.0,4.3),(5.5,5.8)]:
                for i in range(6):
                    angle = math.pi/6+i*math.pi/3
                    radius = af/math.sqrt(3)
                    local = [radius*math.cos(angle),radius*math.sin(angle),0]
                    world = [sum(row[j]*local[j] for j in range(3)) for row in matrix[:3]]
                    x,y = (world[j] for j in dimensions)
                    for wall in range(6):
                        normal = wall*math.pi/3
                        self.assertLessEqual(x*math.cos(normal)+y*math.sin(normal),pocket_af/2-0.149)

    def test_unreviewed_axis_is_rejected(self):
        with self.assertRaises(ValueError):
            module.nut_axis_transform([1,0,0])


class InletActionViewTests(unittest.TestCase):
    def test_compact_inlet_views_have_readable_labels_and_motion_arrows(self):
        for name in ('inlet-jack-mounting', 'inlet-plate-nuts', 'inlet-plate-fastening',
                     'pi-board-fastening', 'shifter-board-fastening'):
            with self.subTest(name=name):
                svg=ET.parse(ROOT/'hardware/build-guide/src/assets/community'/f'{name}.svg').getroot()
                self.assertEqual(svg.attrib['viewBox'], '0 0 600 420')
                labels=list(svg.iter('{http://www.w3.org/2000/svg}text'))
                self.assertGreaterEqual(len(labels), 2)
                self.assertTrue(all(float(label.attrib['font-size']) >= 24 for label in labels))
                arrows=[p for p in svg.iter('{http://www.w3.org/2000/svg}path') if 'marker-end' in p.attrib]
                self.assertGreaterEqual(len(arrows), 2)

    def test_fastening_axes_match_accepted_inlet_plate_bores(self):
        source=module.checked_source()[0]
        with gzip.open(source, 'rt') as stream:
            plate=next(row for row in json.load(stream) if row['path']=='FB21 Inlet plate reused:1')
        matrix=plate['transform'];vertices=plate['vertices_cm']
        points=[[10*(sum(matrix[4*axis+j]*vertices[i+j] for j in range(3))+matrix[4*axis+3]) for axis in range(3)] for i in range(0,len(vertices),3)]
        # This catches a moved hole or changed seating face before the fixed
        # nominal fastener axes can silently become misleading illustrations.
        for center_z, radius in ((-27,1.7),(-53,1.7),(-40,4.1)):
            for face_y in (92.5,94.5):
                circular=[p for p in points if abs(p[1]-face_y)<.001 and abs(math.hypot(p[0]-80,p[2]-center_z)-radius)<.001]
                self.assertGreater(len(circular), 30)


class CurrentGuideSceneTests(unittest.TestCase):
    def test_retired_sideways_frame_is_not_an_available_guide_scene(self):
        # Step 33 uses the upright community/frame-uprights-fastening view.
        self.assertNotIn('assets/r21/base-frame.png', module.scenes())

    def test_retired_stand_is_not_an_available_guide_scene(self):
        self.assertNotIn('assets/r16/service-stand.png', module.scenes())


class R29FasteningGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(module.checked_source()[0], 'rt') as stream:
            cls.rows=json.load(stream)

    def world_points(self, prefix):
        row=next(row for row in self.rows if row['path'].startswith(prefix+' '))
        matrix=row['transform'];vertices=row['vertices_cm']
        return [[10*(sum(matrix[4*axis+j]*vertices[i+j] for j in range(3))+matrix[4*axis+3]) for axis in range(3)] for i in range(0,len(vertices),3)]

    def test_shelf_screw_axes_follow_rotated_native_bores(self):
        for part,face in [('P08',125.3),('P14',128.3)]:
            points=self.world_points(part)
            for x,y in module.SHELF_FASTENING_CENTERS:
                bore=[p for p in points if abs(p[2]-face)<.002 and abs(math.hypot(p[0]-x,p[1]-y)-1.7)<.006]
                self.assertGreater(len(bore),20,(part,x,y))

    def test_lid_screw_axes_follow_asymmetric_native_bores(self):
        # Read the pure coordinate declaration without importing optional renderer dependencies.
        import ast
        tree=ast.parse((ROOT/'hardware/tools/rendering/guide_closeups.py').read_text())
        centers=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUDIO_LID_CENTERS' for t in node.targets))
        points=self.world_points('FB32')
        for x,y in centers:
            for face in (-41.5,-39.5):
                bore=[p for p in points if abs(p[2]-face)<.002 and abs(math.hypot(p[0]-x,p[1]-y)-1.15)<.002]
                self.assertGreater(len(bore),20,(x,y,face))
