#!/usr/bin/env python3
"""Draw one connected circuit, with each physical component appearing once.

The routed edges are also exposed to tests: labels never substitute for wires.
This is an electrical connection map, not a mechanical layout or connector pinout.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import diagrams
from diagrams import Svg, INK, MUTED, PAPER, RED, BLK, BLUE, GRAY

PURPLE, GREEN = "#7150a0", "#34765b"
WIDTH, HEIGHT = 2640, 2120


@dataclass
class Node:
    name: str
    kind: str
    x: float
    y: float
    label: str = ""


@dataclass
class Edge:
    source: str
    target: str
    color: str
    bends: tuple = ()
    cable: bool = False


class Circuit:
    def __init__(self):
        self.nodes = []
        self.ports = {}
        self.edges = []

    def node(self, name, kind, x, y, label=""):
        self.nodes.append(Node(name, kind, x, y, label))
        ports = {}
        if kind == "wago-v":
            ports = {str(n): (x + 80, y + 40 + (n - 1) * 50) for n in range(1, 6)}
        elif kind == "wago-h":
            ports = {str(n): (x + 30 + (n - 1) * 60, y + 70) for n in range(1, 6)}
        elif kind == "pi":
            ports = {
                str(n): (x + 20 + ((n - 1) // 2) * 18, y + (12 if n % 2 else 42))
                for n in range(1, 41)
            }
            ports.update({"USB": (x + 400, y + 160), "POWER": (x + 100, y + 310)})
        elif kind == "shifter":
            ports = {
                p: (x, y + 25 + i * 40) for i, p in enumerate(["V", "G", "DAT", "CLK"])
            }
            ports.update({"D5": (x + 200, y + 60), "C5": (x + 200, y + 130)})
        elif kind == "servo":
            ports = {
                p: (x + 30 + i * 20, y + 120) for i, p in enumerate(["+", "−", "SIG"])
            }
        elif kind == "fuse":
            ports = {"in": (x, y + 20), "out": (x + 180, y + 20)}
        elif kind == "cap":
            ports = {"+": (x + 17, y + 120), "−": (x + 54, y + 145)}
        elif kind == "jack":
            ports = {
                "center": (x + 60, y - 20),
                "sleeve": (x + 60, y + 20),
                "barrel": (x - 60, y),
            }
        elif kind == "supply":
            ports = {"DC": (x + 140, y + 45)}
        elif kind == "button":
            ports = {
                "LED+": (x + 75, y - 25),
                "LED−": (x + 75, y + 5),
                "SW1": (x + 75, y + 35),
                "SW2": (x + 75, y + 65),
            }
        elif kind == "resistor":
            ports = {"in": (x, y), "out": (x + 150, y)}
        elif kind == "audio":
            ports = {
                "USB": (x, y + 40),
                "L+": (x + 180, y + 12),
                "L−": (x + 180, y + 30),
                "R+": (x + 180, y + 60),
                "R−": (x + 180, y + 78),
            }
        elif kind == "speaker":
            ports = {"+": (x - 15, y - 45), "−": (x + 15, y - 45)}
        elif kind == "plug":
            for i, p in enumerate(["+", "DATA", "−"]):
                ports["in" + p] = (x, y + 12 + i * 30)
                ports["out" + p] = (x + 84, y + 12 + i * 30)
        elif kind in ("pebble", "eye"):
            for i, p in enumerate(["+", "DATA", "−"]):
                ports["in" + p] = (x, y + 10 + i * 20)
                ports["out" + p] = (x + 60, y + 10 + i * 20)
        elif kind == "mouth":
            ports = {"DIN": (x, y + 30), "+": (x + 140, y + 10), "−": (x + 230, y + 50)}
        elif kind == "joint":
            ports = {"wire": (x, y)}
        else:
            raise ValueError(kind)
        for p, point in ports.items():
            self.ports[f"{name}.{p}"] = point

    def connect(self, source, target, color=BLK, bends=(), cable=False):
        # Fail generation if a renamed terminal leaves a floating wire.
        self.ports[source]
        self.ports[target]
        self.edges.append(Edge(source, target, color, tuple(bends), cable))


def circuit():
    c = Circuit()
    for args in [
        ("PSU", "supply", 65, 1120, "5 V / 5 A supply"),
        ("J1", "jack", 170, 1430, "J1 · inlet"),
        ("W1", "wago-v", 250, 1130, "W1 · INPUT +5 V"),
        ("W3", "wago-v", 250, 1560, "W3 · GND"),
        ("F1", "fuse", 610, 1400, "F1 · T3.15 A"),
        ("F2", "fuse", 610, 1210, "F2 · T1 A"),
        ("W2", "wago-h", 900, 1300, "W2 · SERVO +5 V"),
        ("W4", "wago-h", 900, 1800, "W4 · GND"),
        ("C1", "cap", 710, 1580, "C1 · 1000 µF / 10 V"),
        ("C2", "cap", 1180, 640, "C2 · 1000 µF / 10 V"),
        ("Pi", "pi", 600, 720, "Raspberry Pi 3A+"),
        ("S1", "shifter", 610, 370, "S1"),
        ("S2", "shifter", 1050, 370, "S2"),
        ("BTN", "button", 185, 795, "Front button"),
        ("R1", "resistor", 280, 650, "R1 · 1 kΩ"),
        ("AUDIO", "audio", 1100, 875, "USB audio · 18833"),
        ("SPK-L", "speaker", 1060, 1120, "Left speaker"),
        ("SPK-R", "speaker", 1240, 1120, "Right speaker"),
        ("LEFT", "servo", 1690, 1030, "Left arm"),
        ("RIGHT", "servo", 2010, 1030, "Right arm"),
        ("HEAD-SERVO", "servo", 2330, 1030, "Head servo"),
        ("H3", "plug", 1380, 768, "BASE → BODY · H3"),
        ("HEAD", "plug", 1520, 523, "HEAD · JST-SM"),
        ("R2", "resistor", 1480, 810, "R2 · 330 Ω"),
        ("lighting+", "joint", 1340, 780),
        ("lighting−", "joint", 1310, 840),
        ("body+", "joint", 1480, 710),
        ("body−", "joint", 1500, 750),
        ("head+", "joint", 1710, 150),
        ("head−", "joint", 1690, 450),
        ("eye6", "eye", 1740, 230, "Eye 1 · pixel 6"),
        ("eye7", "eye", 2020, 230, "Eye 2 · pixel 7"),
        ("mouth", "mouth", 2240, 240, "Mouth · pixels 8–15"),
    ]:
        c.node(*args)
    for i in range(6):
        c.node(f"body{i}", "pebble", 1650 + i * 132, 700, str(i))
    C = c.connect
    C(
        "PSU.DC",
        "J1.barrel",
        PURPLE,
        [(220, 1165), (220, 1360), (70, 1360), (70, 1430)],
        cable=True,
    )
    C("J1.center", "W1.1", RED, [(350, 1410), (350, 1170)])
    C("J1.sleeve", "W3.1", BLK, [(370, 1450), (370, 1600)])
    # The Pi power lead is two conductors entering the single micro-USB plug.
    c.ports["H2.+"] = (687, 1080)
    c.ports["H2.−"] = (713, 1080)
    C("W1.2", "H2.+", RED, [(530, 1220), (530, 1090), (687, 1090)])
    C("W3.2", "H2.−", BLK, [(510, 1650), (510, 1110), (713, 1110)])
    C("W1.3", "F1.in", RED, [(460, 1270), (460, 1420)])
    C("F1.out", "W2.1", RED, [(930, 1420)])
    C("W1.4", "F2.in", RED, [(490, 1320), (490, 1230)])
    C("F2.out", "lighting+.wire", RED, [(1340, 1230)])
    C("lighting+.wire", "H3.in+", RED)
    C("C2.+", "lighting+.wire", RED, [(1197, 780)])
    C("W3.5", "lighting−.wire", BLK, [(440, 1800), (440, 1785), (1310, 1785)])
    C("lighting−.wire", "H3.in−", BLK)
    C("C2.−", "lighting−.wire", BLK, [(1310, 785)])
    C("W2.5", "C1.+", RED, [(1170, 1530), (680, 1530), (680, 1720), (727, 1720)])
    C("C1.−", "W3.4", BLK, [(764, 1770), (470, 1770), (470, 1750)])
    C("W3.3", "W4.1", BLK, [(410, 1700), (410, 1910), (930, 1910)])
    for n, name, y in [(2, "LEFT", 1400), (3, "RIGHT", 1450), (4, "HEAD-SERVO", 1500)]:
        px, _ = c.ports[f"{name}.+"]
        gx, _ = c.ports[f"{name}.−"]
        C(f"W2.{n}", f"{name}.+", RED, [(c.ports[f"W2.{n}"][0], y), (px, y)])
        gy = 1840 + n * 50
        C(f"W4.{n}", f"{name}.−", BLK, [(c.ports[f"W4.{n}"][0], gy), (gx, gy)])
    # Individual GPIO wires, from actual numbered header contacts.
    for pin, port, lane, y in [
        (1, "V", 520, 620),
        (6, "G", 500, 812),
        (12, "DAT", 480, 832),
        (32, "CLK", 460, 892),
    ]:
        px, py = c.ports[f"Pi.{pin}"]
        tx, ty = c.ports[f"S1.{port}"]
        # Even contacts escape downward before turning left, clear of odd contacts.
        via = py if pin % 2 else y
        C(
            f"Pi.{pin}",
            f"S1.{port}",
            PURPLE if port == "V" else BLK if port == "G" else BLUE,
            [(px, via), (lane, via), (lane, ty)],
        )
    for pin, port, lane, y in [
        (17, "V", 900, 620),
        (9, "G", 920, 640),
        (33, "DAT", 940, 660),
        (36, "CLK", 1020, 680),
    ]:
        px, py = c.ports[f"Pi.{pin}"]
        tx, ty = c.ports[f"S2.{port}"]
        via = y if pin % 2 else 790
        C(
            f"Pi.{pin}",
            f"S2.{port}",
            PURPLE if port == "V" else BLK if port == "G" else BLUE,
            [(px, via), (lane, via), (lane, ty)],
        )
    C("S1.D5", "H3.inDATA", BLUE, [(850, 430), (850, 320), (1330, 320), (1330, 810)])
    C(
        "S1.C5",
        "LEFT.SIG",
        BLUE,
        [(870, 500), (870, 570), (1360, 570), (1360, 1210), (1760, 1210)],
    )
    C("S2.D5", "RIGHT.SIG", BLUE, [(1350, 430), (1350, 1180), (2080, 1180)])
    C("S2.C5", "HEAD-SERVO.SIG", BLUE, [(1370, 500), (1370, 1250), (2400, 1250)])
    # Four separate button leads; only its LED-positive wire has R1.
    C("Pi.4", "R1.out", RED, [(638, 792), (435, 792), (435, 650)])
    C("R1.in", "BTN.LED+", RED, [(275, 650), (275, 770)])
    C("Pi.20", "BTN.LED−", BLK, [(782, 872), (360, 872), (360, 800)])
    C("Pi.11", "BTN.SW1", BLUE, [(710, 700), (400, 700), (400, 830)])
    C("Pi.14", "BTN.SW2", BLK, [(728, 852), (380, 852), (380, 860)])
    C("Pi.USB", "AUDIO.USB", PURPLE, [(1055, 880), (1055, 915)], cable=True)
    C("AUDIO.L+", "SPK-L.+", GREEN, [(1285, 887), (1285, 990), (1045, 990)])
    C("AUDIO.L−", "SPK-L.−", PURPLE, [(1295, 905), (1295, 1010), (1075, 1010)])
    C("AUDIO.R+", "SPK-R.+", GREEN, [(1305, 935), (1305, 1030), (1225, 1030)])
    C("AUDIO.R−", "SPK-R.−", PURPLE, [(1320, 953), (1320, 1050), (1255, 1050)])
    # One continuous lighting network, with two detachable plugs.
    C("H3.out+", "body+.wire", RED, [(1480, 780)])
    C("body+.wire", "body0.in+", RED)
    C("body+.wire", "HEAD.in+", RED, [(1480, 535)])
    C("H3.out−", "body−.wire", BLK, [(1500, 840)])
    C("body−.wire", "body0.in−", BLK)
    C("body−.wire", "HEAD.in−", BLK, [(1500, 595)])
    C("H3.outDATA", "R2.in", BLUE)
    C("R2.out", "body0.inDATA", BLUE, [(1640, 810), (1640, 730)])
    for i in range(5):
        for port, color in [("+", RED), ("DATA", BLUE), ("−", BLK)]:
            C(f"body{i}.out{port}", f"body{i + 1}.in{port}", color)
    C(
        "body5.outDATA",
        "HEAD.inDATA",
        BLUE,
        [(2450, 730), (2450, 630), (1460, 630), (1460, 565)],
    )
    C("HEAD.out+", "head+.wire", RED, [(1630, 535), (1630, 150)])
    C("head+.wire", "eye6.in+", RED, [(1710, 240)])
    C("head+.wire", "mouth.+", RED, [(2380, 150)])
    C("HEAD.out−", "head−.wire", BLK, [(1650, 595), (1650, 450)])
    C("head−.wire", "eye6.in−", BLK, [(1690, 280)])
    C("head−.wire", "mouth.−", BLK, [(2470, 450)])
    C("HEAD.outDATA", "eye6.inDATA", BLUE, [(1670, 565), (1670, 260)])
    for port, color in [("+", RED), ("DATA", BLUE), ("−", BLK)]:
        C(f"eye6.out{port}", f"eye7.in{port}", color)
    C("eye7.outDATA", "mouth.DIN", BLUE, [(2150, 260), (2150, 270)])
    return c


def label(g, x, y, s, size=24, **kw):
    g.text(x, y, s, size=size, **kw)


def draw_node(g, n, c):
    x, y, name, kind = n.x, n.y, n.name, n.kind
    if kind == "joint":
        g.dot(x, y, RED if name.endswith("+") else BLK, 6)
        return
    title_y = y - 25
    if kind in ("jack", "button", "speaker"):
        title_y = y - 85
    if kind == "pi":
        title_y = y - 35
    if kind == "jack":
        label(g, x - 100, title_y, n.label, 24, weight=700)
    elif kind == "button":
        label(g, x - 120, title_y, n.label, 24, weight=700)
    elif kind == "speaker":
        label(g, x, y + 75, n.label, 22, weight=700, anchor="middle")
    elif kind == "audio":
        label(g, x + 190, y - 35, n.label, 22, weight=700, anchor="end")
    elif kind == "supply":
        label(g, x, y - 60, "External supply", 21, weight=700)
    elif kind == "pi":
        pass
    elif name == "H3":
        label(g, x, y + 144, n.label, 22, weight=700)
    elif name == "HEAD":
        label(g, x + 190, y + 20, n.label, 22, weight=700)
    elif name == "R2":
        label(g, x + 50, y + 48, n.label, 24, weight=700)
    elif name == "C2":
        label(g, x, y - 45, "C2", 24, weight=700)
        label(g, x + 70, y - 25, "1000 µF / 10 V", 18, anchor="end")
    else:
        label(g, x, title_y, n.label or name, 24, weight=700)
    if kind.startswith("wago"):
        vertical = kind == "wago-v"
        g.rect(
            x,
            y,
            80 if vertical else 300,
            270 if vertical else 70,
            fill="#e2dfd6",
            stroke=GRAY,
            rx=8,
        )
        for i in range(5):
            px, py = c.ports[f"{name}.{i + 1}"]
            lx, ly = (x + 15, py - 15) if vertical else (px - 14, y + 7)
            g.rect(lx, ly, 28, 30, fill="#ec8a38", stroke="#995821", rx=4)
            label(g, lx + 14, ly + 22, str(i + 1), 18, anchor="middle", weight=700)
            g.circle(px, py, 6, fill="#45474a", stroke=GRAY)
            g.wire(
                [(x + 56, py), (px - 7, py)]
                if vertical
                else [(px, y + 48), (px, py - 7)],
                "#ad8557",
                2,
            )
        # Internal copper bus: every port in the block shares one connection.
        g.wire(
            [(x + 56, y + 28), (x + 56, y + 246)]
            if vertical
            else [(x + 22, y + 48), (x + 278, y + 48)],
            "#ad8557",
            4,
        )
    elif kind == "supply":
        g.rect(x, y, 140, 90, fill="#353c43", rx=13)
        label(g, x + 70, y + 36, "5 V DC", 22, fill="#fff", anchor="middle", weight=700)
        label(g, x + 70, y + 64, "5 A", 20, fill="#fff", anchor="middle")
    elif kind == "jack":
        g.circle(x, y, 60, fill="#c5cbd0", stroke=INK)
        g.circle(x, y, 44, fill="#343940", stroke=INK)
        for yy in [y - 20, y + 20]:
            g.rect(x + 48, yy - 5, 12, 10, fill="#bcc5ca", rx=1)
        label(g, x + 67, y - 25, "+", 18, fill=RED, weight=700)
        label(g, x + 67, y + 37, "−", 18, weight=700)
        label(g, x - 100, y + 82, "Unused lug insulated", 18, fill=MUTED)
    elif kind == "fuse":
        g.wire([(x, y + 20), (x + 180, y + 20)], RED, 5)
        g.rect(x + 30, y + 4, 120, 32, fill="#32383e", rx=11)
        g.rect(x + 110, y + 1, 20, 38, fill="#535c64", rx=3)
        for dx in range(38, 100, 9):
            g.wire([(x + dx, y + 7), (x + dx, y + 33)], "#757c82", 1)
    elif kind == "cap":
        g.rect(x, y, 70, 95, fill="#314a59", rx=9)
        g.add(
            f'<ellipse cx="{x + 35}" cy="{y}" rx="35" ry="9" fill="#c2c9cb" stroke="{INK}" stroke-width="2"/>'
        )
        g.wire([(x + 17, y), (x + 53, y)], GRAY, 2)
        g.wire([(x + 35, y - 5), (x + 35, y + 5)], GRAY, 2)
        g.rect(x + 51, y + 10, 14, 77, fill="#d2d9d7", stroke="none", rx=0)
        for yy in [28, 52, 76]:
            label(g, x + 58, y + yy, "−", 17, anchor="middle")
        label(g, x + 25, y + 55, name, 20, anchor="middle", fill="#fff", weight=700)
        g.wire([(x + 17, y + 95), c.ports[name + ".+"]], RED, 4)
        g.wire([(x + 54, y + 95), c.ports[name + ".−"]], BLK, 4)
    elif kind == "pi":
        g.rect(x, y, 400, 310, fill="#397750", rx=14)
        for xx in [x + 14, x + 386]:
            for yy in [y + 14, y + 296]:
                g.circle(xx, yy, 6, fill=PAPER, stroke="#d6bd71")
        g.rect(x + 10, y + 4, 366, 47, fill="#22292c", rx=3)
        # Header is drawn over its wires at the end, keeping all contacts visible.
        g.rect(x + 145, y + 198, 92, 82, fill="#bdc6c9", rx=3)
        g.rect(x + 42, y + 199, 67, 61, fill="#bac5c7", rx=3)
        g.rect(x + 375, y + 134, 25, 52, fill="#bbc4cc", rx=2)
        g.rect(x + 72, y + 285, 56, 25, fill="#bbc4cc", rx=3)
        label(g, x + 275, y + 119, "USB", 19, fill="#fff")
        label(g, x + 267, y + 262, "Pi 3A+", 23, fill="#fff", weight=700)
        label(g, x + 139, y + 288, "POWER", 19, fill="#fff")
        # Repaint the short local escape segments over the PCB (not hidden by it).
        for e in c.edges:
            if e.source.startswith("Pi.") and e.source.split(".")[1].isdigit():
                p = c.ports[e.source]
                local = [p, *e.bends[:2]]
                g.wire(local, PAPER, 8, linecap="butt")
                g.wire(local, e.color, 3)
        used = {1, 6, 12, 32, 17, 9, 33, 36, 11, 14, 4, 20}
        for pin in range(1, 41):
            px, py = c.ports[f"Pi.{pin}"]
            g.circle(
                px,
                py,
                4,
                fill="#dbbd69",
                stroke="#fff" if pin in used else "none",
                sw=1,
            )
            if pin in used:
                stagger = ((pin - 1) // 2 % 2) * 18
                baseline = py - 10 - stagger if pin % 2 else py + 22 + stagger
                g.rect(
                    px - 11, baseline - 16, 22, 21, fill="#22292c", stroke="none", rx=3
                )
                label(
                    g,
                    px,
                    baseline,
                    str(pin),
                    17,
                    fill="#fff",
                    anchor="middle",
                    weight=700,
                )
    elif kind == "shifter":
        g.rect(x, y, 200, 180, fill="#343940", rx=8)
        for p in ["V", "G", "DAT", "CLK", "D5", "C5"]:
            px, py = c.ports[f"{name}.{p}"]
            right = px > x
            g.rect(px - 28 if right else px, py - 13, 28, 26, fill="#467ab0", rx=2)
            g.circle(px - 14 if right else px + 14, py, 7, fill="#c7cdd0", stroke=GRAY)
            label(
                g,
                px - 37 if right else px + 38,
                py + 6,
                p,
                18,
                fill="#fff",
                anchor="end" if right else "start",
            )
        label(g, x + 8, y + 173, "Neo cut · !D5 unused", 14, fill="#fff")
    elif kind == "servo":
        g.rect(x, y, 107, 84, fill="#32383e", rx=6)
        g.rect(x - 10, y + 13, 127, 13, fill="#535b64", rx=2)
        g.circle(x + 29, y, 19, fill="#c1b193", stroke=INK)
        g.circle(x + 29, y, 7, fill="#5d6061", stroke=INK)
        for i, (p, col) in enumerate([("+", RED), ("−", BLK), ("SIG", BLUE)]):
            px, py = c.ports[f"{name}.{p}"]
            g.wire([(px, y + 84), (px, py)], col, 4)
            label(g, px, py + 23, p, 14, fill=col, anchor="middle", weight=700)
    elif kind == "button":
        g.circle(x, y + 20, 70, fill="#bbc4ca", stroke=INK)
        g.circle(x, y + 20, 58, fill="#343940", stroke=INK)
        for p in ["LED+", "LED−", "SW1", "SW2"]:
            px, py = c.ports[f"{name}.{p}"]
            g.rect(px - 24, py - 5, 24, 10, fill="#bcc7ce", rx=1)
            label(
                g,
                x + 15,
                max(y - 28, min(py + 5, y + 66)),
                p,
                15,
                fill="#fff",
                anchor="end",
            )
    elif kind == "resistor":
        g.wire([(x, y), (x + 150, y)], GRAY, 4)
        g.rect(x + 30, y - 14, 90, 28, fill="#e5c798", rx=12)
        colors = (
            ["#77452e", "#171b20", "#c4302b", "#be9b36"]
            if name == "R1"
            else ["#df7d26", "#df7d26", "#77452e", "#be9b36"]
        )
        for i, col in enumerate(colors):
            g.rect(x + 42 + i * 19, y - 13, 7, 26, fill=col, stroke="none", rx=0)
    elif kind == "audio":
        g.rect(x, y, 180, 90, fill="#444b52", rx=8)
        for xx in [x + 25, x + 50]:
            g.circle(xx, y + 35, 7, fill="#161b1f", stroke=GRAY)
        for p in ["L+", "L−", "R+", "R−"]:
            px, py = c.ports[f"{name}.{p}"]
            label(g, px - 10, py + 5, p, 14, fill="#fff", anchor="end")
    elif kind == "speaker":
        g.rect(x - 50, y - 40, 100, 80, fill="#454d54", rx=9)
        # Meet the routed cable ends with short tails entering the housing.
        for p, dx, color in [("+", -15, GREEN), ("−", 15, PURPLE)]:
            g.wire([c.ports[f"{name}.{p}"], (x + dx, y - 35)], color, 4)
        for r, fill in [(34, "#929ca2"), (27, "#41494f"), (11, "#b9c0c4")]:
            g.circle(x, y, r, fill=fill, stroke=INK)
    elif kind == "plug":
        g.rect(x, y, 40, 84, fill="#30343a", rx=4)
        g.rect(x + 44, y, 40, 84, fill="#454b52", rx=4)
        g.rect(x + 28, y - 8, 26, 10, fill="#697078", rx=2)
        for p, col in [("+", RED), ("DATA", BLUE), ("−", BLK)]:
            a, b = c.ports[f"{name}.in{p}"], c.ports[f"{name}.out{p}"]
            g.wire([a, b], col, 4)
        label(g, x + 100, y + 18, "+", 18, fill=RED)
        label(g, x + 100, y + 48, "D", 18, fill=BLUE)
        label(g, x + 100, y + 78, "−", 18)
    elif kind in ("eye", "pebble"):
        g.rect(
            x,
            y,
            60,
            60,
            fill="#2b3438" if kind == "eye" else "#e7e2d3",
            stroke=GRAY,
            rx=7 if kind == "eye" else 22,
        )
        g.rect(x + 16, y + 16, 28, 28, fill="#fcfcf7", stroke="#aeb7b6", rx=3)
        g.rect(x + 24, y + 24, 12, 12, fill="#e5ddb0", stroke="none", rx=2)
        if kind == "eye":
            for xx in [x - 3, x + 55]:
                g.rect(xx, y + 5, 8, 50, fill="#e6e6dc", rx=2)
            label(g, x, y + 91, "IN → OUT", 17)
    elif kind == "mouth":
        g.rect(x, y, 280, 60, fill="#283436", rx=4)
        for i in range(8):
            xx = x + 13 + i * 32
            g.rect(xx, y + 18, 23, 24, fill="#fcfcf7", stroke="#aeb7b6", rx=2)
            g.rect(xx + 7, y + 25, 9, 9, fill="#e5ddb0", stroke="none", rx=1)
        for p in ["DIN", "+", "−"]:
            px, py = c.ports[f"{name}.{p}"]
            g.circle(px, py, 5, fill="#c8a96a", stroke=GRAY)
        label(g, x, y + 93, "DOUT unused", 18, fill=MUTED)


def draw():
    c = circuit()
    g = Svg(WIDTH, HEIGHT, "BlooglyBlob · complete wiring")
    label(
        g,
        28,
        80,
        "Every component appears once. Follow each continuous wire from its source to its destination.",
        25,
        fill=MUTED,
    )
    for x, col, title in [
        (30, RED, "+5 V"),
        (200, BLK, "Ground"),
        (415, BLUE, "Signal / data"),
        (685, PURPLE, "3.3 V or USB cable"),
    ]:
        g.wire([(x, 113), (x + 40, 113)], col, 5)
        label(g, x + 52, 121, title, 21)
    label(
        g,
        1120,
        121,
        "● Joined wires     Crossings without a dot are not connected.",
        21,
    )
    # Zones locate assemblies without pretending that schematic positions are CAD.
    for x, y, w, h, title in [
        (35, 170, 1330, 1900, "ENCLOSURE"),
        (1430, 660, 1170, 650, "BODY / STATIONARY FRAME"),
        (1590, 170, 1010, 320, "HEAD LIGHTING"),
    ]:
        g.rect(x, y, w, h, fill="#f3f1eb", stroke="#d8d3c9", sw=2, rx=18)
        label(
            g,
            x + 210 if title == "HEAD LIGHTING" else x + 18,
            y + 35
            if title == "ENCLOSURE"
            else 975
            if title.startswith("BODY")
            else 440,
            title,
            22,
            fill=MUTED,
            weight=700,
        )
    # Edges are drawn beneath component bodies; contacts meet the component edge.
    for e in c.edges:
        pts = [c.ports[e.source], *e.bends, c.ports[e.target]]
        g.add(
            f'<g data-from="{escape(e.source)}" data-to="{escape(e.target)}"><title>{escape(e.source)} to {escape(e.target)}</title>'
        )
        g.wire(pts, PAPER, 11 if e.cable else 9, linecap="butt")
        g.wire(pts, e.color, 7 if e.cable else 4)
        g.add("</g>")
    for n in c.nodes:
        g.add(
            f'<g data-component="{escape(n.name)}"><title>{escape(n.label or n.name)}</title>'
        )
        draw_node(g, n, c)
        g.add("</g>")
    # Single H2 plug enters the Pi's single POWER socket, not a second Pi drawing.
    g.rect(678, 1030, 44, 50, fill="#323940", rx=6)
    g.rect(685, 1030, 30, 13, fill="#bcc5cb", rx=2)
    label(g, 748, 1048, "H2 · micro-USB", 20, weight=700)
    label(g, 748, 1075, "≤150 mm incl. plug", 18, fill=MUTED)
    # Exposed unused output power tails are capped individually.
    for name in ["body5", "eye7"]:
        for p, col in [("+", RED), ("−", BLK)]:
            x, y = c.ports[f"{name}.out{p}"]
            g.wire([(x, y), (x + 27, y)], col, 4)
            g.rect(x + 22, y - 5, 14, 10, fill="#434d56", rx=3)
    label(g, 2170, 385, "Eye OUT + / − insulated", 19, fill=MUTED)
    label(g, 2270, 805, "Last pebble + / − insulated", 19, fill=MUTED)
    label(g, 1860, 865, "Body data → eyes → mouth", 25, weight=700)
    label(g, 1730, 915, "Head power branches before body pixel 0.", 22, fill=MUTED)
    label(g, 1780, 390, "JST-SH: 5755 → eyes via 6404 → 5755", 20, fill=MUTED)
    label(g, 900, 1224, "Speaker outputs stay separate from ground.", 18, fill=MUTED)
    label(
        g,
        70,
        2035,
        "WAGO ports within each block are internally joined. W1/5 and W4/5 stay empty.",
        21,
    )
    label(
        g,
        1440,
        2070,
        "Positions and connector contact order are schematic. Use the step close-ups for assembly.",
        21,
        fill=MUTED,
    )
    g.add(
        "<desc>One connected wiring diagram. All external wires run continuously between component terminals; no named off-sheet continuations. Pi numbers are physical header pins. HEAD and H3 are three-contact detachable lighting connectors. Three servos connect directly to WAGO power and ground and shifter signal terminals.</desc>"
    )
    return g


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    diagrams.OUT = args.out.parent
    args.out.parent.mkdir(parents=True, exist_ok=True)
    draw().save(args.out.name)


if __name__ == "__main__":
    main()
