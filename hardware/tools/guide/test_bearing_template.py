"""The printable bearing disc retains actual dimensions and both folding tabs."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]


class BearingTemplateTests(unittest.TestCase):
    def test_full_size_disc_and_retained_tabs(self):
        svg = ET.parse(ROOT / 'hardware/build-guide/src/downloads/head-bearing-film-template.svg').getroot()
        ns = {'s': 'http://www.w3.org/2000/svg'}
        self.assertEqual(svg.attrib['width'], '215.9mm')
        self.assertEqual(svg.attrib['viewBox'], '0 0 215.9 279.4')
        circle = svg.find('.//s:circle', ns)
        self.assertEqual(float(circle.attrib['r']) * 2, 82.6)
        paths = svg.findall('.//s:path', ns)
        cut = next(p.attrib['d'] for p in paths if p.attrib['d'].endswith(' Z'))
        points = [tuple(map(float, p)) for p in re.findall(r'([\d.]+),([\d.]+)', cut)]
        cx, cy = float(circle.attrib['cx']), float(circle.attrib['cy'])
        # Tabs extend inward from the 31 mm opening, with 3.2 mm width.
        for x in (-1.6, 1.6):
            for y in (-28.5, 28.5):
                self.assertTrue(any(abs(px-cx-x)<1e-4 and abs(py-cy-y)<1e-4 for px,py in points))
        self.assertEqual(len([p for p in paths if 'stroke-dasharray' in p.attrib]), 2)
        # Arc extrema confirm the 62 mm opening independently of its text label.
        self.assertAlmostEqual(max(p[0] for p in points)-min(p[0] for p in points), 62, places=3)
        self.assertTrue((ROOT / 'hardware/build-guide/src/downloads/head-bearing-film-template.pdf').read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
