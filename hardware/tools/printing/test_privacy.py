"""Account metadata removal must not alter model or process data."""
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

import privacy


class PrivacyTests(unittest.TestCase):
    def test_prefixed_metadata_entities_and_utf8_preserve_surrounding_bytes(self):
        prefix = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                  '<m:model xmlns:m="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
                  '<!-- café: keep formatting and namespaces -->\n').encode()
        suffix = b'\n<m:metadata name="Copyright">private-id</m:metadata><m:build/></m:model>'
        for value in (b'private-id', b'<![CDATA[private-id]]>', b'private&#45;id'):
            data = prefix + b"<m:metadata name='DesignerUserId'>" + value + b'</m:metadata>' + suffix
            self.assertEqual(prefix + suffix, privacy.sanitize_metadata(data))

    def test_empty_and_missing_fields_are_byte_unchanged(self):
        for field in (b'', b'<metadata name="DesignerUserId"/>',
                      b'<metadata name="DesignerUserId"> \n </metadata>'):
            data = b'<model>' + field + b'<build/></model>'
            self.assertEqual(data, privacy.sanitize_metadata(data))

    def test_ambiguous_or_structured_account_metadata_fails_closed(self):
        for fields, message in (
            (b'<metadata name="DesignerUserId"/><metadata name="DesignerUserId">id</metadata>', 'Duplicate'),
            (b'<metadata name="DesignerUserId"><build/></metadata>', 'text only'),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                privacy.sanitize_metadata(b'<model>' + fields + b'</model>')
        with self.assertRaisesRegex(ValueError, 'DTD'):
            privacy.sanitize_metadata(b'<!DOCTYPE model [<!ENTITY id "private-id">]><model/>')
        with self.assertRaisesRegex(ValueError, 'encoding'):
            privacy.sanitize_metadata('<model/>'.encode('utf-16'))

    def test_project_preserves_source_zip_attributes_and_other_members(self):
        with tempfile.TemporaryDirectory() as folder:
            src, dst, again = [Path(folder) / name for name in ('source.3mf', 'public.3mf', 'again.3mf')]
            field = b'<metadata name="DesignerUserId">private-id</metadata>'
            entries = {
                '3D/3dmodel.model': b'<model>' + field + b'<build/></model>',
                'Metadata/extra.xml': b'<model>' + field + b'</model>',
                'Metadata/model_settings.config': b'<config><object id="1"/></config>',
                'Metadata/project_settings.config': b'{"layer_height":0.2}',
                'Metadata/plate_1.png': b'private-id is not a replacement target here',
                'LICENSE.txt': b'private-id retains copyright',
            }
            with zipfile.ZipFile(src, 'w') as z:
                z.comment = b'keep project comment'
                for name, data in entries.items():
                    info = zipfile.ZipInfo(name, (2025, 1, 2, 3, 4, 6))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    info.comment = b'keep member comment'
                    z.writestr(info, data)
            original = src.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Nonempty DesignerUserId'):
                privacy.check_project(src)
            privacy.sanitize_project(src, dst)
            privacy.sanitize_project(src, again)
            privacy.check_project(dst)
            self.assertEqual(original, src.read_bytes())
            self.assertEqual(dst.read_bytes(), again.read_bytes())
            with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst) as zout:
                self.assertEqual(zin.namelist(), zout.namelist())
                self.assertEqual(zin.comment, zout.comment)
                for before, after in zip(zin.infolist(), zout.infolist()):
                    for attr in ('filename', 'date_time', 'compress_type', 'external_attr', 'comment', 'extra'):
                        self.assertEqual(getattr(before, attr), getattr(after, attr))
                    self.assertEqual(entries[before.filename].replace(field, b''), zout.read(after))
            with self.assertRaisesRegex(ValueError, 'differ from source'):
                privacy.sanitize_project(src, src)
            self.assertEqual(original, src.read_bytes())

    def test_config_xml_with_utf8_bom_is_sanitized(self):
        with tempfile.TemporaryDirectory() as folder:
            src, dst = Path(folder) / 'source.3mf', Path(folder) / 'public.3mf'
            field = b'<metadata name="DesignerUserId">private-id</metadata>'
            xml = b'\xef\xbb\xbf<config>' + field + b'</config>'
            with zipfile.ZipFile(src, 'w') as z:
                z.writestr('Metadata/model_settings.config', xml)
            with self.assertRaisesRegex(ValueError, 'Nonempty DesignerUserId'):
                privacy.check_project(src)
            privacy.sanitize_project(src, dst)
            privacy.check_project(dst)
            with zipfile.ZipFile(dst) as z:
                self.assertEqual(z.read('Metadata/model_settings.config'), xml.replace(field, b''))

    def test_config_xml_with_unsupported_encoding_fails_closed(self):
        for encoding in ('utf-16', 'utf-16-be', 'utf-32'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as folder:
                src, dst = Path(folder) / 'source.3mf', Path(folder) / 'public.3mf'
                xml = '<config><metadata name="DesignerUserId">private-id</metadata></config>'.encode(encoding)
                with zipfile.ZipFile(src, 'w') as z:
                    z.writestr('Metadata/model_settings.config', xml)
                for check in (lambda: privacy.check_project(src), lambda: privacy.sanitize_project(src, dst)):
                    with self.assertRaisesRegex(ValueError, 'encoding'):
                        check()

    def test_duplicate_archive_members_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            src, dst = Path(folder) / 'source.3mf', Path(folder) / 'public.3mf'
            with zipfile.ZipFile(src, 'w') as z, warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                z.writestr('3D/3dmodel.model', '<model/>')
                z.writestr('3D/3dmodel.model', '<model/>')
            for check in (lambda: privacy.check_project(src), lambda: privacy.sanitize_project(src, dst)):
                with self.assertRaisesRegex(ValueError, 'Duplicate ZIP'):
                    check()
            self.assertFalse(dst.exists())


if __name__ == '__main__':
    unittest.main()
