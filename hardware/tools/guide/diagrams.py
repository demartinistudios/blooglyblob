#!/usr/bin/env python3
"""Draw the guide's schematic SVG diagrams into hardware/build-guide/src/assets/.

Plans are schematic: positions follow the base layout but are not to scale.
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[3] / 'hardware/build-guide/src/assets'
INK, MUTED, PAPER, LINE = '#292b3b', '#5c6070', '#fbfaf6', '#c9c7c0'
RED, BLK, BLUE, GRAY, COPPER, ORANGE = '#c4302b', '#26262b', '#2f6fb5', '#8d939a', '#875b46', '#c8601d'
FONT = 'Arial,Helvetica,sans-serif'


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.parts = w, h, []
        self.rect(0, 0, w, h, fill=PAPER, stroke='none')
        self.text(28, 44, title, size=28, weight=700)

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

    def save(self, name):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" role="img">'
                f'<title>{escape(name)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0 0 L10 5 L0 10z" fill="{BLUE}"/></marker></defs>')
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
    g = Svg(1200, 700, 'Fit position')
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
    g.text(1170, 690, 'The robot returns to this position whenever the application starts.', size=16, anchor='end', fill=MUTED)
    g.save('servo-fit-position.svg')


# ------------------------------------------------------------------ phone-readable circuit actions
# Every figure is a schematic: component silhouettes help identification, but
# terminal positions on unverified products are never claimed as a pinout.
CIRCUIT_WIDTH = 420


def action(title, height=620, subtitle='Schematic · power unplugged'):
    g = Svg(CIRCUIT_WIDTH, height, title)
    g.text(24, 78, subtitle, size=22, fill=MUTED)
    return g


def lines(g, y, *rows, color=INK):
    for i, row in enumerate(rows):
        g.text(24, y + i * 29, row, size=22, fill=color)


def wago_port(g, y, block, port, color):
    """Front wire-entry face; adopted mounted order is 5,4,3,2,1."""
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
    g.circle(x, y, 8, fill='#b9c2c5', stroke=color, sw=3)


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


def jst(g, y, label):
    # Side silhouette and disconnected lead bundle; functions below are not
    # depicted as a mating-face contact order.
    g.text(24, y, label, size=25, weight=700)
    g.rect(132, y + 24, 110, 55, fill='#353943', rx=4)
    g.rect(156, y + 11, 65, 18, fill='#454d55', rx=2)
    g.rect(242, y + 29, 40, 45, fill='#252932', rx=3)
    for dy, color in ((39, RED), (52, BLK), (65, BLUE)):
        g.wire([(68, y + dy), (132, y + dy)], color, 5)
    g.text(24, y + 113, 'Identify contacts by continuity.', size=22)
    g.text(24, y + 142, 'This is not the socket pin order.', size=22, fill=MUTED)


def physical_action(title, height=620, subtitle='Connection view · not to scale'):
    g = action(title, height, subtitle)
    g.physical_wires = True
    return g


def port_point(port, y):
    return (228 + (5 - port) * 35, y + 1)


def sleeve(g, x, y, length=46, color='#47515b'):
    g.rect(x - 9, y, 18, length, fill=color, stroke=INK, sw=1, rx=4)


def plug_body(g, x, y):
    """Side of a JST-SM housing; wires are separated for tracing, not a pinout."""
    g.rect(x, y, 88, 51, fill='#303740', rx=4)
    g.rect(x + 13, y - 8, 49, 13, fill='#58626c', rx=2)
    g.rect(x + 88, y + 5, 20, 41, fill='#20262c', rx=2)
    for yy in (12, 26, 40):
        g.rect(x + 4, y + yy - 4, 10, 8, fill='#171b20', stroke='none', rx=1)


def wago_insertion():
    g = action('Insert a WAGO wire', 469, '221-415 · one wire per port')
    g.text(24, 121, '1  Strip 11 mm; leave copper bare.', size=22)
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
    g.text(24, 245, '2  Open', size=22)
    g.text(24, 369, '3  Insert fully; close the lever.', size=22)
    g.text(24, 403, 'Pull gently. It must stay in the port.', size=22)
    g.text(24, 432, 'Do not tin the end.', size=22)
    g.save('circuits/wago-insert.svg')


def power_jack_circuit():
    g = physical_action('Insert the power jack leads', 630, 'J1 rear view · soldered leads')
    # Same rear lug rotation as the verified 721AU preparation view.
    g.circle(165, 197, 78, fill='#d8d7cf', stroke=INK, sw=3)
    g.circle(165, 197, 61, fill='#e9e5db', stroke=GRAY)
    g.rect(150, 148, 30, 9, fill='#b9c4c9', rx=0)
    g.rect(209, 183, 9, 30, fill='#47515b', rx=2)
    g.add('<path d="M115 205 L125 235 L134 232 L124 202 Z" fill="#b9c4c9" stroke="#292b3b" stroke-width="2"/>')
    wago_port(g, 389, 'W1', 1, RED)
    wago_port(g, 526, 'W3', 1, BLK)
    g.wire([(125,226),(125,315),(190,315),(190,432),(368,432),port_point(1,389)], RED, 6)
    g.wire([(165, 152), (49, 152), (49, 570), (368, 570), port_point(1,526)], BLK, 6)
    sleeve(g,125,228,45)
    g.rect(139,143,44,18,fill='#47515b',rx=4)
    g.text(219, 145, 'Sleeve −', size=22)
    g.wire([(215,150),(183,152)], MUTED, 1.5)
    g.text(211, 250, 'Shunt capped', size=22)
    g.wire([(267,235),(217,205)], MUTED, 1.5)
    g.text(141, 291, 'Center +', size=22, fill=RED)
    g.text(24, 609, '18 AWG · trace each continuous wire', size=22)
    g.save('circuits/power-jack-leads.svg')

def pi_power_circuit():
    g = physical_action('Pi power lead', 625, 'Adafruit 4056 micro-B lead')
    pi_bench_board(g, 136, 111, 3.2)
    # Micro-B sits in the bottom-edge power socket, not the USB-A data port.
    g.rect(159, 292, 21, 13, fill='#bcc6cd', rx=1)
    g.rect(154, 304, 31, 45, fill='#303740', rx=5)
    for yy in (318,326,334):
        g.wire([(157,yy),(182,yy)],GRAY,1)
    g.text(24, 307, 'PWR IN', size=22)
    g.wire([(111,302),(148,300),(162,296)],MUTED,1.5)
    wago_port(g, 426, 'W1', 2, RED)
    wago_port(g, 549, 'W3', 2, BLK)
    g.wire([(163,349),(163,469),(333,469),port_point(2,426)],RED,6)
    traced_wire(g,[(176,349),(176,574),(333,574),port_point(2,549)],BLK,6)
    g.text(24, 602, '24 AWG · plug + lead ≤150 mm',size=22)
    g.save('circuits/pi-power.svg')

def fuse_prep(name, value, input_port, output):
    g = action(f'{name} · fuse holder loop', 485, '18 AWG factory loop')
    fuse_holder(g, 151, name, value)
    g.wire([(55, 190), (55, 304), (365, 304), (365, 190)], RED, 7)
    g.circle(210, 304, 21, fill=PAPER, stroke=ORANGE, sw=3)
    g.wire([(200, 294), (220, 314)], ORANGE, 3)
    g.wire([(220, 294), (200, 314)], ORANGE, 3)
    g.text(210, 359, 'Cut mark', size=22, anchor='middle')
    lines(g, 412, f'INPUT: W1/{input_port}', f'OUTPUT: {output}')
    g.save(f'circuits/{name.lower()}-prepare.svg')


def f1_circuit():
    g = physical_action('Servo fuse connections', 465, 'Connection view')
    wago_port(g, 146, 'W1', 3, RED)
    fuse_holder(g, 252, 'F1', 'T3.15 A')
    wago_port(g, 415, 'W2', 1, RED)
    g.wire([port_point(3,146),(298,187),(55,187),(55,291)],RED,7)
    g.wire([(365,291),(392,291),(392,445),(368,445),port_point(1,415)],RED,7)
    g.text(24, 337, '18 AWG',size=22)
    g.save('circuits/f1-connect.svg')

def c1_circuit():
    g = physical_action('Servo capacitor connections', 680, 'Connection view')
    capacitor(g, 123, 'C1')
    # Metal legs, soldered extensions, individual insulating sleeves.
    g.wire([(180,249),(180,308)],'#b9c2c5',4)
    g.wire([(244,249),(244,308)],'#b9c2c5',4)
    wago_port(g, 455, 'W2', 5, RED)
    wago_port(g, 578, 'W3', 4, BLK)
    g.wire([(180,300),(180,496),(228,496),port_point(5,455)],RED,6)
    g.wire([(244,300),(286,342),(392,342),(392,617),(263,617),port_point(4,578)],BLK,6)
    sleeve(g,180,251,75); sleeve(g,244,251,75)
    g.text(24, 121, '1000 µF',size=22)
    g.text(24, 150, '10 V',size=22)
    g.text(24, 356, 'Heat-shrink',size=22)
    g.wire([(126,340),(170,293)],MUTED,1.5)
    g.text(24, 660, '18 AWG tails · stripe is negative',size=22)
    g.save('circuits/c1.svg')

def ground_circuit():
    g = physical_action('Ground link', 365, 'Connection view')
    wago_port(g, 147, 'W3', 3, BLK)
    wago_port(g, 298, 'W4', 1, BLK)
    g.wire([port_point(3,147),(298,200),(389,200),(389,342),(368,342),port_point(1,298)],BLK,7)
    g.text(24, 218, 'One 18 AWG wire',size=22)
    g.save('circuits/ground-link.svg')

def c2_circuit():
    g = physical_action('Prepare the base half and C2', 721, 'Loose wires · before installation')
    capacitor(g, 130, 'C2')
    # C2's own legs reach the branch joints directly; there are no wire tails.
    # Individual sleeves run from the rubber seal toward each solder joint.
    for points in (
        [(180,256),(180,314),(107,352),(107,416)],
        [(244,256),(244,314),(322,360),(322,478)],
    ):
        g.wire(points, '#b9c2c5', 4)
        g.wire(points[:-1] + [(points[-1][0], points[-1][1] - 14)], '#47515b', 12)
    g.wire([(30,416),(196,416),(196,573),(229,573)],RED,6)
    traced_wire(g,[(30,478),(178,478),(178,587),(229,587)],BLK,6)
    traced_wire(g,[(322,478),(178,478)],BLK,6)
    # Solder wraps have length and insulation overlap, not schematic dots.
    g.rect(80,406,55,20,fill='#b9c2c5',stroke=GRAY,rx=8)
    g.rect(295,468,54,20,fill='#b9c2c5',stroke=GRAY,rx=8)
    g.wire([(30,531),(160,531),(160,601),(229,601)],BLUE,5)
    plug_body(g,229,561)
    g.text(24, 390, 'F2 output +',size=22,fill=RED)
    g.text(24, 453, 'Return to W3/5',size=22)
    g.text(24, 516, 'DATA to S1 D5',size=22,fill=BLUE)
    g.text(239, 648, 'Base half',size=22,weight=700)
    g.text(24, 680, 'C2: 1000 µF, 10 V · stripe to return',size=22)
    g.text(24, 709, 'Wire functions shown, not pin order.',size=22)
    g.save('circuits/c2-prepare.svg')

def f2_circuit():
    g = physical_action('Light fuse connections', 670, 'Connection view')
    wago_port(g, 143, 'W1', 4, RED)
    fuse_holder(g, 234, 'F2', 'T1 A')
    wago_port(g, 604, 'W3', 5, BLK)
    g.wire([port_point(4,143),(263,184),(55,184),(55,273)],RED,7)
    g.wire([(365,273),(385,273),(385,384),(105,384),(105,466),(256,466)],RED,6)
    traced_wire(g,[(256,480),(186,480),(186,645),(228,645),port_point(5,604)],BLK,6)
    g.wire([(256,494),(46,494),(46,542)],BLUE,5)
    plug_body(g,256,454)
    # Already-insulated capacitor branch, recognizable can shown beside it.
    g.rect(160,304,76,51,fill='#314a59',rx=8)
    g.rect(218,308,13,43,fill='#cdd5d4',stroke='none',rx=0)
    g.text(196,337,'C2',size=22,fill='#fff',anchor='middle')
    g.wire([(178,355),(178,384)],RED,5)
    traced_wire(g,[(223,355),(223,417),(186,417),(186,551)],BLK,5)
    g.rect(151,375,55,18,fill='#47515b',rx=5)
    sleeve(g,186,521,37)
    g.text(263, 540, 'Base half',size=24,weight=700)
    g.text(24, 574, 'S1 D5',size=22,fill=BLUE)
    g.save('circuits/f2-connect.svg')

def gpio_map(g, selected, y=140):
    """Header viewed from above the pins; USB end is at the bottom."""
    g.rect(25, y - 24, 94, 514, fill='#467952', stroke=INK, rx=6)
    g.rect(43, y - 13, 57, 492, fill='#292d30', stroke=INK, rx=2)
    for n in range(1, 41):
        x = 57 if n % 2 else 85
        yy = y + ((n - 1) // 2) * 24
        g.circle(x, yy, 7, fill='#eec469' if n in selected else '#8c8b75', stroke='none')
        if n in selected:
            g.wire([(x, yy), (132, yy)], BLUE, 2)
            g.text(144, yy + 7, f'{n} → {selected[n]}', size=23, weight=700)
    g.text(25, y - 36, '1', size=22, weight=700)
    g.text(90, y - 36, '2', size=22)
    g.rect(34, y + 502, 76, 43, fill='#bfc7ca', rx=2)
    g.rect(46, y + 513, 52, 18, fill='#30383d', rx=0)
    g.text(144, y + 531, 'USB end of Pi', size=22)


def traced_wire(g, points, color, width=5):
    # A paper-colored casing separates crossing insulated wires; no splice dot.
    g.wire(points, PAPER, width + 5)
    g.wire(points, color, width)


def header_board(g, selected, y=151):
    """Enlarged header on an oriented Pi locator, physical pins from pin side."""
    g.rect(17,y-25,106,431,fill='#397750',rx=10)
    g.rect(24,y+99,20,76,fill='#bac5c7',rx=2)
    g.rect(48,y-10,57,398,fill='#242a30',rx=2)
    for n in range(1,41):
        x=63 if n%2 else 90
        yy=y+((n-1)//2)*20
        g.circle(x,yy,4,fill='#daba6d',stroke='none')
        if n in selected:
            g.rect(x-8,yy-8,16,16,fill='#353b44',stroke=selected[n],sw=2,rx=1)

    g.rect(28,y+408,75,40,fill='#bfc7ca',rx=2)
    g.rect(40,y+419,51,16,fill='#30383d',rx=0)
    g.text(24,y-38,'1',size=22,weight=700)
    g.text(137,y+437,'USB end',size=22)
    return {n:(63 if n%2 else 90,y+((n-1)//2)*20) for n in selected}


def header_labels(g, pins):
    for n,(x,y) in pins.items():
        g.label(31 if n%2 else 122,y-7,str(n),size=22,anchor='middle',weight=700,pad=1)


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
    g=action('GPIO lead end',510,'Socket at Pi · bare wire at shifter')
    g.rect(28,152,58,37,fill='#303740',rx=3)
    g.rect(28,161,14,19,fill='#181e25',stroke='none',rx=0)
    g.wire([(86,170),(285,170)],BLUE,7)
    g.wire([(285,170),(349,170)],COPPER,4)
    g.text(24,130,'Keep the 2.54 mm female socket',size=22)
    g.text(24,231,'Remove the other connector; strip',size=22)
    g.text(24,260,'only enough for the terminal.',size=22)
    # Side entry and screw clamp, enlarged.
    g.rect(260,319,116,85,fill='#3c9e68',stroke='#21633f',rx=4)
    g.rect(265,354,65,28,fill='#254c39',rx=1)
    g.circle(320,339,14,fill='#c3cbce',stroke=GRAY)
    g.wire([(310,333),(330,345)],MUTED,3)
    g.wire([(34,367),(161,367)],BLUE,7)
    g.wire([(161,367),(222,367)],COPPER,4)
    g.wire([(166,327),(247,327)],BLUE,3,arrow=True)
    g.text(24,452,'Insert fully, then tighten the screw.',size=22)
    g.text(24,483,'No bare strands outside the block.',size=22)
    g.save('circuits/gpio-lead-prepare.svg')


def gpio_socket_insertion():
    g=action('Plug a socket onto the Pi',450,'One socket · one header pin')

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
    g.text(24,427,'Pi GPIO header · enlarged section',size=22,fill=MUTED)
    g.save('circuits/gpio-socket-insert.svg')


def shifter_circuit(name, selected, outputs):
    g=physical_action(f'Connect the Pi to {name}',820,'Pin-side view · sockets on Pi pins')
    colors={'G':BLK,'V':'#8754ad','DAT':BLUE,'CLK':ORANGE}
    pins=header_board(g,{n:colors[v.split()[-1]] for n,v in selected.items()})
    terminals=shifter_board(g,name)
    # Sleeved socket bodies stay visible; four continuous insulated leads.
    for i,(n,label) in enumerate(selected.items()):
        key=label.split()[-1]; x,y=pins[n]; xx,yy=terminals[key]
        lane=145+i*15
        traced_wire(g,[(x,y),(lane,y),(lane,yy),(xx,yy)],colors[key],4)
        g.rect(x-7,y-7,14,14,fill='#353b44',stroke=colors[key],sw=2,rx=1)
    header_labels(g,pins)
    g.text(209,487,'INPUT',size=22,weight=700)
    if name == 'S1':
        plug_body(g,208,518)
        traced_wire(g,[(405,342),(413,342),(413,501),(184,501),(184,558),(208,558)],BLUE,4)
        for yy in (530,544):
            g.wire([(166,yy),(208,yy)],GRAY,4)
        g.text(324,541,'Base',size=22,weight=700)
        g.text(324,568,'half',size=22,weight=700)

    # Canonical mapping remains explicit below the physical view.
    for i,(n,label) in enumerate(selected.items()):
        g.text(24 if i%2==0 else 215,640+(i//2)*32,f'{n} → {label}',size=23,weight=700)
    lines(g,718,f'D5 → {outputs[0]}',f'C5 → {outputs[1]}','!D5 and output G: unused.')
    g.save(f'circuits/{name.lower()}-inputs.svg')

def shifter_jumpers():
    # Adafruit pinouts: back, left of upper mounting hole, white Neo outline.
    g = action('Cut both Neo jumpers', 420, 'Back of board · locate “Neo”')
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
    lines(g, 342, 'Repeat on S1 and S2.', 'Check the cut is open with a meter.', 'Enlarged jumper')
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
    g.rect(x - 9, y - 15, 18, 30 + down, fill='#47515b', stroke='#1c2126', sw=1, rx=4)


def loose_sleeve(g, x, y):
    """A heat-shrink sleeve waiting on a vertical lead, pushed back from its joint."""
    g.rect(x - 9, y, 18, 34, fill='#6b7580', stroke='#1c2126', sw=1, rx=4)


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
    g = action('Identify the four tabs', 400, 'Rear view · retaining nut off')
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
    g = action('Check the switch pair', 470, 'Rear view · meter in continuity mode')
    cx, cy = 210, 200
    tabs = button_back(g, cx, cy)
    button_tab_labels(g, tabs, cx)
    for key, end, color in (('SW1', (96, 396), RED), ('SW2', (324, 396), BLK)):
        x, y = tabs[key]
        meter_probe(g, (x, y + 10), end, color)
    g.text(cx, 448, 'Beeps only while pressed', size=22, anchor='middle')
    g.save('circuits/button-switch-check.svg')


def button_leads_prepare():
    g = action('Prepare four leads', 500, 'GPIO jumper leads (E24)')
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
    g = action('Solder the switch leads', 440, 'From above · switch pair on top')
    y0 = 215
    tabs = button_top(g, y0, 26)
    for y, pin in zip(tabs, (11, 14)):
        traced_wire(g, [(222, y), (330, y)], BLUE, 4)
        g.rect(184, y - 8, 56, 16, fill='#47515b', stroke='#1c2126', sw=1, rx=4)   # shrunk sleeve
        side_socket(g, 330, y, pin)
    g.text(205, 146, 'Switch tabs', size=22, anchor='middle', weight=700)
    g.text(205, 310, 'Button on a bezel flat', size=22, anchor='middle', fill=MUTED)
    g.text(24, 386, 'Either lead fits either switch tab.', size=22)
    g.text(24, 418, 'LED pair underneath, still bare.', size=22, fill=MUTED)
    g.save('circuits/button-leads-switch.svg')


def button_leads_led():
    g = action('Solder the LED leads', 470, 'From above · LED pair on top')
    y0 = 225
    plus, minus = button_top(g, y0, 18)
    g.text(206, plus - 12, '+', size=24, anchor='middle', weight=700, fill=RED)
    g.text(206, minus + 30, '−', size=24, anchor='middle', weight=700)
    # LED −: lead 20 soldered straight to the tab; its sleeve waits on the lead.
    traced_wire(g, [(214, minus), (330, minus)], BLK, 4)
    joint(g, 214, minus, BLK)
    g.rect(262, minus - 7, 30, 14, fill='#6b7580', stroke='#1c2126', sw=1, rx=4)
    side_socket(g, 330, minus, 20)
    # LED +: R1 in line with the tab, pointing straight back; lead 4 on its free leg.
    g.wire([(206, plus), (234, plus)], GRAY, 3)
    small_resistor(g, 234, plus, 'R1', 36)
    g.wire([(270, plus), (282, plus)], GRAY, 3)
    traced_wire(g, [(282, plus), (330, plus)], RED, 4)
    joint(g, 282, plus, RED)
    g.rect(292, plus - 7, 34, 14, fill='#6b7580', stroke='#1c2126', sw=1, rx=4)
    side_socket(g, 330, plus, 4)
    g.label(252, 140, 'R1 · 1 kΩ', size=22, anchor='middle', weight=700)
    g.wire([(252, 146), (252, plus - 10)], '#ae855e', 2)
    g.text(24, 350, 'R1 points straight back', size=22)
    g.text(24, 381, 'in line with the + tab.', size=22)
    g.text(24, 422, 'Sleeves pushed back on 20 and 4.', size=22, fill=MUTED)
    g.save('circuits/button-leads-led.svg')


def callout(g, x, y, n):
    """A small numbered marker for the order of work."""
    g.circle(x, y, 16, fill=BLUE, stroke=BLUE, sw=1)
    g.text(x, y + 8, str(n), size=22, fill='#fff', anchor='middle', weight=700)


def button_insert_threading():
    g = action('Fit the button in its insert', 450, 'Side view · outside on the left')
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
    g.rect(118, y0 - 50, 16, 100, fill='#b3bac0', stroke=INK, sw=1, rx=2)
    # Sleeved tabs, then the four labeled Pi ends out of the back.
    rows = ((y0 - 27, 20, BLK), (y0 - 9, 4, RED), (y0 + 9, 11, BLUE), (y0 + 27, 14, BLUE))
    for i, (y, pin, color) in enumerate(rows):
        sy = 150 + i * 44
        traced_wire(g, [(250, y), (290, y), (326, sy), (340, sy)], color, 4)
        side_socket(g, 340, sy, pin)
    for y, pin, _ in rows:
        g.rect(212, y - 6, 58 if pin == 4 else 40, 12, fill='#47515b', stroke='#1c2126', sw=1, rx=3)
    callout(g, 360, 112, 1)
    callout(g, 74, y0 - 72, 2)
    callout(g, 152, y0 + 76, 3)
    g.text(24, 382, '1 · Pi ends through FB20 from outside', size=22)
    g.text(24, 413, '2 · Button pushed in after them', size=22)
    g.text(24, 444, '3 · Nut on the back, tightened', size=22)
    g.save('circuits/button-insert-thread.svg')


def button_leads_done():
    g = action('Insulate the LED leads', 420, 'Side view · leads straight back')
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
    g.add(f'<rect x="207" y="{y - 11}" width="80" height="22" rx="5" fill="#47515b" opacity=".55" stroke="#1c2126" stroke-width="1"/>')
    for yy, _, _ in (rows[0], rows[2], rows[3]):
        g.rect(207, yy - 7, 46, 14, fill='#47515b', stroke='#1c2126', sw=1, rx=4)
    g.label(262, 150, 'R1 under sleeve', size=22, anchor='middle', weight=700)
    g.wire([(262, 156), (262, y - 12)], '#ae855e', 2)
    g.text(24, 364, 'Every tab and joint sleeved.', size=22)
    g.text(24, 396, 'Leads stay inside the body outline.', size=22)
    g.save('circuits/button-leads-done.svg')


def button_rear(g, x, y):
    """Finished button rear for the header views: every tab sleeved; returns the tab points."""
    tabs = button_back(g, x, y)
    button_tab_labels(g, tabs, x)
    return tabs


def r1_end_on(g, x, y):
    """R1 seen end-on: it points straight back from the LED + tab, toward the viewer, under its sleeve."""
    g.circle(x, y, 14, fill='#47515b', stroke='#1c2126', sw=1)
    g.circle(x, y, 7, fill='#e5c798', stroke=INK, sw=1)


def button_switch():
    g=physical_action('Connect the button switch',685,'Button rear · LED pair above switch')
    points=header_board(g,{11:BLUE,14:BLUE})
    tabs=button_rear(g,285,305)
    # The LED leads are drawn as stubs; they connect in the next panel.
    lx,ly=tabs['LED−']
    g.wire([(lx,ly-15),(lx,ly-35)],BLK,5)
    tab_sleeve(g,lx,ly)
    r1_end_on(g,*tabs['LED+'])
    sw1,sw2=tabs['SW1'],tabs['SW2']
    traced_wire(g,[points[11],(154,251),(154,452),(sw1[0],452),(sw1[0],sw1[1])],BLUE)
    traced_wire(g,[points[14],(178,271),(178,478),(sw2[0],478),(sw2[0],sw2[1])],BLUE)
    for tx,ty in (sw1,sw2): tab_sleeve(g,tx,ty)
    header_labels(g,points)
    g.text(24,626,'Pin 11 · GPIO17 → switch',size=22)
    g.text(24,657,'Pin 14 · GND → other switch tab',size=22)
    g.save('circuits/button-switch.svg')


def button_led():
    g=physical_action('Connect the button light',690,'Button rear · LED pair above switch')
    points=header_board(g,{4:RED,20:BLK})
    tabs=button_rear(g,285,365)
    # The switch leads are drawn as stubs; they connect in the previous panel.
    for key in ('SW1','SW2'):
        tx,ty=tabs[key]
        g.wire([(tx,ty+33),(tx,ty+55)],BLUE,5)
        tab_sleeve(g,tx,ty)
    lx,ly=tabs['LED−']
    traced_wire(g,[points[20],(151,331),(151,ly),(lx,ly)],BLK)
    tab_sleeve(g,lx,ly)
    px,py=tabs['LED+']
    # R1 points straight back from the LED + tab (toward the viewer); lead 4 leaves its free leg.
    traced_wire(g,[points[4],(170,171),(170,236),(396,236),(396,py),(px,py)],RED)
    r1_end_on(g,px,py)
    g.label(px+40,222,'R1 · 1 kΩ',size=22,anchor='middle',weight=700)
    g.wire([(px+30,228),(px+8,py-12)],'#ae855e',2)
    header_labels(g,points)
    g.text(24,625,'Pi pin 4 · +5 V → R1 → LED +',size=22)
    g.text(24,657,'Pi pin 20 · GND → LED −',size=22)
    g.save('circuits/button-led.svg')


def button_pins():
    g = action('Button · locate Pi pins', 745, 'Physical pins · viewed from above')
    gpio_map(g, {4: 'R1 → LED +', 11: 'switch NO', 14: 'switch return', 20: 'LED −'}, 152)
    g.text(24, 737, 'Switch and LED are separate pairs.', size=22)
    g.save('circuits/button-pins.svg')


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
    g = action('USB audio connections', 680, 'Two plug-in connections')
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
    g = action('Bench power for the Pi', 620, 'Separate from the USB audio cable')
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
    g = physical_action(f'{name} · servo hookup', 675, 'Connection view')
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
    traced_wire(g, [(187, 253), (187, 390), (px, 390), (px, py)], RED, 6)
    gx, gy = port_point(port, 480)
    traced_wire(g, [(211, 253), (211, 274), (400, 274), (400, 520), (gx, 520), (gx, gy)], BLK, 6)
    traced_wire(g, [(235, 253), (235, 264), (412, 264), (412, 615), (390, 615)], BLUE, 5)
    g.text(24, 423, f'{name} positive (+)', size=22)
    g.text(24, 552, f'{name} return (−)', size=22)
    g.save(f'circuits/servo-{name.lower()}.svg')


def body_input():
    g=physical_action('Make the input harness',560,'Body half · bench soldering')
    plug_body(g,278,128)
    g.text(24,120,'Body half',size=24,weight=700)
    g.wire([(278,140),(52,140),(52,395),(180,395)],RED,6)
    g.wire([(278,154),(77,154),(77,437),(180,437)],BLK,6)
    g.wire([(278,168),(260,168),(260,282),(252,282)],BLUE,5)
    resistor(g,135,282,'R2')
    g.wire([(108,282),(100,282),(100,416),(180,416)],BLUE,5)
    # Resin pebble, three continuous strand conductors, encapsulated LED.
    g.rect(178,380,90,73,fill='#ece8d9',stroke='#a5a899',rx=31)
    for yy,color in ((395,RED),(416,BLUE),(437,BLK)):
        g.wire([(267,yy),(390,yy)],color,4)
    g.rect(207,399,31,31,fill='#fafcf9',stroke='#bdc4bd',rx=6)
    g.rect(216,408,13,13,fill='#eee7bb',stroke='none',rx=3)
    g.text(178,482,'First pebble',size=24,weight=700)
    lines(g,521,'Keep R2 close; insulate its two joints.')
    g.save('circuits/body-input.svg')

def body_power():
    g=physical_action('Add the head power pair',632,'Two separate soldered branches')
    plug_body(g,277,119)
    g.text(24,126,'Body half',size=24,weight=700)
    # Splice topology: one incoming body-half wire, strand plus head power pair.
    g.wire([(277,131),(81,131),(81,323)],RED,6)
    g.wire([(277,145),(134,145),(134,384)],BLK,6)
    g.wire([(277,159),(190,159),(190,248),(210,248)],BLUE,5)
    g.wire([(300,248),(327,248),(327,397)],BLUE,5)
    g.rect(210,238,90,20,fill='#47515b',rx=6)
    g.text(254,222,'R2 inside',size=22,anchor='middle')
    g.wire([(81,309),(81,428),(36,428),(36,511)],RED,6)
    g.wire([(134,370),(134,464),(103,464),(103,511)],BLK,6)
    traced_wire(g,[(81,322),(297,322),(297,397)],RED,6)
    traced_wire(g,[(134,384),(357,384),(357,397)],BLK,6)
    sleeve(g,81,299,39);sleeve(g,134,361,40)
    for x in (36,103): sleeve(g,x,491,36)
    g.rect(275,398,105,66,fill='#ece8d9',stroke='#a5a899',rx=29)
    g.rect(313,416,31,31,fill='#fafcf9',stroke='#bdc4bd',rx=6)
    g.text(211,494,'Strand input',size=22,weight=700)
    g.text(24,561,'Head power pair +/GND · 22 AWG',size=22)
    g.text(24,596,'Cap each until HEAD LIGHT is fitted.',size=22)
    g.text(24,625,'DATA stays separate from power.',size=22)
    g.save('circuits/body-power.svg')

def body_output():
    g = action('Body · after light 5', 612)
    g.rect(156, 131, 108, 70, fill='#fff2c9', stroke='#a89978', rx=30)
    g.rect(190, 147, 38, 38, fill='#fafcf9', stroke='#e2d48b', rx=8)
    g.text(210, 119, 'Light 5 output end', size=26, anchor='middle', weight=700)
    g.wire([(170, 201), (170, 295), (63, 295)], RED, 5)
    g.wire([(249, 201), (249, 326), (63, 326)], BLK, 5)
    for y in (295, 326):
        g.rect(42, y - 9, 28, 18, fill='#636b73', rx=5)
    g.text(24, 374, 'Thin + / −: insulate separately.', size=22)
    g.wire([(210, 201), (210, 275), (365, 275), (365, 419), (210, 419)], BLUE, 5)
    g.text(24, 455, 'DOUT → head light cable', size=26, weight=700)
    lines(g, 506, 'Head power comes from the 22 AWG', 'head power pair at the input.', 'Check HEAD LIGHT by continuity.', 'The strand’s output power is unused.')
    g.save('circuits/body-output.svg')


def head_power():
    g = physical_action('Head · power branches', 810)
    g.text(24, 122, 'Head half', size=25, weight=700)
    plug_body(g, 276, 133)
    g.text(137, 265, '+5 V / GND', size=22)
    g.text(137, 296, '22 AWG pair', size=22)
    # First eye and mouth appear once; these power pads are functional locators,
    # not a claim about connector contact order or the stick's physical pinout.
    g.rect(60, 485, 100, 90, fill='#292f38', rx=9)
    g.rect(52, 490, 16, 70, fill='#e6e6dc', rx=2)
    g.rect(91, 513, 38, 34, fill='#fcfcf7', stroke='#aeb7b6', rx=3)
    g.circle(110, 530, 11, fill='#e5ddb0', stroke='none')
    g.rect(245, 485, 150, 90, fill='#283436', rx=5)
    for i in range(8):
        g.rect(255 + i * 16, 520, 12, 22, fill='#fcfcf7', stroke='#aeb7b6', rx=1)
    # Separate junctions, separate rails, and continuous leads to both loads.
    traced_wire(g, [(276, 145), (36, 145), (36, 350)], RED, 5)
    traced_wire(g, [(36, 350), (36, 500), (52, 500)], RED, 5)
    traced_wire(g, [(36, 350), (225, 350), (225, 500), (245, 500)], RED, 5)
    traced_wire(g, [(276, 159), (100, 159), (100, 390)], BLK, 5)
    traced_wire(g, [(100, 390), (100, 440), (30, 440), (30, 550), (52, 550)], BLK, 5)
    traced_wire(g, [(100, 390), (205, 390), (205, 550), (245, 550)], BLK, 5)
    joint(g, 36, 350, RED)
    joint(g, 100, 390, BLK)
    for x, y, color in ((52, 500, RED), (52, 550, BLK), (245, 500, RED), (245, 550, BLK)):
        g.circle(x, y, 5, fill='#c8a96a', stroke=color, sw=2)
    g.text(24, 617, '5755 → eye IN', size=24, weight=700)
    g.text(260, 617, 'Mouth', size=24, weight=700)
    lines(g, 659, '6404 carries power to eye 2.', 'Mouth power has its own branch.',
          'Power shown; DATA is separate.', 'Contact positions are schematic.',
          'Solder and insulate each joint.')
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
    g = action('Head · data path', 782, 'Eyes 6–7 · mouth 8–15')
    lines(g, 131, 'Head half DATA → 5755 → first eye IN', 'Either eye may be first.')
    eye(g, 241, 6, 'First eye')
    g.wire([(92, 284), (92, 357)], BLUE, 4, arrow=True)
    g.text(156, 320, '6404 cable', size=24, weight=700)
    g.text(156, 352, 'OUT → IN', size=22)
    eye(g, 412, 7, 'Second eye')
    g.wire([(92, 455), (92, 555)], BLUE, 4, arrow=True)
    g.text(156, 500, '5755 data only', size=22)
    g.rect(24, 582, 372, 52, fill='#2f413c', rx=5)
    for i in range(8):
        g.rect(35 + i * 45, 593, 31, 30, fill='#f6f3e7', stroke='#adab8b', rx=3)
    g.text(210, 570, 'Mouth DIN · lights 8–15', size=24, anchor='middle', weight=700)
    lines(g, 680, 'Second 5755 red and black wires:', 'insulate separately; leave unused.', 'Mouth DOUT: leave unused.')
    g.save('circuits/head-data.svg')


def wago_reference():
    import json
    root = Path(__file__).resolve().parents[3]
    power = json.loads((root / 'hardware/assembly/electrical.json').read_text())['power']['rows']
    # Canonical table content is used directly; manual wrapping never changes
    # terminal allocations. Four narrow figures replace the all-wire tangle.
    for row in power:
        block = row[0].split()[0]
        g = action(row[0], 685, 'Port reference · use block labels')
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
        lines(g, 620, 'WAGO 221-415 · strip 11 mm.', 'One untinned wire per port.')
        g.save(f'circuits/{block.lower()}-reference.svg')


def solder_detail():
    g = action('Solder and cover each joint', 690, 'Bench detail · wires disconnected')
    lines(g, 133, '1 · Slide heat-shrink on first.')
    g.wire([(41, 177), (153, 177)], RED, 9)
    g.rect(68, 164, 53, 26, fill='#656c74', rx=5)
    g.wire([(153, 177), (187, 177)], COPPER, 6)
    g.wire([(238, 177), (274, 177)], COPPER, 6)
    g.wire([(274, 177), (376, 177)], RED, 9)
    lines(g, 263, '2 · Join the bare ends; solder.')
    g.wire([(41, 316), (172, 316)], RED, 9)
    g.rect(68, 303, 53, 26, fill='#656c74', rx=5)
    g.wire([(170, 316), (251, 316)], COPPER, 6)
    g.rect(183, 308, 55, 16, fill='#c2c9cb', stroke=GRAY, rx=8)
    g.wire([(252, 316), (376, 316)], RED, 9)
    lines(g, 403, '3 · Cover all bare metal; shrink.')
    g.wire([(41, 453), (376, 453)], RED, 9)
    g.rect(153, 442, 125, 22, fill='#424b55', rx=6)
    lines(g, 522, 'Finished: sleeve overlaps insulation', 'at both ends. Pull gently to check.')
    lines(g, 612, 'Use separately on +, − and DATA.', 'Keep joints away from moving bends.')
    g.save('circuits/solder-insulation.svg')


def capacitor_joint_detail():
    g = action('C2 · positive branch joint', 735, 'Positive leg and +5 V wires')
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
        leg = [(224, y + 6), (270, y + 40), (310, y + 40), (310, y + 73)]
        g.wire(leg, '#b9c2c5', 4)
        # Negative leg continues separately to the return branch, outside detail.
        g.wire([(355, y + 73), (355, y + 36)], '#47515b', 10)
        g.text(355, y + 26, 'GND', size=22, anchor='middle')
        if covered:
            g.wire(leg, '#47515b', 12)
            g.rect(159, y - 18, 99, 39, fill='#424b55', rx=6)
        else:
            g.rect(192, y - 10, 50, 24, fill='#c2c9cb', stroke=GRAY, rx=8)
        g.text(24, y + 76, 'Positive leg', size=22)
        g.wire([(149, y + 70), (267, y + 40)], MUTED, 1.5)
        g.text(24, y + 134, 'Heat-shrink to seal' if covered else 'Soldered branch', size=22)
        if covered:
            g.wire([(228, y + 130), (306, y + 73)], MUTED, 1.5)
    g.save('circuits/capacitor-joint.svg')


def mouth_solder():
    g = action('Mouth · solder three leads', 767, 'Pad functions · follow board labels')
    g.rect(24, 118, 372, 52, fill='#2f413c', rx=5)
    for i in range(8):
        g.rect(35 + i * 45, 129, 31, 30, fill='#f6f3e7', stroke='#adab8b', rx=3)
    lines(g, 213, 'Adafruit 1426 · eight LEDs', 'Find +5V, GND and DIN on the back.')
    # Isolated pad detail: never claims an unverified board pad arrangement.
    for y, color, pad, source in ((318, RED, '+5V', 'Head power pair +5 V · 22 AWG'), (438, BLK, 'GND', 'Head power pair GND · 22 AWG'), (558, BLUE, 'DIN', 'Second eye OUT · 5755 data')):
        g.text(24, y - 33, source, size=22)
        g.wire([(28, y), (234, y)], color, 6)
        g.rect(198, y - 12, 36, 24, fill='#444e56', rx=3)
        g.rect(234, y - 22, 141, 44, fill='#2f413c', rx=2)
        g.circle(257, y, 11, fill='#c4cbd0', stroke='#d8bc72', sw=4)
        g.wire([(234, y), (257, y)], '#c4cbd0', 5)
        g.text(281, y + 8, pad, size=24, fill='#fff', weight=700)
    lines(g, 628, 'Sleeves cover exposed wire ends.', 'No solder bridges between pads.', 'Pad details shown separately;', 'positions above are not a pinout.', 'DOUT: leave unused.')
    g.save('circuits/mouth-solder.svg')


def cut_six():
    g = action('Body · keep six pebbles', 850, 'Cut only after the strand test passes')
    g.text(24, 127, 'Mark the tested INPUT end.', size=24, weight=700)
    g.wire([(91, 152), (91, 722)], BLUE, 5)
    ordinals = ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th')
    for i, ordinal in enumerate(ordinals):
        y = 192 + i * 78
        g.rect(51, y - 22, 81, 45, fill='#fff2c9', stroke='#a89978', rx=21)
        g.rect(79, y - 11, 24, 23, fill='#fafcf9', stroke='#e2d48b', rx=4)
        g.text(158, y + 8, f'{ordinal} pebble · light {i}' if i < 6 else '7th pebble · remove', size=23, weight=700 if i==5 else 400)
    g.wire([(38, 622), (372, 622)], ORANGE, 3, dash='7 5')
    g.text(158, 614, 'Cut halfway here.', size=23, fill=ORANGE, weight=700)
    lines(g, 752, 'Keep lights 0–5 from the input end.', 'Leave wire after light 5 for the', 'head light cable.')
    g.save('circuits/cut-six.svg')


def connector_seating():
    g = action('JST-SM · align and seat', 605, 'Body and head light connectors')
    lines(g, 133, '+5 V · GND · DATA')
    for y, seated in ((250, False), (431, True)):
        right = 221 if seated else 278
        for dy in (-10, 0, 10):
            g.wire([(32, y + dy), (103, y + dy)], GRAY, 4)
            g.wire([(right + 70, y + dy), (391, y + dy)], GRAY, 4)
        g.rect(103, y - 25, 118, 50, fill='#353943', rx=4)
        g.rect(126, y - 42, 77, 17, fill='#4a515b', rx=2)
        g.rect(right, y - 24, 70, 48, fill='#252932', rx=3)
        g.rect(right + 7, y - 39, 33, 15, fill='#5e646d', rx=2)
        if not seated:
            g.wire([(257, y), (231, y)], BLUE, 3, arrow=True)
        else:
            g.wire([(195, y - 36), (232, y - 36)], '#7f8993', 6)
    lines(g, 321, 'Align the key and latch; push', 'the housings straight together.')
    lines(g, 503, 'Finished: latch engaged, no gap.', 'Pull the housings gently to check.', 'Release the latch before unplugging.')
    g.save('circuits/jst-sm-seat.svg')


def eye_connector():
    g = action('Eye · plug into IN', 714, 'Adafruit 5975 · connector side')
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
        for dy in (-12, 0, 12):
            g.wire([(33, y + 80 + dy), (plug_x, y + 80 + dy)], GRAY, 4)
        if not seated:
            g.wire([(148, y + 80), (190, y + 80)], BLUE, 3, arrow=True)
    lines(g, 354, 'Align the key; push the housing.')
    lines(g, 610, 'Finished: plug fully in the IN socket.', 'Hold housings when unplugging.', 'First eye OUT → second eye IN.')
    g.save('circuits/eye-connector.svg')


def power_overview():
    g = action('Power · three branches', 833, 'Reference schematic · no mains inside')
    lines(g, 138, 'External 5 V, 5 A supply', '→ J1 center → W1 INPUT +5 V')
    g.wire([(49, 201), (49, 614)], RED, 6)
    branches = ((238, 'W1/2 → Pi power lead', 'Pi USB → audio', 'Unfused supply branch'),
                (416, 'W1/3 → F1 T3.15 A', '→ W2 → three servos', 'C1 across W2 and W3'),
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
    g = action('Strand · identify the wires', 685, 'Adafruit 6026 · inspect your strand')
    lines(g, 129, 'Clear insulation · enlarged detail')
    # Three clear insulated wires, copper identification marks on +5 V.
    for y in (197, 263, 329):
        g.wire([(36, y), (384, y)], '#d7d9d3', 14)
        g.wire([(36, y), (384, y)], '#aaa797', 3)
    for x in range(84, 280, 24):
        g.wire([(x, 190), (x + 8, 204)], COPPER, 4)
    g.text(24, 174, 'Copper coil / dots → +5 V', size=24, weight=700)
    g.text(24, 242, 'Middle wire → DATA (normally)', size=22)
    g.text(24, 309, 'Other outer wire → GND', size=22)
    lines(g, 387, 'Trace each to its factory lead:')
    for y, color, label in ((427, RED, 'red → +5 V'), (470, '#397548', 'green → DATA'), (513, BLK, 'black → GND')):
        g.wire([(29, y), (99, y)], color, 8)
        g.text(121, y + 8, label, size=24, weight=700)
    lines(g, 577, 'Lots can differ. Stop if marks or', 'colors are missing or disagree.', 'Connector sex does not show input.')
    g.save('circuits/strand-wire-identification.svg')


def strand_test_connection():
    g=physical_action('BODY LIGHT · test connection',275,'100-pebble strand')
    # Two keyed housings, fully mated; wires continue at both ends.
    plug_body(g,118,149)
    g.rect(226,154,61,41,fill='#303740',rx=4)
    g.rect(238,143,28,11,fill='#58626c',rx=2)
    for yy,color in ((161,RED),(175,BLK),(189,BLUE)):
        g.wire([(24,yy),(118,yy)],color,5)
        g.wire([(287,yy),(384,yy)],color,5)
    g.text(24,130,'Base half',size=22,weight=700)
    g.text(287,130,'Body half',size=22,anchor='end',weight=700)
    g.text(24,245,'F2 / S1',size=22)
    g.text(221,245,'Prepared strand',size=22)
    g.save('circuits/strand-test-connection.svg')

def strand_input_result():
    g = action('Strand · a positive input test', 510, '100-pebble strand · uncut')
    g.text(24, 131, 'Connected end · INPUT', size=24, weight=700)
    g.rect(26, 163, 67, 42, fill='#353943', rx=4)
    g.wire([(93, 184), (380, 184), (380, 290), (45, 290), (45, 396), (380, 396)], GRAY, 5)
    for i in range(16):
        if i < 8:
            x, y = 119 + i * 34, 184
        else:
            x, y = 357 - (i - 8) * 34, 290
        g.rect(x - 12, y - 15, 24, 30, fill='#f6dc79', stroke='#a89978', rx=9)
        g.rect(x - 6, y - 7, 12, 14, fill='#fffdec', stroke='#e7cb65', rx=3)
    g.text(24, 247, 'First 16 · light in sequence', size=24, weight=700)
    for x in range(89, 375, 41):
        g.rect(x - 12, 381, 24, 30, fill='#deded4', stroke='#a89978', rx=9)
    lines(g, 452, 'Remaining 84 · should stay dark', 'Remainder shown shortened.')
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
    g = action('Supply polarity', 725, 'Supply on · disconnected from robot')
    g.text(210, 127, 'Barrel plug · front view', size=24, anchor='middle', weight=700)
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
    lines(g, 701, 'Positive reading · no minus sign.')
    g.save('circuits/supply-polarity-test.svg')


def robot_power_connection():
    g = action('Power supply connection', 555, 'Barrel plug and power jack · side view')
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
    g = action('J1 · identify the rear lugs', 947, 'Switchcraft 721AU · rear / solder view')
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
    lines(g, 526, 'Confirm each with continuity.', 'Match the drawing’s rotation first.')
    # Side enlargement: wire through lug eye, then insulated finished joint.
    lines(g, 614, 'Solder 18 AWG leads on the bench.')
    for y, covered in ((670, False), (765, True)):
        g.rect(38, y - 24, 56, 48, fill='#cccac1', rx=2)
        g.rect(94, y - 9, 68, 18, fill='#b9c4c9', rx=6)
        g.circle(144, y, 5, fill=PAPER)
        g.wire([(141, y), (188, y), (207, y + 5)], '#b9c4c9', 5)
        g.wire([(202, y + 5), (380, y + 5)], RED, 8)
        if covered:
            g.rect(95, y - 17, 128, 36, fill='#424b55', rx=6)
    lines(g, 837, 'Cover the full lug and bare wire.', 'Insulate both joints separately;', 'Cap the unused switched lug.')
    g.save('circuits/power-jack-lugs.svg')


def tie_mount():
    """Representative physical tie support, not a base placement plan."""
    g = Svg(420, 606, 'Support the capacitor body')
    g.text(24, 77, 'Representative placement', size=22, fill=MUTED)
    g.text(24, 116, '1  Peel, then press', size=24, weight=700)
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
    g.text(24, 315, '2  Loop, then snug', size=24, weight=700)
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
    g.text(24, 589, 'Bond first. Snug; do not crush.', size=22)
    g.save('circuits/tie-mount.svg')


def harness_connections():
    g=action('Plugs and wire ends',701,'Label both halves before connecting')
    for y,title,left,right in ((143,'Body light connector','Base half','Body half'),(327,'Head light connector','Body half','Head half')):
        g.text(24,y,title,size=25,weight=700)
        plug_body(g,85,y+36)
        # Mating housing separated to reveal the keyed interface.
        g.rect(242,y+41,65,41,fill='#303740',rx=4)
        g.rect(247,y+29,28,12,fill='#58626c',rx=2)
        g.rect(242,y+47,8,29,fill='#131a20',rx=0)
        for yy in (y+48,y+62,y+76):
            g.wire([(24,yy),(85,yy)],'#51545b',4)
            g.wire([(307,yy),(389,yy)],'#51545b',4)
        g.wire([(233,y+62),(205,y+62)],BLUE,3,arrow=True)
        g.text(24,y+120,left,size=22)
        g.text(316,y+120,right,size=22)
    g.text(24,486,'Both pairs: +5 V, GND and DATA',size=22)
    g.text(24,531,'Each servo: three bare wire ends',size=24,weight=700)
    # Actual clamp faces rather than a connector icon at the servo ends.
    for y,color,label,terminal in ((566,RED,'Power','WAGO'),(612,BLK,'Ground','WAGO'),(658,BLUE,'Signal','shifter')):
        g.text(24,y+7,label,size=22)
        g.wire([(132,y),(218,y)],color,6)
        g.wire([(218,y),(249,y)],COPPER,4)
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
    fuse_prep('F1', 'T3.15 A', 3, 'W2/1')
    fuse_prep('F2', 'T1 A', 4, 'base-half +5 V / C2 +')
    f1_circuit(); c1_circuit(); ground_circuit(); c2_circuit(); f2_circuit()
    shifter_circuit('S1', {1: 'S1 V', 6: 'S1 G', 12: 'S1 DAT', 32: 'S1 CLK'}, ('base-half DATA', 'LEFT'))
    shifter_circuit('S2', {9: 'S2 G', 17: 'S2 V', 33: 'S2 DAT', 36: 'S2 CLK'}, ('RIGHT', 'HEAD'))
    gpio_lead_preparation(); gpio_socket_insertion(); shifter_jumpers(); button_switch(); button_led(); button_pins(); usb_audio(); pi_bench_power()
    servo_circuit('LEFT', 2, 'S1 C5')
    servo_circuit('RIGHT', 3, 'S2 D5')
    servo_circuit('HEAD', 4, 'S2 C5')
    body_input(); body_power(); body_output(); head_power(); head_data()
    wago_reference()
    solder_detail(); capacitor_joint_detail(); mouth_solder(); cut_six()
    connector_seating(); eye_connector(); power_overview()
    strand_wire_identification(); strand_test_connection(); strand_input_result()
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
