"""Circuit drawings must preserve canonical allocations and readable type."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import consistency
import diagrams

ROOT = Path(__file__).resolve().parents[3]
NS = {'s': 'http://www.w3.org/2000/svg'}
SVG = '{http://www.w3.org/2000/svg}'

# Retired names (INSTRUCTION-DESIGN.md "Names"): the guide's banned terms plus
# the connector names a figure can show. LEFT, RIGHT and HEAD remain the labels
# written on the servo cables, and BODY LIGHT and HEAD LIGHT on the connectors.
RETIRED = [(term, re.compile(pattern, 0 if case else re.I))
           for term, pattern, case, scope in consistency.WRITING['banned'] if scope == 'text']
RETIRED += [(term, re.compile(pattern)) for term, pattern in (
    ('BODY (label)', r'\bBODY\b(?![- ]LIGHT\b)'),
    ('HEAD (label)', r'\bHEAD\b(?![- ](?:LIGHT|SERVO|servo)\b)'),
    ('pixel', r'(?i)\bpixels?\b'),
    ('Pixel Shifter', r'(?i)\bpixel shifters?\b'),
    ('lighting lead', r'(?i)\blighting (?:lead|harness)\b'),
)]
SERVO_LABELS = {'HEAD', 'HEAD · servo hookup', 'HEAD positive (+)', 'HEAD return (−)', 'C5 → HEAD'}


def retired_names(text):
    """Retired terms in one visible label; the servo cable label HEAD is allowed."""
    found = [term for term, pattern in RETIRED if pattern.search(text)]
    if text in SERVO_LABELS:
        found.remove('HEAD (label)')
    return found


def labels(root):
    """Visible text, descriptions and nested titles; the root title is the file name."""
    top = root.find(SVG + 'title')
    return [e.text or '' for e in root.iter() if e.tag in (SVG + 'text', SVG + 'desc', SVG + 'title') and e is not top]


class CircuitDiagramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        cls.canonical = json.loads((ROOT / 'hardware/assembly/electrical.json').read_text())
        with patch.object(diagrams, 'OUT', cls.out):
            diagrams.circuit_actions()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def texts(self, name):
        return [e.text or '' for e in ET.parse(self.out / name).findall('.//s:text', NS)]

    def test_wago_reference_preserves_every_canonical_port_and_order(self):
        for row in self.canonical['power']['rows']:
            block = row[0].split()[0].lower()
            text = self.texts(f'circuits/{block}-reference.svg')
            # Recombine the sole wrapped cell, then compare all five entries,
            # not just presence of strings somewhere in the image.
            if 'Base-half GND,' in text:
                i = text.index('Base-half GND,')
                text[i:i+2] = [' '.join(text[i:i+2])]
            start = text.index('1')
            self.assertEqual(text[start:start+10], [s for n, label in enumerate(row[1:], 1) for s in (str(n), label)])

    def test_shifter_physical_pins_follow_canonical_first_hop(self):
        observed = {}
        for name in ('s1', 's2'):
            for text in self.texts(f'circuits/{name}-inputs.svg'):
                if ' → S' in text:
                    pin, endpoint = text.split(' → ')
                    observed[pin] = endpoint
        expected = {row[0]: row[2].split(' → ')[0] for row in self.canonical['signal']['rows'] if row[2].startswith(('S1 ', 'S2 '))}
        self.assertEqual(observed, expected)

    def test_button_pin_map_matches_canonical_functions(self):
        text = self.texts('circuits/button-pins.svg')
        drawn = dict(value.split(' → ', 1) for value in text if value[:1].isdigit() and ' → ' in value)
        names = {
            'One normally-open switch contact': 'switch NO',
            'Other switch contact': 'switch return',
            'R1 → button LED +': 'R1 → LED +',
            'Button LED −': 'LED −',
        }
        expected = {row[0]: names[row[2]] for row in self.canonical['signal']['rows'] if row[2] in names}
        self.assertEqual(drawn, expected)

    def test_action_landings_match_canonical_wago_allocations(self):
        # Capture the actual rendered port calls, paired with each action's
        # named component. An accidentally moved terminal fails against JSON.
        canonical = {(row[0].split()[0], n): label for row in self.canonical['power']['rows'] for n, label in enumerate(row[1:], 1)}
        cases = [
            (diagrams.power_jack_circuit, (), ['J1 center', 'J1 sleeve']),
            (diagrams.pi_power_circuit, (), ['Pi power lead +', 'Pi power lead return']),
            (diagrams.servo_feed_circuit, (), ['18 AWG feed to W2/1', 'Feed from W1/3']),
            (diagrams.c1_circuit, (), ['C1 +', 'C1 −']),
            (diagrams.ground_circuit, (), ['18 AWG link to W4/1', 'Link from W3/3']),
            (diagrams.f2_circuit, (), ['F2 input', 'Base-half GND, including C2 −']),
        ]
        for name, port, signal in [('LEFT', 2, 'S1 C5'), ('RIGHT', 3, 'S2 D5'), ('HEAD', 4, 'S2 C5')]:
            cases.append((diagrams.servo_circuit, (name, port, signal), [f'{name} servo +', f'{name} servo return']))
        for draw, args, endpoints in cases:
            seen = []
            def capture(g, y, block, port, color):
                seen.append(canonical[block, port])
            with patch.object(diagrams.Svg, 'save'), patch.object(diagrams, 'wago_port', capture):
                draw(*args)
            self.assertEqual(seen, endpoints, draw.__name__)

    def test_supply_polarity_probe_endpoints(self):
        text = self.texts('circuits/supply-polarity-test.svg')
        self.assertIn('Black: outer sleeve', text)
        self.assertIn('Red: inside center', text)

    def wire_paths(self, name, color):
        paths = []
        for path in ET.parse(self.out / name).findall('.//s:path', NS):
            if path.get('stroke') != color or not path.get('d', '').startswith('M'):
                continue
            values = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', path.attrib['d'])]
            paths.append(list(zip(values[::2], values[1::2])))
        return paths

    def test_direct_servo_feed_and_service_isolation_endpoints(self):
        connected = self.wire_paths('circuits/servo-feed-connect.svg', diagrams.RED)
        self.assertEqual(len(connected), 1)
        self.assertEqual(connected[0][0], diagrams.port_point(3, 147))
        self.assertEqual(connected[0][-1], diagrams.port_point(1, 345))
        isolated = self.wire_paths('circuits/servo-feed-isolation.svg', diagrams.RED)
        self.assertEqual(len(isolated), 1)
        self.assertEqual(isolated[0][-1], diagrams.port_point(1, 410))
        self.assertNotIn(diagrams.port_point(3, 147), isolated[0])
        root = ET.parse(self.out / 'circuits/servo-feed-isolation.svg').getroot()
        # The free endpoint is fully within an insulating cap, not bare copper.
        x, y = isolated[0][0]
        caps = root.findall('.//s:rect[@fill="#47515b"]', NS)
        self.assertTrue(any(float(c.get('x')) < x < float(c.get('x')) + float(c.get('width'))
                            and float(c.get('y')) < y < float(c.get('y')) + float(c.get('height'))
                            for c in caps))

    def test_servo_leads_reach_their_actual_canonical_terminals(self):
        for name in ('LEFT', 'RIGHT', 'HEAD'):
            file = f'circuits/servo-{name.lower()}.svg'
            for block, suffix, color, source, y in (
                # Real FS90MG lead order: brown ground, red supply, orange signal.
                ('W2', '+', diagrams.RED, (211, 253), 350),
                ('W4', 'return', diagrams.SERVO_BROWN, (187, 253), 480),
            ):
                row = next(r for r in self.canonical['power']['rows'] if r[0].startswith(block + ' '))
                port = row.index(f'{name} servo {suffix}')
                target = diagrams.port_point(port, y)
                self.assertTrue(any(p[0] == source and p[-1] == target for p in self.wire_paths(file, color)), (name, block))
            signal = next(row[2].split(' → ')[1] for row in self.canonical['signal']['rows'] if row[2].endswith(f'{name} servo signal'))
            shifter, terminal = signal.split()
            self.assertIn(shifter + ' output', self.texts(file))
            self.assertIn(terminal, self.texts(file))
            self.assertTrue(any(p[0] == (235, 253) and p[-1] == (390, 615) for p in self.wire_paths(file, diagrams.SERVO_ORANGE)))

    def test_head_half_joins_eye_lead_by_function(self):
        # JST-SM is +5 V, DATA, GND; the eye lead's JST-SH order is GND, +5 V, DATA.
        texts = self.texts('circuits/head-power.svg')
        for label in ('+5 V', 'DATA', 'GND', 'Head half: JST-SM (large), pins', 'Eye input lead: JST-SH (small)'):
            self.assertIn(label, texts)

    def test_strand_test_names_pins_end_as_likely_input_without_cutting(self):
        identification = self.texts('circuits/strand-wire-identification.svg')
        self.assertIn('Copper coil / dots → +5 V', identification)
        # The likely-input rule and the stop condition are instructions, so they live in the actions.
        actions = ' '.join(next(s for s in json.loads((ROOT / 'hardware/build-guide/src/guide-data.json').read_text())['steps']
                                if s['id'] == 'light-fuse-capacitor')['actions'])
        self.assertIn('is normally the input', actions)
        self.assertIn('disagree with the factory lead colors, stop', actions)
        result = self.texts('circuits/strand-input-result.svg')
        self.assertIn('First 16 · lit in order', result)
        self.assertIn('Remaining 84 · dark', result)
        self.assertFalse(any('cut here' in t.lower() for t in result))

    def test_drawings_carry_labels_not_titles_or_sentences(self):
        # The guide caption gives the view and the actions give instructions.
        for generated in self.out.rglob('*.svg'):
            for text in self.texts(generated.relative_to(self.out)):
                self.assertFalse(text.rstrip().endswith('.'), f'{generated.name}: {text}')

    def test_unknown_resistor_is_rejected_instead_of_drawing_wrong_bands(self):
        with self.assertRaises(KeyError):
            diagrams.resistor(diagrams.Svg(420, 200, 'test'), 20, 120, 'R9')
        self.assertEqual(diagrams.RESISTORS['R2'][1], ('#d06924', '#d06924', '#7c4a31'))

    def test_generated_labels_use_approved_names(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(diagrams, 'OUT', Path(temp)):
            diagrams.servo_fit_position()
            fit = Path(temp) / 'servo-fit-position.svg'
            self.assertEqual(fit.read_bytes(), (ROOT / 'hardware/build-guide/src/assets/servo-fit-position.svg').read_bytes())
            files = [(fit.name, ET.parse(fit).getroot())]
        files += [(str(f.relative_to(self.out)), ET.parse(f).getroot()) for f in sorted(self.out.rglob('*.svg'))]
        found = [(name, text, retired_names(text)) for name, root in files for text in labels(root) if retired_names(text)]
        self.assertEqual(found, [])

    def test_retired_name_check_catches_connector_labels(self):
        for text in ('H3 · base', 'BASE→BODY', 'Test through the BODY plug', 'HEAD DATA → 5755',
                     'HEAD · JST-SM', 'J1 · enclosure inlet', 'Keep all 100 pixels together', 'Gently pull-check.'):
            self.assertTrue(retired_names(text), text)
        for text in ('HEAD', 'HEAD positive (+)', 'C5 → HEAD', 'BODY LIGHT', 'HEAD LIGHT', 'S2.C5 to HEAD-SERVO.SIG', 'W1.2 to pi-power.+'):
            self.assertEqual(retired_names(text), [], text)

    def test_electrical_tables_use_approved_names(self):
        cells = [cell for table in ('power', 'signal') for row in self.canonical[table]['rows'] for cell in row]
        cells += self.canonical['diagram'].splitlines()
        self.assertEqual([(cell, retired_names(cell)) for cell in cells if retired_names(cell)], [])

    def test_committed_outputs_match_generator_and_phone_type_floor(self):
        # Generation and checked-in outputs must agree, and the 420-unit view
        # must not regress to the previous unreadable 12–16-unit captions.
        for generated in self.out.rglob('*.svg'):
            committed = ROOT / 'hardware/build-guide/src/assets' / generated.relative_to(self.out)
            self.assertEqual(generated.read_bytes(), committed.read_bytes(), str(committed))
            svg = ET.parse(generated).getroot()
            self.assertEqual(svg.attrib['viewBox'].split()[2], '420')
            for text in svg.findall('.//s:text', NS):
                self.assertGreaterEqual(float(text.attrib['font-size']), 22, text.text)


if __name__ == '__main__':
    unittest.main()
