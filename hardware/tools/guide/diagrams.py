#!/usr/bin/env python3
"""Draw the guide's schematic SVG diagrams into hardware/build-guide/src/assets/.

Plans are schematic: positions follow the enclosure layout but are not to scale.
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


def legend(g, x, y, items):
    for i, (color, s, dash) in enumerate(items):
        yy = y + i * 28
        g.wire([(x, yy), (x + 44, yy)], color, dash=dash)
        g.text(x + 56, yy + 6, s, size=17, fill=MUTED)


# ------------------------------------------------------------------ base wiring plan
def tag(g, x, y, s, color, anchor='middle', size=14):
    # A short colored lead stub with its name: what lands on this terminal.
    w = max(len(s) * size * 0.56 + 12, 30)
    x0 = x - w / 2 if anchor == 'middle' else x if anchor == 'start' else x - w
    g.rect(x0, y, w, size + 10, fill='#fff', stroke=color, sw=2.5, rx=5)
    g.text(x0 + w / 2, y + size + 3, s, size=size, anchor='middle', fill=INK, weight=700)
    return x0, w


def base_wiring():
    g = Svg(1200, 960, 'Base wiring, seen from below')
    g.text(28, 72, 'Each tag names the lead on that terminal: red +5 V, black return, blue signal. WAGO wire entries face the front. Not to scale.', size=17, fill=MUTED)
    X0, Y0, X1, Y1 = 60, 130, 1140, 880
    g.rect(X0, Y0, X1 - X0, Y1 - Y0, fill='#f1efe8', stroke=GRAY, sw=3, rx=34)
    g.text((X0 + X1) / 2, Y0 - 10, 'REAR (backpack side)', size=17, fill=MUTED, anchor='middle', weight=700)
    g.text((X0 + X1) / 2, Y1 + 30, 'FRONT (face side)', size=17, fill=MUTED, anchor='middle', weight=700)
    g.text(X0 - 16, (Y0 + Y1) / 2, 'ROBOT-LEFT', size=17, fill=MUTED, anchor='middle', weight=700, rotate=-90)
    g.text(X1 + 28, (Y0 + Y1) / 2, 'ROBOT-RIGHT', size=17, fill=MUTED, anchor='middle', weight=700, rotate=90)

    # WAGOs along the robot-left wall, W1 at the rear; port 1 is the end nearest the robot's right.
    PW, BX = 62, 90
    rows = [('W1', 'W1  INPUT +5 V', ['J1 center +', 'H2 Pi +', 'F1 in', 'F2 in', 'empty']),
            ('W2', 'W2  SERVO +5 V', ['F1 out', 'LEFT +', 'RIGHT +', 'HEAD +', 'C1 +']),
            ('W3', 'W3  GND', ['J1 sleeve', 'H2 Pi −', 'link to W4', 'C1 −', 'H3 −']),
            ('W4', 'W4  GND', ['link from W3', 'LEFT −', 'RIGHT −', 'HEAD −', 'empty'])]
    for i, (w, name, leads) in enumerate(rows):
        y = 190 + i * 158
        g.text(BX, y - 12, name, size=17, weight=700)
        g.rect(BX, y, PW * 5, 40, fill='#f5d97a', stroke='#8a6d1c', rx=5)
        for p in range(1, 6):
            x = BX + PW * 5 - (p - 0.5) * PW
            g.rect(x - 16, y + 8, 32, 24, fill='#fff', stroke='#8a6d1c', sw=1.5, rx=3)
            g.text(x, y + 26, str(p), size=15, anchor='middle', weight=700)
            lead = leads[p - 1]
            if lead == 'empty':
                g.text(x, y + 62, 'empty', size=13, anchor='middle', fill=MUTED, italic=True)
                continue
            color = RED if '+' in lead or w in ('W1', 'W2') else BLK
            g.wire([(x, y + 40), (x, y + 48 + (p % 2) * 30)], color, 4)
            words = lead.split(' ')
            tag(g, x, y + 48 + (p % 2) * 30, lead, color, size=12)

    def part(x, y, w, h, name, fill, sub=''):
        g.rect(x, y, w, h, fill=fill, stroke=INK, rx=8)
        g.text(x + w / 2, y - 8, name, size=16, anchor='middle', weight=700)
        if sub:
            g.text(x + w / 2, y + h / 2 + 5, sub, size=14, anchor='middle', fill='#fff' if fill in ('#2d2f3a', '#6f9b72') else INK)

    # Inlet at the rear corner, robot-left
    g.circle(460, 180, 24, fill='#ddd', stroke=INK)
    g.circle(460, 180, 8, fill=INK, stroke=INK)
    g.text(460, 148, 'J1 power inlet', size=16, anchor='middle', weight=700)
    tag(g, 500, 160, 'center → W1/1', RED, anchor='start', size=12)
    tag(g, 500, 186, 'sleeve → W3/1', BLK, anchor='start', size=12)
    # Fuses at the rear
    for x0, name, left, right, lc, rc in ((470, 'F2  T1 A (lighting)', 'out → H3 + and C2 +', 'in ← W1/4', RED, RED),
                                          (760, 'F1  T3.15 A (servos)', 'in ← W1/3', 'out → W2/1', RED, RED)):
        g.rect(x0 + 40, 262, 170, 34, fill='#9fb9d3', stroke=INK, rx=15)
        g.text(x0 + 125, 254, name, size=15, anchor='middle', weight=700)
        tag(g, x0 + 40, 306, left, lc, anchor='start', size=12)
        tag(g, x0 + 210, 336, right, rc, anchor='end', size=12)
    g.circle(508, 279, 24, fill='none', stroke=ORANGE, sw=3)
    g.text(470, 380, 'clamp meter here', size=14, fill=ORANGE, weight=700)
    g.text(470, 397, '(F2 output wire)', size=13, fill=ORANGE)
    # Capacitors
    for (x, y), name, tags in (((520, 470), 'C2', [('+ on H3 +5 V', RED), ('− on H3 return', BLK)]),
                               ((520, 600), 'C1', [('+ → W2/5', RED), ('− → W3/4', BLK)])):
        g.circle(x, y, 22, fill='#3b4652', stroke=INK)
        g.text(x, y + 6, name, size=15, anchor='middle', fill='#fff', weight=700)
        tag(g, x + 32, y - 26, tags[0][0], tags[0][1], anchor='start', size=12)
        tag(g, x + 32, y + 2, tags[1][0], tags[1][1], anchor='start', size=12)
    # Center hole
    HX, HY = 720, 560
    g.circle(HX, HY, 50, fill='#fff', stroke=GRAY, sw=3, dash='6 5')
    g.text(HX, HY - 6, 'center hole', size=14, anchor='middle', fill=MUTED)
    g.text(HX, HY + 12, 'to the body', size=14, anchor='middle', fill=MUTED)
    g.text(HX, HY + 76, 'servo leads LEFT, RIGHT, HEAD', size=14, anchor='middle', fill=MUTED)
    g.text(HX, HY + 94, 'and the BASE→BODY plug', size=14, anchor='middle', fill=MUTED)
    # Level shifters
    for (x, y), name, d5, c5, ins in (((900, 380), 'S1 level shifter', 'D5 → H3 DATA (lights)', 'C5 → LEFT signal', 'in: Pi pins 1, 6, 12, 32'),
                                      ((640, 690), 'S2 level shifter', 'D5 → RIGHT signal', 'C5 → HEAD signal', 'in: Pi pins 17, 9, 33, 36')):
        part(x, y, 150, 64, name, '#2d2f3a', ins.split(':')[0])
        tag(g, x + 150, y + 76, d5, BLUE, anchor='end', size=12)
        tag(g, x + 150, y + 102, c5, BLUE, anchor='end', size=12)
        g.text(x, y + 150, ins, size=13, fill=MUTED)
    # Pi
    part(900, 560, 210, 250, 'Raspberry Pi', '#6f9b72', '')
    g.text(1005, 690, 'GPIO header → S1, S2', size=14, anchor='middle', fill='#fff')
    g.text(1005, 710, 'and the button', size=14, anchor='middle', fill='#fff')
    tag(g, 1005, 780, 'H2 → W1/2 +, W3/2 −', RED, size=12)
    tag(g, 1005, 596, 'USB → audio module', GRAY, size=12)
    # Audio, button, speakers
    part(330, 818, 230, 44, 'USB audio module', '#e4e2da', '')
    g.text(445, 846, 'speaker pairs stay separate', size=13, anchor='middle', fill=MUTED)
    g.circle(640, 838 - 700 + 700, 0, fill='none', stroke='none')
    g.circle(120, 836, 18, fill='#fff', stroke=COPPER, sw=4)
    g.text(146, 842, 'button', size=14)
    for sx in (X0 + 6, X1 - 24):
        g.rect(sx, 640, 18, 120, fill='#ccc', stroke=INK, rx=4)
        g.text(sx + 9, 700, 'speaker', size=12, anchor='middle', fill=INK, rotate=-90)
    g.save('base-wiring.svg')


# ------------------------------------------------------------------ power block diagram
def box(g, x, y, w, h, title, sub='', fill='#fff', stroke=INK):
    g.rect(x, y, w, h, fill=fill, stroke=stroke, rx=10)
    g.text(x + w / 2, y + (h / 2 if not sub else h / 2 - 5), title, size=19, anchor='middle', weight=700)
    if sub:
        g.text(x + w / 2, y + h / 2 + 19, sub, size=15, anchor='middle', fill=MUTED)


def power_diagram():
    g = Svg(1200, 720, 'Power distribution')
    box(g, 30, 290, 170, 80, '5 V supply', 'E20 · 5 V, 5 A', fill='#eee')
    g.text(115, 400, 'stays outside', size=14, anchor='middle', fill=MUTED)
    box(g, 250, 290, 120, 80, 'J1 inlet', '')
    box(g, 420, 280, 150, 100, 'W1', 'input +5 V', fill='#f5d97a')
    g.wire([(200, 330), (250, 330)], RED, 5)
    g.wire([(370, 330), (420, 330)], RED, 5)
    # Pi branch (before the fuses)
    box(g, 700, 90, 170, 80, 'H2 Pi lead', '150 mm max')
    box(g, 950, 90, 210, 80, 'Raspberry Pi', 'micro-USB power')
    g.wire([(570, 300), (620, 300), (620, 130), (700, 130)], RED, 4)
    g.wire([(870, 130), (950, 130)], RED, 4)
    g.text(700, 192, 'no fuse: relies on the supply’s', size=14, fill=ORANGE)
    g.text(700, 210, 'overload shutdown', size=14, fill=ORANGE)
    box(g, 950, 200, 210, 60, 'USB audio', '→ two speakers')
    g.wire([(1055, 170), (1055, 200)], GRAY, 4)
    box(g, 950, 20, 210, 50, 'Button light', 'Pi 5 V → R1')
    g.wire([(1055, 90), (1055, 70)], RED, 3)
    # Servo branch
    box(g, 640, 290, 130, 80, 'F1', 'T3.15 A', fill='#9fb9d3')
    box(g, 820, 280, 130, 100, 'W2', 'servo +5 V', fill='#f5d97a')
    box(g, 1000, 290, 160, 80, '3 servos', 'left · right · head')
    g.wire([(570, 330), (640, 330)], RED, 5)
    g.wire([(770, 330), (820, 330)], RED, 5)
    g.wire([(950, 330), (1000, 330)], RED, 5)
    g.circle(885, 420, 20, fill='#3b4652', stroke=INK)
    g.text(885, 426, 'C1', size=14, anchor='middle', fill='#fff', weight=700)
    g.wire([(885, 380), (885, 400)], RED, 3)
    # Lighting branch
    box(g, 640, 480, 130, 80, 'F2', 'T1 A', fill='#9fb9d3')
    box(g, 820, 480, 150, 80, 'H3 + C2', 'lighting lead')
    g.wire([(570, 360), (600, 360), (600, 520), (640, 520)], RED, 5)
    g.wire([(770, 520), (820, 520)], RED, 5)
    box(g, 1010, 440, 150, 60, 'Body lights', '0–5 on the strand')
    box(g, 1010, 540, 150, 70, 'Head', 'eyes 6–7, mouth 8–15')
    g.wire([(970, 505), (990, 505), (990, 470), (1010, 470)], RED, 4)
    g.wire([(970, 535), (990, 535), (990, 575), (1010, 575)], RED, 4)
    g.text(1085, 632, 'via BASE→BODY, then HEAD', size=14, anchor='middle', fill=MUTED)
    # Returns
    box(g, 250, 560, 150, 80, 'W3', 'GND', fill='#f5d97a')
    box(g, 460, 560, 150, 80, 'W4', 'GND (servos)', fill='#f5d97a')
    g.wire([(400, 600), (460, 600)], BLK, 5)
    g.text(430, 588, '18 AWG', size=13, anchor='middle', fill=MUTED)
    g.wire([(310, 370), (310, 560)], BLK, 4, dash='8 6')
    g.text(320, 470, 'every return comes back here', size=15, fill=MUTED)
    legend(g, 30, 690, [(RED, '+5 V', None)])
    legend(g, 160, 690, [(BLK, 'return (GND)', None)])
    g.text(1170, 700, 'Not to scale. No mains wiring inside the robot.', size=15, anchor='end', fill=MUTED)
    g.save('power-diagram.svg')


# ------------------------------------------------------------------ Pi pin map
def pi_pin_map():
    names = {1: '3.3 V', 2: '5 V', 3: 'BCM2', 4: '5 V', 5: 'BCM3', 6: 'GND', 7: 'BCM4', 8: 'BCM14', 9: 'GND', 10: 'BCM15',
             11: 'BCM17', 12: 'BCM18', 13: 'BCM27', 14: 'GND', 15: 'BCM22', 16: 'BCM23', 17: '3.3 V', 18: 'BCM24', 19: 'BCM10', 20: 'GND',
             21: 'BCM9', 22: 'BCM25', 23: 'BCM11', 24: 'BCM8', 25: 'GND', 26: 'BCM7', 27: 'ID_SD', 28: 'ID_SC', 29: 'BCM5', 30: 'GND',
             31: 'BCM6', 32: 'BCM12', 33: 'BCM13', 34: 'GND', 35: 'BCM19', 36: 'BCM16', 37: 'BCM26', 38: 'BCM20', 39: 'GND', 40: 'BCM21'}
    used = {1: ('S1 V', '#e3963e'), 6: ('S1 G', BLK), 12: ('S1 DAT · lights', BLUE), 32: ('S1 CLK · left shoulder', BLUE),
            17: ('S2 V', '#e3963e'), 9: ('S2 G', BLK), 33: ('S2 DAT · right shoulder', BLUE), 36: ('S2 CLK · head', BLUE),
            11: ('button switch', BLUE), 14: ('button switch', BLK), 4: ('R1 → button light +', RED), 20: ('button light −', BLK)}
    test = {2: 'test lead (5 V)', 39: 'test lead (GND)'}
    g = Svg(1000, 1110, 'Pi header pins, seen from above the pins')
    # Board sketch showing where pin 1 is
    g.rect(40, 80, 330, 250, fill='#6f9b72', stroke=INK, rx=12)
    g.rect(70, 96, 270, 32, fill='#1f2a1f', stroke='none', rx=4)
    g.rect(74, 100, 18, 12, fill='#f7d046', stroke=INK, sw=1, rx=1)
    g.text(83, 150, 'pin 1', size=16, fill='#fff', anchor='middle', weight=700)
    g.rect(330, 190, 56, 70, fill='#ccc', stroke=INK, rx=4)
    g.text(310, 232, 'USB', size=16, fill='#fff', anchor='end', weight=700)
    g.text(205, 300, 'Raspberry Pi 3 Model A+', size=16, fill='#fff', anchor='middle')
    for i, line in enumerate(['Pin 1 is at the end of the header farthest', 'from the USB socket. On the underside,', 'its solder pad is square.', '', 'BCM numbers are software names;', 'pin numbers are header positions.', '', 'Pins 2 and 39 carry only the temporary', 'test leads used in the power checks.']):
        g.text(430, 110 + i * 26, line, size=18, fill=INK if i < 3 else MUTED)
    legend(g, 430, 360, [('#e3963e', '3.3 V', None), (RED, '5 V', None)])
    legend(g, 620, 360, [(BLK, 'GND', None), (BLUE, 'signal', None)])
    cx, top, pitch = 500, 450, 31
    g.rect(cx - 36, top - 20, 72, pitch * 19 + 40, fill='#1f2a1f', stroke=INK, rx=6)
    for n in range(1, 41):
        row, left = (n - 1) // 2, n % 2 == 1
        x, y = (cx - 17 if left else cx + 17), top + row * pitch
        color = used.get(n, (None, None))[1]
        fill = color or ('#f7d046' if n in test else '#b9b9b9')
        if n == 1:
            g.rect(x - 10, y - 10, 20, 20, fill=fill, stroke='#fff', sw=2, rx=1)
        else:
            g.circle(x, y, 10, fill=fill, stroke='#fff' if color else '#777', sw=1.5)
        sign, anchor = (-1, 'end') if left else (1, 'start')
        g.text(cx + sign * 48, y + 5, str(n), size=14, anchor=anchor, weight=700)
        g.text(cx + sign * 78, y + 5, names[n], size=14, anchor=anchor, fill=MUTED)
        txt = used[n][0] if n in used else test.get(n, '')
        if txt:
            g.text(cx + sign * 150, y + 6, txt, size=16, anchor=anchor, weight=700 if n in used else 400, italic=n in test)
    g.save('pi-pin-map.svg')


# ------------------------------------------------------------------ lighting chain
def lights(g, x, y, n, first, gap=46, r=15, color='#fff4c8'):
    for i in range(n):
        g.circle(x + i * gap, y, r, fill=color, stroke=INK)
        g.text(x + i * gap, y + 5, str(first + i), size=14, anchor='middle', weight=700)


def led_chain():
    g = Svg(1300, 640, 'The lighting chain: one data line through 16 lights')
    # Data row
    box(g, 30, 110, 140, 70, 'Pi GPIO18', 'pin 12')
    box(g, 220, 110, 150, 70, 'S1', 'DAT in → D5 out')
    box(g, 420, 110, 110, 70, 'R2', '330 Ω')
    g.rect(580, 95, 330, 100, fill='#fff', stroke=COPPER, rx=10)
    g.text(745, 88, 'Body strand (already joined)', size=15, anchor='middle', fill=COPPER, weight=700)
    lights(g, 610, 145, 6, 0, gap=54)
    box(g, 960, 110, 130, 70, 'HEAD plug', '')
    for a, b in ((170, 220), (370, 420), (530, 580), (910, 960)):
        g.wire([(a, 145), (b - 4, 145)], BLUE, 4, arrow=True)
    g.label(395, 225, 'BASE→BODY plug', size=14, fill=MUTED, anchor='middle')
    g.wire([(395, 110), (395, 180)], GRAY, 3, dash='5 4')
    g.label(915, 225, 'light 5 out = HEAD DATA', size=14, fill=MUTED)
    # Head row
    g.rect(90, 290, 1150, 150, fill='#fff', stroke=COPPER, rx=12)
    g.text(110, 318, 'In the head', size=16, fill=COPPER, weight=700)
    box(g, 130, 340, 170, 80, 'First eye', 'light 6 · IN → OUT')
    box(g, 400, 340, 170, 80, 'Second eye', 'light 7 · IN → OUT')
    g.rect(680, 340, 520, 80, fill='#fff', stroke=INK, rx=10)
    g.text(700, 364, 'Mouth stick: DIN → lights 8–15 (DOUT unused)', size=15, fill=INK, weight=700)
    lights(g, 715, 395, 8, 8, gap=60, r=13)
    g.wire([(1025, 180), (1025, 250), (60, 250), (60, 380), (126, 380)], BLUE, 4, arrow=True)
    g.wire([(300, 380), (396, 380)], BLUE, 4, arrow=True)
    g.wire([(570, 380), (676, 380)], BLUE, 4, arrow=True)
    g.label(348, 372, '6404', size=13, fill=MUTED, anchor='middle')
    g.label(622, 372, '5755 data wire', size=13, fill=MUTED, anchor='middle')
    # Power row
    g.text(30, 500, 'Power doesn’t follow the data:', size=18, weight=700)
    g.wire([(40, 535), (84, 535)], RED, 4)
    g.text(96, 541, 'F2 → H3 → BASE→BODY → the strand’s own wires power lights 0–5; its outgoing power wires after light 5 are insulated.', size=16, fill=MUTED)
    g.wire([(40, 570), (84, 570)], RED, 4)
    g.text(96, 576, 'A separate 22 AWG pair → HEAD → splits to the first eye’s IN (the 6404 cable powers the second eye)', size=16, fill=MUTED)
    g.text(96, 600, 'and straight to the mouth stick’s power pads.', size=16, fill=MUTED)
    g.save('led-chain.svg')


# ------------------------------------------------------------------ body strand joins
def body_strand():
    g = Svg(1200, 560, 'Body strand joins (body side)')
    g.rect(30, 150, 120, 180, fill='#fff', stroke=INK, rx=10)
    g.text(90, 140, 'BASE→BODY', size=15, anchor='middle', weight=700)
    g.text(90, 348, 'body half', size=14, anchor='middle', fill=MUTED)
    ys = {'+5 V': 190, 'GND': 240, 'DATA': 290}
    for k, y in ys.items():
        g.text(90, y + 5, k, size=14, anchor='middle', weight=700)
    # strand
    xs = [420 + i * 110 for i in range(6)]
    for i, x in enumerate(xs):
        g.circle(x, 240, 22, fill='#fff4c8', stroke=INK)
        g.text(x, 246, str(i), size=16, anchor='middle', weight=700)
    # power rails along the strand (drawn above/below the pebbles)
    g.wire([(150, ys['+5 V']), (260, ys['+5 V']), (260, 200), (xs[-1] + 60, 200)], RED, 4)
    g.wire([(150, ys['GND']), (240, ys['GND']), (240, 280), (xs[-1] + 60, 280)], BLK, 4)
    for x in xs:
        g.wire([(x, 200), (x, 218)], RED, 3)
        g.wire([(x, 262), (x, 280)], BLK, 3)
    # data through R2, then pebble to pebble
    g.wire([(150, ys['DATA']), (220, ys['DATA']), (220, 330), (290, 330)], BLUE, 4)
    g.rect(290, 316, 70, 28, fill='#e8d6b0', stroke=INK, rx=6)
    g.text(325, 336, 'R2', size=15, anchor='middle', weight=700)
    g.wire([(360, 330), (380, 330), (380, 240), (396, 240)], BLUE, 4, arrow=True)
    for a, b in zip(xs, xs[1:]):
        g.wire([(a + 22, 240), (b - 26, 240)], BLUE, 3, arrow=True)
    g.text(290, 372, '330 Ω, close to light 0', size=14, fill=MUTED)
    # end caps on the outgoing power
    for y, c in ((200, RED), (280, BLK)):
        g.rect(xs[-1] + 60, y - 9, 26, 18, fill='#555', stroke=c, rx=4)
    g.text(xs[-1] + 96, 196, 'outgoing power:', size=14, fill=MUTED)
    g.text(xs[-1] + 96, 214, 'insulate, unused', size=14, fill=MUTED)
    # head pair and HEAD plug
    HX = 1000
    g.rect(HX, 400, 150, 130, fill='#fff', stroke=INK, rx=10)
    g.text(HX + 75, 392, 'HEAD (body half)', size=15, anchor='middle', weight=700)
    for k, y in (('+5 V', 430), ('GND', 465), ('DATA', 500)):
        g.text(HX + 75, y + 5, k, size=14, anchor='middle', weight=700)
    g.wire([(260, 200), (260, 430), (HX, 430)], RED, 4)
    g.wire([(240, 280), (240, 465), (HX, 465)], BLK, 4)
    g.dot(260, 200, RED, 6)
    g.dot(240, 280, BLK, 6)
    g.text(270, 422, 'new 22 AWG head pair', size=15, fill=MUTED)
    g.wire([(xs[-1] + 22, 240), (xs[-1] + 40, 240), (xs[-1] + 40, 500), (HX, 500)], BLUE, 4, arrow=False)
    g.text(xs[-1] + 50, 330, 'light 5 out', size=14, fill=MUTED)
    g.text(xs[-1] + 50, 348, '= HEAD DATA', size=14, fill=MUTED)
    g.text(30, 540, 'The joins are soldered and insulated. Pebbles sit about 100 mm apart on the strand; the loops aren’t drawn.', size=15, fill=MUTED)
    g.save('body-strand.svg')


# ------------------------------------------------------------------ servo fit pose
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


def servo_fit_pose():
    g = Svg(1200, 700, 'Fit pose and rest pose')
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
    g.text(1170, 690, 'The robot returns to this pose whenever the application starts.', size=16, anchor='end', fill=MUTED)
    g.save('servo-fit-pose.svg')


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
    g = action('Insert a WAGO wire', 440, '221-415 · one wire per port')
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
    g.text(24, 403, 'Gently pull-check. Do not tin the end.', size=22)
    g.save('circuits/wago-insert.svg')


def inlet_circuit():
    g = physical_action('Land the two inlet leads', 630, 'J1 rear view · soldered leads')
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
    g.save('circuits/inlet.svg')

def pi_power_circuit():
    g = physical_action('Connect the Pi power lead', 645, 'H2 · Adafruit 4056 micro-B lead')
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
    g.text(24, 631, 'Verify polarity before plugging in.',size=22)
    g.save('circuits/pi-power.svg')

def fuse_prep(name, value, input_port, output):
    g = action(f'{name} · prepare the holder', 690)
    fuse_holder(g, 151, name, value)
    g.wire([(55, 190), (55, 304), (365, 304), (365, 190)], RED, 7)
    g.circle(210, 304, 21, fill=PAPER, stroke=ORANGE, sw=3)
    g.wire([(200, 294), (220, 314)], ORANGE, 3)
    g.wire([(220, 294), (200, 314)], ORANGE, 3)
    g.text(210, 359, 'Mark, then cut the loop once.', size=22, anchor='middle')
    lines(g, 412, f'INPUT: W1/{input_port}', f'OUTPUT: {output}', 'Dry-route both ends before cutting.', 'Keep the fuse out while wiring.')
    lines(g, 566, 'Factory loop: 18 AWG.', 'Output extension, if needed:', '18 AWG; solder and insulate.', 'Keep the holder opening accessible.')
    g.save(f'circuits/{name.lower()}-prepare.svg')


def f1_circuit():
    g = physical_action('Connect the servo fuse', 491)
    wago_port(g, 146, 'W1', 3, RED)
    fuse_holder(g, 252, 'F1', 'T3.15 A')
    wago_port(g, 415, 'W2', 1, RED)
    g.wire([port_point(3,146),(298,187),(55,187),(55,291)],RED,7)
    g.wire([(365,291),(392,291),(392,445),(368,445),port_point(1,415)],RED,7)
    g.text(24, 337, '18 AWG · fuse out while wiring',size=22)
    g.text(24, 481, 'No direct W1-to-W2 link.',size=22,weight=700)
    g.save('circuits/f1-land.svg')

def c1_circuit():
    g = physical_action('Connect the servo capacitor', 680)
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
    g.text(24, 356, 'Sleeve each leg',size=22)
    g.wire([(126,340),(170,293)],MUTED,1.5)
    g.text(24, 660, '18 AWG tails · stripe is negative',size=22)
    g.save('circuits/c1.svg')

def ground_circuit():
    g = physical_action('Join the ground blocks', 382)
    wago_port(g, 147, 'W3', 3, BLK)
    wago_port(g, 298, 'W4', 1, BLK)
    g.wire([port_point(3,147),(298,200),(389,200),(389,342),(368,342),port_point(1,298)],BLK,7)
    g.text(24, 218, 'One 18 AWG wire',size=22)
    g.text(24, 370, 'W3/3 to W4/1 · leave port 5 empty',size=22)
    g.save('circuits/ground-link.svg')

def c2_circuit():
    g = physical_action('Prepare H3 and C2', 721, 'Loose harness · before installation')
    capacitor(g, 130, 'C2')
    # C2 legs attach to insulated tails; staggered positive/negative splices.
    g.wire([(180,256),(180,324)],'#b9c2c5',4)
    g.wire([(244,256),(244,324)],'#b9c2c5',4)
    g.wire([(180,314),(107,352),(107,416)],RED,6)
    g.wire([(244,314),(322,360),(322,478)],BLK,6)
    sleeve(g,180,258,68); sleeve(g,244,258,68)
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
    g.text(239, 648, 'H3 base half',size=22,weight=700)
    g.text(24, 680, 'C2: 1000 µF, 10 V · stripe to return',size=22)
    g.text(24, 709, 'Wire functions shown, not pin order.',size=22)
    g.save('circuits/c2-prepare.svg')

def f2_circuit():
    g = physical_action('Land the lighting harness', 728)
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
    g.text(263, 540, 'H3',size=24,weight=700)
    g.text(24, 574, 'S1 D5',size=22,fill=BLUE)
    g.text(24, 666, 'One return wire in W3/5.',size=22)
    g.text(24, 697, 'Leave BASE→BODY disconnected.',size=22)
    g.save('circuits/f2-land.svg')

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
    g=action('Prepare eight GPIO leads',510,'Socket at Pi · bare wire at shifter')
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
        g.text(324,551,'H3',size=22,weight=700)

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
    lines(g, 342, 'Repeat on S1 and S2.', 'Check the cut is open with a meter.', 'Enlarged locator · not to scale')
    g.save('circuits/shifter-neo.svg')


def button_rear(g, x, y):
    g.circle(x,y,99,fill='#c7cbce',stroke=INK,sw=3)
    g.circle(x,y,87,fill='#343b43',stroke=GRAY,sw=2)
    g.text(x,y-45,'LED',size=22,fill='#eee',anchor='middle')
    for xx,yy in ((x-25,y-15),(x+26,y-15),(x-35,y+41),(x+36,y+41)):
        g.rect(xx-5,yy-9,10,23,fill='#c6cdd1',rx=1)
    g.text(x-50,y-6,'−',size=22,fill='#fff',anchor='middle')
    g.text(x+51,y-6,'+',size=22,fill='#fff',anchor='middle')
    g.text(x,y+26,'SW',size=22,fill='#eee',anchor='middle')


def button_switch():
    g=physical_action('Connect the button switch',685,'Button rear · LED pair above switch')
    points=header_board(g,{11:BLUE,14:BLK})
    button_rear(g,285,305)
    traced_wire(g,[points[11],(154,251),(154,461),(250,461),(250,356)],BLUE)
    traced_wire(g,[points[14],(178,271),(178,487),(321,487),(321,356)],BLK)
    for xx in (250,321): sleeve(g,xx,343,27)
    header_labels(g,points)
    g.text(24,626,'Pin 11 · GPIO17 → switch',size=22)
    g.text(24,657,'Pin 14 · GND → other switch tab',size=22)
    g.save('circuits/button-switch.svg')

def button_led(prepare=False):
    title='Prepare the button light' if prepare else 'Connect the button light'
    g=physical_action(title,735,'Button rear · LED pair above switch')
    if prepare:
        points={4:(90,171),20:(90,331)}
        g.text(24,120,'Leave Pi ends unplugged',size=22,weight=700)
        for n,(x,y) in points.items():
            g.rect(x-45,y-12,45,24,fill='#303740',rx=3)
            g.rect(x-45,y-6,10,12,fill='#151b20',stroke='none',rx=0)
            g.text(24,y-24,'Pin 4 · +5 V' if n==4 else 'Pin 20 · GND',size=22)
    else:
        points=header_board(g,{4:RED,20:BLK})
    button_rear(g,285,365)
    g.text(285,257,'Button',size=22,anchor='middle',weight=700)
    traced_wire(g,[points[4],(170,171),(170,211),(215,211)],RED)
    # Entire resistor and both joints are under one insulating sleeve.
    g.wire([(215,211),(334,211)],RED,5)
    g.rect(198,197,136,28,fill='#47515b',rx=7)
    g.text(266,182,'R1 · 1 kΩ inside',size=22,anchor='middle',weight=700)
    traced_wire(g,[(334,211),(373,211),(373,319),(311,319),(311,350)],RED)
    traced_wire(g,[points[20],(151,331),(151,506),(260,506),(260,350)],BLK)
    # Both push-on contacts have an insulating cover; never just one.
    for xx in (260,311): sleeve(g,xx,338,32)
    if not prepare: header_labels(g,points)
    g.text(24,625,'Pi pin 4 · +5 V → R1 → LED +',size=22)
    g.text(24,657,'Pi pin 20 · GND → LED −',size=22)
    g.text(24,700,'Insulate both contacts and all joins.',size=22)
    g.save('circuits/button-led-prepare.svg' if prepare else 'circuits/button-led.svg')


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
    g = action('Connect USB audio', 820, 'Two plug-in connections')
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
    # Audio module remains in its black enclosure, with its own USB-A male plug.
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
    lines(g,706,'1 · Cable plug → Pi USB-A socket.',
          '2 · Audio plug → cable socket.',
          'Keep the audio module in its case.')
    g.save('circuits/usb-audio.svg')


def pi_bench_power():
    g = action('Bench power for the Pi', 745, 'Separate from the USB audio cable')
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
    lines(g,643,'Use the Pi’s micro-USB power port.',
          'Shut down before unplugging.',
          'Keep servo and LED wiring off.')
    g.save('circuits/pi-bench-power.svg')


def servo_circuit(name, port, signal):
    g = physical_action(f'{name} · servo hookup', 756)
    g.rect(132, 141, 154, 112, fill='#32383e', rx=7)
    g.rect(115, 159, 188, 20, fill='#535c64', rx=3)
    g.circle(167, 140, 24, fill='#bdaf92', stroke=INK)
    g.circle(167, 140, 10, fill='#5c6060', stroke=INK)
    g.text(210, 219, name, size=27, fill='#fff', anchor='middle', weight=700)
    wago_port(g, 350, 'W2', port, RED)
    wago_port(g, 480, 'W4', port, BLK)
    # A terminal detail identifies the actual shifter landing, not a free wire.
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
    lines(g, 694, 'Verify the servo lead functions.', 'Terminal detail is not plug order.')
    g.save(f'circuits/servo-{name.lower()}.svg')


def body_input():
    g=physical_action('Make the permanent input',560,'BODY pigtail · bench soldering')
    plug_body(g,278,128)
    g.text(24,120,'BODY',size=24,weight=700)
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
    g=physical_action('Add the HEAD power tails',632,'Two separate soldered branches')
    plug_body(g,277,119)
    g.text(24,126,'BODY',size=24,weight=700)
    # Splice topology: one incoming pigtail, strand plus dedicated HEAD tail.
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
    g.text(24,561,'HEAD + / GND tails · 22 AWG',size=22)
    g.text(24,596,'Cap separately until HEAD is fitted.',size=22)
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
    g.text(24, 455, 'DOUT → HEAD DATA', size=26, weight=700)
    lines(g, 506, 'HEAD power comes from the', 'separate 22 AWG pair at the input.', 'Confirm HEAD contacts by continuity.', 'The strand’s output power is unused.')
    g.save('circuits/body-output.svg')


def head_power():
    g = physical_action('Head · power branches', 810)
    g.text(24, 122, 'HEAD · head half', size=25, weight=700)
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
    g = action('Head · follow the data', 782)
    lines(g, 131, 'HEAD DATA → 5755 → first eye IN', 'Either eye may be first.')
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
            if label == 'H3 return, including C2 −':
                g.text(86, y, 'H3 return,', size=23)
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
    lines(g, 522, 'Finished: sleeve overlaps insulation', 'at both ends. Gently pull-check.')
    lines(g, 612, 'Use separately on +, − and DATA.', 'Keep joints away from moving bends.')
    g.save('circuits/solder-insulation.svg')


def capacitor_joint_detail():
    g = action('C2 · cover the branch joint', 772, 'Bench detail · positive branch shown')
    lines(g, 123, '1 · Park tubing on the single wire.')
    g.text(24, 160, 'F2 · 18 AWG', size=22)
    g.wire([(32, 209), (166, 209)], RED, 9)
    g.rect(62, 194, 60, 30, fill='#626b72', rx=5)
    g.wire([(166, 209), (219, 209)], COPPER, 6)
    for yy, end_y in ((204, 184), (216, 244)):
        g.wire([(192, yy), (237, yy)], COPPER, 4)
        g.wire([(237, yy), (293, yy), (315, end_y), (380, end_y)], RED, 6)
    g.text(287, 170, 'H3 + · 22 AWG', size=22, anchor='middle')
    g.text(254, 280, 'Insulated C2 + tail', size=22, anchor='middle')
    lines(g, 330, '2 · Solder the three bare ends.', 'Both outgoing wires stay parallel', 'through the sleeve.')
    g.wire([(32, 455), (184, 455)], RED, 9)
    g.rect(62, 440, 60, 30, fill='#626b72', rx=5)
    g.rect(172, 445, 75, 24, fill='#c2c9cb', stroke=GRAY, rx=8)
    for yy, end_y in ((450, 432), (462, 491)):
        g.wire([(241, yy), (293, yy), (315, end_y), (380, end_y)], RED, 6)
    lines(g, 541, '3 · Cover metal; overlap insulation.')
    g.wire([(32, 591), (211, 591)], RED, 9)
    for yy, end_y in ((586, 568), (598, 626)):
        g.wire([(211, yy), (293, yy), (315, end_y), (380, end_y)], RED, 6)
    g.rect(149, 574, 127, 34, fill='#424b55', rx=6)
    lines(g, 682, 'Make the return branch separately.', 'Insulate each capacitor leg-to-tail', 'joint up to the capacitor’s seal.')
    g.save('circuits/capacitor-joint.svg')


def mouth_solder():
    g = action('Mouth · solder three leads', 767, 'Pad functions · follow board labels')
    g.rect(24, 118, 372, 52, fill='#2f413c', rx=5)
    for i in range(8):
        g.rect(35 + i * 45, 129, 31, 30, fill='#f6f3e7', stroke='#adab8b', rx=3)
    lines(g, 213, 'Adafruit 1426 · eight LEDs', 'Find +5V, GND and DIN on the back.')
    # Isolated pad detail: never claims an unverified board pad arrangement.
    for y, color, pad, source in ((318, RED, '+5V', 'HEAD +5 V · 22 AWG'), (438, BLK, 'GND', 'HEAD GND · 22 AWG'), (558, BLUE, 'DIN', 'Second eye OUT · 5755 data')):
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
    g = action('Body · keep six pebbles', 821, 'Cut only after the strand test passes')
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
    lines(g, 752, 'Keep lights 0–5 from the input end.', 'Leave wire after light 5 for HEAD.')
    g.save('circuits/cut-six.svg')


def connector_seating():
    g = action('JST-SM · align and seat', 605, 'BASE→BODY and HEAD connectors')
    lines(g, 133, 'First: continuity-check both halves.', 'Match +5 V, GND and DATA labels.')
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
    branches = ((238, 'W1/2 → H2 → Pi', 'Pi USB → audio', 'Unfused supply branch'),
                (416, 'W1/3 → F1 T3.15 A', '→ W2 → three servos', 'C1 across W2 and W3'),
                (593, 'W1/4 → F2 T1 A', '→ H3 → body + head', 'C2 across the H3 feed'))
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
    g=physical_action('Test through the BODY plug',458,'Keep all 100 pixels together')
    # Two keyed housings, fully mated; wires continue at both ends.
    plug_body(g,118,149)
    g.rect(226,154,61,41,fill='#303740',rx=4)
    g.rect(238,143,28,11,fill='#58626c',rx=2)
    for yy,color in ((161,RED),(175,BLK),(189,BLUE)):
        g.wire([(24,yy),(118,yy)],color,5)
        g.wire([(287,yy),(384,yy)],color,5)
    g.text(24,130,'H3 · base',size=22,weight=700)
    g.text(262,130,'BODY',size=22,weight=700)
    g.text(24,245,'F2 / S1',size=22)
    g.text(221,245,'Prepared strand',size=22)
    lines(g,318,'R2 and power branches stay attached.',
          'HEAD tails capped; servos unplugged.',
          'F2 T1 A fitted; F1 removed.',
          'After testing, unplug BODY from H3.')
    g.save('circuits/strand-test-connection.svg')

def strand_input_result():
    g = action('Strand · a positive input test', 673, 'Keep the full strand uncut for this test')
    g.text(24, 131, 'Connected end → mark INPUT', size=24, weight=700)
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
    lines(g, 546, 'Passing result: light starts here.', 'Darkness alone does not identify', 'the other end. Check wiring first.', 'Shut down and unplug to reconnect.')
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
    g = action('Supply · check the polarity', 770, 'Supply on · disconnected from robot')
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
    lines(g, 701, 'Positive reading · no minus sign.', 'Keep probe tips from touching.')
    g.save('circuits/supply-polarity-test.svg')


def robot_power_connection():
    g = action('Connect the power supply', 575, 'Plug into the robot before the wall')
    # Side view of the hollow barrel plug and panel jack, aligned for insertion.
    g.rect(70, 210, 108, 60, fill='#303740', rx=12)
    for xx in (82, 96, 110):
        g.wire([(xx, 216), (xx, 264)], GRAY, 2)
    g.rect(174, 222, 73, 36, fill='#c8cdd0', rx=2)
    g.rect(238, 229, 10, 22, fill='#353d43', rx=1)
    # A narrow section of the enclosure wall locates the inlet, not a second board.
    g.rect(305, 145, 18, 170, fill='#825f47', stroke='none', rx=1)
    g.rect(291, 210, 18, 60, fill='#c0c6c9', rx=3)
    g.rect(309, 215, 69, 50, fill='#303740', rx=6)
    g.rect(292, 227, 10, 26, fill='#161b20', stroke='none', rx=1)
    g.wire([(295, 240), (325, 240)], '#bca46f', 4)
    g.wire([(250, 184), (289, 184)], BLUE, 4, arrow=True)
    g.text(70, 167, 'Barrel plug', size=24, weight=700)
    g.text(380, 127, 'J1 · enclosure inlet', size=22, anchor='end', weight=700)
    g.wire([(70, 240), (36, 240), (36, 433), (84, 433)], '#303740', 7)
    # Recognizable enclosed desktop supply; mains connection intentionally off-view.
    g.rect(84, 379, 240, 106, fill='#303740', rx=16)
    g.rect(130, 398, 150, 65, fill='#deded7', stroke='none', rx=3)
    g.text(205, 425, '5 V DC · 5 A', size=23, anchor='middle', weight=700)
    g.text(205, 452, 'Center positive', size=22, anchor='middle')
    for xx in (96, 106, 116):
        g.wire([(xx, 394), (xx, 469)], '#626b72', 2)
    lines(g, 334, 'Push the plug fully into the inlet.')
    lines(g, 531, 'Mean Well GST40A05-P1J')
    g.save('circuits/robot-power-connection.svg')


def inlet_terminals():
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
    g.text(218, 433, 'SHUNT · unused', size=23, weight=700)
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
    lines(g, 837, 'Cover the full lug and bare wire.', 'Insulate both joints separately;', 'cap the unused shunt lug too.')
    g.save('circuits/inlet-terminals.svg')


def button_terminals():
    g = Svg(420, 386, 'Identify the four terminals')
    g.text(24, 78, 'Rear view · closer LED tabs at top', size=22, fill=MUTED)
    g.rect(100, 103, 220, 236, fill='#292e36', stroke=INK, rx=25)
    g.circle(210, 221, 103, fill='#343b43', stroke='#81868a', sw=3)
    # Real rear geometry: upper close LED pair; lower wider switch pair.
    for x, y in ((175, 197), (236, 197), (165, 268), (247, 268)):
        g.rect(x, y, 10, 28, fill='#c9d0d4', stroke='#f6f6ee', rx=1)
    g.text(151, 221, '−', size=24, fill='#fff', anchor='middle')
    g.text(274, 221, '+', size=24, fill='#fff', anchor='middle')
    g.text(210, 258, 'R16-503', size=22, fill='#e0e1df', anchor='middle')
    # Leaders terminate on the actual tabs; pale inner segments stay visible.
    for x, outer in ((180, 73), (241, 347)):
        g.wire([(x, 201), (outer, 180)], '#ae855e', 2)
        g.dot(x, 201, '#f4e7c4', r=3)
    g.text(8, 169, 'LED −', size=22, weight=700)
    g.text(412, 169, 'LED +', size=22, fill=RED, anchor='end', weight=700)
    g.wire([(170, 289), (170, 347), (250, 347), (252, 289)], '#ae855e', 2)
    g.dot(170, 289, '#f4e7c4', r=3)
    g.dot(252, 289, '#f4e7c4', r=3)
    g.text(210, 376, 'Switch', size=23, anchor='middle', weight=700)
    g.save('circuits/button-terminals.svg')


def tie_mount():
    """Representative physical tie support, not an enclosure placement plan."""
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
    for y,title,left,right in ((143,'BASE→BODY','Enclosure · H3','Body'),(327,'HEAD lighting','Body','Head')):
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
    inlet_circuit(); pi_power_circuit(); wago_insertion(); harness_connections()
    fuse_prep('F1', 'T3.15 A', 3, 'W2/1')
    fuse_prep('F2', 'T1 A', 4, 'H3 +5 V / C2 +')
    f1_circuit(); c1_circuit(); ground_circuit(); c2_circuit(); f2_circuit()
    shifter_circuit('S1', {1: 'S1 V', 6: 'S1 G', 12: 'S1 DAT', 32: 'S1 CLK'}, ('LIGHTING', 'LEFT'))
    shifter_circuit('S2', {9: 'S2 G', 17: 'S2 V', 33: 'S2 DAT', 36: 'S2 CLK'}, ('RIGHT', 'HEAD'))
    gpio_lead_preparation(); gpio_socket_insertion(); shifter_jumpers(); button_switch(); button_led(); button_led(prepare=True); button_pins(); usb_audio(); pi_bench_power()
    servo_circuit('LEFT', 2, 'S1 C5')
    servo_circuit('RIGHT', 3, 'S2 D5')
    servo_circuit('HEAD', 4, 'S2 C5')
    body_input(); body_power(); body_output(); head_power(); head_data()
    wago_reference()
    solder_detail(); capacitor_joint_detail(); mouth_solder(); cut_six()
    connector_seating(); eye_connector(); power_overview()
    strand_wire_identification(); strand_test_connection(); strand_input_result()
    supply_polarity_test(); robot_power_connection()
    inlet_terminals(); button_terminals(); tie_mount()


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
        servo_fit_pose()
    circuit_actions()
    print(f'ok: {OUT}')


if __name__ == '__main__':
    main()
