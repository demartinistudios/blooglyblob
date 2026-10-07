#!/usr/bin/env python3
"""Draw the guide's part cartoons into hardware/build-guide/src/assets/cartoons/.

One style for every bought part, consumable, fastener and tool (printed parts keep
their model renders). Everything is drawn in millimetres in one projection: the plan
keeps its true shape and heights rise up the page at K per millimetre, so each item
reads as if it were lying on the bench and seen from a little in front. Light comes
from the upper left; every solid gets the same outline, lift shadow and shading rules.

Rerun it and review the diff: the output is byte-stable.
"""
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[3] / 'hardware/build-guide/src/assets/cartoons'
W, H, MARGIN = 560, 420, 34
K = 0.45                      # page-up offset per millimetre of height
BG = '#f3f7fa'
INK = '#23272f'               # outlines
LW = 2.6                      # outer outline width (px)
LI = 1.1                      # inner detail line width (px)
FONT = 'Arial,Helvetica,sans-serif'


# ----------------------------------------------------------------- colour helpers
def _rgb(c):
    c = c.lstrip('#')
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, t):
    """Blend colour a toward b by t (0..1)."""
    return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(_rgb(a), _rgb(b)))


def lit(c, t=.35):
    return mix(c, '#ffffff', t)


def dim(c, t=.3):
    return mix(c, '#101418', t)


# Shared materials
PCB = '#3f9c5c'
GOLD = '#d8ae48'
STEEL = '#c2c8cf'
CHROME = '#d5dade'
BLACK = '#2e3035'
WHITE_PL = '#f1eee6'          # off-white nylon (JST, WAGO bodies)
RED_W, BLACK_W = '#d23a2e', '#2b2c30'


def f(v):
    s = f'{v:.1f}'
    return '0' if s in ('0.0', '-0.0') else s.rstrip('0').rstrip('.') if '.' in s else s


def pts(ps):
    return ' '.join(f'{f(x)},{f(y)}' for x, y in ps)


# ----------------------------------------------------------------- geometry (mm)
def arc(cx, cy, r, a0, a1, n=None):
    n = n or max(3, int(abs(a1 - a0) / 12))
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rrect(x, y, w, h, r=0):
    """Rounded rectangle as a polygon (y down)."""
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return (arc(x + w - r, y + r, r, -90, 0) + arc(x + w - r, y + h - r, r, 0, 90)
            + arc(x + r, y + h - r, r, 90, 180) + arc(x + r, y + r, r, 180, 270))


def circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def ellipse(cx, cy, rx, ry, n=48):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ----------------------------------------------------------------- picture
class Pic:
    """A cartoon drawn in mm. Draw twice: once to measure, once to place."""

    def __init__(self, scale=None, fit=True):
        self.parts, self.notes, self.fixed, self.ids, self.last_clip = [], [], scale, 0, None
        self.s, self.ox, self.oy = scale or 1.0, 0.0, 0.0
        self.box = [1e9, 1e9, -1e9, -1e9]

    # projection: plan (x, y) at height z, in mm -> page px
    def P(self, x, y, z=0):
        X, Y = self.ox + x * self.s, self.oy + (y - z * K) * self.s
        b = self.box
        b[0], b[1], b[2], b[3] = min(b[0], X), min(b[1], Y), max(b[2], X), max(b[3], Y)
        return X, Y

    def add(self, s):
        self.parts.append(s)

    def uid(self, stem):
        self.ids += 1
        return f'{stem}{self.ids}'

    # --- primitives in page space from mm polygons
    def poly(self, ps, z=0, fill='none', stroke='none', sw=LI, extra=''):
        q = [self.P(x, y, z) for x, y in ps]
        self.add(f'<polygon points="{pts(q)}" fill="{fill}" stroke="{stroke}" stroke-width="{f(sw)}" stroke-linejoin="round"{extra}/>')

    def line(self, ps, z=0, stroke=INK, sw=LI, extra='', cap='round'):
        q = [self.P(x, y, z) for x, y in ps]
        self.add(f'<polyline points="{pts(q)}" fill="none" stroke="{stroke}" stroke-width="{f(sw)}" stroke-linejoin="round" stroke-linecap="{cap}"{extra}/>')

    def spline(self, ps, z=0, stroke=INK, sw=LI, extra=''):
        """Smooth curve through points (Catmull-Rom as cubic Beziers)."""
        q = [self.P(x, y, z) for x, y in ps]
        d = f'M{f(q[0][0])} {f(q[0][1])}'
        for i in range(len(q) - 1):
            p0, p1, p2, p3 = q[max(i - 1, 0)], q[i], q[i + 1], q[min(i + 2, len(q) - 1)]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d += f' C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(p2[0])} {f(p2[1])}'
        self.add(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{f(sw)}" stroke-linejoin="round" stroke-linecap="round"{extra}/>')

    def text(self, x, y, z, s, size, fill, anchor='middle', weight=700, rotate=0):
        X, Y = self.P(x, y, z)
        t = f' transform="rotate({rotate} {f(X)} {f(Y)})"' if rotate else ''
        self.add(f'<text x="{f(X)}" y="{f(Y)}" font-family="{FONT}" font-size="{f(size * self.s)}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{t}>{escape(s)}</text>')

    # --- solids
    def prism(self, ps, z0, z1, top, side=None, edge=True, detail=None):
        """A flat-topped solid: footprint polygon ps raised from z0 to z1.

        Outline trick: every piece stroked at 2*LW first, then filled, so only the outer
        contour of the union survives. `detail` draws on the top face before the edge line.
        """
        side = side or dim(top, .35)
        bot = [self.P(x, y, z0) for x, y in ps]
        tp = [self.P(x, y, z1) for x, y in ps]
        # Only sides facing the viewer (outward normal toward +y) can show; skip the rest.
        area = sum(ps[i][0] * ps[(i + 1) % len(ps)][1] - ps[(i + 1) % len(ps)][0] * ps[i][1] for i in range(len(ps)))
        quads = []
        for i in range(len(ps)):
            j = (i + 1) % len(ps)
            ny = (ps[i][0] - ps[j][0]) if area > 0 else (ps[j][0] - ps[i][0])
            if ny > -1e-9:
                quads.append([tp[i], tp[j], bot[j], bot[i]])
        pieces = [bot, tp] + quads
        o = ''.join(f'<polygon points="{pts(p)}"/>' for p in pieces)
        self.add(f'<g fill="none" stroke="{INK}" stroke-width="{f(2 * LW)}" stroke-linejoin="round">{o}</g>')
        s = ''.join(f'<polygon points="{pts(p)}"/>' for p in [bot] + quads)
        self.add(f'<g fill="{side}" stroke="{side}" stroke-width=".6" stroke-linejoin="round">{s}</g>')
        self.add(f'<polygon points="{pts(tp)}" fill="{top}"/>')
        if detail:
            detail()
        if edge and z1 > z0:
            self.add(f'<polygon points="{pts(tp)}" fill="none" stroke="{INK}" stroke-width="{f(LI)}" stroke-linejoin="round" stroke-opacity=".55"/>')

    def flat(self, ps, z, fill, stroke=INK, sw=LI, op=.55):
        """A painted/printed area on a surface (no thickness)."""
        q = [self.P(x, y, z) for x, y in ps]
        self.add(f'<polygon points="{pts(q)}" fill="{fill}" stroke="{stroke}" stroke-width="{f(sw)}" stroke-opacity="{op}" stroke-linejoin="round"/>')

    def hole(self, cx, cy, r, z):
        """A through hole: shows the bench below."""
        self.flat(circle(cx, cy, r, 32), z, dim(BG, .12), sw=LI, op=.8)

    def wire(self, ps, color, d=1.6, z=None, stripe=None):
        """An insulated wire lying on the bench (d = outer diameter in mm)."""
        z = d / 2 if z is None else z
        w = d * self.s
        self.spline(ps, z, INK, w + 2 * LW * .8)
        self.spline(ps, z, color, w)
        self.spline([(x, y - d * .18) for x, y in ps], z, lit(color, .45), w * .28, extra=' stroke-opacity=".7"')

    # --- round things lying along x (screws, tubes, barrels)
    def band(self, yc, za, r):
        """Page-space (as plan y at z=0) top and bottom of a lying cylinder's silhouette."""
        c, h = yc - za * K, r * math.sqrt(1 + K * K)
        return c - h, c + h

    def rod(self, x0, x1, yc, r, color, za=None, face=None, tip=None, serr=0, hi=.5, stroke=True, ef=.3):
        """A cylinder lying along x. The left end face is shown as a narrow ellipse (a slight
        turn toward the viewer); `face` draws on it. `tip` rounds or chamfers the right end."""
        za = r if za is None else za
        t, b = self.band(yc, za, r)
        c, h = (t + b) / 2, (b - t) / 2
        e = ef * h
        top, bot = [], []
        if serr:
            n = int((x1 - x0) / (serr / 2))
            for i in range(n + 1):
                x = x0 + i * serr / 2
                dd = .22 * serr * 2 if i % 2 else 0
                top.append((x, t + dd)); bot.append((x, b - dd))
        else:
            top, bot = [(x0, t), (x1, t)], [(x0, b), (x1, b)]
        if tip == 'round':
            end = [(x1 + e * math.cos(math.radians(a)), c + h * math.sin(math.radians(a))) for a in range(-90, 91, 10)]
        elif tip == 'chamfer':
            end = [(x1, t + h * .35), (x1 + e * .6, c - h * .35), (x1 + e * .6, c + h * .35), (x1, b - h * .35)]
        else:
            end = [(x1 + e * math.cos(math.radians(a)), c + h * math.sin(math.radians(a))) for a in range(-90, 91, 10)]
        body = top + end + bot[::-1]
        q = [self.P(x, y) for x, y in body]
        cid = self.last_clip = self.uid('c')
        self.add(f'<clipPath id="{cid}"><polygon points="{pts(q)}"/></clipPath>')
        if stroke:
            self.add(f'<polygon points="{pts(q)}" fill="none" stroke="{INK}" stroke-width="{f(2 * LW)}" stroke-linejoin="round"/>')
        self.add(f'<polygon points="{pts(q)}" fill="{color}"/>')
        g = f'<g clip-path="url(#{cid})">'
        X0, X1 = x0 - 1, x1 + 2
        for y0, y1, col, op in ((c + .42 * h, b + 1, dim(color, .38), 1), (c - .62 * h, c - .22 * h, lit(color, .55), hi),
                                (c - .9 * h, c - .72 * h, lit(color, .3), hi * .6)):
            g += f'<polygon points="{pts([self.P(X0, y0), self.P(X1, y0), self.P(X1, y1), self.P(X0, y1)])}" fill="{col}" fill-opacity="{op}"/>'
        self.add(g + '</g>')
        if face is not False:
            fp = ellipse(x0, c, e, h, 40)
            if stroke:
                self.add(f'<polygon points="{pts([self.P(x, y) for x, y in fp])}" fill="none" stroke="{INK}" stroke-width="{f(2 * LW)}"/>')
            self.add(f'<polygon points="{pts([self.P(x, y) for x, y in fp])}" fill="{mix(color, "#ffffff", .18)}"/>')
            if face:
                face(x0, c, e, h)
        return c, h, e

    def clipped(self, cid, polys):
        """Paint (mm polygon, fill) pairs inside a rod's outline: bands, stripes, sleeves."""
        g = ''.join(f'<polygon points="{pts([self.P(x, y) for x, y in ps])}" fill="{c}"/>' for ps, c in polys)
        self.add(f'<g clip-path="url(#{cid})">{g}</g>')

    def ribbon(self, cl, widths, round_end=False):
        """Polygon around a centreline with a width at each point (mm)."""
        left, right = [], []
        for i, (x, y) in enumerate(cl):
            a, b = cl[max(i - 1, 0)], cl[min(i + 1, len(cl) - 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            w = widths[i] / 2
            left.append((x + nx * w, y + ny * w)); right.append((x - nx * w, y - ny * w))
        if round_end:
            (x, y), w = cl[-1], widths[-1] / 2
            a0 = math.degrees(math.atan2(left[-1][1] - y, left[-1][0] - x))
            left += arc(x, y, w, a0, a0 - 180, 12)[1:-1]
        return left + right[::-1]

    def dim_line(self, x0, x1, y, label):
        """A dimension under a part, outside the shadow layer."""
        a, b = self.P(x0, y), self.P(x1, y)
        c = '#4f6273'
        self.notes.append(
            f'<g stroke="{c}" stroke-width="1.6" fill="none"><path d="M{f(a[0])} {f(a[1] - 7)}V{f(a[1] + 7)}M{f(b[0])} {f(b[1] - 7)}V{f(b[1] + 7)}"/>'
            f'<path d="M{f(a[0] + 1)} {f(a[1])}H{f(b[0] - 1)}"/>'
            f'<path d="M{f(a[0] + 8)} {f(a[1] - 4.5)}L{f(a[0] + 1)} {f(a[1])}L{f(a[0] + 8)} {f(a[1] + 4.5)}M{f(b[0] - 8)} {f(b[1] - 4.5)}L{f(b[0] - 1)} {f(b[1])}L{f(b[0] - 8)} {f(b[1] + 4.5)}"/></g>'
            f'<text x="{f((a[0] + b[0]) / 2)}" y="{f(a[1] + 30)}" font-family="{FONT}" font-size="21" font-weight="700" fill="{c}" text-anchor="middle">{escape(label)}</text>')

    # --- output
    def svg(self, title):
        body = ''.join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">'
                f'<title>{escape(title)}</title>'
                '<defs><filter id="lift" x="-15%" y="-15%" width="135%" height="140%" color-interpolation-filters="sRGB">'
                '<feOffset in="SourceAlpha" dx="5" dy="9" result="o"/><feGaussianBlur in="o" stdDeviation="3.5" result="b"/>'
                '<feFlood flood-color="#1c3346" flood-opacity=".2"/><feComposite in2="b" operator="in" result="s"/>'
                '<feMerge><feMergeNode in="s"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
                f'<rect width="{W}" height="{H}" fill="{BG}"/><g filter="url(#lift)">{body}</g>{''.join(self.notes)}</svg>\n')


def render(draw, title, scale=None, origin=None):
    """Measure the drawing, then fit it centred on the canvas.

    With a fixed scale and origin (page px of mm 0,0), items of one family line up
    across pictures: every screw head sits in the same place, so lengths compare.
    """
    m = Pic(scale)
    draw(m)
    x0, y0, x1, y1 = m.box
    s = scale or min((W - 2 * MARGIN) / (x1 - x0), (H - 2 * MARGIN) / (y1 - y0))
    p = Pic(s)
    p.ox = (W - (x1 - x0) * s / m.s) / 2 - x0 * s / m.s
    p.oy = (H - (y1 - y0) * s / m.s) / 2 - y0 * s / m.s
    if origin:
        p.ox, p.oy = origin
    draw(p)
    return p.svg(title)


# ================================================================= purchased parts
def pi3a(p):
    """Raspberry Pi 3 Model A+, component side up, GPIO header along the far edge.

    Positions from the Raspberry Pi 3A+ mechanical drawing (65 x 56 mm, holes 3.5 mm in).
    """
    T = 1.4  # board top
    p.prism(rrect(0, 0, 65, 56, 3), 0, T, PCB, dim(PCB, .45), detail=lambda: pi_board_art(p, T))
    for x, y in ((3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)):
        p.flat(circle(x, y, 3.1), T, GOLD, op=.35)
        p.hole(x, y, 1.375, T)
    # wireless module can
    p.prism(rrect(5.5, 7, 12, 11.5, .6), T, T + 1.6, CHROME, dim(CHROME, .3),
            detail=lambda: p.flat(rrect(7.2, 8.7, 8.6, 8.1, .8), T + 1.6, mix(CHROME, '#ffffff', .25), op=.35))
    # SoC with its metal lid on a darker substrate
    p.prism(rrect(19.3, 17.1, 15, 15, .4), T, T + .5, '#1f4a33')
    p.prism(rrect(20.2, 18.0, 13.2, 13.2, .6), T + .5, T + 1.4, CHROME, dim(CHROME, .3),
            detail=lambda: [p.line([(22, y), (27 + (y % 2) * 2, y)], T + 1.4, '#8b939b', .9) for y in (21.5, 23, 25.5, 27)])
    # power management chip and a few passives
    p.prism(rrect(9.5, 36.5, 6, 6, .3), T, T + .9, BLACK)
    for x, y, w, h, c in ((18, 36, 2, 1.2, '#b88b5b'), (18, 38.5, 2, 1.2, '#b88b5b'), (22, 37, 1.2, 2, BLACK),
                          (24, 37, 1.2, 2, '#b88b5b'), (12, 30, 2, 1.2, '#b88b5b'), (37, 21, 1.2, 2, '#b88b5b'),
                          (37, 25, 2, 1.2, BLACK), (47, 26, 3, 3, '#6f747b'), (57, 7.5, 2.4, 1.4, '#e8e2d2')):
        p.prism(rrect(x, y, w, h, .15), T, T + .6, c)
    # GPIO: 2 x 20 header, pins up
    x0, y0 = 32.5 - 25.4, 3.5 - 2.54
    p.prism(rrect(x0, y0, 50.8, 5.08, .2), T, T + 2.5, BLACK, '#1b1c20',
            detail=lambda: [p.line([(x0 + i * 2.54, y0 + .3), (x0 + i * 2.54, y0 + 4.78)], T + 2.5, '#44464d', .8) for i in range(1, 20)])
    for row in (1, 0):
        for i in range(20):
            cx, cy = x0 + 1.27 + i * 2.54, y0 + 1.27 + row * 2.54
            a = p.P(cx, cy, T + 2.5)
            b = p.P(cx, cy, T + 8.5)
            p.add(f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{dim(GOLD, .45)}" stroke-width="{f(.64 * p.s + 1.4)}"/>'
                  f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{GOLD}" stroke-width="{f(.64 * p.s - .6)}"/>')
            p.flat(rrect(cx - .32, cy - .32, .64, .64), T + 8.5, lit(GOLD, .4), dim(GOLD, .5), .6, 1)
    # display (DSI) and camera (CSI) ribbon connectors
    for x, y, w, h in ((1.8, 16.5, 3.4, 23), (43.4, 33.5, 2.6, 21.5)):
        p.prism(rrect(x, y, w, h, .3), T, T + 3.5, WHITE_PL)
        p.prism(rrect(x + .35, y + .6, w - .7, h - 1.2, .3), T + 3.5, T + 5.2, '#5b3a25')
    # USB-A, protruding past the right edge; opening faces right
    p.prism(rrect(53.3, 17.9, 15.4, 13.2, .5), T, T + 7, CHROME, dim(CHROME, .32), detail=lambda: usb_a_top(p, 53.3, 17.9, T + 7))
    # HDMI, micro-B power and audio jack along the near edge
    p.prism([(24.2, 45.8), (39.6, 45.8), (39.6, 55), (38.6, 57), (25.2, 57), (24.2, 55)], T, T + 6.1, CHROME, dim(CHROME, .32),
            detail=lambda: [p.line([(26, 47.5 + i * 1.6), (37.8, 47.5 + i * 1.6)], T + 6.1, '#9ca3aa', .9) for i in range(4)])
    p.prism(rrect(6.9, 51.5, 7.4, 5.6, .6), T, T + 2.8, CHROME, dim(CHROME, .32))
    p.prism(rrect(50.2, 44, 6.6, 12.4, .3), T, T + 6, BLACK, '#1b1c20')
    p.prism(rrect(51.2, 56.4, 4.6, 2.8, .3), T + .6, T + 5.4, BLACK, '#1b1c20',
            detail=lambda: p.flat(circle(53.5, 57.8, 1.1, 20), T + 5.4, '#111214', op=.9))


def pi_board_art(p, z):
    """Traces and silkscreen on the Pi's top face."""
    tr = dict(stroke=lit(PCB, .22), sw=.9)
    for path in ([(8, 20), (8, 30), (14, 36)], [(18, 25), (12, 25), (12, 34)], [(34, 26), (42, 26), (47, 31), (47, 33)],
                 [(34, 22), (44, 22), (50, 16), (58, 16)], [(27, 32), (27, 42), (30, 45)], [(22, 44), (18, 48), (15, 48)],
                 [(40, 40), (48, 40), (52, 44)], [(36, 10), (36, 15)], [(20, 10), (20, 15)], [(58, 36), (58, 44)]):
        p.line(path, z, tr['stroke'], tr['sw'])
    for x, y in ((40, 12), (44, 12), (48, 12), (10, 44), (20, 40), (42, 36), (60, 40)):
        p.flat(circle(x, y, .5, 12), z, lit(GOLD, .2), op=.0)
    p.text(31.8, 41.2, z, 'HDMI', 2.2, '#f4f6f4')
    p.text(10.6, 49.2, z, 'PWR IN', 1.3, '#f4f6f4')
    p.text(47, 9.3, z, 'Raspberry Pi 3 Model A+', 1.35, '#f4f6f4')
    p.text(3.0, 28, z, 'DISPLAY', 1.2, '#f4f6f4', rotate=-90)
    p.text(42.4, 44, z, 'CAMERA', 1.2, '#f4f6f4', rotate=-90)


def usb_a_top(p, x, y, z):
    p.flat(rrect(x + 1.2, y + 1.4, 11.5, 10.4, .6), z, lit(CHROME, .2), op=.25)
    for yy in (y + 3.2, y + 8.6):
        p.flat(rrect(x + 3.5, yy, 3.2, 1.4, .3), z, '#8e969e', op=.5)
    p.line([(x + 15.4, y + .5), (x + 15.4, y + 12.7)], z, dim(CHROME, .5), 1.4)


def speaker(p, ox, oy):
    """Adafruit 1669 enclosed speaker, cone up, lead leaving the left end. 70 x 30.5 mm,
    holes on a 64 x 24 mm pattern."""
    L, Wd = 70, 30.5
    plus = [(ox, oy + 6), (ox + 9.5, oy + 6), (ox + 9.5, oy), (ox + 60.5, oy), (ox + 60.5, oy + 6), (ox + L, oy + 6),
            (ox + L, oy + 24.5), (ox + 60.5, oy + 24.5), (ox + 60.5, oy + Wd), (ox + 9.5, oy + Wd), (ox + 9.5, oy + 24.5), (ox, oy + 24.5)]
    p.prism(plus, 0, 13.5, BLACK, '#202226')
    p.prism(rrect(ox, oy, L, Wd, 1.2), 13.5, 15, '#35373c', '#1d1f22',
            detail=lambda: [p.hole(ox + x, oy + y, 1.6, 15) for x in (3, 67) for y in (3.25, 27.25)])
    cx, cy = ox + 31, oy + Wd / 2

    def face():
        z = 16.6
        p.flat(ellipse(cx, cy, 19, 12.6), z, '#1f2124', op=.8)
        p.flat(ellipse(cx, cy, 17.4, 11.4), z, '#3a3c41', op=.4)
        for k in (0, 1, 2):
            p.flat(ellipse(cx, cy, 16 - k * 1.1, 10.4 - k * .8), z, 'none', '#55585e', .8, .9)
        p.flat(ellipse(cx, cy, 12.6, 8.4), z, '#2a2c30', op=.6)
        p.flat(circle(cx, cy - .2, 7.4, 40), z, '#c9962e', op=.5)
        p.flat(circle(cx, cy - .6, 6.8, 40), z, '#3b3e44', op=.7)
        p.flat(ellipse(cx - 2, cy - 3, 3.6, 1.8), z, '#6d7179', stroke='none')
    p.prism(plus, 15, 16.6, '#303236', '#1d1f22', detail=face)


def speaker_pair(p):
    for i, oy in enumerate((0, 44)):
        a, b = (0, oy + 13.6), (0, oy + 16.9)
        red_first = i == 0
        p.wire([(0, oy + 14.2), (-8, oy + 14.6), (-18, oy + 18 + (i * 2 - 1) * -4), (-26, 36.4 + (-1.8 if i == 0 else 1.8) + (0 if red_first else 0))],
               RED_W if red_first else BLACK_W, 1.5, z=4)
        p.wire([(0, oy + 16.4), (-8, oy + 16.8), (-18, oy + 20 + (i * 2 - 1) * -4), (-26, 36.4 + (-.6 if i == 0 else .6))],
               BLACK_W if red_first else RED_W, 1.5, z=4)
        speaker(p, 0, oy)
    # JST PH four-pin plug joining both leads
    p.prism(rrect(-34.5, 31.5, 8, 9.9, .4), 0, 5.8, WHITE_PL, dim(WHITE_PL, .2),
            detail=lambda: [p.flat(rrect(-33.6, 32.4 + i * 2, 1.4, 1.3, .2), 5.8, '#c9c4b6', op=.6) for i in range(4)])


# ------------------------------------------------------------------ fasteners
FS, FO = 18, (70, 188)      # every fastener: px per mm, and page position of the head end
NS, FC = 32, (280, 185)     # nuts and washers share their own, larger scale; page position of their centre


def thread(p, x0, x1, d, R, yc=0, pitch=None):
    pitch = pitch or {3: .5, 2: .4}[d]
    p.rod(x0, x1, yc, d / 2 * .94, STEEL, za=R, face=False, tip='chamfer', serr=pitch)
    t, b = p.band(yc, R, d / 2 * .94)
    x = x0 + pitch
    while x < x1 - pitch * .6:
        p.line([(x, t + .1), (x + pitch * .5, b - .1)], 0, dim(STEEL, .32), .9)
        x += pitch


def socket_head(p, d, yc, R, hl):
    def face(x, c, e, h):
        af = {3: 2.5, 2: 1.5}[d] / 2 / math.cos(math.radians(30))
        hexa = [(x + e * .92 * af / h * math.cos(math.radians(a)), c + af * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
        p.flat(ellipse(x, c, e * .86, h * .86, 40), 0, 'none', dim(STEEL, .3), .9, .7)
        p.flat(hexa, 0, '#3b4148', op=.9)
        p.flat(hexa[:3] + [(x, c)], 0, '#59616a', stroke='none')
    c, h, e = p.rod(0, hl, yc, R, STEEL, za=R, face=face, tip='flat')
    for k in (-.55, -.2, .2, .55):
        p.line([(e * .9, c + k * h), (hl - .15, c + k * h)], 0, dim(STEEL, .3), .8)


def button_head(p, yc, R, hl):
    """ISO 7380 button head: a low dome, hex socket in its crown."""
    t, b = p.band(yc, R, R)
    c, h = (t + b) / 2, (b - t) / 2
    dome = [(hl * (1 - math.sqrt(max(0, 1 - (v / h) ** 2))) * 1.0, c + v) for v in [h * (i / 10) for i in range(-10, 11)]]
    body = dome + [(hl + .05, b), (hl + .05, t)]
    q = [p.P(x, y) for x, y in body]
    p.add(f'<polygon points="{pts(q)}" fill="none" stroke="{INK}" stroke-width="{f(2 * LW)}" stroke-linejoin="round"/>'
          f'<polygon points="{pts(q)}" fill="{STEEL}"/>')
    p.flat([(x + .08, y) for x, y in dome if abs(y - c) < h * .75] + [(hl, c + h * .3), (hl, c - h * .3)], 0, lit(STEEL, .35), stroke='none')
    af = 1.3 / 2 / math.cos(math.radians(30))
    hexa = [(hl * .3 + .22 * af * math.cos(math.radians(a)), c + af * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    p.flat(hexa, 0, '#3b4148', op=.9)


def screw(d, L, head='socket', label=True):
    """A metric screw lying on the bench, head to the left, with its length marked."""
    def draw(p, yc=0, mark=True):
        if head == 'socket':
            hd, hl = (5.5, 3) if d == 3 else (3.8, 2)
        elif head == 'button':
            hd, hl = 3.5, 1.3
        else:
            hd, hl = 6, 1.65
        R = hd / 2
        if head == 'cs':
            thread(p, hl - .05, L, d, R, yc)
            t, b = p.band(yc, R, R)
            c, h = (t + b) / 2, (b - t) / 2
            r = d / 2 * .94 * math.sqrt(1 + K * K)
            cone = [(0, t), (hl, c - r), (hl, c + r), (0, b)]
            q = [p.P(x, y) for x, y in cone]
            p.add(f'<polygon points="{pts(q)}" fill="none" stroke="{INK}" stroke-width="{f(2 * LW)}" stroke-linejoin="round"/>'
                  f'<polygon points="{pts(q)}" fill="{STEEL}"/>')
            p.flat([(0, c - h * .55), (hl * .9, c - r * .5), (hl * .9, c - r * .1), (0, c - h * .1)], 0, lit(STEEL, .4), stroke='none')
            e = .3 * h
            p.flat(ellipse(0, c, e, h, 40), 0, mix(STEEL, '#ffffff', .18))
            af = 2 / 2 / math.cos(math.radians(30))
            p.flat([(e * .92 * af / h * math.cos(math.radians(a)), c + af * math.sin(math.radians(a))) for a in range(-90, 270, 60)], 0, '#3b4148', op=.9)
            x_under, end = 0, L
        else:
            thread(p, hl - .05, hl + L, d, R, yc)
            if head == 'socket':
                socket_head(p, d, yc, R, hl)
            else:
                button_head(p, yc, R, hl)
            x_under, end = hl, hl + L
        if mark:
            tb = p.band(yc, R, R)[1]
            p.dim_line(x_under, end + .25, tb + 2.2, f'{L} mm')
    return draw


def m2x8(p):
    """M2 x 8: plain socket heads, and the three button heads the head seats need."""
    screw(2, 8)(p, yc=-3.4, mark=False)
    screw(2, 8, 'button')(p, yc=3.4)


def nut(d):
    """An ordinary hex nut lying flat, measured across the flats."""
    af, t = (5.5, 2.4) if d == 3 else (4, 1.6)
    def draw(p):
        rv = af / 2 / math.cos(math.radians(30))
        hexa = [(rv * math.cos(math.radians(a)), rv * math.sin(math.radians(a))) for a in range(30, 390, 60)]
        def top():
            p.flat(circle(0, 0, af / 2 * .96, 40), t, lit(STEEL, .2), stroke=dim(STEEL, .3), sw=.9, op=.8)
            p.flat(circle(0, 0, d / 2 * 1.02, 32), t, '#5b636b', op=.9)
            p.flat(circle(0, .12 * d, d / 2 * .76, 32), t, BG, stroke='none')
            # Visible thread crests on the bore wall, not a solid grey disc.
            for off in (-.08 * d, .06 * d):
                p.line(arc(0, off, d * .45, 195, 345, 18), t, '#a8afb6', .9)
        p.prism(hexa, 0, t, STEEL, dim(STEEL, .32), detail=top)
        p.dim_line(-af / 2, af / 2, rv + 1.2, f'{af:g} mm across flats')
    return draw


def washer(od, idia, t, color=STEEL, label=True):
    def draw(p):
        ring = circle(0, 0, od / 2, 48)
        p.prism(ring, 0, t, color, dim(color, .3),
                detail=lambda: [p.flat(circle(0, 0, idia / 2, 32), t, '#78838e', stroke=INK, sw=1, op=.7),
                                p.flat(circle(0, .1 * t, idia * .45, 32), t, BG, stroke='none'),
                                p.flat(ellipse(-od * .18, -od * .2, od * .12, od * .05), t, lit(color, .6), stroke='none')])
        if label:
            p.dim_line(-od / 2, od / 2, od / 2 + 1.0, f'{od:g} mm')
    return draw


def center_screw(p):
    """The servo's own centre screw: a short screw with a wide washer-faced Phillips head."""
    R = 2.6
    thread(p, .95, 5.2, 2, R, pitch=.45)
    def face(x, c, e, h):
        p.flat(ellipse(x, c, e * .9, h * .9, 36), 0, 'none', dim(STEEL, .3), .9, .6)
        p.line([(x, c - h * .55), (x, c + h * .55)], 0, '#3b4148', 2.2)
        p.line([(x - e * .55, c), (x + e * .55, c)], 0, '#3b4148', 2.2)
    p.rod(0, 1.0, 0, R, STEEL, za=R, face=face, tip='round')


# ------------------------------------------------------------------ first tools and consumables
def flush_cutters(p):
    """Flush cutters (Adafruit 152): short broad jaws, spring pivot, red grips over a black layer."""
    steel, steel_hi = '#4b5058', '#a3abb4'
    red = '#d8342a'
    up = [(28, -3.4), (40, -6.4), (58, -10.6), (80, -14.2), (100, -15.6), (116, -15)]
    lo = [(28, 3.4), (40, 6.8), (58, 11.6), (80, 16), (100, 18), (116, 17.6)]
    for cl in (lo, up):
        p.prism(p.ribbon(cl[:3], [5.2, 5.2, 4.8]), 1.5, 5, steel, dim(steel, .3))
        p.prism(p.ribbon(cl[1:], [9.6, 10.8, 11.6, 11.8, 11.2], round_end=True), 0, 8.5, red, '#26272b',
                detail=lambda g=cl: p.spline([(x, y - 2.2) for x, y in g[2:6]], 8.5, lit(red, .4), 1.6 * p.s, extra=' stroke-opacity=".75"'))
    head = ([(0, -.5), (3, -2.4), (8, -4.8), (13, -6.6)] + arc(21, 0, 7.6, -120, -30, 6)
            + [(29, -3.6), (29, 3.6)] + arc(21, 0, 7.6, 30, 120, 6) + [(13, 6.6), (8, 4.8), (3, 2.4), (0, .5)])
    def jaws():
        p.line([(.8, 0), (16, 0)], 5, '#17191c', 1.5)
        p.spline([(1.5, -1), (6.5, -3.2), (12, -5.2)], 5, steel_hi, 1.5)
        p.spline([(1.5, 1), (6.5, 3.2), (12, 5.2)], 5, steel_hi, 1.5)
        p.flat(circle(21, 0, 4.6, 40), 5, '#5c626b', op=.8)
        p.flat(circle(21, 0, 2.8, 32), 5, '#b1b8bf', op=.8)
        for r in (2.1, 1.4, .7):
            p.flat(circle(21, 0, r, 24), 5, 'none', '#6b727b', .9, 1)
    p.prism(head, 1.5, 5, steel, dim(steel, .35), detail=jaws)


def heat_shrink(p):
    """An assortment of black heat-shrink tube, open ends toward the viewer."""
    black = '#34363b'
    y = 0
    for d, L, x0 in ((1.6, 58, 9), (2.4, 66, 3), (3.2, 74, 11), (4.8, 64, 1), (6.4, 78, 7), (9.5, 70, 0)):
        r = d / 2
        def ring(x, c, e, h):
            p.flat(ellipse(x, c, e * .8, h * .8, 32), 0, '#121316', op=.9)
            p.flat(ellipse(x + e * .12, c + h * .12, e * .62, h * .62, 32), 0, '#08090a', stroke='none')
        cc, hh, _ = p.rod(x0, x0 + L, y + r, r, black, za=r, face=ring, tip='flat', hi=.45, ef=.42)
        for k in range(2):
            xx = x0 + 14 + k * 30
            p.line([(xx, cc - hh * .05), (xx + 9, cc - hh * .05)], 0, '#8a8e96', max(.7, d * .12))
        y += d + 2.2



# ------------------------------------------------------------------ small boards and components
MASK, SILK, FR4 = '#1f2226', '#f1f1ec', '#cdbf96'   # Adafruit black solder mask, white silkscreen, board edge


def gold_hole(p, x, y, r, z, pad=.45):
    p.flat(circle(x, y, r + pad, 32), z, GOLD, op=.45)
    p.hole(x, y, r, z)


def led5050(p, x, y, z):
    """A 5050 RGB LED: white body, round window over the three dies."""
    def top():
        p.flat(circle(x + 2.5, y + 2.5, 2.05, 36), z + 1.6, '#f7efcf', op=.45)
        for dx, dy, c in ((1.7, 1.9, '#d24a3c'), (2.9, 1.9, '#3c9a52'), (2.3, 3.0, '#3f64c4')):
            p.flat(rrect(x + dx, y + dy, .55, .55, .1), z + 1.6, c, stroke='none')
    p.prism(rrect(x, y, 5, 5, .3), z, z + 1.6, '#f5f3ee', '#cfcac0', detail=top)


def jst_sh3(p, x, y, z, leads='right'):
    """Right-angle JST-SH three-pin socket seen from above; its three leads point inward."""
    lx = x + 4 if leads == 'right' else x - .8
    for i in range(3):
        p.prism(rrect(lx, y + 2.1 + i * 1.0, .8, .45), z, z + .25, '#c9cdd2', '#8f969e', edge=False)
    p.prism(rrect(x, y, 4, 6.2, .3), z, z + 2.9, WHITE_PL, '#cfc9b9',
            detail=lambda: p.flat(rrect(x + .6, y + .7, 2.8, 4.8, .3), z + 2.9, '#e4dfd2', op=.3))


def neopixel_eye(p):
    """Adafruit 5975, twice: LED side up (left) and socket side up (right). 12.3 x 11.3 mm."""
    T = 1.6
    for ox, front in ((0, True), (17, False)):
        def art(ox=ox, front=front):
            if not front:
                p.text(ox + 2.7, 10.6, T, 'In', 1.5, SILK)
                p.text(ox + 9.6, 10.6, T, 'Out', 1.5, SILK)
        p.prism(rrect(ox, 0, 12.3, 11.3, 1.7), 0, T, MASK, FR4, detail=art)
        for y in (1.45, 9.85):
            gold_hole(p, ox + 6.15, y, .95, T, .35)
        if front:
            led5050(p, ox + 3.65, 3.4, T)
        else:
            jst_sh3(p, ox + .5, 2.6, T, 'right')
            jst_sh3(p, ox + 7.8, 2.6, T, 'left')


def neopixel_stick(p):
    """Adafruit 1426: eight 5050 LEDs on a black 51.1 x 10.2 mm stick, four pads at each end."""
    T, L, Wd = 1.6, 51.1, 10.2
    def art():
        for x in (.5, L - 2.3):
            for i in range(4):
                p.flat(rrect(x, 1.3 + i * 2.05, 1.8, 1.3, .25), T, GOLD, op=.45)
    p.prism(rrect(0, 0, L, Wd, .5), 0, T, MASK, FR4, detail=art)
    xs = [3.2 + i * 5.75 for i in range(8)]
    for x in (xs[1] + 5.37, xs[5] + 5.37):
        gold_hole(p, x, 1.3, .6, T, .3)
    for x in xs:
        led5050(p, x, 2.6, T)


def terminal_block(p, x, y, z, n=4, pitch=2.54, depth=6.4, h=8.6):
    green = '#47ad6c'
    def screws():
        for i in range(n):
            cx, cy = x + depth * .55, y + .6 + pitch * (i + .5)
            p.flat(circle(cx, cy, 1.05, 28), z + h, '#2f7d4c', op=.8)
            p.flat(circle(cx, cy, .82, 28), z + h, '#c3c9cf', op=.8)
            p.line([(cx - .6, cy - .35), (cx + .6, cy + .35)], z + h, '#5f666e', 1.1)
    p.prism(rrect(x, y, depth, pitch * n + 1.2, .3), z, z + h, green, dim(green, .3), detail=screws)


def pixel_shifter(p):
    """Adafruit 6066 Pixel Shifter: 25.5 x 15 mm, green four-way terminals on both ends."""
    T, L, Wd = 1.6, 25.5, 15
    def art():
        p.text(4.3, 1.75, T, '3-5VDC', 1.35, SILK)
        p.text(21.6, 1.75, T, '5V', 1.35, SILK)
        p.text(4.4, 14.5, T, 'INPUT', 1.3, SILK)
        p.text(21.2, 14.5, T, 'OUTPUT', 1.3, SILK)
    p.prism(rrect(0, 0, L, Wd, 1.4), 0, T, MASK, FR4, detail=art)
    for y in (2.42, 12.58):
        gold_hole(p, 12.75, y, 1.1, T)
    p.prism(rrect(10.6, 5.2, 4.3, 4.8, .2), T, T + 1.2, '#2a2b2f')
    for x, y in ((9.2, 5.6), (9.2, 8.4), (15.6, 6.0), (15.6, 8.8)):
        p.prism(rrect(x, y, 1.2, .8, .1), T, T + .5, '#b88b5b')
    terminal_block(p, .5, 1.9, T)
    terminal_block(p, L - 6.9, 1.9, T)


def usb_audio(p):
    """Waveshare USB TO AUDIO (18833): black case 53 x 23.5 x 14.6 mm, USB-A plug at one end,
    four-pin speaker socket at the other."""
    L, Wd, Hh = 53, 23.5, 14.6
    case = '#2b2d32'
    p.prism(rrect(-12, Wd / 2 - 6, 13, 12, .3), 5, 9.5, CHROME, dim(CHROME, .3),
            detail=lambda: [p.flat(rrect(-8.5, Wd / 2 + dy, 2.4, 2.4, .2), 9.5, '#7d858d', op=.6) for dy in (-3.6, 1.2)])
    def art():
        p.flat(rrect(2.2, 4.2, 5.2, 15.1, .9), Hh, '#6cc24a', stroke='none')
        p.text(4.8, Wd / 2, Hh, 'USB', 3.1, '#ffffff', rotate=-90)
        p.text(26.5, 15.6, Hh, 'USB TO AUDIO', 3.5, '#ffffff')
        p.line([(12, 11.2), (41, 11.2)], Hh, '#6cc24a', 1.8)
        p.flat(circle(11.2, 3.4, .75, 20), Hh, '#6f747c', stroke='none')
        p.text(14.2, 3.9, Hh, 'PWR', 1.3, '#d9dadc')
        p.flat(rrect(46.6, 7.4, 4.2, 8.7, .4), Hh, '#15161a', stroke='#8a8f97', sw=1, op=.9)
        for i in range(4):
            p.flat(circle(48.7, 8.5 + i * 2.15, .42, 16), Hh, '#b7bcc2', stroke='none')
        for y in (2.8, 20.7):
            p.flat(circle(49.6, y, .9, 20), Hh, '#141518', stroke='#8a8f97', sw=.9, op=.9)
    p.prism(rrect(0, 0, L, Wd, 3.2), 0, Hh, case, '#18191c', detail=art)


def microsd(p):
    """PNY Elite 32 GB microSD card, label side up, contacts end at the top."""
    card = [(1.4, 0), (11, 0), (11, 15), (0, 15), (0, 7.3), (.8, 6.5), (.8, 5.6), (1.4, 5.0)]
    def art():
        p.text(6.2, 5.0, 1, 'PNY ELITE', 1.2, '#e9e9ea')
        p.text(6.0, 10.2, 1, '32GB', 3.1, '#ffffff')
        p.text(3.4, 13.4, 1, 'microSD HC', .9, '#c9cacd', anchor='start')
        for y in (13.9, 14.3):
            p.line([(8.2, y), (10.4, y)], 1, '#4a4c52', .8)
    p.prism(card, 0, 1, '#35373d', '#18191c', detail=art)


def capacitor(p):
    """Panasonic EEU-FR1A102: 1000 uF 10 V, 10 x 16 mm, black sleeve, vent end toward the viewer."""
    r, L = 5, 16
    def vent(x, c, e, h):
        p.flat(ellipse(x, c, e * .86, h * .86, 36), 0, '#c9ced3', stroke='none')
        p.line([(x, c - h * .55), (x, c + h * .55)], 0, '#8b929a', 1.2)
        p.line([(x - e * .5, c), (x + e * .5, c)], 0, '#8b929a', 1.2)
    # leads first: they leave the far end
    for dy, ln in ((-1.9, 16), (1.9, 19)):
        a, b = p.P(L, dy - r * K), p.P(L + ln, dy - r * K)
        p.add(f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{INK}" stroke-width="{f(.6 * p.s + 2 * LW * .7)}" stroke-linecap="round"/>'
              f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="#cfd3d8" stroke-width="{f(.6 * p.s)}" stroke-linecap="round"/>')
    c, h, e = p.rod(0, L, 0, r, '#2a2b30', face=vent, tip='round', hi=.35)
    stripe = (c - h * .62, c - h * .18)
    p.clipped(p.last_clip, [([(1.2, stripe[0]), (L + 3, stripe[0]), (L + 3, stripe[1]), (1.2, stripe[1])], '#8e949c')])
    for i in range(4):
        x = 3.2 + i * 3.3
        p.line([(x, (stripe[0] + stripe[1]) / 2), (x + 1.4, (stripe[0] + stripe[1]) / 2)], 0, '#2a2b30', 1.6)
    p.text(8.8, c + h * .5, 0, '1000µF 10V', 1.9, '#a6acb4')


def resistor(bands):
    """A Yageo CFR-25 carbon-film resistor: tan body, four colour bands, leads both ends."""
    def draw(p):
        r = 1.2
        a, b = p.P(-9, -r * K), p.P(15.3, -r * K)
        p.add(f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{INK}" stroke-width="{f(.55 * p.s + 2 * LW * .7)}" stroke-linecap="round"/>'
              f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="#cfd3d8" stroke-width="{f(.55 * p.s)}" stroke-linecap="round"/>')
        c, h, e = p.rod(0, 6.3, 0, r, '#d9bf92', face=lambda x, c, e, h: None, tip='round', hi=.55)
        p.clipped(p.last_clip, [([(x, c - h - 1), (x + .62, c - h - 1), (x + .62, c + h + 1), (x, c + h + 1)], col)
                                for x, col in zip((1.0, 2.0, 3.0, 4.9), bands)])
    return draw


def fuse(rating):
    """Eaton BK1-S505H 5 x 20 mm time-delay fuse: white ceramic tube, nickel end caps."""
    def draw(p):
        r = 2.5
        c, h, e = p.rod(4.6, 15.4, 0, r * .96, '#f0ede6', za=r, face=False, hi=.6)
        p.text(10, c + h * .25, 0, rating, 1.2, '#4f5358')
        p.rod(15, 20, 0, r, '#c7ccd2', za=r, face=False, tip='round')
        p.rod(0, 5, 0, r, '#c7ccd2', za=r,
              face=lambda x, c, e, h: p.flat(ellipse(x, c, e * .6, h * .6, 30), 0, '#dfe3e7', stroke='none'))
    return draw



# ------------------------------------------------------------------ cables and connectors
def crsample(ps, n=10):
    """Dense points along a Catmull-Rom curve through ps (plan mm)."""
    out = []
    for i in range(len(ps) - 1):
        p0, p1, p2, p3 = ps[max(i - 1, 0)], ps[i], ps[i + 1], ps[min(i + 2, len(ps) - 1)]
        for k in range(n):
            t = k / n
            out.append(tuple(.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                   + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    out.append(ps[-1])
    return out


def offset(ps, d):
    out = []
    for i, (x, y) in enumerate(ps):
        a, b = ps[max(i - 1, 0)], ps[min(i + 1, len(ps) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        out.append((x - dy / n * d, y + dx / n * d))
    return out


def cable(p, path, colors, d=1.2, gap=None, strip=0, tin='#c9cdd2'):
    """Parallel insulated wires along a path (a flat ribbon or a loose bundle); optional stripped ends."""
    gap = gap or d * 1.02
    dense = crsample(path)
    n = len(colors)
    for i, col in enumerate(colors):
        ps = offset(dense, (i - (n - 1) / 2) * gap)
        if strip:
            end = ps[-1]
            a = ps[-4]
            ux, uy = end[0] - a[0], end[1] - a[1]
            m = math.hypot(ux, uy) or 1
            tip = (end[0] + ux / m * strip, end[1] + uy / m * strip)
            p.wire([end, tip], tin, d * .55, z=d / 2)
        p.wire(ps, col, d, z=d / 2)


def local(cx, cy, ang):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return lambda u, v: (cx + u * ca - v * sa, cy + u * sa + v * ca)


def conn(p, cx, cy, ang, L, Wd, H, color, side=None, feats=None, z0=0, r=.4, face=None):
    """A connector body centred at (cx, cy), its axis at `ang` degrees; u runs along the axis
    from the mating face (u = -L/2) to the wire end. `feats(loc, ztop)` draws on its top.
    With ang = -90 the mating face looks at the viewer; `face(F)` draws on it, where F(v, z)
    is the page point at v across the face and height z."""
    loc = local(cx, cy, ang)
    poly = [loc(u, v) for u, v in rrect(-L / 2, -Wd / 2, L, Wd, r)]
    p.prism(poly, z0, z0 + H, color, side, detail=(lambda: feats(loc, z0 + H)) if feats else None)
    if face:
        face(lambda v, z: p.P(*loc(-L / 2, v), z))
    return loc


def fpoly(p, F, vz, fill, stroke=INK, sw=LI, op=.6):
    """A polygon on a connector's mating face, from (v, z) pairs."""
    p.add(f'<polygon points="{pts([F(v, z) for v, z in vz])}" fill="{fill}" stroke="{stroke}" stroke-width="{f(sw)}" stroke-opacity="{op}" stroke-linejoin="round"/>')


def frect(v, z, w, h):
    return [(v, z), (v + w, z), (v + w, z + h), (v, z + h)]


def lpoly(loc, ps):
    return [loc(u, v) for u, v in ps]


def jst_sm(p, cx, cy, kind):
    """JST-SM three-pin housing, black, standing on its cable end with the mating face up.
    The receptacle is the smaller housing with three square sockets and the press latch; the
    plug is the larger, shrouded housing with three pins set inside. The receptacle slides
    into the plug's shroud."""
    H = 12 if kind == 'rec' else 11
    def face():
        if kind == 'rec':
            for dx in (-2.2, 0, 2.2):
                p.flat(rrect(cx + dx - .8, cy - .8, 1.6, 1.6, .2), H, '#0e0f11', op=.9)
            p.flat(rrect(cx - 1.4, cy - 3.6, 2.8, 1.3, .3), H, '#4a4c52', op=.6)
        else:
            p.flat(rrect(cx - 4.0, cy - 2.6, 8.0, 5.2, .4), H, '#0e0f11', op=.9)
            for dx in (-2.2, 0, 2.2):
                p.flat(rrect(cx + dx - .4, cy - .4, .8, .8, .1), H, '#c9ced3', stroke='none')
            p.flat(rrect(cx - 1.3, cy - 3.9, 2.6, 1.0, .3), H, '#141518', op=.8)
    if kind == 'rec':
        outline = rrect(cx - 3.5, cy - 2.6, 7.0, 5.2, .5)
    else:
        outline = rrect(cx - 4.8, cy - 3.4, 9.6, 6.8, .5)
    p.prism(outline, 0, H, '#2e2f34', '#1b1c1f', detail=face)


def jst_sh_plug(p, cx, cy, ang):
    """JST-SH three-pin plug (1 mm pitch), white."""
    def top(loc, z):
        p.flat(lpoly(loc, rrect(-1.9, -1.8, 1.4, 3.6, .2)), z, '#e0dbcd', op=.35)
        for v in (-1, 0, 1):
            p.flat(lpoly(loc, rrect(.3, v - .3, 1.3, .6, .1)), z, '#d2ccbd', op=.5)
    return conn(p, cx, cy, ang, 4.4, 5.2, 2.9, WHITE_PL, '#cfc9b9', top, r=.25)


def jst_eye_lead(p):
    """Adafruit 6406: JST-SH plug to plug, black / red / white, 200 mm, loosely coiled."""
    cable(p, [(-40, 22), (-40, 6), (-30, -8), (-8, -14), (14, -10), (30, 2), (24, 16), (6, 18),
              (-6, 10), (4, 0), (22, 4), (40, 14), (40, 22)], (BLACK_W, RED_W, '#eeeeea'), .9)
    jst_sh_plug(p, -40, 24.2, -90)
    jst_sh_plug(p, 40, 24.2, -90)


def jst_link(p):
    """Adafruit 6404: JST-SH plug to plug, black / red / white, 100 mm."""
    cable(p, [(-26, 22), (-26, 8), (-18, -4), (0, -9), (18, -4), (26, 8), (26, 22)], (BLACK_W, RED_W, '#eeeeea'), .9)
    jst_sh_plug(p, -26, 24.2, -90)
    jst_sh_plug(p, 26, 24.2, -90)


def jst_sm_pair(p):
    """Adafruit 1663: JST-SM three-pin receptacle and plug, each on dark three-wire ribbon
    with tinned ends."""
    smoke = '#3b3d43'
    cable(p, [(0, 2), (2, 12), (18, 18), (44, 15), (66, 8)], (smoke,) * 3, 1.25, strip=3)
    cable(p, [(20, 2), (22, 8), (34, 13), (50, 25), (68, 25)], (smoke,) * 3, 1.25, strip=3)
    jst_sm(p, 0, 0, 'rec')
    jst_sm(p, 20, 0, 'plug')


def usb_c_panel_cable(p):
    """Adafruit 4056: panel-mount USB-C socket (two ears, M3 screws 20 mm apart) standing with
    its face up, 4.5 mm black cable, micro-B plug."""
    blk = '#2a2b2f'
    cable(p, [(0, 4), (4, 14), (22, 22), (50, 20), (62, 4), (54, -12), (42, -14)], (blk,), 4.5)
    p.prism(rrect(-6, -5, 12, 10, 2.2), 0, 11, blk, '#17181b')
    def plate():
        p.flat(rrect(-4.6, -1.7, 9.2, 3.4, 1.6), 14, '#101114', op=.9)
        p.flat(rrect(-3.1, -.45, 6.2, .9, .4), 14, '#8a9199', stroke='none')
        for x in (-10, 10):
            p.flat(circle(x, 0, 2.3, 32), 14, '#d3d7db', op=.8)
            p.line([(x - 1.2, 0), (x + 1.2, 0)], 14, '#5d646c', 1.6)
            p.line([(x, -1.2), (x, 1.2)], 14, '#5d646c', 1.6)
    p.prism(rrect(-14, -3.9, 28, 7.8, 3.9), 11, 14, '#c3c9cf', '#8c949c', detail=plate)
    conn(p, 33, -14, 180, 18, 10, 7.5, blk, '#17181b',
         lambda loc, z: p.flat(lpoly(loc, rrect(-5, -3, 9, 6, 2)), z, '#34363b', op=.4), r=2.6)
    conn(p, 21, -14, 0, 6, 7, 2.5, CHROME, dim(CHROME, .3), z0=2.5, r=.6)


def usb_extension(p):
    """USB-A male to USB-A female data extension cable; the socket stands with its opening up."""
    blk = '#2a2b2f'
    cable(p, [(12, 0), (40, -2), (64, 10), (62, 32), (44, 38), (34, 30)], (blk,), 3.6)
    conn(p, 0, 0, 0, 20, 16, 8, blk, '#17181b',
         lambda loc, z: p.flat(lpoly(loc, rrect(-6, -5, 10, 10, 2)), z, '#34363b', op=.4), r=2.5)
    conn(p, -15, 0, 0, 12, 12, 4.5, CHROME, dim(CHROME, .3), z0=1.8,
         feats=lambda loc, z: [p.flat(lpoly(loc, rrect(-3.5, v - 1.2, 2.4, 2.4, .2)), z, '#7d858d', op=.6) for v in (-2.8, 2.8)])
    def socket():
        p.flat(rrect(27.4, 23.1, 13.2, 5.8, .4), 20, '#cdd2d7', op=.9)
        p.flat(rrect(28.1, 23.6, 11.8, 4.8, .3), 20, '#17181b', op=.9)
        p.flat(rrect(28.8, 23.9, 10.4, 1.7, .2), 20, '#e8e4d6', op=.6)
    p.prism(rrect(25.5, 21.5, 17, 9, 2.4), 0, 20, blk, '#1b1c1f', detail=socket)


def jumper_leads(p):
    """Jumper leads with 2.54 mm female housings, stripped at the far end."""
    cols = ('#7a4a2a', RED_W, '#e37a22', '#e8c334', '#3f9a57', '#3b6fc1')
    for i, col in enumerate(cols):
        y = i * 5.2
        cable(p, [(8, y), (40, y + 1.5 + i * .6), (75, y + 3 + i * 1.2)], (col,), 1.3, strip=4)
        conn(p, 0, y, 0, 14, 2.6, 2.6, '#2c2d31', '#161719',
             lambda loc, z: p.flat(lpoly(loc, rrect(-6.6, -.5, 1, 1, .1)), z, '#111214', op=.9), r=.2)



# ------------------------------------------------------------------ strands, supplies and cords
def pebble_strand(p):
    """Adafruit 6026 NeoPixel Pebble strand: thin clear three-core wire with a milky resin
    pebble every 100 mm, coiled; red / green / black lead to a JST-SM housing at each end:
    sockets (receptacle) at one end, pins (plug) at the other."""
    wire = '#dfe4ea'
    loops = []
    for k in range(5):
        cx, cy, rx, ry = 2 + k * 1.8, k * 1.2, 34 - k * 1.1, 22 - k * .8
        loops.append([(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(0, 361, 20)])
    for lp in loops:
        p.wire(lp, wire, 1.1)
    for k, lp in enumerate(loops):
        for j in (3 + k * 4, 12 + k * 3):
            (x0, y0), (x1, y1) = lp[j % 18], lp[(j + 1) % 18]
            a = math.atan2(y1 - y0, x1 - x0)
            pts_ = [((x0 + x1) / 2 + 2.6 * math.cos(t) * math.cos(a) - 1.15 * math.sin(t) * math.sin(a),
                     (y0 + y1) / 2 + 2.6 * math.cos(t) * math.sin(a) + 1.15 * math.sin(t) * math.cos(a)) for t in [i * math.pi / 12 for i in range(24)]]
            p.prism(pts_, .2, 1.8, '#f3f0e8', '#cfc9bb')
    for sgn, (sx, sy), kind in ((-1, (-32, 4), 'rec'), (1, (38, 6), 'plug')):
        tail = [(sx, sy), (sx + sgn * 8, sy + 10), (sx + sgn * 14, sy + 22)]
        p.wire(tail, wire, 1.1)
        cable(p, [tail[-1], (sx + sgn * 17, sy + 30), (sx + sgn * 18, sy + 38)], (RED_W, '#2f8f64', BLACK_W), 1.0)
        jst_sm(p, sx + sgn * 18, sy + 42, kind)


def barrel_plug(p, x, yc, ang=0):
    """A straight 2.1 mm DC barrel plug lying along +x from x, tip to the left."""
    p.rod(x + 9, x + 24, yc, 4.5, '#2a2b2f', face=False, tip='round', hi=.3)
    p.rod(x, x + 9.5, yc, 2.75, '#c9ced3', za=4.5,
          face=lambda X, c, e, h: [p.flat(ellipse(X, c, e * .72, h * .72, 30), 0, '#2a2b2f', stroke='none'),
                                   p.flat(ellipse(X, c, e * .28, h * .28, 20), 0, '#c9ced3', stroke='none')])


def power_supply(p):
    """Mean Well GST40A05-P1J desktop supply: black 125 x 50 x 31.5 mm case, DC cord to a
    2.1 mm straight barrel plug (the IEC inlet is on the far end)."""
    cable(p, [(125, 25), (140, 26), (152, 40), (140, 62), (100, 70), (60, 72), (34, 70)], ('#2a2b2f',), 3.4)
    p.prism(rrect(122, 20, 10, 10, 2), 6, 16, '#2a2b2f', '#17181b')
    def label():
        p.flat(rrect(22, 10, 72, 30, 1.5), 31.5, '#50535b', op=.4)
        for i, w in enumerate((44, 58, 36, 52, 30)):
            p.line([(28, 15.5 + i * 4.6), (28 + w, 15.5 + i * 4.6)], 31.5, '#8c9098', 1.8)
        p.flat(rrect(100, 14, 12, 22, 1), 31.5, '#26272b', op=.4)
    p.prism(rrect(0, 0, 125, 50, 7), 0, 31.5, '#2e2f34', '#1a1b1e', detail=label)
    barrel_plug(p, 10, 70)


def mains_cord(p):
    """Mean Well YP12 / YC12: US NEMA 5-15P plug to IEC C13 socket, black."""
    blk = '#2a2b2f'
    cable(p, [(24, 0), (50, 2), (78, 16), (74, 40), (46, 46), (40, 36)], (blk,), 6)
    for v in (-6.3, 6.3):
        conn(p, -6, v, 0, 16, 1.6, 6.4, '#c9ced3', '#8f969d', z0=3.2, r=.3)
    p.rod(-12, 1, 0, 2.4, '#c9ced3', za=11.5, face=None, tip='round')
    conn(p, 12, 0, 0, 26, 30, 22, blk, '#17181b',
         lambda loc, z: p.flat(lpoly(loc, rrect(-8, -11, 14, 22, 4)), z, '#34363b', op=.4), r=5)
    def c13():
        p.flat([(28, 30.5), (52, 30.5), (52, 38), (48.5, 41.5), (31.5, 41.5), (28, 38)], 30, '#101114', op=.9)
        for x, y in ((33.5, 34.5), (46.5, 34.5), (40, 38.2)):
            p.flat(rrect(x - 1.1 if y < 36 else x - 2.2, y - 2.2 if y < 36 else y - 1.1, 2.2 if y < 36 else 4.4, 4.4 if y < 36 else 2.2, .3), 30, '#050506', op=.9)
    p.prism(rrect(25, 27, 30, 18, 3), 0, 30, blk, '#1b1c1f', detail=c13)


# ------------------------------------------------------------------ mechanical parts
def servo(p):
    """Kitronik 25105 (FS90MG-CL) clippable servo lying on its label side: translucent blue
    case, brass 21T output spline, orange / red / brown leads to crocodile clips."""
    blue, blue_side = '#3d64d8', '#2743a0'
    T = 12.1
    # profile from the Kitronik drawing, output up the page (y down)
    body = rrect(4.9, 8.3, 22.5, 22.4, .8)
    ears = rrect(0, 12.5, 32.3, 2.5, .6)
    for i, (col, clip) in enumerate((('#e8841f', '#f2d23a'), (RED_W, '#d8342a'), ('#6b3d22', '#2b2c30'))):
        cable(p, [(4.9, 26.5 + i * .9), (-6, 27 + i * 1.5), (-16, 26 + i * 6), (-26, 22 + i * 9)], (col,), 1.1)
        loc = conn(p, -34, 22 + i * 9, 0, 18, 6.6, 5, clip, dim(clip, .35),
                   lambda loc, z, c=clip: p.flat(lpoly(loc, rrect(-8, -2.2, 14, 4.4, 2)), z, lit(c, .25), op=.2), r=3)
        p.prism(lpoly(loc, [(-9, -1.8), (-17, -.6), (-17, .6), (-9, 1.8)]), 1.2, 3.2, '#c9ced3', '#8f969d')
    p.prism(ears, T * .42, T * .62, blue, blue_side)
    def label():
        p.flat(rrect(7.4, 13.5, 17.5, 14.2, .8), T, '#ffffff', op=.5)
        p.flat(ellipse(16.1, 16.7, 6.2, 2.1, 36), T, 'none', '#2b2c30', 1.2, .9)
        p.text(16.1, 17.4, T, 'Kitronik', 2.2, '#2b2c30')
        p.flat(rrect(7.4, 20.2, 17.5, 7.5, .2), T, '#2f9a53', stroke='none')
        p.text(16.1, 23.2, T, 'CLIPPABLE SERVO', 1.75, '#ffffff')
        p.text(16.1, 26.0, T, '25105', 1.75, '#ffffff')
    p.prism(body, 0, T, blue, blue_side, detail=label)
    p.prism(rrect(12.8, 4, 14.4, 5, .8), 1, T - 1, blue, blue_side)
    p.prism(rrect(18.6, 0, 5.4, 4.4, .4), 3.6, T - 3.6, '#d0a64c', '#9a7630',
            detail=lambda: [p.line([(19.2 + i * .85, .4), (19.2 + i * .85, 4)], T - 3.6, '#9a7630', .9) for i in range(6)])


def horn(p):
    """The supplied round disk horn (black POM), splined face up: 23.55 mm across, raised hub."""
    R = 23.55 / 2
    def face():
        rng = [(7.0, 0), (8.6, 7), (10.2, 14)]
        for q in range(4):
            for r, da in rng:
                a = math.radians(q * 90 + 20 + da + (q % 2) * 12)
                p.hole(r * math.cos(a), r * math.sin(a), .55, 1.6)
        for q in range(4):
            a = math.radians(q * 90 + 65)
            p.flat(circle(7.6 * math.cos(a), 7.6 * math.sin(a), 2.4, 28), 1.6, 'none', '#4b4d53', .9, .9)
    p.prism(circle(0, 0, R, 72), 0, 1.6, '#2b2c30', '#18191b', detail=face)
    def hub():
        teeth = [((2.45 if i % 2 else 2.15) * math.cos(math.pi * i / 21), (2.45 if i % 2 else 2.15) * math.sin(math.pi * i / 21)) for i in range(42)]
        p.flat(teeth, 4.65, '#141517', op=.9)
        p.hole(0, 0, 1.0, 4.65)
    p.prism(circle(0, 0, 3.4, 48), 1.6, 4.65, '#303136', '#1b1c1f', detail=hub)


def wago(p):
    """WAGO 221-415: clear housing 30 x 18.6 x 8.4 mm, five orange levers, wire entries toward
    the viewer."""
    clear, clear_side = '#dfe7ec', '#b6c3cc'
    pitch = 18.6 / 5
    def inside():
        p.flat(rrect(1.2, 21.5, 16.2, 5.5, .5), 8.4, '#aeb6bd', op=.25)
        for i in range(5):
            x = pitch * (i + .5)
            p.flat(circle(x, 25.3, 1.25, 24), 8.4, '#8d98a2', op=.5)
            p.flat(rrect(x - .5, 29.0, 1.0, .6, .1), 8.4, '#6f7a84', stroke='none')
    p.prism(rrect(0, 0, 18.6, 30, 1.2), 0, 8.4, clear, clear_side, detail=inside)
    for i in range(5):
        x0 = pitch * i + .35
        def ridges(x0=x0):
            for k in range(4):
                p.line([(x0 + .5, 2.2 + k * 1.3), (x0 + pitch - 1.2, 2.2 + k * 1.3)], 9.3, '#b8611a', .9)
        p.prism(rrect(x0, .8, pitch - .7, 18.5, .6), 8.4, 9.3, '#f08c28', '#c5661b', detail=ridges)
    p.prism(rrect(0, 29.4, 18.6, .6, .3), 0, 8.4, clear, clear_side)
    for i in range(5):
        c = p.P(pitch * (i + .5), 30, 4.0)
        p.add(f'<ellipse cx="{f(c[0])}" cy="{f(c[1])}" rx="{f(1.2 * p.s)}" ry="{f(1.05 * p.s * K * 2)}" fill="#6d7780" stroke="{INK}" stroke-width="{f(LI)}" stroke-opacity=".6"/>')


def fuse_holder(p):
    """Schurter FDI 8601.2001.08 in-line 5 x 20 mm fuse holder: black body up to 48 x 16 mm,
    factory-fitted 18 AWG leads (dark pink), supplied as one loop."""
    pink = '#9b3552'
    p.wire([(46, -4.2), (58, -5), (66, -18), (50, -36), (20, -40), (-10, -34), (-20, -16), (-10, -5), (0, -4)], pink, 2.0, z=4.5)
    blk = '#2b2c30'
    segs = [(40, 46, 3.6), (30, 40.2, 5.6), (22, 30.2, 6.4), (16, 22.2, 6.9), (13, 16.2, 8), (8, 13.2, 5.4), (0, 8.2, 4.2)]
    for x0, x1, r in segs:
        p.rod(x0, x1, 0, r, blk, za=8, face=None, tip='round', hi=.35)
    for x in (1.5, 3.2, 4.9, 6.6):
        t, b = p.band(0, 8, 4.2)
        p.line([(x, t + .6), (x, b - .6)], 0, '#4d5056', 1.1)


def button(p):
    """Adafruit 1479 16 mm illuminated momentary button, standing lens-up: black 18 x 18 mm
    bezel, white lens with a clear ring, threaded body and its ring nut."""
    blk = '#2c2d31'
    def threads():
        for z in (1.2, 2.6, 4.0, 5.4, 6.8, 8.2):
            p.line([(7.6 * math.cos(math.radians(a)), 7.6 * math.sin(math.radians(a))) for a in range(5, 176, 10)], z, '#55585f', 1.1)
    p.prism(circle(0, 0, 7.6, 48), 0, 25, blk, '#3a3c42')
    threads()
    for z in (9.6, 11.0, 12.4):
        p.line([(7.6 * math.cos(math.radians(a)), 7.6 * math.sin(math.radians(a))) for a in range(5, 176, 10)], z, '#55585f', 1.1)
    p.prism(circle(0, 0, 10.4, 48), 14.5, 18, '#26272b', '#2f3136',
            detail=lambda: [p.line([(10.4 * math.cos(math.radians(a)), 10.4 * math.sin(math.radians(a))), (9.2 * math.cos(math.radians(a)), 9.2 * math.sin(math.radians(a)))], 14.5, '#45474d', 1.2) for a in range(0, 360, 20)])
    for a in range(10, 171, 20):
        x, y = 10.4 * math.cos(math.radians(a)), 10.4 * math.sin(math.radians(a))
        p.line([(x, y), (x, y)], 14.5, '#45474d', 1)
        q0, q1 = p.P(x, y, 14.5), p.P(x, y, 18)
        p.add(f'<line x1="{f(q0[0])}" y1="{f(q0[1])}" x2="{f(q1[0])}" y2="{f(q1[1])}" stroke="#4a4c53" stroke-width="1.4"/>')
    def lens():
        p.flat(circle(0, 0, 7.6, 48), 29.4, '#dfe3e7', op=.8)
        p.flat(circle(0, 0, 6.4, 48), 29.4, '#fbfbf8', op=.5)
        p.flat(ellipse(-2.2, -2.4, 3, 1.4), 29.4, '#ffffff', stroke='none')
    p.prism(rrect(-9, -9, 18, 18, 2.4), 25, 28.2, blk, '#1c1d20')
    p.prism(circle(0, 0, 7.6, 48), 28.2, 29.4, '#e9ecef', '#b9c0c6', detail=lens)


def power_jack(p):
    """Switchcraft 721AU sealed 2.1 mm solder-lug power jack: nickel threaded bushing with nut and
    washer, black body, two solder-eyelet lugs."""
    r_body = 6.4
    for dy in (-2.6, 2.6):
        a = p.P(22, dy, r_body)
        conn(p, 25, dy, 0, 8, 2.8, .6, '#c9ced3', '#8f969d', z0=r_body - .3, r=.4,
             feats=lambda loc, z: p.hole(*loc(1.6, 0), .7, z))
    p.rod(9, 23, 0, r_body, '#2c2d31', za=r_body, face=None, tip='round', hi=.3)
    p.rod(5.5, 7.2, 0, 5.4, '#c9ced3', za=r_body, face=None, tip='round')
    p.rod(3.2, 5.8, 0, 5.0, '#b7bec5', za=r_body, face=None, tip='round')
    def bush(x, c, e, h):
        p.flat(ellipse(x, c, e * .66, h * .66, 30), 0, '#2a2b2f', stroke='none')
        p.flat(ellipse(x, c, e * .2, h * .2, 20), 0, '#d8dce0', stroke='none')
    c, h, e = p.rod(0, 9, 0, 3.95, '#cdd2d7', za=r_body, face=bush, tip='round', serr=.8)


def rubber_feet(p):
    """Four illustrative adhesive feet on a backing sheet; dimensions are selected to fit the post faces."""
    p.prism(rrect(0, 0, 36, 36, 2), 0, .4, '#f6f5f0', '#d6d3c8')
    for x, y in ((9.5, 9.5), (26.5, 9.5), (9.5, 26.5), (26.5, 26.5)):
        p.prism(circle(x, y, 6, 48), .4, 2.6, '#2c2d31', '#18191b',
                detail=lambda x=x, y=y: p.flat(circle(x, y, 4.6, 40), 2.6, '#35373c', op=.0))
        p.prism(circle(x, y, 4.6, 40), 2.6, 3.4, '#34363b', '#232428',
                detail=lambda x=x, y=y: p.flat(ellipse(x - 1.6, y - 1.8, 1.8, .9), 3.4, '#5a5d64', stroke='none'))



# ------------------------------------------------------------------ consumables
FOAM, FOAM_SIDE = '#f7f6f1', '#d9d6cc'      # white Plastazote


def foam_dots(p, x0, y0, w, h, z, n=26, seed=1):
    """A faint closed-cell texture: a few scattered pores, placed deterministically."""
    r = seed
    for i in range(n):
        r = (r * 1103515245 + 12345) % 2147483648
        x = x0 + (r % 1000) / 1000 * w
        r = (r * 1103515245 + 12345) % 2147483648
        y = y0 + (r % 1000) / 1000 * h
        p.flat(circle(x, y, .18 + (i % 3) * .06, 10), z, '#dedbd1', stroke='none')


def clear_film(p):
    """Clear eye film: a transparency offcut with the two cut rounded rectangles (12.6 x 8.6 mm)."""
    film, edge = '#e3eef4', '#b9ccd8'
    def sheet():
        for x in (6, 23):
            p.flat(rrect(x, 7, 12.6, 8.6, 4.2), .25, BG, stroke='#8aa3b3', sw=1.2, op=.9)
        p.line([(3, 20), (13, 2)], .25, '#ffffff', 2.2, extra=' stroke-opacity=".8"')
    p.prism(rrect(0, 0, 42, 24, .4), 0, .25, film, edge, detail=sheet)
    for x, y in ((8, 30), (25, 31.5)):
        p.prism(rrect(x, y, 12.6, 8.6, 4.2), 0, .25, film, edge,
                detail=lambda x=x, y=y: p.line([(x + 2.5, y + 7), (x + 6, y + 1.5)], .25, '#ffffff', 2, extra=' stroke-opacity=".8"'))


def eye_foam(p):
    """Two 14 x 10 mm patches of white 4 mm Plastazote."""
    for x in (0, 19):
        p.prism(rrect(x, 0, 14, 10, .3), 0, 4, FOAM, FOAM_SIDE, detail=lambda x=x: foam_dots(p, x + .5, .5, 13, 9, 4, 14, x + 3))


def mouth_foam(p):
    """A strip of white 4 mm Plastazote, 7.4 mm wide, cut long and gently curved."""
    cl = [(40 * math.sin(math.radians(a)), 18 - 18 * math.cos(math.radians(a))) for a in range(-60, 61, 6)]
    strip = p.ribbon(cl, [7.4] * len(cl))
    p.prism(strip, 0, 4, FOAM, FOAM_SIDE, detail=lambda: foam_dots(p, -30, 2, 60, 10, 4, 30, 7))


def body_foam(p):
    """A sheet of white 4 mm Plastazote, cut from the 224.8 x 114.3 mm template; one corner
    lifts to show it is soft sheet."""
    def top():
        r = 5
        for i in range(90):
            r = (r * 1103515245 + 12345) % 2147483648
            x = 6 + (r % 1000) / 1000 * 200
            r = (r * 1103515245 + 12345) % 2147483648
            y = 6 + (r % 1000) / 1000 * 100
            p.flat(circle(x, y, .9 + (i % 3) * .35, 12), 4, '#e2dfd5', stroke='none')
    sheet = [(0, 1.5), (1.5, 0), (224.8, 0), (224.8, 90), (200.8, 114.3), (1.5, 114.3), (0, 112.8)]
    p.prism(sheet, 0, 4, FOAM, FOAM_SIDE, detail=top)
    p.prism([(200.8, 114.3), (224.8, 90), (216, 102)], 4, 14, '#e9e6dd', '#d2cec2')


def wire_hank(p, cx, cy, color, loops=5, rx=26, ry=15, d=2.4, tail=1):
    """A loose hank of insulated wire: offset loops, a paper band, one free end."""
    for k in range(loops):
        a0, ox, oy = k * 23, (k - 2) * 1.6, (k % 2) * 1.4 - .7
        lp = [(cx + ox + (rx - k * .9) * math.cos(math.radians(a + a0)), cy + oy + (ry - k * .7) * math.sin(math.radians(a + a0))) for a in range(0, 361, 15)]
        p.wire(lp, color, d)
    end = (cx + rx * math.cos(math.radians(40)), cy + ry * math.sin(math.radians(40)))
    p.wire([end, (end[0] + 10, end[1] + 6 * tail), (end[0] + 22, end[1] + 4 * tail)], color, d)
    p.wire([(end[0] + 22, end[1] + 4 * tail), (end[0] + 26, end[1] + 3.6 * tail)], '#c9cdd2', d * .55)
    p.prism(rrect(cx - rx - 2.5, cy - 4, 7, 8, 1), d, d + .8, '#e8e4d6', '#c3bdab')


def wire_18awg(p):
    """18 AWG stranded silicone wire, a red and a black hank."""
    wire_hank(p, 0, 0, RED_W)
    wire_hank(p, 6, 36, BLACK_W, tail=-1)


def wire_22awg(p):
    """Adafruit 3111: six 22 AWG stranded hook-up wire spools in their open box."""
    kraft, kraft_side = '#caa878', '#a3825a'
    cols = ('#3b6fc1', '#f2f2ee', '#2f9a57', '#ecc93a', RED_W, BLACK_W)
    p.prism(rrect(0, 0, 60, 78, 1), 0, 4, kraft, kraft_side)
    for i, col in enumerate(cols):
        y = 9 + i * 11.2
        cable(p, [(39, y + 2), (55, y + 1), (68, y + 3), (78, y + 7)], (col,), 1.5, strip=2)
        p.rod(12, 48, y, 4.8, col, za=5.5, face=None, tip='round', hi=.4)
        p.rod(8, 12, y, 5.4, '#2d2e33', za=5.5, face=lambda x, c, e, h: p.flat(ellipse(x, c, e * .3, h * .3, 20), 0, '#151619', stroke='none'), tip='round')
        p.rod(48, 51, y, 5.4, '#2d2e33', za=5.5, face=None, tip='round')
    p.prism(rrect(0, 72, 60, 6, .6), 0, 12, kraft, kraft_side)


def cable_ties(p):
    """2.5 mm nylon cable ties, about 100 mm long: a few loose and one closed."""
    nat, nat_side = '#f1eee4', '#cfc9b8'
    for i in range(5):
        y = i * 6.5
        p.prism(rrect(0, y, 100, 2.5, .6), 0, 1, nat, nat_side,
                detail=lambda y=y: [p.line([(20 + k * 3.2, y + .5), (20 + k * 3.2, y + 2)], 1, '#d6d0c0', .8) for k in range(24)])
        p.prism(rrect(-4.5, y - .7, 5, 3.9, .5), 0, 2.4, nat, nat_side,
                detail=lambda y=y: p.flat(rrect(-3.2, y + .2, 2.4, 2.1, .2), 2.4, '#a7a08e', op=.6))
    ring = circle(60, 52, 13, 60)
    p.prism(p.ribbon(ring + ring[:1], [2.5] * 61), 0, 1, nat, nat_side)
    p.prism(rrect(44.5, 49.5, 4.5, 5, .5), 0, 2.4, nat, nat_side)


def magnets(p):
    """3/16 x 1/16 inch (4.76 x 1.59 mm) nickel-plated disc magnets: a stack of three and one
    lying flat beside it."""
    ni, ni_side = '#d3d8dd', '#8e969e'
    def face(x, y, z):
        p.flat(circle(x, y, 1.9, 36), z, 'none', '#aab2ba', 1, .9)
        p.line([(x - 1.4, y + .5), (x - .3, y - 1.3)], z, '#f7f9fb', 1.6)
    for k in range(3):
        p.prism(circle(0, 0, 2.38, 40), k * 1.59, (k + 1) * 1.59, ni, ni_side,
                detail=(lambda: face(0, 0, 4.77)) if k == 2 else None)
    p.prism(circle(8, 1.5, 2.38, 40), 0, 1.59, ni, ni_side, detail=lambda: face(8, 1.5, 1.59))


def epoxy(p):
    """Two-part epoxy in a dual syringe: resin and hardener side by side, plunger cap and nozzle cap."""
    for yc, fill in ((0, '#f1e6c2'), (5.6, '#e7c98a')):
        p.rod(18, 84, yc, 2.6, '#eef3f6', za=3, face=None, tip='round', hi=.7)
        p.clipped(p.last_clip, [([(30, yc - 6), (84, yc - 6), (84, yc + 6), (30, yc + 6)], fill)])
        for x in range(34, 82, 8):
            p.line([(x, yc - 2.4 - 3 * K), (x, yc - 1.2 - 3 * K)], 0, '#7d8790', .9)
    p.prism(rrect(84, -3.4, 5, 12.6, .8), 0, 6, '#dfe3e7', '#aeb6bd')
    p.prism(rrect(89, 1.4, 9, 2.8, .6), 1.5, 4.5, '#dfe3e7', '#aeb6bd')
    p.prism(rrect(97, 1.1, 5, 3.4, 1.2), 1.2, 4.8, '#2f73c8', '#1f4f8c')
    p.prism(rrect(4, -3.6, 14, 13, 1.6), 0, 6.4, '#2f73c8', '#1f4f8c')
    p.prism(rrect(0, -2.4, 4.5, 10.6, 1), .6, 5.8, '#2f73c8', '#1f4f8c')


def mounting_tape(p):
    """Generic double-sided tape roll and cut piece, not a qualified product profile."""
    p.prism(circle(20, 20, 20), 0, 8, '#454651', '#292a31',
            detail=lambda: p.hole(20, 20, 11, 8))
    p.prism(rrect(47, 17, 25, 18, .5), 0, 1, '#454651', '#292a31')
    p.prism([(47,17),(72,17),(72,26),(47,24)], 1, 2, '#eddcc0', '#d1b98e')


def adhesive_tie_square(p):
    """Nominal one-inch square; generic slot construction, not a selected model."""
    p.prism(rrect(0, 0, 25.4, 25.4, 1), 0, 1, '#d8c5a3', '#ad9673')
    p.prism(rrect(0, 0, 25.4, 25.4, 1), 1, 2, '#f0ede7', '#c4c2bb')
    p.prism(rrect(7, 7, 11.4, 11.4, 1), 2, 6, '#f0ede7', '#b9b6b0')
    p.flat(rrect(9, 8, 7.4, 2.7, .4), 6, '#41414a', stroke=INK)
    p.flat(rrect(9, 14.7, 7.4, 2.7, .4), 6, '#41414a', stroke=INK)
    p.text(12.7, 31, 0, '1 inch', 3.6, INK)


def ca_glue(p):
    """Unbranded cyanoacrylate bottle; not the two-part epoxy used elsewhere."""
    p.prism(rrect(0, 12, 22, 35, 3), 0, 8, '#f0ede7', '#c5c1b9')
    p.prism(rrect(7, 2, 8, 12, 1), 0, 8, '#7661a7', '#514277')
    p.prism([(9,2),(13,2),(12,-9),(10,-9)], 0, 8, '#f0ede7', '#c5c1b9')
    p.text(11, 32, 8, 'CA', 7, '#514277')


def foam_lining(p):
    """Nonconductive closed-cell foam offcuts for the audio lid lining."""
    p.prism(rrect(0, 0, 44, 28, .6), 0, 1, '#3a3c42', '#222327',
            detail=lambda: foam_dots_dark(p, 1, 1, 42, 26, 1))
    p.text(22, 14, 1, '1 mm', 4.2, '#c9ccd2')


def foam_dots_dark(p, x0, y0, w, h, z, seed=2):
    r = seed
    for i in range(30):
        r = (r * 1103515245 + 12345) % 2147483648
        x = x0 + (r % 1000) / 1000 * w
        r = (r * 1103515245 + 12345) % 2147483648
        y = y0 + (r % 1000) / 1000 * h
        p.flat(circle(x, y, .22, 10), z, '#4c4f56', stroke='none')



def pla_spool(p):
    """A 1.75 mm PLA filament spool standing on its rim; any colour you like."""
    fil = '#4b57b9'
    # Draw the rear flange first, so it cannot hide the wound filament.
    p.rod(62, 66, 0, 100, '#2d2e33', za=100, face=None, tip='round')
    t, b = p.band(0, 100, 88)
    p.wire([(50, t + 8), (76, t - 5), (92, t + 8), (91, t + 30)], fil, 1.75, z=0)
    p.rod(16, 62, 0, 88, fil, za=100, face=None, tip='round', hi=.4)
    t, b = p.band(0, 100, 88)
    for k in range(1, 12):
        p.line([(16 + k * 4, t + 4), (16 + k * 4, b - 4)], 0, dim(fil, .25), .8)
    def flange(x, c, e, h):
        p.flat(ellipse(x, c, e * .92, h * .92, 60), 0, '#3a3c42', stroke='none')
        for k in range(6):
            a = math.radians(k * 60 + 30)
            cx_, cy_ = x + e * .58 * math.cos(a), c + h * .58 * math.sin(a)
            p.flat(ellipse(cx_, cy_, e * .2, h * .2, 30), 0, fil, stroke=INK, sw=1, op=.5)
        p.flat(ellipse(x, c, e * .3, h * .3, 40), 0, '#4a4c52', stroke='none')
        p.flat(ellipse(x, c, e * .2, h * .2, 40), 0, BG, stroke=INK, sw=1, op=.6)
    p.rod(12, 16, 0, 100, '#2d2e33', za=100, face=flange, tip='round', ef=.34)


def solder_kit(p):
    """Solder on a small spool, a flux pen and a sheet of wire labels."""
    tin = '#c9ced4'
    p.wire([(28, 4), (40, 0), (52, 4), (60, 12)], tin, 1.0, z=.5)
    p.rod(4, 26, 8, 12, tin, za=14, face=None, tip='round', hi=.6)
    t, b = p.band(8, 14, 12)
    for k in range(1, 11):
        p.line([(4 + k * 2, t + 1), (4 + k * 2, b - 1)], 0, '#9aa2aa', .7)
    p.rod(26, 28, 8, 14, '#2f73c8', za=14, face=None, tip='round')
    p.rod(2, 4, 8, 14, '#2f73c8', za=14, face=lambda x, c, e, h: p.flat(ellipse(x, c, e * .35, h * .35, 30), 0, '#1f4f8c', stroke='none'), tip='round')
    # flux pen
    p.rod(4, 70, 40, 5, '#f2f2ee', face=None, tip='round', hi=.5)
    p.clipped(p.last_clip, [([(24, 30), (56, 30), (56, 50), (24, 50)], '#e5aa2c')])
    p.text(40, 40 - 5 * K + 1.2, 0, 'FLUX', 3.4, '#2b2c30')
    p.rod(-6, 4.5, 40, 4.2, '#2b2c30', za=5, face=None, tip='round')
    # wire labels
    def labels():
        for i in range(4):
            for j in range(3):
                p.flat(rrect(84 + j * 13, 6 + i * 11, 11, 8, .6), .3, '#ffffff', stroke='#b8bec5', sw=1, op=1)
                p.line([(86 + j * 13, 10 + i * 11), (92 + j * 13, 10 + i * 11)], .3, '#9aa2aa', 1)
    p.prism(rrect(80, 2, 44, 50, 1), 0, .3, '#e9ecef', '#c3c9cf', detail=labels)




# ------------------------------------------------------------------ tools
def grips(p, x0, color, under, spread=1.0, length=88, thick=8.5, y0=0):
    """Two plier handles from a pivot at (x0, 0), opening to the right."""
    steel = '#4b5058'
    for sgn in (1, -1):
        cl = [(x0 + u * length, y0 + sgn * (3.2 + u ** 1.1 * 13 * spread)) for u in (0, .14, .34, .59, .82, 1)]
        p.prism(p.ribbon(cl[:3], [5, 5, 4.6]), 1.5, 5, steel, dim(steel, .3))
        p.prism(p.ribbon(cl[1:], [9.4, 10.6, 11.2, 11.2, 10.6], round_end=True), 0, thick, color, under,
                detail=lambda g=cl: p.spline([(x, y - 2.1) for x, y in g[2:6]], thick, lit(color, .4), 1.5 * p.s, extra=' stroke-opacity=".7"'))


def pivot(p, x, z=5, y=0):
    p.flat(circle(x, y, 4.2, 36), z, '#5c626b', op=.8)
    p.flat(circle(x, y, 2.5, 30), z, '#b1b8bf', op=.8)
    p.flat(circle(x, y, 1.2, 20), z, 'none', '#6b727b', .9, 1)


def soldering_station(p):
    """A soldering iron resting in its stand (coil holder, brass wool and sponge), and a small
    fume extractor with its filter facing the iron."""
    base, base_side = '#3a3c42', '#222327'
    def tray():
        p.flat(rrect(6, 8, 42, 30, 3), 7, '#26272b', op=.8)
        p.flat(rrect(9, 11, 18, 24, 2), 7, '#e9c94a', op=.6)
        for i in range(3):
            for j in range(4):
                p.flat(circle(12.5 + i * 5.5, 14.5 + j * 5.6, .9, 12), 7, '#caa634', stroke='none')
        p.flat(circle(37.5, 23, 8, 36), 7, '#c9a24c', op=.6)
        for a in range(0, 360, 30):
            p.line([(37.5 + 2.2 * math.cos(math.radians(a)), 23 + 2.2 * math.sin(math.radians(a))),
                    (37.5 + 7 * math.cos(math.radians(a + 70)), 23 + 7 * math.sin(math.radians(a + 70)))], 7, '#9a7a30', 1)
    p.prism(rrect(0, 0, 110, 46, 6), 0, 7, base, base_side, detail=tray)
    p.prism(rrect(72, 17, 14, 12, 2), 7, 22, '#50535a', '#2e3034')
    # Match the projected handle axis: y23 at z30, not the bench plane.
    p.wire([(198, 23 - 30 * K), (213, 18), (219, 39), (203, 49)], '#2a2b2f', 4, z=0)
    # coil holder, widening toward the handle
    for k in range(10):
        x = 58 + k * 4.2
        r = 7 + k * .75
        t, b = p.band(23, 30, r)
        p.add(f'<path d="M{f(p.P(x, t)[0])} {f(p.P(x, t)[1])}Q{f(p.P(x + 3.6, (t + b) / 2)[0])} {f(p.P(x + 3.6, (t + b) / 2)[1])} {f(p.P(x, b)[0])} {f(p.P(x, b)[1])}" fill="none" stroke="{INK}" stroke-width="{f(.9 * p.s + 2)}" stroke-linecap="round"/>'
              f'<path d="M{f(p.P(x, t)[0])} {f(p.P(x, t)[1])}Q{f(p.P(x + 3.6, (t + b) / 2)[0])} {f(p.P(x + 3.6, (t + b) / 2)[1])} {f(p.P(x, b)[0])} {f(p.P(x, b)[1])}" fill="none" stroke="#c4cad0" stroke-width="{f(.9 * p.s)}" stroke-linecap="round"/>')
    # the iron: tip and barrel inside the coil, grip and handle out the back
    p.rod(188, 201, 23, 3.8, '#26272b', za=30, face=None, tip='round')
    p.rod(140, 190, 23, 7, '#2b2c30', za=30, face=None, tip='round', hi=.35)
    p.rod(108, 142, 23, 8.5, '#2d6bc4', za=30, face=None, tip='round', hi=.5)
    t, b = p.band(23, 30, 8.5)
    for x in range(111, 140, 3):
        p.line([(x, t + 1.5), (x, b - 1.5)], 0, '#1f4f8c', 1)
    p.rod(60, 108, 23, 3.4, '#c4cad0', za=30, face=None, tip='round')
    p.rod(44, 60, 23, 1.6, '#9aa1a8', za=30, face=None, tip='chamfer')
    # fume extractor
    def grille(F):
        cz = 24
        for r in (20, 15, 10, 5):
            ring = [F(r * math.cos(t), cz + r * math.sin(t)) for t in [i * math.pi / 24 for i in range(48)]]
            p.add(f'<polygon points="{pts(ring)}" fill="{"#4a4c53" if r == 20 else "none"}" stroke="#15161a" stroke-width="1.3"/>')
        for k in range(8):
            a = k * math.pi / 4
            a0, a1 = F(2 * math.cos(a), cz + 2 * math.sin(a)), F(20 * math.cos(a), cz + 20 * math.sin(a))
            p.add(f'<line x1="{f(a0[0])}" y1="{f(a0[1])}" x2="{f(a1[0])}" y2="{f(a1[1])}" stroke="#15161a" stroke-width="1.3"/>')
    conn(p, 196, -30, -90, 30, 52, 50, '#2e3035', '#393b41', r=4, face=grille)


def multimeter(p):
    """A digital multimeter (Adafruit 2034 style) in its blue holster, with red and black leads."""
    blue, blue_side = '#2f8fd8', '#1f63a0'
    for x, col in ((-30, BLACK_W), (112, RED_W)):
        p.prism(rrect(x - 3.2, 70, 6.4, 80, 3), 0, 6, col, dim(col, .35))
        p.prism(rrect(x - 4.5, 128, 9, 5, 1.5), 0, 7, col, dim(col, .35))
        p.prism(rrect(x - .7, 44, 1.4, 27, .6), 2.5, 3.5, '#c9ced3', '#8f969d')
    def face():
        p.flat(rrect(10, 10, 66, 170, 6), 28, '#dfe3e7', op=.8)
        p.flat(rrect(16, 16, 54, 34, 3), 28, '#9fb09a', op=.8)
        p.text(43, 42, 28, '0.00', 18, '#2b3b2c')
        c = (43, 106)
        for k in range(0, 360, 18):
            a = math.radians(k)
            p.line([(c[0] + 24 * math.cos(a), c[1] + 24 * math.sin(a)), (c[0] + 27 * math.cos(a), c[1] + 27 * math.sin(a))], 28, '#6d747c', 1.4)
        for x, ring, label in ((22, RED_W, 'A'), (36, RED_W, 'mA'), (50, BLACK_W, 'COM'), (64, RED_W, 'VΩ')):
            p.flat(circle(x, 167, 4.6, 28), 28, ring, op=.8)
            p.flat(circle(x, 167, 2.4, 20), 28, '#101113', op=.8)
            p.text(x, 157, 28, label, 3.2, '#2b3036')
    p.prism(rrect(0, 0, 86, 190, 12), 0, 28, blue, blue_side, detail=face)
    p.prism(circle(43, 106, 19, 48), 28, 33, '#f4f4f1', '#c9c9c4',
            detail=lambda: p.prism(rrect(40, 85, 6, 42, 3), 33, 37, '#f4f4f1', '#c9c9c4',
                                   detail=lambda: p.line([(43, 88), (43, 96)], 37, '#2b2c30', 2.2)))
    # Leads leave seated right-angle banana plugs in COM and V/ohms.
    for x, col, tail in ((50, BLACK_W, [(45, 182), (26, 198), (0, 202), (-28, 186), (-30, 150 - 6*K)]),
                         (64, RED_W, [(68, 184), (88, 201), (111, 183), (112, 150 - 6*K)])):
        p.wire([(x, 167 - 28*K)] + tail, col, 2.8, z=0)
        p.prism(rrect(x - 3, 164, 6, 10, 2), 28, 32, col, dim(col, .3))


def wire_stripper(p):
    """A plier-type wire stripper: long flat jaws with graded stripping holes, 18-28 AWG."""
    steel = '#4b5058'
    grips(p, 58, '#e6b91f', '#26272b')
    def jaws():
        p.line([(1, 0), (56, 0)], 5, '#17191c', 1.5)
        sizes = (('28', .45), ('26', .5), ('24', .6), ('22', .72), ('20', .88), ('18', 1.05))
        for i, (lab, r) in enumerate(sizes):
            x = 12 + i * 6.2
            p.flat(circle(x, 0, r + .3, 20), 5, '#1a1c20', op=.9)
            p.text(x, -3.4, 5, lab, 2.2, '#d7dce1')
        p.spline([(2, -2.2), (30, -5.8), (54, -6.5)], 5, '#9aa2ab', 1.4)
        pivot(p, 62)
    p.prism([(0, -1.6), (12, -4.2), (40, -6.8), (60, -7.8), (66, -6), (68, 0), (66, 6), (60, 7.8), (40, 6.8), (12, 4.2), (0, 1.6)],
            1.5, 5, steel, dim(steel, .35), detail=jaws)


def drivers_and_pliers(p):
    """A precision screwdriver, a 1.5 mm L-key (short leg about 13 mm) and fine pliers."""
    # screwdriver
    p.rod(0, 70, 0, 4.6, '#9aa2aa', face=None, tip='round', hi=.6)
    t, b = p.band(0, 4.6, 4.6)
    for x in range(6, 60, 2):
        p.line([(x, t + .8), (x + 1, b - .8)], 0, '#6f777f', .9)
    p.rod(-6, .5, 0, 4.4, '#2d6bc4', za=4.6, face=None, tip='round')
    p.rod(70, 96, 0, 1.2, '#c9ced3', za=4.6, face=None, tip='flat')
    # Flattened blade continues from the shaft; this is a slotted driver.
    p.prism([(95,-1.2),(103,-1.6),(105,-1.6),(105,1.6),(103,1.6),(95,1.2)], 4.1, 4.9, '#c9ced3', '#7d8791')
    # L-key
    key = [(0, 22), (60, 22), (60, 35), (58.2, 35), (58.2, 23.8), (0, 23.8)]
    p.prism(key, 0, 1.5, '#3b3e44', '#1f2124')
    # fine pliers: long thin jaws
    steel = '#4b5058'
    Y = 62
    grips(p, 68, '#3aa05c', '#1f2124', spread=.8, length=70, y0=Y)
    head = [(30, -.4), (46, -1.8), (60, -3.8), (72, -3.5), (74, 0), (72, 3.5), (60, 3.8), (46, 1.8), (30, .4)]
    p.prism([(x, y + Y) for x, y in head], 1.5, 5, steel, dim(steel, .35),
            detail=lambda: [p.line([(31, Y), (60, Y)], 5, '#17191c', 1.2), pivot(p, 66, 5, Y)])


def caliper(p):
    """A digital caliper and a capped fine-point marker for measurements and cut lines."""
    st, st_side = '#c9ced4', '#8f969d'
    def beam():
        for i in range(0, 140, 2):
            p.line([(14 + i, 1), (14 + i, 3.2 if i % 10 == 0 else 2.2)], 3, '#5d646c', .8)
    p.prism(rrect(0, 0, 160, 16, 1), 0, 3, st, st_side, detail=beam)
    p.prism([(0, 16), (12, 16), (12, 38), (6, 52), (2, 52), (0, 44)], 0, 3, st, st_side)
    p.prism([(4, 0), (12, 0), (12, -8), (8, -14), (6, -14), (4, -8)], 0, 3, st, st_side)
    x = 42
    p.prism([(x - 12, 16), (x, 16), (x, 38), (x - 6, 52), (x - 10, 52), (x - 12, 44)], 3, 6, st, st_side)
    p.prism([(x - 8, 0), (x, 0), (x, -8), (x - 4, -14), (x - 6, -14), (x - 8, -8)], 3, 6, st, st_side)
    def head():
        p.flat(rrect(x + 6, 4, 34, 13, 1.5), 12, '#9fb09a', op=.8)
        p.text(x + 23, 14.2, 12, '0.00', 9, '#2b3b2c')
        for i, c in enumerate(('#d23a2e', '#2b2c30', '#2b2c30')):
            p.flat(circle(x + 10 + i * 12, 23, 2.6, 24), 12, c, op=.8)
    p.prism(rrect(x - 2, -2, 50, 30, 3), 3, 12, '#34363c', '#1f2124', detail=head)
    p.prism(rrect(x + 26, 29.5, 10, 8, 2), 3, 9, '#c9ced4', '#8f969d')
    p.prism(rrect(160, 6.5, 14, 3, .6), 0, 2, st, st_side)
    # Capped marker: cap meets the barrel, with a clip attached to the cap.
    p.rod(35, 132, 76, 4.5, '#34363c', za=5, face=None, tip='round')
    p.rod(12, 37, 76, 5, '#22242a', za=5, face=None, tip='round')
    p.prism(rrect(15, 72, 19, 2, .6), 9, 10.5, '#606773', '#30343c')


def deburr_kit(p):
    """Deburring tool, file, glasses, craft knife and scissors on a cutting mat."""
    def grid():
        for i in range(0, 161, 10):
            p.line([(i, 0), (i, 180)], 1, '#3b8f68', .9 if i % 50 else 1.6)
        for j in range(0, 181, 10):
            p.line([(0, j), (160, j)], 1, '#3b8f68', .9 if j % 50 else 1.6)
    p.prism(rrect(0, 0, 160, 180, 2), 0, 1, '#2f7a57', '#1f5a3f', detail=grid)
    # deburring tool
    p.rod(14, 86, 22, 6, '#e0572e', za=7, face=None, tip='round', hi=.5)
    p.rod(86, 96, 22, 3, '#c9ced4', za=7, face=None, tip='round')
    p.wire([(96, 22 - 7 * K), (110, 22 - 7 * K), (116, 17 - 7 * K), (113, 13 - 7 * K)], '#c9ced4', 1.8, z=0)
    # needle file
    p.rod(14, 60, 52, 4.5, '#2b2c30', za=5, face=None, tip='round', hi=.3)
    p.prism([(60, 50), (130, 51), (136, 52), (130, 53), (60, 54)], 3.5, 5, '#9aa2aa', '#6f777f',
            detail=lambda: [p.line([(62 + k * 3, 50.5), (63.5 + k * 3, 53.5)], 5, '#6f777f', .8) for k in range(22)])
    # safety glasses, folded
    def lens(cx):
        return [(cx + 17 * math.cos(t) * (1 - .12 * math.sin(t)), 84 + 11 * math.sin(t)) for t in [i * math.pi / 20 for i in range(40)]]
    # Continuous rims, nose bridge and folded temples keep the lenses attached.
    p.wire([(41,81),(33,67),(64,67)], '#3a3c42', 2.3, z=3)
    p.wire([(119,81),(129,67),(99,67)], '#3a3c42', 2.3, z=3)
    for cx in (58, 102):
        p.prism(lens(cx), 1, 3, '#dbe9f1', '#a9c0cf',
                detail=lambda cx=cx: p.line([(cx - 8, 90), (cx + 2, 78)], 3, '#ffffff', 2.4, extra=' stroke-opacity=".8"'))
        rim=lens(cx)
        p.line(rim+[rim[0]], 3, '#3a3c42', 2.2)
    p.wire([(74,81),(80,78),(86,81)], '#3a3c42', 2.3, z=3)
    # Craft knife: the blade heel is held inside the metal collet.
    p.rod(14, 87, 119, 4, '#b8c0c8', za=5, face=None, tip='round')
    p.rod(86, 98, 119, 4.4, '#707983', za=5, face=None, tip='flat')
    p.prism([(96,116),(126,116),(100,124),(96,124)], 4.5, 5.2, '#d4d9de', '#929ca5')
    # Closed scissors: two blades share the pivot and continue into the handles.
    for dy, z in [(-1.5,3),(1.5,4)]:
        p.prism([(51,151+dy),(69,148+dy),(137,150+dy),(141,151+dy),(69,154+dy),(51,155+dy)], z, z+1, '#c2c9d1', '#7d8791')
    p.flat(circle(70,151,2.8,24),5.2,'#59636e')
    for cy in (141,166):
        # Colored rims leave the finger holes open to the mat below.
        ring=ellipse(37,cy,17,9,40)
        p.line(ring+[ring[0]],4,'#244b79',4)
        p.line([(51,cy),(61,153)],4,'#244b79',4)


def pin_vise(p):
    """A pin vise (hand drill) with its collet, and a 2.2 mm twist drill bit."""
    p.rod(20, 92, 0, 5.5, '#b9c0c7', face=None, tip='round', hi=.6)
    t, b = p.band(0, 5.5, 5.5)
    for x in range(24, 88, 2):
        p.line([(x, t + .8), (x + 1, b - .8)], 0, '#7c848c', .9)
    p.rod(92, 104, 0, 7, '#c9ced4', za=5.5, face=None, tip='round')
    p.rod(8, 20, 0, 4.2, '#c9ced4', za=5.5, face=None, tip='round')
    p.rod(0, 8.5, 0, 2.4, '#d5dade', za=5.5, face=None, tip='chamfer')
    # drill bit
    p.rod(20, 70, 22, 1.1, '#9aa2aa', face=None, tip='chamfer', hi=.7)
    t, b = p.band(22, 1.1, 1.1)
    for x in [38 + k * 2.4 for k in range(13)]:
        p.line([(x, t + .1), (x + 1.4, b - .1)], 0, '#5f666e', .9)
    p.text(30, 29, 0, '2.2 mm', 4, '#4f6273')


def heat_gun(p):
    """A heat gun lying on its side: nozzle to the left, pistol grip and trigger below."""
    body, body_side = '#34363c', '#1f2124'
    acc, acc_side = '#e0782a', '#a4531a'
    p.prism([(62, 26), (84, 26), (96, 78), (92, 86), (72, 86), (66, 70)], 0, 34, acc, acc_side)
    p.prism([(60, 30), (68, 30), (72, 44), (64, 44)], 6, 28, '#2b2c30', '#18191b')
    p.prism(rrect(40, -4, 80, 34, 12), 0, 44, body, body_side,
            detail=lambda: [p.line([(104 + k * 3, 2), (104 + k * 3, 24)], 44, '#1a1b1e', 1.6) for k in range(5)])
    p.rod(0, 42, 13, 9, '#c9ced4', za=22, face=lambda x, c, e, h: p.flat(ellipse(x, c, e * .7, h * .7, 30), 0, '#3b3e44', stroke='none'), tip='round')
    cable(p, [(90, 86), (96, 104), (118, 110), (140, 104)], ('#2a2b2f',), 5)


def laptop_reader(p):
    """A laptop for writing the card, and a USB microSD reader with the card in it."""
    def deck():
        for r in range(5):
            for c in range(13):
                p.flat(rrect(18 + c * 20, 14 + r * 17, 17, 14, 2), 14, '#2a2b30', op=.2)
        p.flat(rrect(100, 106, 100, 58, 4), 14, '#b9bfc6', op=.4)
    p.prism(rrect(0, 0, 300, 180, 8), 0, 14, '#c9ced4', '#9aa2aa', detail=deck)
    def screen(F):
        fpoly(p, F, frect(-138, 14, 276, 170), '#1f2328', op=.9)
        fpoly(p, F, frect(-132, 20, 264, 158), '#3d6fb8', op=.4)
        fpoly(p, F, frect(-110, 60, 120, 90), '#eef2f5', op=.3)
        fpoly(p, F, frect(-104, 132, 108, 10), '#2f9a53', stroke='none')
    conn(p, 150, -6, -90, 8, 300, 196, '#c9ced4', '#aeb5bc', r=6, face=screen)
    # reader, drawn larger than life so the slot and card show
    p.prism(rrect(236, 190, 64, 30, 4), 0, 12, '#2b2c30', '#18191b',
            detail=lambda: p.flat(rrect(270, 197, 22, 16, 2), 12, '#3a3c42', op=.6))
    p.prism(rrect(210, 194, 27, 22, 1.5), 3.5, 11, CHROME, dim(CHROME, .3),
            detail=lambda: [p.flat(rrect(214, 197 + dy, 4, 4, .4), 11, '#7d858d', op=.6) for dy in (1, 11)])
    p.prism([(290, 198), (312, 198), (312, 212), (290, 212)], 4, 5.5, '#35373d', '#18191c',
            detail=lambda: p.text(302, 207, 5.5, '32GB', 5, '#ffffff'))



# ================================================================= registry
ITEMS = {
    'E09': (pi3a, 'Raspberry Pi 3 Model A+', None, None),
    'E16': (speaker_pair, 'Adafruit 1669 enclosed speaker pair', None, None),
    'M2x6': (screw(2, 6), 'M2 x 6 socket-head screw', FS, FO),
    'M2x8': (m2x8, 'M2 x 8 socket-head and button-head screws', FS, FO),
    'M2x10': (screw(2, 10), 'M2 x 10 socket-head screw', FS, FO),
    'M2x12': (screw(2, 12), 'M2 x 12 socket-head screw', FS, FO),
    'M3x6': (screw(3, 6), 'M3 x 6 socket-head screw', FS, FO),
    'M3x8': (screw(3, 8), 'M3 x 8 socket-head screw', FS, FO),
    'M3x10': (screw(3, 10), 'M3 x 10 socket-head screw', FS, FO),
    'M3x12': (screw(3, 12), 'M3 x 12 socket-head screw', FS, FO),
    'M3x14': (screw(3, 14), 'M3 x 14 socket-head screw', FS, FO),
    'M3x16': (screw(3, 16), 'M3 x 16 socket-head screw', FS, FO),
    'M3x18': (screw(3, 18), 'M3 x 18 socket-head screw', FS, FO),
    'M3x20': (screw(3, 20), 'M3 x 20 socket-head screw', FS, FO),
    'M3x10CS': (screw(3, 10, 'cs'), 'M3 x 10 countersunk screw', FS, FO),
    'CENTER': (center_screw, 'Supplied servo centre screw', FS, FO),
    'N2': (nut(2), 'M2 hex nut', NS, FC),
    'N3': (nut(3), 'M3 hex nut', NS, FC),
    'W2': (washer(4.37, 2.31, .25), 'M2 metal washer', NS, FC),
    'W3': (washer(7.01, 3.2, .53), 'M3 washer', NS, FC),
    'T01': (flush_cutters, 'Flush cutters', None, None),
    'C12': (heat_shrink, 'Heat-shrink tubing', None, None),
    'E03': (neopixel_eye, 'Adafruit 5975 NeoPixel eye board, both sides', None, None),
    'E04': (neopixel_stick, 'Adafruit 1426 NeoPixel stick', None, None),
    'E15': (pixel_shifter, 'Adafruit 6066 Pixel Shifter', None, None),
    'E14': (usb_audio, 'Waveshare USB TO AUDIO module', None, None),
    'E13': (microsd, '32 GB microSD card', None, None),
    'E08': (capacitor, 'Panasonic EEU-FR1A102 capacitor', None, None),
    'R1': (resistor(('#7a4a2a', '#1f1f22', '#d0342c', '#c9a13e')), '1 kilohm resistor', None, None),
    'R2': (resistor(('#e07b22', '#e07b22', '#7a4a2a', '#c9a13e')), '330 ohm resistor', None, None),
    'F2': (fuse('T1A 250V'), '1 A time-delay fuse', None, None),
    'E10': (jst_sm_pair, 'Adafruit 1663 JST-SM three-pin plug and receptacle', None, None),
    'E11': (jst_eye_lead, 'Adafruit 6406 JST-SH plug-to-plug cable, 200 mm', None, None),
    'E12': (jst_link, 'Adafruit 6404 JST-SH plug-to-plug cable', None, None),
    'E22': (usb_c_panel_cable, 'Adafruit 4056 panel USB-C to micro-B cable', None, None),
    'E23': (usb_extension, 'USB-A extension cable', None, None),
    'E24': (jumper_leads, 'GPIO jumper leads', None, None),
    'E05': (pebble_strand, 'Adafruit 6026 NeoPixel Pebble strand', None, None),
    'E20': (power_supply, 'Mean Well GST40A05-P1J 5 V supply', None, None),
    'E21': (mains_cord, 'US mains cord, NEMA 5-15P to IEC C13', None, None),
    'E01': (servo, 'Kitronik 25105 clippable servo', None, None),
    'E02': (horn, 'Supplied round disk servo horn', None, None),
    'E06': (wago, 'WAGO 221-415 lever connector', None, None),
    'E07': (fuse_holder, 'Schurter FDI in-line fuse holder with leads', None, None),
    'E17': (button, 'Adafruit 1479 illuminated pushbutton', None, None),
    'E18': (power_jack, 'Switchcraft 721AU solder-lug power jack', None, None),
    'E25': (rubber_feet, 'Adhesive rubber feet', None, None),
    'C01': (clear_film, 'Clear eye film', None, None),
    'C02': (eye_foam, 'Eye diffuser foam patches', None, None),
    'C03': (mouth_foam, 'Mouth diffuser foam strip', None, None),
    'C04': (body_foam, 'Body diffuser foam sheet', None, None),
    'C05': (wire_18awg, '18 AWG red and black wire', None, None),
    'C06': (wire_22awg, '22 AWG hook-up wire spools', None, None),
    'C07': (cable_ties, '2.5 mm cable ties', None, None),
    'C08': (magnets, 'Disc magnets', None, None),
    'C09': (epoxy, 'Two-part epoxy', None, None),
    'C10': (foam_lining, 'Thin foam lining offcuts', None, None),
    'C13': (pla_spool, 'PLA filament spool', None, None),
    'C14': (solder_kit, 'Solder, flux and wire labels', None, None),
    'C16': (mounting_tape, 'Double-sided mounting tape, generic illustration', None, None),
    'C17': (adhesive_tie_square, 'One-inch adhesive tie mount, generic illustration', None, None),
    'C18': (ca_glue, 'CA glue for nut pockets', None, None),
    'T02': (soldering_station, 'Soldering iron, stand and fume extractor', None, None),
    'T03': (multimeter, 'Digital multimeter with leads', None, None),
    'T04': (wire_stripper, 'Wire stripper', None, None),
    'T05': (drivers_and_pliers, 'Small driver, hex key and fine pliers', None, None),
    'T06': (caliper, 'Digital caliper and marker', None, None),
    'T07': (deburr_kit, 'Cutting and cleanup tools on a mat', None, None),
    'T08': (pin_vise, 'Pin vise and 2.2 mm drill bit', None, None),
    'T09': (heat_gun, 'Heat gun', None, None),
    'T10': (laptop_reader, 'Computer and USB microSD reader', None, None),
}


def workbench(out):
    """Compose existing original tool cartoons without duplicating their drawings."""
    import base64
    body=[]
    for pid,label,x,y in [('T05','Drivers & pliers',0,0),('T04','Wire stripper',280,0),
                          ('T02','Soldering station',0,210),('T03','Multimeter',280,210)]:
        source=(out/(pid+'.svg'))
        if not source.exists():source=OUT/(pid+'.svg')
        encoded=base64.b64encode(source.read_bytes()).decode()
        body.append(f'<image x="{x}" y="{y}" width="280" height="175" href="data:image/svg+xml;base64,{encoded}"/>')
        body.append(f'<text x="{x+140}" y="{y+195}" text-anchor="middle" font-family="{FONT}" font-size="20" fill="{INK}">{escape(label)}</text>')
    (out/'Workbench.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 420" role="img"><title>Drivers, wire stripper, soldering station and multimeter</title><rect width="560" height="420" fill="'+BG+'"/>'+''.join(body)+'</svg>')


def main(args):
    out = OUT
    if args[:1] == ['--out']:
        out, args = Path(args[1]), args[2:]
    out.mkdir(parents=True, exist_ok=True)
    for pid, (draw, title, scale, origin) in ITEMS.items():
        if not args or pid in args:
            (out / f'{pid}.svg').write_text(render(draw, title, scale, origin))
    if not args or 'Workbench' in args:workbench(out)
    print('ok')


if __name__ == '__main__':
    main(sys.argv[1:])
