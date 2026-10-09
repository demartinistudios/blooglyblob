#!/usr/bin/env python3
"""Draw the guide's schematic SVG diagrams into hardware/build-guide/src/assets/.

Plans are schematic: positions follow the base layout but are not to scale.
"""
import re
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[3] / 'hardware/build-guide/src/assets'
INK, MUTED, PAPER, LINE = '#292b3b', '#5c6070', '#fbfaf6', '#c9c7c0'
RED, BLK, BLUE, GRAY, COPPER, ORANGE = '#c4302b', '#26262b', '#2f6fb5', '#8d939a', '#875b46', '#c8601d'
LEAD = '#3a3d44'  # Adafruit 1663 JST-SM leads: black, labeled by function
SERVO_BROWN, SERVO_ORANGE = '#6b4329', '#ee8a2c'  # Kitronik FS90MG-CL ground and signal; supply is RED
SHRINK, SHRINK_EDGE = '#47515b', '#1c2126'  # every heat-shrink sleeve, waiting or shrunk
SHRINK_OVER = .5  # a sleeve over a resistor lets the resistor show through
SOLDER = '#c2c9cb'  # a bare solder joint, before it is covered
FONT = 'Arial,Helvetica,sans-serif'


class Svg:
    """A drawing labels what it shows. It has no drawn title, view line or notes:
    the guide caption gives the view and the actions give instructions."""

    def __init__(self, w, h, title, crop=False):
        self.w, self.h, self.title, self.crop, self.parts = w, h, title, crop, []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill='#fff', stroke=INK, sw=2, rx=6, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def circle(self, x, y, r, fill='#fff', stroke=INK, sw=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=18, fill=INK, weight=400, anchor='start', rotate=None, italic=False):
        t = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ''
        st = ' font-style="italic"' if italic else ''
        self.add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"{t}{st}>{escape(s)}</text>')

    def wire(self, pts, color, sw=4, dash=None, arrow=False, linecap='round'):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        m = ' marker-end="url(#arrow)"' if arrow else ''
        path = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
        self.add(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="{linecap}"{d}{m}/>')

    def dot(self, x, y, color, r=5):
        self.circle(x, y, r, fill=color, stroke=color, sw=1)

    def label(self, x, y, s, size=16, fill=INK, anchor='start', weight=400, pad=4):
        # Text on a paper-colored backing so it stays legible over wires.
        w = len(s) * size * 0.55 + pad * 2
        x0 = x - pad if anchor == 'start' else x - w / 2 if anchor == 'middle' else x - w + pad
        self.add(f'<rect x="{x0:.1f}" y="{y - size + 1}" width="{w:.1f}" height="{size + 6}" rx="3" fill="{PAPER}" opacity=".92"/>')
        self.text(x, y + 1, s, size=size, fill=fill, anchor=anchor, weight=weight)

    def extent(self):
        """Vertical extent of the drawn content, so the view crops to it."""
        ys = []
        for part in self.parts:
            tag = part[1:part.index(' ')]
            a = dict(re.findall(r'([\w-]+)="([^"]*)"', part[:part.index('>')]))
            if tag == 'rect':
                ys += [float(a['y']), float(a['y']) + float(a['height'])]
            elif tag == 'circle':
                ys += [float(a['cy']) - float(a['r']), float(a['cy']) + float(a['r'])]
            elif tag == 'ellipse':
                ys += [float(a['cy']) - float(a['ry']), float(a['cy']) + float(a['ry'])]
            elif tag == 'text':
                y, size = float(a['y']), float(a['font-size'])
                length = len(re.sub('<[^>]+>', '', part)) * size * 0.6
                ys += [y - (length if 'rotate(' in part else size), y + size * 0.3]
            elif tag in ('path', 'polygon'):
                own = []
                if tag == 'polygon':
                    own = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', a['points'])][1::2]
                else:
                    tokens = re.findall(r'[MLHVQCAZ]|-?\d+(?:\.\d+)?', a['d'])
                    i, command = 0, 'M'
                    while i < len(tokens):
                        if tokens[i] in 'MLHVQCAZ':
                            command = tokens[i]; i += 1; continue
                        take = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'Q': 4, 'C': 6, 'A': 7}[command]
                        values = [float(v) for v in tokens[i:i + take]]; i += take
                        if command == 'V':
                            own.append(values[0])
                        elif command == 'A':
                            own += [values[6] - values[1], values[6] + values[1]]
                        elif command != 'H':
                            own += values[1::2]
                width = float(a.get('stroke-width', 0))
                ys += [min(own) - width / 2, max(own) + width / 2]
        return min(ys), max(ys)

    def save(self, name):
        top, height = 0, self.h
        if self.crop:
            low, high = self.extent()
            top, height = max(0, int(low) - 18), int(high) + 18 - max(0, int(low) - 18)
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {top} {self.w} {height}" width="{self.w}" height="{height}" role="img">'
                f'<title>{escape(name)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0 0 L10 5 L0 10z" fill="{BLUE}"/></marker></defs>'
                f'<rect x="0" y="{top}" width="{self.w}" height="{height}" fill="{PAPER}"/>')
        (OUT / name).write_text(head + ''.join(self.parts) + '</svg>\n')


# ------------------------------------------------------------------ servo fit position
def robot_front(g, cx, base_y, arm_angle_deg=0, dashed=False, arms=True):
    import math
    body = '#5b5fa8'
    # base and body
    g.rect(cx - 120, base_y - 60, 240, 60, fill='#34343c', stroke=INK, rx=8)
    g.rect(cx - 70, base_y - 250, 140, 190, fill='#f2efe6', stroke=INK, rx=26)
    # head
    g.circle(cx, base_y - 320, 72, fill=body, stroke=INK, sw=3)
    for dx in (-26, 26):
        g.circle(cx + dx, base_y - 332, 15, fill='#c98a5a', stroke=INK)
        g.circle(cx + dx, base_y - 332, 7, fill='#fff', stroke='none')
    g.add(f'<path d="M{cx - 26} {base_y - 296} Q{cx} {base_y - 276} {cx + 26} {base_y - 296}" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>')
    g.wire([(cx, base_y - 392), (cx, base_y - 420)], '#5b5fa8', 5)
    g.circle(cx, base_y - 426, 9, fill='#d9e4f5', stroke=INK)
    if arms:
        for side in (-1, 1):
            sx, sy = cx + side * 84, base_y - 230
            g.circle(sx, sy, 14, fill='#c98a5a', stroke=INK)
            g.add(f'<rect x="{sx - 13}" y="{sy}" width="26" height="150" rx="13" fill="{body}" stroke="{INK}" stroke-width="2"/>')
            g.circle(sx, sy + 162, 15, fill=body, stroke=INK)


def servo_fit_position():
    g = Svg(1200, 700, 'Fit position', crop=True)
    robot_front(g, 300, 620)
    g.text(300, 650, 'Front view', size=18, anchor='middle', weight=700)
    g.label(120, 180, 'Head faces forward', size=17, weight=700, anchor='middle')
    g.label(88, 540, 'Arms hang', size=17, weight=700, anchor='middle')
    g.label(88, 562, 'straight down', size=17, weight=700, anchor='middle')
    # Side view with the raise range
    cx, by = 820, 620
    g.rect(cx - 90, by - 60, 180, 60, fill='#34343c', stroke=INK, rx=8)
    g.rect(cx - 60, by - 250, 120, 190, fill='#f2efe6', stroke=INK, rx=26)
    g.circle(cx, by - 320, 72, fill='#5b5fa8', stroke=INK, sw=3)
    g.circle(cx + 58, by - 332, 13, fill='#c98a5a', stroke=INK)
    sx, sy = cx, by - 230
    g.circle(sx, sy, 14, fill='#c98a5a', stroke=INK)
    g.add(f'<rect x="{sx - 13}" y="{sy}" width="26" height="150" rx="13" fill="#5b5fa8" stroke="{INK}" stroke-width="2"/>')
    g.add(f'<rect x="{sx}" y="{sy - 13}" width="150" height="26" rx="13" fill="none" stroke="#5b5fa8" stroke-width="3" stroke-dasharray="8 6"/>')
    g.add(f'<path d="M{sx + 40} {sy + 120} A 125 125 0 0 0 {sx + 125} {sy + 30}" fill="none" stroke="{ORANGE}" stroke-width="3" marker-end="url(#arrow)"/>')
    g.text(cx + 170, sy - 20, 'raises to about level', size=16, fill=MUTED)
    g.text(cx + 170, sy + 2, 'in front (dashed)', size=16, fill=MUTED)
    g.text(cx - 40, 650, 'Side view (robot facing right)', size=18, anchor='middle', weight=700)
    g.text(cx + 150, by - 420, 'FRONT →', size=16, fill=MUTED, weight=700)
    g.save('servo-fit-position.svg')


# ------------------------------------------------------------------ phone-readable circuit actions
# Every figure is a schematic: component silhouettes help identification, but
# terminal positions on unverified products are never claimed as a pinout.
CIRCUIT_WIDTH = 420


def action(title, height=620):
    return Svg(CIRCUIT_WIDTH, height, title, crop=True)


def lines(g, y, *rows, color=INK):
    for i, row in enumerate(rows):
        g.text(24, y + i * 29, row, size=22, fill=color)


def wago_port(g, y, block, port, color, label_above=False):
    """Front wire-entry face; adopted mounted order is 5,4,3,2,1."""
    if label_above:
        g.text(205, y - 63, f'{block} / port {port}', size=25, weight=700)
    else:
        g.text(24, y, f'{block} / port {port}', size=25, weight=700)
    g.rect(205, y - 53, 186, 72, fill='#e5e1d6', stroke=GRAY, rx=9)
    selected_x = 228 + (5 - port) * 35
    for n in range(5):
        x = 216 + n * 35
        active = 5 - n == port
        g.rect(x, y - 44, 25, 30, fill='#eb8b3e', stroke=color if active else '#9c5420', sw=3 if active else 1, rx=4)
        g.text(x + 12, y - 22, str(5 - n), size=22, anchor='middle', weight=700)
        g.circle(x + 12, y + 1, 7, fill=color if active else '#444', stroke=color if active else GRAY)
    if not getattr(g, 'physical_wires', False):
        g.wire([(24, y + 26), (selected_x, y + 26), (selected_x, y + 7)], color, 6)


def joint(g, x, y, color):
    g.circle(x, y, 8, fill=SOLDER, stroke=color, sw=3)


RESISTORS = {
    'R1': ('1 kΩ', ('#7c4a31', '#222', '#b63226')),
    'R2': ('330 Ω', ('#d06924', '#d06924', '#7c4a31')),
}


def resistor(g, x, y, key):
    g.wire([(x - 27, y), (x + 117, y)], GRAY, 4)
    g.rect(x, y - 15, 90, 30, fill='#e5c798', stroke=INK, rx=12)
    value, colors = RESISTORS[key]
    for i, col in enumerate((*colors, '#be9b36')):
        g.rect(x + 12 + i * 19, y - 14, 7, 28, fill=col, stroke='none', rx=0)
    g.text(x + 45, y - 30, f'{key} · {value}', size=24, anchor='middle', weight=700)


def capacitor(g, y, name):
    g.rect(153, y, 114, 126, fill='#314a59', stroke=INK, rx=12)
    g.add(f'<ellipse cx="210" cy="{y}" rx="57" ry="13" fill="#b8c0c1" stroke="{INK}" stroke-width="2"/>')
    g.wire([(184, y), (236, y)], GRAY, 2)
    g.wire([(210, y - 8), (210, y + 8)], GRAY, 2)
    g.rect(235, y + 14, 25, 104, fill='#ced7d5', stroke='none', rx=0)
    for dy in (39, 69, 99):
        g.text(247, y + dy, '−', size=24, anchor='middle')
    g.text(192, y + 69, name, size=27, fill='#fff', anchor='middle', weight=700)
    g.wire([(180, y + 126), (180, y + 162)], RED, 5)
    g.wire([(244, y + 126), (244, y + 162)], BLK, 5)
    # Polarity is identified by the stripe and separately colored tails.


def fuse_holder(g, y, name, value):
    g.wire([(55, y + 39), (365, y + 39)], RED, 7)
    g.rect(114, y + 12, 96, 54, fill='#202d38', stroke=INK, rx=17)
    g.rect(210, y + 12, 96, 54, fill='#354653', stroke=INK, rx=17)
    for x in (132, 145, 158, 263, 276, 289):
        g.wire([(x, y + 21), (x, y + 57)], '#819098', 2)
    g.text(210, y - 8, f'{name} · {value}', size=26, anchor='middle', weight=700)


def physical_action(title, height=620):
    g = action(title, height)
    g.physical_wires = True
    return g


def port_point(port, y):
    return (228 + (5 - port) * 35, y + 1)


def shrink(g, x, y, w, h, rx=4):
    """Heat-shrink, drawn the same in every picture whatever color the builder uses.

    A joint, leg or part the actions sleeve is drawn under heat-shrink in the picture
    of the panel that sleeves it and in every later picture. Only a panel that solders
    and leaves the shrinking to a later panel shows the sleeve waiting on its lead."""
    g.rect(x, y, w, h, fill=SHRINK, stroke=SHRINK_EDGE, sw=1, rx=rx)


def shrink_over(g, x, y, w, h, rx=4):
    """Heat-shrink over a resistor: the same sleeve, see-through so the part inside shows."""
    g.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{SHRINK}" '
          f'fill-opacity="{SHRINK_OVER}" stroke="{SHRINK_EDGE}" stroke-width="1"/>')


def shrink_wire(g, pts, sw=12):
    """Heat-shrink along a bent leg or lead."""
    g.wire(pts, SHRINK_EDGE, sw + 2)
    g.wire(pts, SHRINK, sw)


def sleeve(g, x, y, length=46):
    shrink(g, x - 9, y, 18, length)


JST_BODY = '#303740'
JST_TRIM = '#58626c'
STRAND_WIRES = (RED, '#2f8f64', '#26262b')  # pebble strand pigtail: +5 V, DATA, GND


def jst_sm_half(g, kind, face_x, cy, facing='right', open_face=True):
    """JST-SM 2.5 mm half seen from its latch side; contacts +5 V, DATA, GND top to bottom.

    Seen from the latch side, that order holds for a sockets half facing right and a pins
    half facing left (the two mate). A pins half facing right is seen from below.

    'pins' is the larger housing: an open shroud with three pins set back inside it and a
    catch on top. 'sockets' is the smaller housing: three socket holes in its face and the
    press latch on its latch side; it slides into the shroud. open_face cuts the shroud's near wall
    away to show the pins; a mated pins half is drawn closed. Returns the x where its
    wires leave.
    """
    s = 1 if facing == 'right' else -1

    def box(back, front, y, h, **kw):
        # back/front: distance behind the mating face.
        a, b = face_x - s * back, face_x - s * front
        g.rect(min(a, b), y, abs(a - b), h, **kw)

    if kind == 'pins':
        length = 96
        box(length, 0, cy - 29, 58, fill=JST_BODY, rx=4)
        if open_face:
            box(34, 0, cy - 23, 46, fill='#0f1317', stroke='none', rx=1)
            for dy in (-14, 0, 14):
                box(34, 10, cy + dy - 2.5, 5, fill='#d3d8db', stroke='#8d939a', sw=1, rx=1)
        else:
            box(28, 12, cy - 5, 10, fill='#171b20', stroke='none', rx=1)
    else:
        length = 76
        box(length, 0, cy - 21, 42, fill=JST_BODY, rx=4)
        for dy in (-14, 0, 14):
            box(10, 2, cy + dy - 4, 8, fill='#05070a', stroke='#8d939a', sw=1, rx=1)
        box(56, 14, cy - 7, 14, fill=JST_TRIM, rx=3)
        box(24, 14, cy - 7, 14, fill='#7d8790', stroke='none', rx=2)
    for dy in (-14, 0, 14):
        box(length - 2, length - 12, cy + dy - 4, 8, fill='#171b20', stroke='none', rx=1)
    return face_x - s * length


def jst_sm_face(g, kind, cx, cy):
    """JST-SM mating face seen end-on, latch up: pins in an open shroud, or three socket holes."""
    if kind == 'pins':
        g.rect(cx - 40, cy - 25, 80, 50, fill=JST_BODY, rx=4)
        g.rect(cx - 33, cy - 18, 66, 36, fill='#0f1317', stroke='none', rx=2)
        g.rect(cx - 9, cy - 31, 18, 7, fill=JST_TRIM, rx=2)
        for dx in (-20, 0, 20):
            g.rect(cx + dx - 4, cy - 4, 8, 8, fill='#d3d8db', stroke='#8d939a', sw=1, rx=1)
    else:
        g.rect(cx - 31, cy - 17, 62, 34, fill=JST_BODY, rx=3)
        g.rect(cx - 9, cy - 24, 18, 8, fill=JST_TRIM, rx=2)
        for dx in (-20, 0, 20):
            g.rect(cx + dx - 5, cy - 5, 10, 10, fill='#05070a', stroke='#8d939a', sw=1, rx=1)


def jst_sm_mated(g, join_x, cy):
    """Sockets half (left) pushed into the pins half's shroud (right).

    Returns the wire exits of the sockets half and the pins half."""
    left = jst_sm_half(g, 'sockets', join_x + 30, cy)
    right = jst_sm_half(g, 'pins', join_x, cy, facing='left', open_face=False)
    return left, right


def wago_insertion():
    g = action('Insert a WAGO wire', 469)
    g.text(24, 121, '1 Bare end', size=22)
    g.wire([(35, 157), (229, 157)], RED, 9)
    g.wire([(229, 157), (300, 157)], COPPER, 6)
    g.wire([(229, 179), (300, 179)], MUTED, 2)
    g.text(263, 207, '11 mm', size=22, anchor='middle')
    # Side cutaway of the opened entry; clear housing, hinged orange lever.
    g.rect(231, 262, 146, 71, fill='#dfded5', stroke=GRAY, rx=8)
    g.rect(235, 286, 105, 22, fill='#55564f', rx=2)
    g.add('<path d="M316 275 L329 225 L345 229 L330 280 Z" fill="#ee8b35" stroke="#a25322" stroke-width="2"/>')
    g.wire([(32, 297), (157, 297)], RED, 9)
    g.wire([(157, 297), (209, 297)], COPPER, 6)
    g.wire([(174, 263), (222, 263)], BLUE, 3, arrow=True)
    g.text(24, 245, '2 Lever open', size=22)
    g.save('circuits/wago-insert.svg')


def power_jack_circuit():
    g = physical_action('Insert the power jack leads', 630)
    # Same rear lug rotation as the verified 721AU preparation view.
    g.circle(165, 197, 78, fill='#d8d7cf', stroke=INK, sw=3)
    g.circle(165, 197, 61, fill='#e9e5db', stroke=GRAY)
    g.rect(150, 148, 30, 9, fill='#b9c4c9', rx=0)
    shrink(g, 209, 183, 9, 30, rx=2)
    g.add('<path d="M115 205 L125 235 L134 232 L124 202 Z" fill="#b9c4c9" stroke="#292b3b" stroke-width="2"/>')
    # Labels sit above each WAGO so the ground lead's left-hand run stays clear.
    wago_port(g, 389, 'W1', 1, RED, label_above=True)
    wago_port(g, 526, 'W3', 1, BLK, label_above=True)
    g.wire([(125,226),(125,315),(190,315),(190,432),(368,432),port_point(1,389)], RED, 6)
    g.wire([(165, 152), (49, 152), (49, 570), (368, 570), port_point(1,526)], BLK, 6)
    sleeve(g,125,228,45)
    shrink(g,139,143,44,18)
    g.text(258, 118, 'Sleeve → GND', size=22)
    g.wire([(262,124),(183,150)], MUTED, 1.5)
    g.text(262, 206, 'Unused', size=22)
    g.text(262, 232, 'switched lug', size=22)
    g.wire([(258,206),(219,199)], MUTED, 1.5)
    g.text(141, 295, 'Center pin → +5 V', size=22, fill=RED)
    g.text(24, 609, '18 AWG', size=22)
    g.save('circuits/power-jack-leads.svg')

def pi_power_circuit():
    g = physical_action('Pi power lead', 695)
    pi_bench_board(g, 136, 111, 3.2)
    # Micro-B sits in the bottom-edge power socket, not the USB-A data port.
    g.rect(159, 292, 21, 13, fill='#bcc6cd', rx=1)
    g.rect(154, 304, 31, 45, fill='#303740', rx=5)
    for yy in (318,326,334):
        g.wire([(157,yy),(182,yy)],GRAY,1)
    g.text(24, 307, 'PWR IN', size=22)
    g.wire([(111,302),(148,300),(162,296)],MUTED,1.5)
    wago_port(g, 496, 'W1', 2, RED)
    wago_port(g, 619, 'W3', 2, BLK)
    g.wire([(163,370),(163,539),(333,539),port_point(2,496)],RED,6)
    traced_wire(g,[(176,370),(176,644),(333,644),port_point(2,619)],BLK,6)
    # Cable jacket stripped back; each unused wire ends under its own sleeve.
    g.rect(155,349,36,26,fill='#30343a',rx=3)
    for x, y in ((188,390),(183,406)):
        g.wire([(x,375),(x,y),(236,y)],GRAY,4)
        shrink(g,214,y-7,30,14)
    g.text(254,406,'Unused wires',size=22)
    g.text(24, 672, '24 AWG',size=22)
    g.save('circuits/pi-power.svg')

def fuse_prep(name, value, input_port, output):
    g = action(f'{name} · fuse holder loop', 485)
    fuse_holder(g, 151, name, value)
    g.text(24, 352, '18 AWG', size=22)
    g.wire([(55, 190), (55, 304), (365, 304), (365, 190)], RED, 7)
    g.circle(210, 304, 21, fill=PAPER, stroke=ORANGE, sw=3)
    g.wire([(200, 294), (220, 314)], ORANGE, 3)
    g.wire([(220, 294), (200, 314)], ORANGE, 3)
    g.text(250, 359, 'Cut in the middle', size=22, anchor='middle')
    lines(g, 412, f'INPUT: W1/{input_port}', f'OUTPUT: {output}')
    g.save(f'circuits/{name.lower()}-prepare.svg')


def servo_feed_prepare():
    g = physical_action('Prepare the servo feed', 470)
    g.text(24, 200, 'Red 18 AWG', size=22)
    # One loose insulated conductor, with two untinned copper ends.
    g.wire([(47, 244), (91, 244)], COPPER, 6)
    g.wire([(91, 244), (329, 244)], RED, 10)
    g.wire([(329, 244), (373, 244)], COPPER, 6)
    for left, right in ((47, 91), (329, 373)):
        g.wire([(left, 272), (right, 272)], MUTED, 2)
        g.text((left + right) / 2, 307, '11 mm', size=22, anchor='middle')
    g.save('circuits/servo-feed-prepare.svg')


def servo_feed_circuit():
    g = physical_action('Connect the servo feed', 470)
    wago_port(g, 147, 'W1', 3, RED)
    wago_port(g, 345, 'W2', 1, RED)
    g.wire([port_point(3,147),(298,200),(24,200),(24,280),
            (392,280),(392,392),(368,392),port_point(1,345)],RED,7)
    g.text(60, 251, 'W1/3 → W2/1',size=22,weight=700)
    g.save('circuits/servo-feed-connect.svg')


def c1_circuit():
    g = physical_action('Servo capacitor connections', 680)
    capacitor(g, 123, 'C1')
    # Metal legs, soldered extensions, individual insulating sleeves.
    g.wire([(180,249),(180,308)],'#b9c2c5',4)
    g.wire([(244,249),(244,308)],'#b9c2c5',4)
    wago_port(g, 455, 'W2', 5, RED)
    wago_port(g, 578, 'W3', 4, BLK)
    g.wire([(180,300),(180,496),(228,496),port_point(5,455)],RED,6)
    g.wire([(244,300),(244,350),(392,350),(392,617),(263,617),port_point(4,578)],BLK,6)
    sleeve(g,180,251,75); sleeve(g,244,251,75)
    g.text(24, 121, '1000 µF',size=22)
    g.text(24, 150, '10 V',size=22)
    g.text(24, 356, 'Heat-shrink',size=22)
    g.wire([(126,340),(170,293)],MUTED,1.5)
    g.text(24, 660, '18 AWG tails · stripe is negative',size=22)
    g.save('circuits/c1.svg')

def ground_circuit():
    g = physical_action('Ground link', 365)
    wago_port(g, 147, 'W3', 3, BLK)
    wago_port(g, 298, 'W4', 1, BLK)
    g.wire([port_point(3,147),(298,200),(389,200),(389,342),(368,342),port_point(1,298)],BLK,7)
    g.text(24, 218, 'One 18 AWG wire',size=22)
    g.save('circuits/ground-link.svg')

def c2_circuit():
    g = physical_action('Base half, C2 and R2', 721)
    capacitor(g, 130, 'C2')
    # C2's own legs reach the branch joints directly; there are no wire tails.
    # Each leg is sleeved from the rubber seal to its joint's sleeve.
    for points in (
        [(180,256),(180,314),(107,352),(107,416)],
        [(244,256),(244,314),(322,360),(322,478)],
    ):
        shrink_wire(g, points)
    # F2 output is red 18 AWG; the base half's own leads are black (1663).
    g.wire([(30,416),(107,416)],RED,6)
    g.wire([(107,416),(196,416),(196,573),(229,573)],LEAD,5)
    traced_wire(g,[(30,478),(178,478),(178,587),(229,587)],LEAD,5)
    traced_wire(g,[(322,478),(178,478)],LEAD,5)
    # Finished: each joint and R2 under its own sleeve.
    shrink(g,74,403,67,26)
    shrink(g,289,465,66,26)
    g.wire([(30,531),(160,531),(160,601),(229,601)],LEAD,5)
    small_resistor(g,62,531,'R2',56)
    shrink_over(g,54,519,72,24)
    jst_sm_half(g,'sockets',305,587)
    g.text(24, 390, 'From F2',size=22,fill=RED)
    g.text(24, 453, 'GND → W3/5',size=22)
    g.text(24, 508, 'R2 in DATA',size=22)
    g.text(24, 566, 'To S1 D5',size=22)
    g.text(239, 648, 'Base half',size=22,weight=700)
    g.text(24, 680, 'C2: 1000 µF, 10 V · stripe to GND',size=22)
    g.text(24, 709, 'Base half: JST-SM 2.5 mm (large)',size=22)
    g.save('circuits/c2-prepare.svg')


def f2_circuit():
    g = physical_action('Light fuse connections', 670)
    wago_port(g, 143, 'W1', 4, RED)
    fuse_holder(g, 234, 'F2', 'T1 A')
    wago_port(g, 604, 'W3', 5, BLK)
    g.wire([port_point(4,143),(263,184),(55,184),(55,273)],RED,7)
    g.wire([(365,273),(385,273),(385,384),(178,384)],RED,6)
    g.wire([(178,384),(105,384),(105,466),(256,466)],LEAD,5)
    traced_wire(g,[(256,480),(186,480),(186,645),(228,645),port_point(5,604)],LEAD,5)
    g.wire([(256,494),(46,494),(46,542)],LEAD,5)
    jst_sm_half(g,'sockets',332,480)
    # Already-insulated capacitor branch, recognizable can shown beside it.
    g.rect(160,304,76,51,fill='#314a59',rx=8)
    g.rect(218,308,13,43,fill='#cdd5d4',stroke='none',rx=0)
    g.text(196,337,'C2',size=22,fill='#fff',anchor='middle')
    g.wire([(178,355),(178,384)],RED,5)
    traced_wire(g,[(223,355),(223,417),(186,417),(186,551)],BLK,5)
    shrink(g,151,375,55,18)
    sleeve(g,186,521,37)
    small_resistor(g,58,494,'R2',48)
    shrink_over(g,50,482,64,24)
    g.text(58, 474, 'R2', size=22)
    g.text(263, 540, 'Base half',size=24,weight=700)
    g.text(24, 574, 'S1 D5',size=22)
    g.text(24, 700, 'Base half: JST-SM 2.5 mm (large)',size=22)
    g.save('circuits/f2-connect.svg')


def traced_wire(g, points, color, width=5):
    # A paper-colored casing separates crossing insulated wires; no splice dot.
    g.wire(points, PAPER, width + 5)
    g.wire(points, color, width)


HEADER_PITCH = 24


def header_pin(n, y):
    """Odd pins in the inner row (left), even pins in the outer row at the board edge (right)."""
    return (66 if n % 2 else 94, y + ((n - 1) // 2) * HEADER_PITCH)


def header_board(g, selected, y=151):
    """Pi header from the pin side, microSD end up: every row numbered by its odd pin,
    so the builder can count rows from the microSD end."""
    bottom = y + 19 * HEADER_PITCH
    # The board continues past the torn left edge; its right edge is the board edge.
    tear = ' '.join(f'{46 + 6 * (i % 2)},{yy}' for i, yy in enumerate(range(bottom + 26, y - 27, -12)))
    g.add(f'<polygon points="46,{y - 27} 122,{y - 27} 122,{bottom + 26} {tear}" fill="#397750" stroke="{INK}" stroke-width="2" stroke-linejoin="round"/>')
    g.rect(54, y - 14, 54, bottom - y + 28, fill='#242a30', rx=2)
    for n in range(1, 41):
        x, yy = header_pin(n, y)
        g.circle(x, yy, 4, fill='#daba6d', stroke='none')
        if n in selected:
            g.rect(x - 8, yy - 8, 16, 16, fill='#353b44', stroke=selected[n], sw=2, rx=1)
        if n % 2 and n not in selected:
            g.text(40, yy + 8, str(n), size=22, fill=MUTED, anchor='end')
    g.text(16, y - 40, 'microSD end', size=22, weight=700)
    g.rect(52, bottom + 34, 62, 40, fill='#bfc7ca', rx=2)
    g.rect(62, bottom + 46, 42, 16, fill='#30383d', rx=0)
    g.text(126, bottom + 62, 'USB end', size=22, weight=700)
    # Rows 19-20 carry no lead in any header view, so the edge label always fits there.
    g.text(150, bottom + 8, 'Board edge', size=22, weight=700)
    g.wire([(148, bottom), (124, bottom - 14)], MUTED, 1.5)
    return {n: header_pin(n, y) for n in selected}


def header_labels(g, pins):
    for n, (x, y) in pins.items():
        if n % 2:
            g.text(40, y + 8, str(n), size=22, weight=700, anchor='end')
        else:
            g.label(138, y + 7, str(n), size=22, anchor='middle', weight=700, pad=1)


def pi_pin1():
    """Pin 1 marked on the base beside the header, as seen through the open bottom."""
    g=physical_action('Mark pin 1',720)
    pins=header_board(g,{1:RED})
    header_labels(g,pins)
    x,y=pins[1]
    # A wire label stuck on the base just past the board edge, level with row 1.
    g.rect(150,y-20,40,40,fill='#f1e6b8',stroke=INK,sw=1.5,rx=3)
    g.text(170,y+8,'1',size=24,weight=700,anchor='middle')
    g.text(206,y+8,'Wire label',size=22)
    g.text(150,y+60,'Pin 1',size=22,weight=700)
    g.wire([(148,y+46),(x+10,y+8)],MUTED,1.5)
    g.save('circuits/pi-pin1.svg')


def shifter_board(g, name, x=208, y=273):
    """6066 top view from official PCB: input G,V,DAT,CLK; output G,D5,!D5,C5."""
    g.rect(x,y,197,178,fill='#283841',rx=10)
    for yy in (y+14,y+164):
        g.circle(x+99,yy,6,fill=PAPER,stroke='#b19b61',sw=3)
    g.rect(x+89,y+61,23,47,fill='#181d24',rx=2)
    for i,label in enumerate(('G','V','DAT','CLK')):
        yy=y+31+i*38
        for tx in (x+4,x+167):
            g.rect(tx,yy-17,27,34,fill='#3c9e68',stroke='#21633f',rx=2)
            g.circle(tx+14,yy,8,fill='#c3cbce',stroke='#397351',sw=2)
            g.wire([(tx+8,yy-4),(tx+20,yy+4)],'#5d666c',2)
        g.text(x+38,yy+7,label,size=22,fill='#fff')
        g.text(x+159,yy+7,('G','D5','!D5','C5')[i],size=22,fill='#fff',anchor='end')
    g.text(x+98,y-20,name,size=26,weight=700,anchor='middle')
    return {label:(x+4,y+31+i*38) for i,label in enumerate(('G','V','DAT','CLK'))}


def gpio_lead_preparation():
    g=action('GPIO lead end',510)
    g.rect(28,152,58,37,fill='#303740',rx=3)
    g.rect(28,161,14,19,fill='#181e25',stroke='none',rx=0)
    g.wire([(86,170),(285,170)],BLUE,7)
    g.wire([(285,170),(349,170)],COPPER,4)
    g.text(24,130,'2.54 mm female socket',size=22)
    g.text(300,215,'Bare end',size=22,anchor='middle')
    # Side entry and screw clamp, enlarged.
    g.rect(260,319,116,85,fill='#3c9e68',stroke='#21633f',rx=4)
    g.rect(265,354,65,28,fill='#254c39',rx=1)
    g.circle(320,339,14,fill='#c3cbce',stroke=GRAY)
    g.wire([(310,333),(330,345)],MUTED,3)
    g.wire([(34,367),(161,367)],BLUE,7)
    g.wire([(161,367),(222,367)],COPPER,4)
    g.wire([(166,327),(247,327)],BLUE,3,arrow=True)
    g.text(318,442,'Terminal screw',size=22,anchor='middle')
    g.save('circuits/gpio-lead-prepare.svg')


def gpio_socket_insertion():
    g=action('Plug a socket onto the Pi',450)

    def face(points, fill, stroke=INK):
        g.add('<polygon points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="{fill}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>')

    def post(x,y):
        # Square header post: top and two visible faces, not a wire solder lug.
        face([(x-6,y-63),(x+2,y-61),(x+2,y),(x-6,y-2)],'#c59c48','#81632d')
        face([(x+2,y-61),(x+7,y-65),(x+7,y-4),(x+2,y)],'#a78038','#81632d')
        face([(x-6,y-63),(x-1,y-67),(x+7,y-65),(x+2,y-61)],'#f1d68d','#81632d')

    # Enlarged local section of the two-row Pi header, viewed obliquely.
    face([(45,329),(297,384),(377,331),(125,276)],'#43845a','#28573b')
    face([(45,329),(297,384),(297,391),(45,336)],'#2b583e','#28573b')
    face([(57,318),(281,367),(333,333),(109,284)],'#343a3f')
    face([(57,318),(281,367),(281,382),(57,333)],'#20262b')
    face([(281,367),(333,333),(333,348),(281,382)],'#141a1f')
    for i in range(5):
        post(98+46*i,306+10*i)
    for i in range(5):
        post(72+46*i,324+10*i)

    # The target post is front row, column 3: its tip is centered at (164,280).
    # Connector and pin share a vertical insertion axis; no hidden wire crimping.
    g.add(f'<path d="M164 143 V120 Q164 104 180 104 H205" fill="none" stroke="{BLUE}" stroke-width="9" stroke-linecap="round"/>')
    face([(134,145),(172,154),(194,140),(156,131)],'#59616c')
    face([(134,145),(172,154),(172,244),(134,235)],'#343c46')
    face([(172,154),(194,140),(194,230),(172,244)],'#202731')
    # Retention window and terminal catch identify a preassembled jumper socket.
    face([(144,174),(162,178),(162,200),(144,196)],'#171d24','#151a20')
    face([(147,183),(159,186),(159,194),(147,191)],'#a9b1b9','#69747d')
    g.wire([(136,224),(170,232)],'#64707b',1)
    g.text(243,160,'Female',size=22)
    g.text(243,187,'socket',size=22)
    g.wire([(231,177),(201,177)],MUTED,1.5)
    g.wire([(164,250),(164,274)],BLUE,3,arrow=True)
    g.text(24,230,'Pi pin',size=22)
    g.wire([(79,239),(151,279)],MUTED,1.5)
    g.save('circuits/gpio-socket-insert.svg')


def shifter_circuit(name, selected):
    g=physical_action(f'Connect the Pi to {name}',900)
    colors={'G':BLK,'V':'#8754ad','DAT':BLUE,'CLK':ORANGE}
    pins=header_board(g,{n:colors[v.split()[-1]] for n,v in selected.items()})
    terminals=shifter_board(g,name)
    # Sleeved socket bodies stay visible; four continuous insulated leads.
    for i,(n,label) in enumerate(selected.items()):
        key=label.split()[-1]; x,y=pins[n]; xx,yy=terminals[key]
        lane=154+i*13
        traced_wire(g,[(x,y),(lane,y),(lane,yy),(xx,yy)],colors[key],4)
        g.rect(x-7,y-7,14,14,fill='#353b44',stroke=colors[key],sw=2,rx=1)
    header_labels(g,pins)
    g.text(209,487,'INPUT',size=22,weight=700)

    # Canonical mapping remains explicit below the physical view.
    for i,(n,label) in enumerate(selected.items()):
        g.text(24 if i%2==0 else 215,730+(i//2)*32,f'{n} → {label}',size=23,weight=700)
    g.save(f'circuits/{name.lower()}-inputs.svg')


def shifter_outputs():
    """Output side of S1 and S2: what each output terminal drives, as labeled at the bench."""
    g=physical_action('Level shifter outputs',660)
    for i,(name,d5,c5) in enumerate((('S1',None,'LEFT'),('S2','RIGHT','HEAD'))):
        y=110+i*290
        shifter_board(g,name,x=24,y=y)
        for k,tag in ((1,d5),(3,c5)):
            yy=y+31+k*38
            if tag:
                g.wire([(218,yy),(252,yy)],MUTED,2)
                g.rect(252,yy-17,104,34,fill='#fffdf4',stroke=INK,sw=1.5,rx=3)
                g.text(304,yy+8,tag,size=22,anchor='middle',weight=700)
        if name=='S1':
            yy=y+31+38
            g.wire([(218,yy),(405,yy)],LEAD,5)
            small_resistor(g,290,yy,'R2',48)
            g.text(314,yy-16,'R2',size=22,anchor='middle',weight=700)
            g.text(236,yy+32,'Base-half DATA',size=22)
        g.text(24,y+214,'Output G and !D5: empty',size=22,fill=MUTED)
    g.save('circuits/shifter-outputs.svg')

def shifter_jumpers():
    # Adafruit pinouts: back, left of upper mounting hole, white Neo outline.
    g = action('Cut both Neo jumpers', 420)
    g.rect(55, 122, 310, 178, fill='#273746', rx=12)
    g.circle(280, 172, 18, fill=PAPER, stroke='#c5a571', sw=5)
    g.text(264, 117, 'Top hole', size=22, anchor='middle')
    g.wire([(278, 124), (280, 149)], MUTED, 2)
    g.rect(102, 149, 111, 106, fill='none', stroke='#fff', rx=4)
    g.text(157, 180, 'Neo', size=24, fill='#fff', anchor='middle')
    for x in (123, 174):
        g.rect(x, 209, 17, 25, fill='#dbb87a', stroke='#dbb87a', rx=2)
    g.wire([(140, 221), (174, 221)], '#dbb87a', 5)
    g.wire([(156, 204), (160, 238)], ORANGE, 4)
    g.text(266, 270, 'Cut here', size=22, fill='#fff', anchor='middle')
    g.wire([(224, 256), (161, 229)], '#fff', 2)
    g.save('circuits/shifter-neo.svg')


def button_back(g, cx, cy):
    """Rear of the Adafruit 1479: 18 mm square bezel behind the Ø16 body and Ø11.8 rear face.

    Tabs: the closer upper pair is the LED (− left, + right); the wider lower pair
    is the switch. Spacing is enlarged so each lead can be traced."""
    g.rect(cx - 92, cy - 92, 184, 184, fill='#292e36', stroke=INK, rx=24)
    g.circle(cx, cy, 82, fill='#343b43', stroke='#81868a', sw=3)
    g.circle(cx, cy, 60, fill='#3d454e', stroke='#5d666f', sw=2)
    tabs = {'LED−': (cx - 22, cy - 22), 'LED+': (cx + 22, cy - 22),
            'SW1': (cx - 34, cy + 26), 'SW2': (cx + 34, cy + 26)}
    for x, y in tabs.values():
        g.rect(x - 5, y - 12, 10, 24, fill='#c9d0d4', stroke='#f6f6ee', sw=1, rx=1)
    return tabs


def tab_sleeve(g, x, y, down=18):
    """Shrunk heat-shrink over one tab and its joint; the lead leaves from its lower end."""
    shrink(g, x - 9, y - 15, 18, 30 + down)


def small_resistor(g, x, y, key, length=40):
    """Horizontal resistor body from x to x + length, with its value bands."""
    g.rect(x, y - 8, length, 16, fill='#e5c798', stroke=INK, sw=1, rx=6)
    for i, col in enumerate((*RESISTORS[key][1], '#be9b36')):
        g.rect(x + 6 + i * 8, y - 7, 4, 14, fill=col, stroke='none', rx=0)


def pi_socket(g, x, y, pin):
    """2.54 mm female socket at a lead's Pi end, opening downward, with its pin label."""
    g.rect(x - 11, y, 22, 42, fill='#303740', rx=3)
    g.rect(x - 4, y + 32, 8, 8, fill='#151b20', stroke='none', rx=0)
    g.text(x, y + 70, str(pin), size=22, anchor='middle', weight=700)


def button_tab_labels(g, tabs, cx):
    g.text(cx - 44, tabs['LED−'][1] + 8, '−', size=22, fill='#fff', anchor='middle')
    g.text(cx + 44, tabs['LED+'][1] + 8, '+', size=22, fill='#fff', anchor='middle')


def button_terminals():
    g = action('Identify the four tabs', 400)
    cx, cy = 210, 215
    tabs = button_back(g, cx, cy)
    button_tab_labels(g, tabs, cx)
    for key, tx, anchor, color in (('LED−', 24, 'start', INK), ('LED+', 396, 'end', RED)):
        x, y = tabs[key]
        g.wire([(x, y - 12), (x + (-1 if anchor == 'start' else 1) * 40, 112), (tx + (40 if anchor == 'start' else -40), 112)], '#ae855e', 2)
        g.dot(x, y - 12, '#f4e7c4', r=3)
        g.text(tx, 104, 'LED −' if key == 'LED−' else 'LED +', size=22, fill=color, anchor=anchor, weight=700)
    (x1, y1), (x2, y2) = tabs['SW1'], tabs['SW2']
    g.wire([(x1, y1 + 12), (x1, 334), (x2, 334), (x2, y2 + 12)], '#ae855e', 2)
    for x, y in (tabs['SW1'], tabs['SW2']):
        g.dot(x, y + 12, '#f4e7c4', r=3)
    g.text(cx, 366, 'Switch pair', size=22, anchor='middle', weight=700)
    g.save('circuits/button-terminals.svg')


def meter_probe(g, tip, end, color):
    """A meter probe: bare metal tip on the tab, finger guard, then a thick insulated handle."""
    import math
    (x0, y0), (x1, y1) = tip, end
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    gx, gy = x0 + ux * 46, y0 + uy * 46
    g.wire([(x0, y0), (gx, gy)], '#b9bec3', 4)
    g.wire([(gx - uy * 16, gy + ux * 16), (gx + uy * 16, gy - ux * 16)], color, 8)
    g.wire([(gx, gy), (x1, y1)], color, 16)


def button_switch_check():
    g = action('Check the switch pair', 470)
    cx, cy = 210, 200
    tabs = button_back(g, cx, cy)
    button_tab_labels(g, tabs, cx)
    for key, end, color in (('SW1', (96, 396), RED), ('SW2', (324, 396), BLK)):
        x, y = tabs[key]
        meter_probe(g, (x, y + 10), end, color)
    g.save('circuits/button-switch-check.svg')


def button_leads_prepare():
    g = action('Prepare four leads', 500)
    # One lead as supplied: the far connector is cut off.
    g.rect(24, 132, 44, 22, fill='#303740', rx=3)
    g.rect(24, 138, 10, 10, fill='#151b20', stroke='none', rx=0)
    g.wire([(68, 143), (330, 143)], BLUE, 6)
    g.rect(330, 132, 44, 22, fill='none', stroke=GRAY, sw=2, rx=3, dash='5 4')
    g.wire([(300, 118), (300, 170)], ORANGE, 3, dash='6 4')
    g.text(300, 194, 'Cut', size=22, fill=ORANGE, anchor='middle', weight=700)
    # The four prepared leads: socket kept, cut end stripped, socket labeled.
    for i, pin in enumerate((11, 14, 20, 4)):
        y = 236 + i * 46
        g.rect(24, y - 11, 44, 22, fill='#303740', rx=3)
        g.rect(24, y - 5, 10, 10, fill='#151b20', stroke='none', rx=0)
        g.wire([(68, y), (300, y)], BLUE, 6)
        g.wire([(300, y), (336, y)], COPPER, 3)
        g.rect(84, y - 16, 44, 32, fill='#fff', stroke=INK, sw=1, rx=3)
        g.text(106, y + 8, str(pin), size=22, anchor='middle', weight=700)
    g.text(24, 440, 'Socket end · Pi pin on its label', size=22)
    g.text(24, 472, 'Stripped end · button tab', size=22)
    g.save('circuits/button-leads-prepare.svg')


def button_top(g, y0, spread):
    """The button lying on one bezel flat, seen from above: lens left, tabs pointing right.

    Only the top pair of tabs shows; `spread` is half their spacing (enlarged)."""
    g.rect(22, y0 - 40, 26, 80, fill='#e9e6dc', stroke=INK, rx=8)             # lens
    g.rect(48, y0 - 58, 22, 116, fill='#292e36', stroke=INK, rx=4)            # 18 mm bezel
    g.rect(70, y0 - 50, 118, 100, fill='#343b43', stroke=INK, rx=2)           # Ø16 body
    for x in range(78, 184, 9):
        g.wire([(x, y0 - 50), (x + 4, y0 + 50)], '#55585f', 2)
    tabs = (y0 - spread, y0 + spread)
    for y in tabs:
        g.rect(188, y - 4, 34, 8, fill='#c9d0d4', stroke='#f6f6ee', sw=1, rx=1)
    return tabs


def side_socket(g, x, y, pin):
    """2.54 mm female socket at a lead's Pi end, lying along the lead, with its pin label."""
    g.rect(x, y - 8, 34, 16, fill='#303740', rx=2)
    g.text(x + 64, y + 8, str(pin), size=22, anchor='end', weight=700)


def button_leads_switch():
    g = action('Solder the switch leads', 440)
    y0 = 215
    tabs = button_top(g, y0, 26)
    for y, pin in zip(tabs, (11, 14)):
        traced_wire(g, [(222, y), (330, y)], BLUE, 4)
        shrink(g, 184, y - 8, 56, 16)
        side_socket(g, 330, y, pin)
    g.text(205, 146, 'Switch tabs', size=22, anchor='middle', weight=700)
    g.save('circuits/button-leads-switch.svg')


def button_leads_led():
    g = action('Solder the LED leads', 470)
    y0 = 225
    plus, minus = button_top(g, y0, 18)
    g.text(206, plus - 12, '+', size=24, anchor='middle', weight=700, fill=RED)
    g.text(206, minus + 30, '−', size=24, anchor='middle', weight=700)
    # LED −: lead 20 soldered straight to the tab; its sleeve waits on the lead.
    traced_wire(g, [(214, minus), (330, minus)], BLK, 4)
    joint(g, 214, minus, BLK)
    shrink(g, 262, minus - 7, 30, 14)
    side_socket(g, 330, minus, 20)
    # LED +: R1 in line with the tab, pointing straight back; lead 4 on its free leg.
    g.wire([(206, plus), (234, plus)], GRAY, 3)
    small_resistor(g, 234, plus, 'R1', 36)
    g.wire([(270, plus), (282, plus)], GRAY, 3)
    traced_wire(g, [(282, plus), (330, plus)], RED, 4)
    joint(g, 282, plus, RED)
    shrink(g, 292, plus - 7, 34, 14)
    side_socket(g, 330, plus, 4)
    g.label(252, 140, 'R1 · 1 kΩ', size=22, anchor='middle', weight=700)
    g.wire([(252, 146), (252, plus - 10)], '#ae855e', 2)
    g.save('circuits/button-leads-led.svg')


def callout(g, x, y, n):
    """A small numbered marker for the order of work."""
    g.circle(x, y, 16, fill=BLUE, stroke=BLUE, sw=1)
    g.text(x, y + 8, str(n), size=22, fill='#fff', anchor='middle', weight=700)


def button_insert_threading():
    g = action('Fit the button in its insert', 450)
    y0 = 215
    # FB20 in section: a 2 mm plate with its Ø16.2 hole.
    for top, h in ((y0 - 100, 60), (y0 + 40, 60)):
        g.rect(104, top, 14, h, fill='#c0845a', stroke=INK, sw=1, rx=1)
    g.text(111, y0 - 110, 'FB20', size=22, anchor='middle', weight=700)
    # The button, seated from outside: lens and 18 mm bezel against the outer face,
    # Ø16 body through the hole, retaining nut tight against the inner face.
    g.rect(64, y0 - 30, 20, 60, fill='#e9e6dc', stroke=INK, rx=6)
    g.rect(84, y0 - 48, 20, 96, fill='#292e36', stroke=INK, rx=3)
    g.rect(104, y0 - 36, 108, 72, fill='#343b43', stroke=INK, rx=2)
    for x in range(140, 206, 9):
        g.wire([(x, y0 - 36), (x + 4, y0 + 36)], '#55585f', 2)
    # Retaining nut, its toothed face against the insert.
    g.rect(122, y0 - 50, 14, 100, fill='#b3bac0', stroke=INK, sw=1, rx=2)
    teeth = ' '.join(f'{122 if i % 2 == 0 else 118},{y0 - 50 + i * 5}' for i in range(21))
    g.add(f'<polygon points="{teeth} 122,{y0 + 50}" fill="#b3bac0" stroke="{INK}" stroke-width="1.5" stroke-linejoin="round"/>')
    g.label(160, y0 - 70, 'Teeth', size=22, weight=700)
    g.wire([(168, y0 - 64), (124, y0 - 44)], '#ae855e', 2)
    # Sleeved tabs, then the four labeled Pi ends out of the back.
    rows = ((y0 - 27, 20, BLK), (y0 - 9, 4, RED), (y0 + 9, 11, BLUE), (y0 + 27, 14, BLUE))
    for i, (y, pin, color) in enumerate(rows):
        sy = 150 + i * 44
        traced_wire(g, [(250, y), (290, y), (326, sy), (340, sy)], color, 4)
        side_socket(g, 340, sy, pin)
    for y, pin, _ in rows:
        shrink(g, 212, y - 6, 58 if pin == 4 else 40, 12, rx=3)
    callout(g, 360, 112, 1)
    callout(g, 74, y0 - 72, 2)
    callout(g, 152, y0 + 76, 3)
    g.text(24, 382, '1 Pi ends · 2 Button · 3 Nut', size=22)
    g.save('circuits/button-insert-thread.svg')


def button_leads_done():
    g = action('Insulate the LED leads', 420)
    y0 = 225
    g.rect(24, y0 - 32, 32, 64, fill='#e9e6dc', stroke=INK, rx=8)            # lens, Ø13
    g.rect(56, y0 - 45, 35, 90, fill='#292e36', stroke=INK, rx=4)            # 18 mm bezel
    g.rect(91, y0 - 40, 120, 80, fill='#343b43', stroke=INK, rx=2)           # Ø16 body
    for x in range(99, 206, 9):
        g.wire([(x, y0 - 40), (x + 4, y0 + 40)], '#55585f', 2)
    # Dashed body outline: the retaining nut passes over everything inside it.
    for yy in (y0 - 40, y0 + 40):
        g.wire([(211, yy), (300, yy)], GRAY, 2, dash='6 5')
    rows = ((y0 - 27, 20, BLK), (y0 - 9, 4, RED), (y0 + 9, 11, BLUE), (y0 + 27, 14, BLUE))
    for y, pin, color in rows:
        g.rect(211, y - 3, 28, 6, fill='#c9d0d4', stroke='none', rx=1)
    for i, (y, pin, color) in enumerate(rows):
        sy = 176 + i * 42
        traced_wire(g, [(250, y), (300, y), (326, sy), (330, sy)], color, 4)
        g.rect(330, sy - 8, 34, 16, fill='#303740', rx=2)
        g.text(404, sy + 8, str(pin), size=22, anchor='end', weight=700)
    y = rows[1][0]
    small_resistor(g, 248, y, 'R1', 34)
    shrink_over(g, 207, y - 11, 80, 22, rx=5)
    for yy, _, _ in (rows[0], rows[2], rows[3]):
        shrink(g, 207, yy - 7, 46, 14)
    g.label(262, 150, 'R1 under sleeve', size=22, anchor='middle', weight=700)
    g.wire([(262, 156), (262, y - 12)], '#ae855e', 2)
    g.save('circuits/button-leads-done.svg')


def upright_resistor(g, x, y, key, length=36):
    """Vertical resistor body from y up to y - length, with its value bands."""
    g.rect(x - 8, y - length, 16, length, fill='#e5c798', stroke=INK, sw=1, rx=6)
    for i, col in enumerate((*RESISTORS[key][1], '#be9b36')):
        g.rect(x - 7, y - length + 6 + i * 8, 14, 4, fill=col, stroke='none', rx=0)


def loose_socket(g, x, y, pin, side):
    """A lead's 2.54 mm socket hanging loose, opening upward, with its label beside it."""
    g.rect(x - 11, y - 40, 22, 40, fill='#303740', rx=3)
    g.rect(x - 4, y - 38, 8, 8, fill='#151b20', stroke='none', rx=0)
    tx = x - 18 if side == 'left' else x + 18
    g.text(tx, y - 12, str(pin), size=22, anchor='end' if side == 'left' else 'start', weight=700)


def button_header_view(g, plugged):
    """The finished button from behind beside the Pi header. All four leads come off it,
    drawn folded flat: the LED pair up, the switch pair down. R1 lies in line with the
    LED + tab under a see-through sleeve. Leads in `plugged` reach their pins; the others
    hang loose with their labeled sockets."""
    colors = {11: BLUE, 14: BLUE, 4: RED, 20: BLK}
    points = header_board(g, {n: colors[n] for n in plugged})
    cx, cy = 300, 340
    tabs = button_back(g, cx, cy)
    button_tab_labels(g, tabs, cx)
    sw1, sw2 = tabs['SW1'], tabs['SW2']
    lx, ly = tabs['LED−']
    px, py = tabs['LED+']
    top_minus, top_plus = ly - 33, py - 66
    if 11 in plugged:
        traced_wire(g, [points[11], (170, points[11][1]), (170, 470), (sw1[0], 470), (sw1[0], sw1[1])], BLUE)
        traced_wire(g, [points[14], (150, points[14][1]), (150, 496), (sw2[0], 496), (sw2[0], sw2[1])], BLUE)
    if 20 in plugged:
        traced_wire(g, [points[20], (200, points[20][1]), (200, 215), (lx, 215), (lx, ly)], BLK)
        traced_wire(g, [points[4], (px, points[4][1]), (px, py)], RED)
    else:
        g.wire([(lx, ly), (lx, top_minus - 22)], BLK, 5)
        loose_socket(g, lx, top_minus - 22, 20, 'left')
        g.wire([(px, py), (px, top_plus - 22)], RED, 5)
        loose_socket(g, px, top_plus - 22, 4, 'right')
    for x, y in (sw1, sw2):
        tab_sleeve(g, x, y)
    shrink(g, lx - 9, top_minus, 18, ly + 15 - top_minus)
    upright_resistor(g, px, py - 18, 'R1')
    shrink_over(g, px - 11, top_plus, 22, py + 15 - top_plus)
    g.label(240, 150, 'R1 · 1 kΩ', size=22, anchor='middle', weight=700)
    g.wire([(285, 156), (px - 10, py - 40)], '#ae855e', 2)
    header_labels(g, points)
    return g


def button_switch():
    g = button_header_view(physical_action('Connect the button switch', 790), {11, 14})
    g.text(24, 730, 'Pin 11 · GPIO17 → switch', size=22)
    g.text(24, 761, 'Pin 14 · GND → other switch tab', size=22)
    g.save('circuits/button-switch.svg')


def button_led():
    g = button_header_view(physical_action('Connect the button light', 790), {11, 14, 4, 20})
    g.text(24, 730, 'Pi pin 4 · +5 V → R1 → LED +', size=22)
    g.text(24, 761, 'Pi pin 20 · GND → LED −', size=22)
    g.save('circuits/button-led.svg')


def pi_bench_board(g, x, y, scale):
    """Component-side Pi 3A+ outline; port positions from its mechanical drawing."""
    def rect(px, py, w, h, fill, rx=1):
        g.rect(x+px*scale,y+py*scale,w*scale,h*scale,fill=fill,rx=rx)
    rect(0,0,65,56,'#397750',8)
    for px,py in [(3.5,3.5),(61.5,3.5),(3.5,52.5),(61.5,52.5)]:
        g.circle(x+px*scale,y+py*scale,1.375*scale,fill=PAPER,stroke='#d6bd71')
    rect(7.1,.96,50.8,5.08,'#22292c')
    for row in [2.23,4.77]:
        for i in range(20):
            g.circle(x+(8.37+i*2.54)*scale,y+row*scale,.38*scale,fill='#ddbd6c',stroke='none')
    rect(5.5,7,12,11.5,'#bac5c7')
    rect(20.2,18,13.2,13.2,'#b8c0c4')
    rect(1.8,16.5,3.4,23,'#e8e3d5')
    rect(43.4,33.5,2.6,21.5,'#e8e3d5')
    rect(53.3,17.9,15.4,13.2,'#bbc4cc')
    rect(67.5,19.6,1.2,9.8,'#22272d')
    rect(24.2,45.8,15.4,11.2,'#bbc4cc')
    rect(6.9,51.5,7.4,5.6,'#bbc4cc')
    rect(7.6,55.6,6,1.5,'#22272d')
    rect(50.2,44,6.6,15.2,'#22272d')


def usb_audio():
    g = action('USB audio connections', 680)
    g.text(24,123,'Raspberry Pi 3A+ · E09',size=24,weight=700)
    pi_bench_board(g,24,145,3.4)
    # Male plug enters the Pi's right-facing USB-A receptacle.
    g.rect(305,214,36,29,fill='#c6cdd2',rx=1)
    for yy in [219,232]:
        g.rect(315,yy,9,6,fill='#707a81',stroke='none',rx=0)
    g.rect(341,207,34,43,fill='#30343c',rx=5)
    g.wire([(298,228),(267,228)],COPPER,3,arrow=True)
    g.text(272,185,'1',size=26,weight=700,fill=COPPER)
    # One continuous cable ends at a FEMALE socket, not at the audio case.
    g.add('<path d="M375 228 H384 Q394 228 394 240 V386 Q394 407 374 407 H52 Q33 407 33 426 V505 Q33 525 53 525 H89" fill="none" stroke="#30343c" stroke-width="8" stroke-linecap="round"/>')
    g.text(24,371,'USB-A socket on the Pi',size=22)
    g.wire([(254,348),(270,320),(248,252)],MUTED,1.5)
    g.text(56,451,'USB-A extension · E23',size=24,weight=700)
    g.rect(89,503,65,44,fill='#30343c',rx=6)
    g.rect(144,509,11,32,fill='#bac5cb',rx=1)
    g.rect(149,515,6,20,fill='#111720',rx=0)
    # Audio module remains in its black case, with its own USB-A male plug.
    g.rect(203,511,37,29,fill='#c6cdd2',rx=1)
    for yy in [516,529]:
        g.rect(212,yy,9,6,fill='#707a81',stroke='none',rx=0)
    g.rect(239,487,158,76,fill='#262a31',rx=10)
    g.rect(245,497,8,54,fill='#87bc53',stroke='none',rx=1)
    g.text(259,532,'USB AUDIO',size=22,fill='#fff',weight=700)
    g.circle(265,501,3,fill='#87bc53',stroke='none')
    for yy in [505,516,527,538]:
        g.circle(389,yy,2.6,fill='#b7c0c7',stroke='none')
    g.wire([(197,525),(166,525)],COPPER,3,arrow=True)
    g.text(173,489,'2',size=26,weight=700,fill=COPPER)
    g.text(24,598,'Female socket',size=22)
    g.wire([(119,575),(132,550)],MUTED,1.5)
    g.text(194,622,'Waveshare 18833',size=24,weight=700)
    g.text(194,652,'Audio module · E14',size=22)
    g.wire([(310,596),(318,568)],MUTED,1.5)
    g.save('circuits/usb-audio.svg')


def pi_bench_power():
    g = action('Bench power for the Pi', 620)
    pi_bench_board(g,72,133,4)
    g.text(24,110,'Raspberry Pi 3A+',size=24,weight=700)
    # Micro-B power connector is on the near edge, beside HDMI.
    g.add('<path d="M101 412 L105 399 H123 L127 412 V423 H101 Z" fill="#c6cdd2" stroke="#292b3b" stroke-width="2"/>')
    g.rect(96,423,36,54,fill='#30343c',rx=6)
    g.wire([(114,477),(114,559)],BLK,7)
    g.wire([(114,393),(114,371)],COPPER,3,arrow=True)
    g.text(162,440,'Micro-USB',size=24,weight=700)
    g.text(162,471,'power plug',size=24)
    g.wire([(156,450),(135,442)],MUTED,1.5)
    g.text(250,503,'USB-A',size=24,weight=700)
    g.text(250,532,'for audio',size=22)
    g.wire([(309,480),(363,342),(349,257)],MUTED,1.5)
    g.text(24,595,'5 V / 2.5 A bench supply',size=24,weight=700)
    g.save('circuits/pi-bench-power.svg')


def servo_circuit(name, port, signal):
    g = physical_action(f'{name} · servo hookup', 675)
    g.rect(132, 141, 154, 112, fill='#32383e', rx=7)
    g.rect(115, 159, 188, 20, fill='#535c64', rx=3)
    g.circle(167, 140, 24, fill='#bdaf92', stroke=INK)
    g.circle(167, 140, 10, fill='#5c6060', stroke=INK)
    g.text(210, 219, name, size=27, fill='#fff', anchor='middle', weight=700)
    wago_port(g, 350, 'W2', port, RED)
    wago_port(g, 480, 'W4', port, BLK)
    # A terminal detail identifies the actual shifter terminal, not a free wire.
    shifter, terminal = signal.split()
    g.text(225, 567, f'{shifter} output', size=24, weight=700)
    g.rect(225, 584, 165, 68, fill='#283841', rx=8)
    g.rect(362, 600, 28, 30, fill='#3c9e68', stroke='#21633f', rx=2)
    g.circle(375, 615, 8, fill='#c3cbce', stroke=GRAY)
    g.wire([(370, 611), (380, 619)], MUTED, 2)
    g.text(244, 623, terminal, size=25, fill='#fff', weight=700)
    # Each lead starts at the servo case and ends at its selected terminal.
    px, py = port_point(port, 350)
    # Real lead order out of the case: brown, red, orange.
    traced_wire(g, [(211, 253), (211, 390), (px, 390), (px, py)], RED, 6)
    gx, gy = port_point(port, 480)
    traced_wire(g, [(187, 253), (187, 282), (400, 282), (400, 520), (gx, 520), (gx, gy)], SERVO_BROWN, 6)
    traced_wire(g, [(235, 253), (235, 264), (412, 264), (412, 615), (390, 615)], SERVO_ORANGE, 5)
    g.text(24, 423, f'{name} positive (+)', size=22)
    g.text(24, 552, f'{name} return (−)', size=22)
    g.save(f'circuits/servo-{name.lower()}.svg')


SH_WIRES = (('#26262b', 'GND'), (RED, '+5 V'), ('#f4f4ef', 'DATA'))


def sh_wire(g, pts, color, sw=5):
    """JST-SH lead wire; the white wire gets a dark edge so it reads on paper."""
    if color == '#f4f4ef':
        g.wire(pts, MUTED, sw + 2)
    g.wire(pts, color, sw)


def sh_plug(g, x, y):
    """Small white JST-SH 1.0 mm plug, mating face left; wires leave the right."""
    g.rect(x, y - 17, 26, 34, fill='#eee9df', stroke=INK, sw=1.5, rx=2)
    g.rect(x - 4, y - 8, 4, 16, fill='#d4cabc', stroke='none', rx=1)


def sh_bundle(g, x0, x1, y):
    """Black, red and white JST-SH lead wires from a plug at x0 to x1."""
    for i, (color, _) in enumerate(SH_WIRES):
        sh_wire(g, [(x0, y - 10 + i * 10), (x1, y - 10 + i * 10)], color)


def head_leads():
    g = action('Head leads · cut the cable', 540)
    sh_bundle(g, 56, 364, 160)
    sh_plug(g, 30, 160)
    g.rect(364, 143, 26, 34, fill='#eee9df', stroke=INK, sw=1.5, rx=2)
    g.wire([(210, 124), (210, 196)], ORANGE, 3, dash='7 5')
    g.text(210, 226, 'Cut in the middle', size=22, fill=ORANGE, anchor='middle', weight=700)
    g.text(24, 124, '200 mm', size=22, fill=MUTED)
    for y, name, use in ((300, 'Eye input lead', 'head half → first eye IN'), (420, 'Mouth lead', 'second eye OUT → mouth')):
        g.text(24, y - 30, name, size=25, weight=700)
        sh_bundle(g, 56, 190, y)
        sh_plug(g, 30, y)
        g.text(24, y + 46, use, size=22)
    lines(g, 510, 'JST-SH 1.0 mm (small)', 'Black GND · red +5 V · white DATA')
    g.save('circuits/head-leads.svg')


def body_output():
    g = action('Body · after light 5', 600)
    g.rect(156, 121, 108, 60, fill='#fff2c9', stroke='#a89978', rx=28)
    g.rect(191, 132, 38, 38, fill='#fafcf9', stroke='#e2d48b', rx=8)
    g.text(280, 160, 'Light 5', size=26, weight=700)
    # Clear strand wire to the joints, then the black 1663 leads to the housing.
    for x, end in ((180, 470), (210, 456), (240, 442)):
        g.wire([(x, 181), (x, 300)], '#aaa797', 4)
        shrink(g, x - 7, 300, 14, 40)
        g.wire([(x, 340), (x, end), (262, end)], LEAD, 4)
    for x, fn in ((180, '+5 V'), (210, 'DATA'), (240, 'GND')):
        g.text(x + 7, 284, fn, size=22, rotate=-90)
    jst_sm_half(g, 'sockets', 338, 456)
    g.text(24, 520, 'HEAD LIGHT body half', size=24, weight=700)
    g.text(24, 552, 'JST-SM 2.5 mm (large)', size=22)
    g.text(24, 582, 'Sockets', size=22)
    g.save('circuits/body-output.svg')


def head_power():
    g = physical_action('Head half · eye input lead', 560)
    g.text(24, 122, 'HEAD LIGHT head half', size=24, weight=700)
    jst_sm_half(g, 'pins', 386, 161)
    # Black 1663 leads fan out to one joint each, then the lead's own colors.
    rows = ((147, 200, 230, '+5 V', RED), (161, 230, 300, 'DATA', '#f4f4ef'), (175, 260, 370, 'GND', '#26262b'))
    for y0, drop, row, fn, color in rows:
        g.wire([(290, y0), (drop, y0), (drop, row), (150, row)], LEAD, 4)
        shrink(g, 127, row - 8, 46, 16)
        g.text(150, row + 34, fn, size=22, anchor='middle', weight=700)
    for y0, drop, row, fn, color in rows:
        slot = 290 + [c for c, _ in SH_WIRES].index(color) * 10
        if fn == 'GND':
            g.wire([(127, row), (95, row), (70, slot), (56, slot)], PAPER, 11)
        sh_wire(g, [(127, row), (95, row), (70, slot), (56, slot)], color)
    sh_plug(g, 30, 300)
    g.text(24, 444, 'Eye input lead → first eye IN', size=22)
    lines(g, 484, 'Head half: JST-SM (large), pins', 'Eye input lead: JST-SH (small)')
    g.save('circuits/head-power.svg')


def eye(g, y, number, label):
    g.rect(50, y - 42, 84, 84, fill='#292f38', stroke=INK, rx=15)
    g.circle(92, y - 32, 6, fill=PAPER, stroke='#bfa768')
    g.circle(92, y + 32, 6, fill=PAPER, stroke='#bfa768')
    g.rect(70, y - 22, 44, 44, fill='#f6f3e7', stroke='#a39d80', rx=4)
    g.circle(92, y, 13, fill='#e7de90', stroke='#fff')
    g.text(156, y - 7, label, size=25, weight=700)
    g.text(156, y + 26, f'Light {number} · IN → OUT', size=22)


def head_data():
    g = action('Head · one chain', 782)
    lines(g, 160, 'Head half → eye input lead')
    eye(g, 241, 6, 'First eye')
    g.wire([(92, 284), (92, 357)], BLUE, 4, arrow=True)
    g.text(156, 320, 'Eye cable', size=24, weight=700)
    g.text(156, 352, 'OUT → IN', size=22)
    eye(g, 412, 7, 'Second eye')
    g.wire([(92, 455), (92, 555)], BLUE, 4, arrow=True)
    g.text(156, 492, 'Mouth lead', size=24, weight=700)
    g.text(156, 524, 'OUT → mouth', size=22)
    g.rect(24, 582, 372, 52, fill='#2f413c', rx=5)
    for i in range(8):
        g.rect(35 + i * 45, 593, 31, 30, fill='#f6f3e7', stroke='#adab8b', rx=3)
    g.text(120, 570, 'Mouth · lights 8–15', size=24, weight=700)
    g.save('circuits/head-data.svg')


def wago_reference():
    import json
    root = Path(__file__).resolve().parents[3]
    power = json.loads((root / 'hardware/assembly/electrical.json').read_text())['power']['rows']
    # Canonical table content is used directly; manual wrapping never changes
    # terminal allocations. Four narrow figures replace the all-wire tangle.
    for row in power:
        block = row[0].split()[0]
        g = action(row[0], 685)
        for i, label in enumerate(row[1:], 1):
            y = 148 + (i - 1) * 99
            color = RED if block in ('W1', 'W2') else BLK
            g.circle(47, y, 22, fill=color, stroke=color)
            g.text(47, y + 8, str(i), size=26, fill='#fff', anchor='middle', weight=700)
            # One unusually long canonical cell needs two lines.
            if label == 'Base-half GND, including C2 −':
                g.text(86, y, 'Base-half GND,', size=23)
                g.text(86, y + 29, 'including C2 −', size=23)
            else:
                g.text(86, y + 8, label, size=23)
        lines(g, 620, 'WAGO 221-415 · 11 mm strip')
        g.save(f'circuits/{block.lower()}-reference.svg')


def solder_detail():
    g = action('Solder and cover each joint', 690)
    lines(g, 133, '1 Heat-shrink on first')
    g.wire([(41, 177), (153, 177)], RED, 9)
    shrink(g, 68, 164, 53, 26)
    g.wire([(153, 177), (187, 177)], COPPER, 6)
    g.wire([(238, 177), (274, 177)], COPPER, 6)
    g.wire([(274, 177), (376, 177)], RED, 9)
    lines(g, 263, '2 Soldered joint')
    g.wire([(41, 316), (172, 316)], RED, 9)
    shrink(g, 68, 303, 53, 26)
    g.wire([(170, 316), (251, 316)], COPPER, 6)
    g.rect(183, 308, 55, 16, fill=SOLDER, stroke=GRAY, rx=8)
    g.wire([(252, 316), (376, 316)], RED, 9)
    lines(g, 403, '3 Joint covered')
    g.wire([(41, 453), (376, 453)], RED, 9)
    shrink(g, 153, 440, 125, 26)
    g.save('circuits/solder-insulation.svg')


def capacitor_joint_detail():
    g = action('C2 · positive branch joint', 735)
    for y, covered in ((185, False), (510, True)):
        g.text(24, y - 65, 'F2 output', size=22, weight=700)
        g.text(24, y - 36, '18 AWG', size=22)
        g.text(247, y - 65, 'Base-half +5 V', size=22, weight=700)
        g.text(247, y - 36, '22 AWG', size=22)
        g.wire([(24, y), (183, y)], RED, 9)
        g.wire([(183, y), (247, y)], COPPER, 6)
        g.wire([(247, y), (395, y)], RED, 6)
        # C2 is inverted for this close-up: the legs leave its rubber seal.
        g.rect(288, y + 73, 90, 112, fill='#314a59', rx=10)
        g.rect(352, y + 87, 20, 87, fill='#ced7d5', stroke='none', rx=0)
        g.rect(294, y + 71, 78, 10, fill='#202d32', rx=3)
        g.text(319, y + 138, 'C2', size=26, fill='#fff', anchor='middle', weight=700)
        for dy in (111, 141, 170):
            g.text(362, y + dy, '−', size=22, anchor='middle')
        # The leg lies along the wires in the joint and leaves its sleeve on the axis.
        leg = [(200, y + 8), (280, y + 8), (310, y + 38), (310, y + 73)]
        g.wire(leg, '#b9c2c5', 4)
        # Negative leg continues separately to the return branch, outside detail.
        shrink_wire(g, [(355, y + 73), (355, y + 36)], 10)
        g.text(355, y + 26, 'GND', size=22, anchor='middle')
        if covered:
            shrink_wire(g, leg)
            shrink(g, 159, y - 18, 99, 39)
        else:
            g.rect(192, y - 10, 50, 24, fill=SOLDER, stroke=GRAY, rx=8)
        g.text(24, y + 76, 'Positive leg', size=22)
        g.wire([(149, y + 70), (300, y + 30)], MUTED, 1.5)
        g.text(24, y + 134, 'Heat-shrink to seal' if covered else 'Soldered branch', size=22)
        if covered:
            g.wire([(228, y + 130), (306, y + 73)], MUTED, 1.5)
    g.save('circuits/capacitor-joint.svg')


def mouth_solder():
    g = action('Mouth · solder the lead', 700)
    g.rect(24, 118, 372, 52, fill='#2f413c', rx=5)
    for i in range(8):
        g.rect(35 + i * 45, 129, 31, 30, fill='#f6f3e7', stroke='#adab8b', rx=3)
    for y, color, pad, source in ((330, RED, '+5V', 'Red'), (440, '#26262b', 'GND', 'Black'), (550, '#f4f4ef', 'DIN', 'White')):
        g.text(24, y - 33, source, size=22, weight=700)
        # Tinned pad, short strip, no sleeve: the wire is tacked straight onto the pad.
        sh_wire(g, [(28, y), (240, y)], color, 6)
        g.rect(234, y - 22, 141, 44, fill='#2f413c', rx=2)
        g.circle(257, y, 11, fill='#c4cbd0', stroke='#d8bc72', sw=4)
        g.wire([(240, y), (257, y)], '#c4cbd0', 5)
        g.text(281, y + 8, pad, size=24, fill='#fff', weight=700)
    lines(g, 628, 'DOUT: unused')
    g.save('circuits/mouth-solder.svg')


def cut_six():
    g = action('Body · keep six pebbles', 850)
    g.text(24, 127, 'INPUT end', size=24, weight=700)
    g.wire([(91, 152), (91, 722)], BLUE, 5)
    ordinals = ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th')
    for i, ordinal in enumerate(ordinals):
        y = 192 + i * 78
        g.rect(51, y - 22, 81, 45, fill='#fff2c9', stroke='#a89978', rx=21)
        g.rect(79, y - 11, 24, 23, fill='#fafcf9', stroke='#e2d48b', rx=4)
        g.text(158, y + 8, f'{ordinal} pebble · light {i}' if i < 6 else '7th pebble · remove', size=23, weight=700 if i==5 else 400)
    g.wire([(38, 622), (372, 622)], ORANGE, 3, dash='7 5')
    g.text(158, 614, 'Cut here', size=23, fill=ORANGE, weight=700)
    g.save('circuits/cut-six.svg')


def connector_seating():
    g = action('Plug in until it clicks', 700)
    lines(g, 133, 'JST-SM 2.5 mm (large)', '+5 V · DATA · GND, top to bottom')
    left = jst_sm_half(g, 'sockets', 170, 262)
    right = jst_sm_half(g, 'pins', 256, 262, facing='left')
    g.wire([(244, 262), (184, 262)], BLUE, 3, arrow=True)
    # The same two halves seen end-on, as you look into each mating face.
    jst_sm_face(g, 'sockets', 112, 372)
    jst_sm_face(g, 'pins', 304, 372)
    g.text(24, 450, 'Sockets', size=22, weight=700)
    g.text(396, 450, 'Pins', size=22, weight=700, anchor='end')
    g.text(24, 479, 'Smaller', size=22)
    g.text(396, 479, 'Larger, shrouded', size=22, anchor='end')
    for dy in (-14, 0, 14):
        g.wire([(24, 262 + dy), (left, 262 + dy)], LEAD, 4)
        g.wire([(right, 262 + dy), (396, 262 + dy)], LEAD, 4)
    left, right = jst_sm_mated(g, 182, 570)
    for dy in (-14, 0, 14):
        g.wire([(24, 570 + dy), (left, 570 + dy)], LEAD, 4)
        g.wire([(right, 570 + dy), (396, 570 + dy)], LEAD, 4)
    g.save('circuits/jst-sm-seat.svg')


def eye_connector():
    g = action('Eye · plug into IN', 714)
    for y, seated in ((155, False), (406, True)):
        g.rect(192, y, 170, 159, fill='#292f38', stroke=INK, rx=27)
        for yy in (y + 19, y + 140):
            g.circle(277, yy, 12, fill=PAPER, stroke='#bfa768', sw=3)
        for x in (199, 310):
            g.rect(x, y + 40, 44, 80, fill='#eee9df', rx=2)
        g.text(216, y + 145, 'IN', size=22, fill='#fff', anchor='middle', weight=700)
        g.text(327, y + 145, 'OUT', size=22, fill='#fff', anchor='middle', weight=700)
        plug_x = 154 if seated else 89
        g.rect(plug_x, y + 52, 49, 56, fill='#eee9df', rx=2)
        g.rect(plug_x + 13, y + 47, 15, 5, fill='#d4cabc', rx=0)
        for dy, (color, _) in zip((-12, 0, 12), SH_WIRES):
            sh_wire(g, [(33, y + 80 + dy), (plug_x, y + 80 + dy)], color, 4)
        if not seated:
            g.wire([(148, y + 80), (190, y + 80)], BLUE, 3, arrow=True)
    lines(g, 354, 'JST-SH 1.0 mm (small)', 'Black GND · red +5 V · white DATA')
    g.save('circuits/eye-connector.svg')



def eye_cable():
    """Both eye boards from behind, joined OUT to IN by the eye cable before fastening."""
    g = action('Eye cable · first eye OUT to second eye IN', 520)
    top = 150
    for x, name in ((8, 'First eye'), (272, 'Second eye')):
        g.text(x + 70, top - 16, name, size=22, anchor='middle', weight=700)
        g.rect(x, top, 140, 125, fill='#292f38', stroke=INK, rx=22)
        for yy in (top + 16, top + 109):
            g.circle(x + 70, yy, 10, fill=PAPER, stroke='#bfa768', sw=3)
        for sx in (x + 6, x + 94):
            g.rect(sx, top + 31, 40, 64, fill='#eee9df', rx=2)
        g.text(x + 26, top + 117, 'IN', size=22, fill='#fff', anchor='middle', weight=700)
        g.text(x + 114, top + 117, 'OUT', size=22, fill='#fff', anchor='middle', weight=700)
    mid = top + 63
    for plug_x in (138, 242):
        g.rect(plug_x, mid - 24, 40, 48, fill='#eee9df', rx=2)
        g.rect(plug_x + 13, mid - 29, 14, 5, fill='#d4cabc', rx=0)
    # A flat loop between the plugs: the black wire runs innermost.
    for i, (color, _) in enumerate(SH_WIRES):
        dy = (i - 1) * 11
        left_x, right_x, low = 198 - i * 9, 222 + i * 9, top + 175 + i * 11
        sh_wire(g, [(178, mid + dy), (left_x, mid + dy), (left_x, low), (right_x, low),
                    (right_x, mid + dy), (242, mid + dy)], color, 4)
    lines(g, top + 245, 'Eye cable (E12) · 100 mm', 'JST-SH 1.0 mm (small)', 'Black GND · red +5 V · white DATA')
    g.save('circuits/eye-cable.svg')

def power_overview():
    g = action('Power · three branches', 833)
    lines(g, 119, 'Mean Well GST40A05-P1J', 'External 5 V, 5 A supply', '→ J1 center → W1 INPUT +5 V')
    g.wire([(49, 201), (49, 614)], RED, 6)
    branches = ((238, 'W1/2 → Pi power lead', 'Pi USB → audio', 'Unfused supply branch'),
                (416, 'W1/3 → W2/1', '18 AWG → three servos', 'C1 across W2 and W3'),
                (593, 'W1/4 → F2 T1 A', '→ base half → body + head', 'C2 across the base-half feed'))
    for y, first, second, third in branches:
        g.wire([(49, y), (90, y)], RED, 5)
        joint(g, 49, y, RED)
        g.text(104, y + 8, first, size=23, weight=700)
        g.text(104, y + 43, second, size=23)
        g.text(104, y + 78, third, size=22, fill=MUTED)
    lines(g, 743, 'J1 sleeve → W3 GND', 'W3/3 → 18 AWG link → W4/1', 'Both capacitors: 1000 µF · 10 V')
    g.save('power-diagram.svg')


def strand_wire_identification():
    g = action('Strand · identify the wires', 685)
    # Three clear insulated wires, copper identification marks on +5 V.
    for y in (197, 263, 329):
        g.wire([(36, y), (384, y)], '#d7d9d3', 14)
        g.wire([(36, y), (384, y)], '#aaa797', 3)
    for x in range(84, 280, 24):
        g.wire([(x, 190), (x + 8, 204)], COPPER, 4)
    g.text(24, 174, 'Copper coil / dots → +5 V', size=24, weight=700)
    g.text(24, 242, 'Middle wire → DATA (normally)', size=22)
    g.text(24, 309, 'Other outer wire → GND', size=22)
    lines(g, 387, 'Factory leads:')
    for y, color, label in ((427, RED, 'red → +5 V'), (470, '#397548', 'green → DATA'), (513, BLK, 'black → GND')):
        g.wire([(29, y), (99, y)], color, 8)
        g.text(121, y + 8, label, size=24, weight=700)
    g.save('circuits/strand-wire-identification.svg')


def body_light_wire_exits():
    """Lower and middle body lights from the front, to scale.

    R33 pads: centres X ±23.15; lower Z 10-30, middle Z 36-56; front upright
    X ±5. The pads face out at 40°, so behind a pad is toward the middle of the
    robot. In the owner's bench build every wire between the two rows bends in
    behind its pad and crosses behind the front upright, clear of the lights."""
    s, cx, top = 6, 210, 70  # px per mm, robot centre, y of Z 60
    def y(z):
        return top + (60 - z) * s
    def x(xmm):
        return cx + xmm * s
    g = physical_action('Body lights · wire exits', 520)
    def clear_wire(path):
        for color, width in (('#d7d9d3', 9), ('#aaa797', 2)):
            g.add(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    # Wires that cross behind the front upright are drawn before it.
    for side in (-1, 1):
        px = x(side * 23.15)
        # Lower top exit: straight past the tie, then in behind the pad.
        clear_wire(f'M{px} {y(30)} L{px} {y(31.5)} Q{px} {y(32.6)} {px - side * 3 * s} {y(32.8)} L{cx} {y(35.5)}')
        # Middle bottom exit: straight past the tie, then in behind the pad.
        clear_wire(f'M{px} {y(36)} L{px} {y(34.5)} Q{px} {y(33.4)} {px - side * 3 * s} {y(33.2)} L{cx} {y(30.5)}')
    # Bracket arms reach the pads from the uprights.
    for z0 in (10, 36):
        for side in (-1, 1):
            g.rect(min(x(side * 4), x(side * 20)), y(z0 + 12), abs(x(20) - x(4)), 4 * s, fill='#d9dcdf', stroke=MUTED, sw=1.5, rx=2)
    g.rect(x(-5), y(60), 10 * s, 56 * s, fill='#c9cdd2', stroke=MUTED, rx=2)
    for z0 in (10, 36):
        for side in (-1, 1):
            px = x(side * 23.15)
            g.rect(px - 9, y(z0 + 20), 18, 20 * s, fill='#e3ded1', stroke=MUTED, rx=2)
            clear_wire(f'M{px} {y(z0) + 2} L{px} {y(z0 + 20) - 2}')
            g.add(f'<ellipse cx="{px}" cy="{y(z0 + 10)}" rx="12" ry="{6 * s}" fill="#eef0e6" fill-opacity=".85" stroke="{MUTED}" stroke-width="2"/>')
            for zt in (z0 + 2, z0 + 18):
                g.rect(px - 12, y(zt + 1.25), 24, round(2.5 * s), fill=BLK, stroke=BLK, sw=1, rx=2)
    # The other exits leave straight; the loose loops between lights come next.
    for side in (-1, 1):
        px = x(side * 23.15)
        clear_wire(f'M{px} {y(10)} L{px} {y(6)}')
        clear_wire(f'M{px} {y(56)} L{px} {y(60)}')
    g.text(24, y(60) - 14, 'Middle lights', size=22, weight=700)
    g.text(24, y(6) + 34, 'Lower lights', size=22, weight=700)
    g.text(406, y(6) + 34, 'Front upright', size=22, weight=700, anchor='end')
    g.wire([(330, y(6) + 14), (x(3), y(8))], MUTED, 1.5)
    g.text(406, y(60) - 14, 'Wires behind', size=22, weight=700, anchor='end')
    g.wire([(350, y(60) - 6), (x(-9), y(33.5))], MUTED, 1.5)
    g.save('circuits/body-light-wire-exits.svg')


def strand_test_connection():
    g=physical_action('BODY LIGHT · strand test',275)
    # The base half's sockets pushed into the strand's shrouded pins plug.
    left,right=jst_sm_mated(g,196,175)
    for dy,color in zip((-14,0,14),STRAND_WIRES):
        g.wire([(24,175+dy),(left,175+dy)],LEAD,5)
        g.wire([(right,175+dy),(396,175+dy)],color,4)
    g.text(24,130,'Base half',size=22,weight=700)
    g.text(396,130,'Likely input',size=22,anchor='end',weight=700)
    g.text(24,245,'F2 / C2 / R2',size=22)
    g.text(396,245,'Uncut strand',size=22,anchor='end')
    g.text(210,280,'JST-SM 2.5 mm (large)',size=22,anchor='middle')
    g.save('circuits/strand-test-connection.svg')


def strand_input_result():
    g = action('Strand · a positive input test', 510)
    g.text(24, 131, 'Connected end · INPUT', size=24, weight=700)
    rear = jst_sm_half(g, 'pins', 24, 184, facing='left')
    for dy, color in zip((-14, 0, 14), STRAND_WIRES):
        g.wire([(rear, 184 + dy), (rear + 8, 184 + dy), (rear + 16, 184)], color, 4)
    g.wire([(rear + 16, 184), (380, 184), (380, 290), (45, 290), (45, 396), (380, 396)], GRAY, 5)
    for i in range(16):
        if i < 8:
            x, y = 148 + i * 30, 184
        else:
            x, y = 358 - (i - 8) * 30, 290
        g.rect(x - 12, y - 15, 24, 30, fill='#f6dc79', stroke='#a89978', rx=9)
        g.rect(x - 6, y - 7, 12, 14, fill='#fffdec', stroke='#e7cb65', rx=3)
    g.text(24, 247, 'First 16 · lit in order', size=24, weight=700)
    for x in range(89, 375, 41):
        g.rect(x - 12, 381, 24, 30, fill='#deded4', stroke='#a89978', rx=9)
    lines(g, 452, 'Remaining 84 · dark')
    g.save('circuits/strand-input-result.svg')


def meter(g, x, y, reading, unit='DC V'):
    g.rect(x, y, 149, 189, fill='#d8aa43', stroke=INK, sw=3, rx=18)
    g.rect(x + 15, y + 20, 119, 47, fill='#d4dccb', rx=3)
    g.text(x + 74, y + 53, reading, size=27, anchor='middle', weight=700)
    g.text(x + 74, y + 94, unit, size=23, anchor='middle', weight=700)
    g.circle(x + 74, y + 126, 21, fill='#3d4650')
    g.wire([(x + 74, y + 127), (x + 85, y + 112)], '#fff', 3)
    for dx, color in ((39, BLK), (111, RED)):
        g.circle(x + dx, y + 169, 7, fill=color, stroke=INK)


def supply_polarity_test():
    g = action('Supply polarity', 725)
    g.text(210, 127, 'Barrel plug', size=24, anchor='middle', weight=700)
    g.circle(210, 228, 66, fill='#aeb6bb', sw=3)
    g.circle(210, 228, 48, fill='#272d33')
    g.circle(210, 228, 23, fill='#a99c78', stroke='#e0d6bb', sw=3)
    g.circle(210, 228, 12, fill='#272d33', stroke='none')
    # Tip in the hollow center; second tip contacts the outside metal sleeve.
    g.wire([(210, 228), (272, 300)], GRAY, 4)
    g.wire([(272, 300), (309, 346)], RED, 13)
    g.wire([(154, 236), (101, 300)], GRAY, 4)
    g.wire([(101, 300), (61, 346)], BLK, 13)
    g.text(24, 385, 'Black: outer sleeve', size=22)
    g.text(24, 416, 'Red: inside center', size=22, fill=RED)
    meter(g, 136, 460, '5.0–5.25')
    g.wire([(61, 346), (12, 346), (12, 656), (175, 656), (175, 629)], BLK, 4)
    g.wire([(309, 346), (367, 441), (367, 656), (247, 656), (247, 629)], RED, 4)
    g.save('circuits/supply-polarity-test.svg')


def robot_power_connection():
    g = action('Power supply connection', 555)
    # Side view of the hollow barrel plug and power jack, aligned for insertion.
    g.rect(70, 210, 108, 60, fill='#303740', rx=12)
    for xx in (82, 96, 110):
        g.wire([(xx, 216), (xx, 264)], GRAY, 2)
    g.rect(174, 222, 73, 36, fill='#c8cdd0', rx=2)
    g.rect(238, 229, 10, 22, fill='#353d43', rx=1)
    # A narrow section of the base wall locates the power jack, not a second board.
    g.rect(305, 145, 18, 170, fill='#825f47', stroke='none', rx=1)
    g.rect(291, 210, 18, 60, fill='#c0c6c9', rx=3)
    g.rect(309, 215, 69, 50, fill='#303740', rx=6)
    g.rect(292, 227, 10, 26, fill='#161b20', stroke='none', rx=1)
    g.wire([(295, 240), (325, 240)], '#bca46f', 4)
    g.wire([(250, 184), (289, 184)], BLUE, 4, arrow=True)
    g.text(70, 167, 'Barrel plug', size=24, weight=700)
    g.text(380, 127, 'Power jack (J1)', size=22, anchor='end', weight=700)
    g.wire([(70, 240), (36, 240), (36, 433), (84, 433)], '#303740', 7)
    # Recognizable enclosed desktop supply; mains connection intentionally off-view.
    g.rect(84, 379, 240, 106, fill='#303740', rx=16)
    g.rect(130, 398, 150, 65, fill='#deded7', stroke='none', rx=3)
    g.text(205, 425, '5 V DC · 5 A', size=23, anchor='middle', weight=700)
    g.text(205, 452, 'Center positive', size=22, anchor='middle')
    for xx in (96, 106, 116):
        g.wire([(xx, 394), (xx, 469)], '#626b72', 2)
    lines(g, 531, 'Mean Well GST40A05-P1J')
    g.save('circuits/robot-power-connection.svg')


def power_jack_terminals():
    g = action('J1 · identify the rear lugs', 947)
    # Publisher drawing orientation: sleeve top; shunt right; center lower-left.
    g.circle(211, 262, 110, fill='#d8d7cf', stroke=INK, sw=3)
    g.circle(211, 262, 89, fill='#e9e5db', stroke=GRAY)
    g.rect(189, 195, 44, 10, fill='#b9c4c9', rx=0)
    g.rect(272, 241, 10, 44, fill='#b9c4c9', rx=0)
    g.add('<path d="M143 266 L155 309 L163 306 L151 264 Z" fill="#b9c4c9" stroke="#292b3b" stroke-width="2"/>')
    g.wire([(211, 195), (211, 155)], BLK, 2)
    g.text(211, 136, 'SLEEVE → GND', size=24, anchor='middle', weight=700)
    g.wire([(281, 263), (350, 263), (350, 402)], MUTED, 2)
    g.text(396, 433, 'Unused switched lug', size=22, weight=700, anchor='end')
    g.wire([(150, 285), (66, 341), (66, 414)], RED, 2)
    g.text(24, 474, 'CENTER PIN → +5 V', size=24, fill=RED, weight=700)
    # Side enlargement: wire through lug eye, then insulated finished joint.
    lines(g, 614, '18 AWG lead')
    for y, covered in ((670, False), (765, True)):
        g.rect(38, y - 24, 56, 48, fill='#cccac1', rx=2)
        g.rect(94, y - 9, 68, 18, fill='#b9c4c9', rx=6)
        g.circle(144, y, 5, fill=PAPER)
        g.wire([(141, y), (188, y), (207, y + 5)], '#b9c4c9', 5)
        g.wire([(202, y + 5), (380, y + 5)], RED, 8)
        if covered:
            shrink(g, 95, y - 17, 128, 36)
    lines(g, 837, 'Heat-shrink over lug and joint')
    g.save('circuits/power-jack-lugs.svg')


def tie_mount():
    """Representative physical tie support, not a base placement plan."""
    g = Svg(420, 606, 'Support the capacitor body', crop=True)
    g.text(24, 116, 'Tie square', size=24, weight=700)
    # Loose adhesive square above a flat surface, seen from above and the side.
    g.add('<path d="M39 271 L227 271 L274 242 L86 242 Z" fill="#d7d9d8" stroke="#8d939a" stroke-width="2"/>')
    g.add('<path d="M73 214 L209 214 L246 190 L110 190 Z M73 214 L73 223 L209 223 L246 199 L246 190 M209 214 L209 223" fill="#e3ded1" stroke="#5c6070" stroke-width="2"/>')
    g.add('<path d="M116 203 L116 180 L177 180 L197 167 L136 167 L116 180 M177 180 L177 203 L197 190 L197 167" fill="#f8f5e9" stroke="#5c6070" stroke-width="2"/>')
    g.rect(129, 189, 34, 14, fill=BLK, stroke='none', rx=1)
    # Curled backing peels away from the adhesive face.
    g.add('<path d="M73 224 L142 224 Q131 197 89 184 L57 156 Q45 190 73 224 Z" fill="#efd08a" stroke="#a98040" stroke-width="2"/>')
    g.wire([(75, 193), (52, 170), (43, 144)], BLUE, 3, arrow=True)
    g.wire([(229, 216), (229, 256)], BLUE, 3, arrow=True)
    g.text(282, 211, 'Clean,', size=22)
    g.text(282, 239, 'flat face', size=22)
    g.text(24, 315, 'Cable tie', size=24, weight=700)
    # Square and raised tie bridge beneath the body, with its slot visible.
    g.add('<path d="M175 498 L267 498 L291 484 L199 484 Z M175 498 L175 506 L267 506 L291 492 L291 484 M267 498 L267 506" fill="#e3ded1" stroke="#5c6070" stroke-width="2"/>')
    g.rect(197, 474, 48, 24, fill='#f8f5e9', stroke=MUTED, rx=2)
    g.rect(206, 487, 29, 9, fill=BLK, stroke='none', rx=1)
    # Horizontal radial capacitor: rubber seal/leads left, uncovered vent right.
    g.add('<path d="M109 377 L306 377 A21 54 0 0 1 306 485 L109 485 Z" fill="#344752" stroke="#292b3b" stroke-width="2"/>')
    g.add('<ellipse cx="109" cy="431" rx="21" ry="54" fill="#262c33" stroke="#292b3b" stroke-width="2"/>')
    g.add('<ellipse cx="306" cy="431" rx="21" ry="54" fill="#bbc4c7" stroke="#292b3b" stroke-width="2"/>')
    g.wire([(297, 403), (315, 458)], GRAY, 2)
    g.wire([(315, 403), (297, 458)], GRAY, 2)
    g.wire([(100, 418), (78, 410), (50, 410)], RED, 6)
    g.wire([(100, 451), (77, 465), (50, 465)], BLK, 6)
    # Band wraps around the cylinder and passes through the mount's slot.
    g.add('<path d="M222 380 C197 380 193 398 193 432 C193 467 200 484 219 484 L219 491 L231 491 L231 484 C246 482 252 463 252 431 C252 400 248 386 231 380" fill="none" stroke="#ad7836" stroke-width="9" stroke-linejoin="round"/>')
    g.rect(221, 371, 23, 18, fill='#d5aa67', stroke='#875b46', rx=2)
    g.wire([(243, 378), (264, 358), (270, 333)], '#ad7836', 8)
    g.wire([(277, 360), (289, 334)], BLUE, 3, arrow=True)
    g.text(24, 353, 'Leads clear', size=22)
    g.wire([(99, 361), (106, 387)], MUTED, 1.5)
    g.text(408, 539, 'Vent clear', size=22, anchor='end')
    g.wire([(326, 514), (312, 472)], MUTED, 1.5)
    g.text(24, 547, 'Through slot', size=22)
    g.wire([(166, 533), (218, 493)], MUTED, 1.5)
    g.save('circuits/tie-mount.svg')


def harness_connections():
    g=action('Plugs and wire ends',761)
    for y,title,left_name,right_name in ((143,'Body light connector','Base half','Strand input'),(327,'Head light connector','Body half','Head half')):
        g.text(24,y,title,size=25,weight=700)
        cy=y+66
        left=jst_sm_half(g,'sockets',138,cy)
        right=jst_sm_half(g,'pins',250,cy,facing='left')
        far=STRAND_WIRES if right_name=='Strand input' else (LEAD,)*3
        for dy,color in zip((-14,0,14),far):
            g.wire([(24,cy+dy),(left,cy+dy)],LEAD,4)
            g.wire([(right,cy+dy),(396,cy+dy)],color,4)
        g.wire([(238,cy),(152,cy)],BLUE,3,arrow=True)
        g.text(24,y+120,left_name,size=22)
        g.text(396,y+120,right_name,size=22,anchor='end')
    lines(g,486,'Both pairs: JST-SM 2.5 mm (large)','Sockets: base half, head light body half','Pins: strand input, head half')
    g.text(24,591,'Each servo: three bare wire ends',size=24,weight=700)
    # Actual clamp faces rather than a connector icon at the servo ends.
    for y,color,label,terminal in ((626,RED,'Red · power','WAGO'),(672,SERVO_BROWN,'Brown · ground','WAGO'),(718,SERVO_ORANGE,'Orange · signal','shifter')):
        g.text(24,y+7,label,size=22)
        g.wire([(196,y),(228,y)],color,6)
        g.wire([(228,y),(252,y)],COPPER,4)
        if terminal=='WAGO':
            g.rect(267,y-17,47,33,fill='#dfded5',stroke=GRAY,rx=5)
            g.rect(288,y-22,17,17,fill='#ee8b35',stroke='#a25322',rx=2)
            g.circle(273,y,5,fill='#444',stroke='none')
        else:
            g.rect(267,y-17,47,33,fill='#3c9e68',stroke='#21633f',rx=3)
            g.circle(293,y-2,9,fill='#c3cbce',stroke=GRAY)
            g.wire([(287,y-6),(299,y+2)],MUTED,2)
        g.text(323,y+7,terminal,size=22)
    g.save('circuits/harness-connections.svg')


def circuit_actions():
    (OUT / 'circuits').mkdir(parents=True, exist_ok=True)
    power_jack_circuit(); pi_power_circuit(); wago_insertion(); harness_connections()
    servo_feed_prepare(); servo_feed_circuit()
    fuse_prep('F2', 'T1 A', 4, 'base-half +5 V / C2 +')
    c1_circuit(); ground_circuit(); c2_circuit(); f2_circuit()
    shifter_circuit('S1', {1: 'S1 V', 6: 'S1 G', 12: 'S1 DAT', 32: 'S1 CLK'})
    shifter_circuit('S2', {9: 'S2 G', 17: 'S2 V', 33: 'S2 DAT', 36: 'S2 CLK'})
    shifter_outputs()
    pi_pin1(); gpio_lead_preparation(); gpio_socket_insertion(); shifter_jumpers(); button_switch(); button_led(); usb_audio(); pi_bench_power()
    servo_circuit('LEFT', 2, 'S1 C5')
    servo_circuit('RIGHT', 3, 'S2 D5')
    servo_circuit('HEAD', 4, 'S2 C5')
    head_leads(); body_output(); head_power(); head_data()
    wago_reference()
    solder_detail(); capacitor_joint_detail(); mouth_solder(); cut_six()
    connector_seating(); eye_connector(); eye_cable(); power_overview()
    strand_wire_identification(); strand_test_connection(); strand_input_result(); body_light_wire_exits()
    supply_polarity_test(); robot_power_connection()
    power_jack_terminals(); button_terminals(); button_switch_check(); button_leads_prepare()
    button_leads_switch(); button_leads_led(); button_leads_done(); button_insert_threading(); tie_mount()


def main():
    import argparse
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Write into a new review directory instead of source assets.')
    parser.add_argument('--circuits', action='store_true', help='Generate only the narrow circuit action figures.')
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        OUT = args.out
    if not args.circuits:
        servo_fit_position()
    circuit_actions()
    print(f'ok: {OUT}')


if __name__ == '__main__':
    main()
