"""Print downloads must follow the selected printing manifest without altering CAD."""
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

import packages
import build


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.manifest = json.loads((packages.PRINTING / 'manifest.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_manifest_selects_exact_current_projects(self):
        selected = packages.sources()
        self.assertEqual(selected['pla'], packages.PRINTING / self.manifest['master_project'])
        self.assertEqual(selected['petg'], packages.PRINTING / self.manifest['optional_petg_project'])

    def test_missing_declared_source_does_not_choose_other_project(self):
        folder = self.root / 'missing-source'
        folder.mkdir()
        manifest = dict(self.manifest, master_project='missing.3mf')
        (folder / 'manifest.json').write_text(json.dumps(manifest))
        (folder / 'newest-but-unselected.3mf').write_bytes(b'not selected')
        with self.assertRaisesRegex(FileNotFoundError, 'missing.3mf'):
            packages.sources(folder)

    def test_missing_thumbnail_fails(self):
        folder = self.root / 'missing-thumbnail'
        folder.mkdir()
        (folder / 'manifest.json').write_text(json.dumps(self.manifest))
        for key in ('master_project', 'optional_petg_project'):
            with zipfile.ZipFile(packages.PRINTING / self.manifest[key]) as src:
                with zipfile.ZipFile(folder / self.manifest[key], 'w') as dst:
                    for info in src.infolist():
                        if info.filename != 'Metadata/plate_2.png':
                            dst.writestr(info, src.read(info))
        shutil.copyfile(packages.OBJECT_SETTINGS, folder / 'object-settings.csv')
        with self.assertRaisesRegex(ValueError, 'Metadata/plate_2.png'):
            packages.sources(folder)

    def test_readme_follows_manifest_estimates_and_parts(self):
        manifest = json.loads(json.dumps(self.manifest))
        plate = manifest['plates'][0]
        plate['estimated_seconds'] = 3600
        plate['estimated_grams'] = 1.25
        plate['parts'] = {'FB01': 2}
        plate['purpose'] = 'Private design experiment, do not publish'
        readme = packages.print_set_readme(manifest)
        self.assertIn('| 1 | White (W1) | 2 | 1 h 00 min, 1.25 g | FB01 ×2 |', readme)
        pieces = sum(sum(p['parts'].values()) for p in manifest['plates'])
        types = len({part for p in manifest['plates'] for part in p['parts']})
        self.assertIn(f"{len(manifest['plates'])} plates, {pieces} pieces, {types} part types", readme)
        self.assertNotIn('Private design experiment', readme)

    def test_stl_selection_keeps_optional_parts_and_excludes_retired_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            catalog = directory / 'parts.json'
            catalog.write_text(json.dumps({'parts': [{'part_id': 'CURRENT'}],
                                           'optional_parts': [{'part_id': 'OPTIONAL'}]}))
            for name in ('CURRENT', 'OPTIONAL', 'RETIRED'):
                (directory / f'{name}.stl').write_bytes(name.encode())
            self.assertEqual([p.name for p in packages.stl_sources(directory, catalog)],
                             ['CURRENT.stl', 'OPTIONAL.stl'])
            (directory / 'OPTIONAL.stl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing catalog STL downloads.*OPTIONAL'):
                packages.stl_sources(directory, catalog)

    def test_public_project_removes_only_account_metadata(self):
        for field in ('<metadata name="DesignerUserId">test-account</metadata>',
                      '<metadata name="DesignerUserId"></metadata>',
                      '<metadata name="DesignerUserId"/>', ''):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                src, dst = Path(folder) / 'source.3mf', Path(folder) / 'public.3mf'
                prefix = '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
                suffix = ('<metadata name="Copyright">test-account retains copyright</metadata>'
                          '<resources/><build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 2 3 4"/></build></model>')
                model = (prefix + field + suffix).encode()
                with zipfile.ZipFile(src, 'w') as z:
                    z.writestr('3D/3dmodel.model', model)
                    z.writestr('Metadata/plate_1.png', b'test-account thumbnail bytes')
                    z.writestr('Metadata/project_settings.config', '{"printer_model": "X1C"}')
                original = src.read_bytes()
                packages.public_3mf(src, dst)
                self.assertEqual(original, src.read_bytes())
                with zipfile.ZipFile(dst) as z:
                    expected = (prefix + suffix).encode() if 'test-account' in field else model
                    self.assertEqual(expected, z.read('3D/3dmodel.model'))
                    self.assertEqual(b'test-account thumbnail bytes', z.read('Metadata/plate_1.png'))
                    self.assertEqual(b'{"printer_model": "X1C"}', z.read('Metadata/project_settings.config'))

    def test_downloads_preserve_bytes_and_are_deterministic(self):
        first = self.root / 'first' / 'downloads'
        second = self.root / 'second' / 'downloads'
        packages.write(first)
        packages.write(second)
        for path in first.rglob('*'):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes(), path.name)
        for path in packages.stl_sources():
            self.assertEqual(path.read_bytes(), (first / 'stl' / path.name).read_bytes())
        self.assertEqual(packages.OBJECT_SETTINGS.read_bytes(), (first / 'BlooglyBlob-object-settings.csv').read_bytes())
        for source_key, public_name in [('master_project', 'BlooglyBlob-PLA.3mf'),
                                        ('optional_petg_project', 'BlooglyBlob-PETG-ball.3mf')]:
            with zipfile.ZipFile(packages.PRINTING / self.manifest[source_key]) as source, zipfile.ZipFile(first / public_name) as public:
                self.assertEqual(source.namelist(), public.namelist())
                for info in source.infolist():
                    expected = source.read(info)
                    if info.filename.endswith(packages.TEXT):
                        for old, new in packages.NAMES.items():
                            expected = expected.replace(old.encode(), new.encode())
                    if info.filename.endswith('.model') and b'DesignerUserId' in expected:
                        source_root, public_root = ET.fromstring(expected), ET.fromstring(public.read(info.filename))
                        for parent in source_root.iter():
                            for element in list(parent):
                                if element.tag.endswith('}metadata') and element.get('name') == 'DesignerUserId' and (element.text or '').strip():
                                    parent.remove(element)
                        self.assertEqual(ET.canonicalize(ET.tostring(source_root), strip_text=True),
                                         ET.canonicalize(ET.tostring(public_root), strip_text=True), info.filename)
                        self.assertFalse(any(e.get('name') == 'DesignerUserId' and (e.text or '').strip() for e in public_root.iter()))
                        continue
                    self.assertEqual(expected, public.read(info.filename), info.filename)
                if source_key == 'master_project':
                    for plate in self.manifest['plates']:
                        n = plate['plate_number']
                        self.assertEqual(source.read(f'Metadata/plate_{n}.png'), (first.parent / f'assets/plates/plate-{n}.png').read_bytes())
        with zipfile.ZipFile(first / 'BlooglyBlob-STL.zip') as z:
            expected_stls = {f'BlooglyBlob-STL/{p.name}' for p in packages.stl_sources()}
            self.assertEqual(set(z.namelist()), expected_stls | {'BlooglyBlob-STL/README.txt'})
            self.assertEqual({p.name for p in (first / 'stl').iterdir()},
                             {p.name for p in packages.stl_sources()})
            for path in packages.stl_sources():
                self.assertEqual(path.read_bytes(), z.read(f'BlooglyBlob-STL/{path.name}'))
            self.assertTrue(all(i.date_time == packages.ZIP_TIME for i in z.infolist()))
        with zipfile.ZipFile(first / 'BlooglyBlob-print-set.zip') as z:
            readme = z.read('BlooglyBlob-print-set/README.md').decode()
            plates = self.manifest['plates']
            minutes = sum(p['estimated_seconds'] for p in plates) // 60
            hours, minutes = divmod(minutes, 60)
            grams = sum(p['estimated_grams'] for p in plates)
            self.assertIn(f'Estimated total: {hours} h {minutes:02d} min and {grams:.2f} g', readme)
            for plate in plates:
                color = 'Copper silk' if plate['color'] == 'Copper' else plate['color']
                pieces = sum(plate['parts'].values())
                items = ', '.join(part + (f' ×{n}' if n > 1 else '')
                                  for part, n in plate['parts'].items())
                self.assertIn(f"| {plate['plate_number']} | {color} ({plate['id']}) | {pieces} | "
                              f"{packages.duration(plate['estimated_seconds'])}, "
                              f"{plate['estimated_grams']:.2f} g | {items} |", readme)
            self.assertNotIn(self.manifest['cad_revision'].split('/')[0], readme)
            for name in ('BlooglyBlob-PLA.3mf', 'BlooglyBlob-PETG-ball.3mf', 'BlooglyBlob-object-settings.csv'):
                self.assertEqual((first / name).read_bytes(), z.read(f'BlooglyBlob-print-set/{name}'))


class PrintMetadataTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(packages.MANIFEST.read_text())
        self.prints = json.loads((build.SRC / 'print-data.json').read_text())

    def test_current_metadata_matches_selected_manifest(self):
        build.check_print_data(self.prints, self.manifest)

    def test_metadata_drift_is_rejected(self):
        changes = {
            'id': lambda p: p[1].update(id='old-K1'),
            'plate number': lambda p: p[1]['settings'].update({'Plate number': 7}),
            'quantity': lambda p: p[1]['quantities'].update(FB01=2),
            'part ids': lambda p: p[1]['parts'].append('FB41'),
            'grams': lambda p: p[1]['estimate'].update(grams=314.30),
            'time': lambda p: p[1]['estimate'].update(time='13 h 38 min'),
            'missing plate': lambda p: p.pop(),
            'duplicate plate': lambda p: p.append(p[1]),
            'display order': lambda p: p.reverse(),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                prints = json.loads(json.dumps(self.prints))
                change(prints)
                with self.assertRaisesRegex(ValueError, 'Print metadata'):
                    build.check_print_data(prints, self.manifest)

    def test_plate_settings_total_is_truncated_manifest_total(self):
        page = (build.SRC / 'repeat-build.html').read_text()
        build.check_plate_total(page, self.manifest)
        manifest = json.loads(json.dumps(self.manifest))
        manifest['plates'][0]['estimated_seconds'] += 60
        with self.assertRaisesRegex(ValueError, 'Estimated total'):
            build.check_plate_total(page, manifest)

    def test_invalid_preflight_keeps_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, dist = root / 'src', root / 'dist'
            src.mkdir()
            dist.mkdir()
            marker = dist / 'keep.txt'
            marker.write_text('existing preview')
            for filename in build.DATA:
                shutil.copyfile(build.SRC / filename, src / filename)
            self.prints[1]['estimate']['grams'] = 314.30
            (src / 'print-data.json').write_text(json.dumps(self.prints))
            # This executes real source selection and preflight, stopping any full build.
            with patch.object(build, 'SRC', src), patch.object(build, 'DIST', dist), \
                    patch.object(build, 'ROOT', root), \
                    patch.object(build.shutil, 'rmtree') as remove_output, \
                    patch.object(build.packages, 'write') as write_packages, \
                    patch.object(build.shutil, 'copytree'), patch.object(build, 'check_links'):
                with self.assertRaisesRegex(ValueError, 'Print metadata'):
                    build.build()
                remove_output.assert_not_called()
                write_packages.assert_not_called()
            self.assertEqual(marker.read_text(), 'existing preview')


if __name__ == '__main__':
    unittest.main()
