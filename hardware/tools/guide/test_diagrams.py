"""Circuit drawings must preserve canonical allocations and readable type."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import diagrams

ROOT = Path(__file__).resolve().parents[3]
NS = {'s': 'http://www.w3.org/2000/svg'}


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
            if 'H3 return,' in text:
                i = text.index('H3 return,')
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
            (diagrams.inlet_circuit, (), ['J1 center', 'J1 sleeve']),
            (diagrams.pi_power_circuit, (), ['H2 Pi +', 'H2 Pi return']),
            (diagrams.f1_circuit, (), ['F1 input', 'F1 output']),
            (diagrams.c1_circuit, (), ['C1 +', 'C1 −']),
            (diagrams.ground_circuit, (), ['18 AWG link to W4/1', 'Link from W3/3']),
            (diagrams.f2_circuit, (), ['F2 input', 'H3 return, including C2 −']),
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
        self.assertIn('Positive reading · no minus sign.', text)

    def wire_paths(self, name, color):
        paths = []
        for path in ET.parse(self.out / name).findall('.//s:path', NS):
            if path.get('stroke') != color or not path.get('d', '').startswith('M'):
                continue
            values = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', path.attrib['d'])]
            paths.append(list(zip(values[::2], values[1::2])))
        return paths

    def test_servo_leads_reach_their_actual_canonical_terminals(self):
        for name in ('LEFT', 'RIGHT', 'HEAD'):
            file = f'circuits/servo-{name.lower()}.svg'
            for block, suffix, color, source, y in (
                ('W2', '+', diagrams.RED, (187, 253), 350),
                ('W4', 'return', diagrams.BLK, (211, 253), 480),
            ):
                row = next(r for r in self.canonical['power']['rows'] if r[0].startswith(block + ' '))
                port = row.index(f'{name} servo {suffix}')
                target = diagrams.port_point(port, y)
                self.assertTrue(any(p[0] == source and p[-1] == target for p in self.wire_paths(file, color)), (name, block))
            signal = next(row[2].split(' → ')[1] for row in self.canonical['signal']['rows'] if row[2].endswith(f'{name} servo signal'))
            shifter, terminal = signal.split()
            self.assertIn(shifter + ' output', self.texts(file))
            self.assertIn(terminal, self.texts(file))
            self.assertTrue(any(p[0] == (235, 253) and p[-1] == (390, 615) for p in self.wire_paths(file, diagrams.BLUE)))

    def test_head_power_has_continuous_separate_rails_to_both_loads(self):
        rails = {}
        for color, source, targets in (
            (diagrams.RED, (276, 145), {(52, 500), (245, 500)}),
            (diagrams.BLK, (276, 159), {(52, 550), (245, 550)}),
        ):
            paths = self.wire_paths('circuits/head-power.svg', color)
            graph = {}
            segments = []
            for path in paths:
                for a, b in zip(path, path[1:]):
                    graph.setdefault(a, set()).add(b)
                    graph.setdefault(b, set()).add(a)
                    segments.append((a, b))
            reached, queue = set(), [source]
            while queue:
                point = queue.pop()
                if point not in reached:
                    reached.add(point)
                    queue.extend(graph.get(point, ()))
            self.assertTrue(targets <= reached, (color, targets - reached))
            rails[color] = segments
        # A crossing can have an insulating halo; a shared longitudinal run
        # between opposite polarities cannot show two independent conductors.
        for a, b in rails[diagrams.RED]:
            for p, q in rails[diagrams.BLK]:
                for axis in (0, 1):
                    run = 1 - axis
                    if a[axis] == b[axis] == p[axis] == q[axis]:
                        overlap = min(max(a[run], b[run]), max(p[run], q[run])) - max(min(a[run], b[run]), min(p[run], q[run]))
                        self.assertLessEqual(overlap, 0, (a, b, p, q))

    def test_strand_test_does_not_imply_connector_direction_or_cutting(self):
        identification = self.texts('circuits/strand-wire-identification.svg')
        self.assertIn('Connector sex does not show input.', identification)
        self.assertIn('colors are missing or disagree.', identification)
        result = self.texts('circuits/strand-input-result.svg')
        self.assertIn('Keep the full strand uncut for this test', result)
        self.assertIn('Remaining 84 · should stay dark', result)
        self.assertFalse(any('cut here' in t.lower() for t in result))

    def test_unknown_resistor_is_rejected_instead_of_drawing_wrong_bands(self):
        with self.assertRaises(KeyError):
            diagrams.resistor(diagrams.Svg(420, 200, 'test'), 20, 120, 'R9')
        self.assertEqual(diagrams.RESISTORS['R2'][1], ('#d06924', '#d06924', '#7c4a31'))

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
