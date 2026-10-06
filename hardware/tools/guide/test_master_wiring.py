"""The complete sheet must draw the canonical connections, not repeated lookups."""

import json
import re
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import diagrams
import master_wiring as master
from test_diagrams import labels, retired_names

ROOT = Path(__file__).resolve().parents[3]
NS = {"s": "http://www.w3.org/2000/svg"}


class MasterWiringTests(unittest.TestCase):
    def setUp(self):
        self.c = master.circuit()
        self.pairs = {frozenset((e.source, e.target)) for e in self.c.edges}
        self.electrical = json.loads(
            (ROOT / "hardware/assembly/electrical.json").read_text()
        )

    def test_each_wago_port_has_exactly_its_canonical_wire(self):
        destinations = {
            "J1 center": "J1.center",
            "J1 sleeve": "J1.sleeve",
            "Pi power lead +": "pi-power.+",
            "Pi power lead return": "pi-power.−",
            "18 AWG feed to W2/1": "W2.1",
            "Feed from W1/3": "W1.3",
            "F2 input": "F2.in",
            "C1 +": "C1.+",
            "C1 −": "C1.−",
            "18 AWG link to W4/1": "W4.1",
            "Link from W3/3": "W3.3",
            "Base-half GND, including C2 −": "lighting−.wire",
        }
        for name, node in [
            ("LEFT", "LEFT"),
            ("RIGHT", "RIGHT"),
            ("HEAD", "HEAD-SERVO"),
        ]:
            destinations[name + " servo +"] = node + ".+"
            destinations[name + " servo return"] = node + ".−"
        for row in self.electrical["power"]["rows"]:
            for n, value in enumerate(row[1:], 1):
                port = f"{row[0].split()[0]}.{n}"
                adjacent = [
                    e.target if e.source == port else e.source
                    for e in self.c.edges
                    if port in (e.source, e.target)
                ]
                self.assertEqual(
                    adjacent, [] if value == "Empty" else [destinations[value]], port
                )

    def test_servo_feed_is_one_direct_edge_and_only_lighting_has_a_fuse(self):
        self.assertIn(frozenset(("W1.3", "W2.1")), self.pairs)
        self.assertEqual([n.name for n in self.c.nodes if n.kind == "fuse"], ["F2"])

    def test_all_twelve_pi_connections_and_button_resistor(self):
        button = {
            "One normally-open switch contact": "BTN.SW1",
            "Other switch contact": "BTN.SW2",
            "R1 → button LED +": "R1.out",
            "Button LED −": "BTN.LED−",
        }
        expected = set()
        for row in self.electrical["signal"]["rows"]:
            first = row[2].split(" → ")[0]
            target = (
                first.replace(" ", ".")
                if first.startswith(("S1 ", "S2 "))
                else button[row[2]]
            )
            expected.add(frozenset(("Pi." + row[0], target)))
        observed = {
            frozenset((e.source, e.target))
            for e in self.c.edges
            if e.source.startswith("Pi.") and e.source.split(".")[1].isdigit()
        }
        self.assertEqual(observed, expected)
        self.assertIn(frozenset(("R1.in", "BTN.LED+")), self.pairs)

    def test_lighting_is_one_chain_for_power_and_data(self):
        expected = [
            ("S1.D5", "R2.in"),
            ("R2.out", "body-light.inDATA"),
            ("F2.out", "lighting+.wire"),
            ("C2.+", "lighting+.wire"),
            ("C2.−", "lighting−.wire"),
            ("eye7.outDATA", "mouth.DIN"),
        ]
        for port in ["+", "DATA", "−"]:
            expected += [
                (f"body-light.out{port}", f"body0.in{port}"),
                (f"body5.out{port}", f"head-light.in{port}"),
                (f"head-light.out{port}", f"eye6.in{port}"),
                (f"eye6.out{port}", f"eye7.in{port}"),
            ]
            expected += [(f"body{i}.out{port}", f"body{i + 1}.in{port}") for i in range(5)]
        expected += [("eye7.out+", "mouth.+"), ("eye7.out−", "mouth.−")]
        # No branch joints bypass the chain.
        self.assertFalse(any(n.name in ("body+", "body−", "head+", "head−") for n in self.c.nodes))
        for edge in [
            ("S1.C5", "LEFT.SIG"),
            ("S2.D5", "RIGHT.SIG"),
            ("S2.C5", "HEAD-SERVO.SIG"),
        ]:
            self.assertIn(frozenset(edge), self.pairs)

    def test_routes_do_not_overlap_or_disappear_behind_wagos(self):
        segments = []
        for edge in self.c.edges:
            points = [self.c.ports[edge.source], *edge.bends, self.c.ports[edge.target]]
            for a, b in zip(points, points[1:]):
                if a != b:
                    self.assertTrue(a[0] == b[0] or a[1] == b[1], edge)
                    segments.append((edge, a, b))
        for i, (edge, a, b) in enumerate(segments):
            for other, p, q in segments[i + 1 :]:
                if edge == other:
                    continue
                for axis in (0, 1):
                    run = 1 - axis
                    if a[axis] == b[axis] == p[axis] == q[axis]:
                        overlap = min(max(a[run], b[run]), max(p[run], q[run])) - max(
                            min(a[run], b[run]), min(p[run], q[run])
                        )
                        self.assertLessEqual(overlap, 0, (edge, other))
            for node in self.c.nodes:
                if not node.kind.startswith("wago"):
                    continue
                w, h = (80, 270) if node.kind == "wago-v" else (300, 70)
                if a[0] == b[0]:
                    hidden = node.x < a[0] < node.x + w and min(
                        max(a[1], b[1]), node.y + h
                    ) > max(min(a[1], b[1]), node.y)
                else:
                    hidden = node.y < a[1] < node.y + h and min(
                        max(a[0], b[0]), node.x + w
                    ) > max(min(a[0], b[0]), node.x)
                self.assertFalse(hidden, (edge, node.name))

    def test_button_tabs_and_speaker_tails_meet_their_component_bodies(self):
        for node in self.c.nodes:
            if node.kind not in ("button", "speaker"):
                continue
            svg = diagrams.Svg(2640, 2120, "contact geometry")
            master.draw_node(svg, node, self.c)
            root = ET.fromstring(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                + "".join(svg.parts)
                + "</svg>"
            )
            if node.kind == "button":
                body = root.find("s:circle", NS)
                cx, cy, radius = (float(body.attrib[k]) for k in ("cx", "cy", "r"))
                tabs = root.findall('s:rect[@fill="#bcc7ce"]', NS)
                self.assertEqual(len(tabs), 4)
                for tab in tabs:
                    x, y, w, h = (
                        float(tab.attrib[k]) for k in ("x", "y", "width", "height")
                    )
                    near_x, near_y = max(x, min(cx, x + w)), max(y, min(cy, y + h))
                    self.assertLessEqual(
                        (near_x - cx) ** 2 + (near_y - cy) ** 2, radius**2
                    )
            else:
                body = root.find('s:rect[@fill="#454d54"]', NS)
                x, y, w, h = (
                    float(body.attrib[k]) for k in ("x", "y", "width", "height")
                )
                for port, color in (("+", master.GREEN), ("−", master.PURPLE)):
                    tails = root.findall(f's:path[@stroke="{color}"]', NS)
                    self.assertEqual(len(tails), 1)
                    values = [
                        float(v)
                        for v in re.findall(r"-?\d+(?:\.\d+)?", tails[0].attrib["d"])
                    ]
                    self.assertEqual(
                        tuple(values[:2]), self.c.ports[f"{node.name}.{port}"]
                    )
                    self.assertTrue(
                        x <= values[-2] <= x + w and y <= values[-1] <= y + h
                    )

    def test_drawn_labels_use_approved_names(self):
        root = ET.fromstring(self.drawn())
        texts = labels(root)
        texts += [v for e in root.iter() for k, v in e.attrib.items() if k.startswith("data-")]
        self.assertIn("Body light connector · JST-SM (large)", texts)
        self.assertIn("Head light connector · JST-SM (large)", texts)
        self.assertEqual([(t, retired_names(t)) for t in texts if retired_names(t)], [])

    def drawn(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(diagrams, "OUT", Path(temp)):
                master.draw().save("master-wiring.svg")
            return (Path(temp) / "master-wiring.svg").read_bytes()

    def test_svg_has_one_component_each_and_continuous_terminal_to_terminal_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(diagrams, "OUT", Path(temp)):
                master.draw().save("master-wiring.svg")
            actual = (Path(temp) / "master-wiring.svg").read_bytes()
        root = ET.fromstring(actual)
        components = [
            e.attrib["data-component"]
            for e in root.findall(".//s:g[@data-component]", NS)
        ]
        self.assertEqual(Counter(components), Counter(n.name for n in self.c.nodes))
        drawn = root.findall(".//s:g[@data-from]", NS)
        self.assertEqual(len(drawn), len(self.c.edges))
        for group, edge in zip(drawn, self.c.edges):
            self.assertEqual(
                (group.attrib["data-from"], group.attrib["data-to"]),
                (edge.source, edge.target),
            )
            path = group.findall("s:path", NS)[-1].attrib["d"]
            a, b = self.c.ports[edge.source], self.c.ports[edge.target]
            self.assertTrue(path.startswith(f"M{a[0]} {a[1]} L"), edge.source)
            self.assertTrue(path.endswith(f"{b[0]} {b[1]}"), edge.target)
        self.assertEqual(
            actual,
            (
                ROOT / "hardware/build-guide/src/assets/circuits/master-wiring.svg"
            ).read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
