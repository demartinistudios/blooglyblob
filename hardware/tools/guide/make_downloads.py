#!/usr/bin/env python3
"""Draw the guide's printable templates into hardware/build-guide/src/downloads/.

Rerunnable and byte-stable. Needs rsvg-convert for the PDFs. The outputs are
committed guide source; the build copies them like any other authored file.
The print packages (3MFs and ZIPs) are made at build time by packages.py.
"""
import json, math, os, re, subprocess, tempfile
from consistency import allocation_totals, indexed
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / 'hardware/build-guide/src/downloads'
INK = '#17232b'
FONT = 'Arial, Helvetica, sans-serif'
PDF_TIME = '1790294400'  # 2026-09-25 00:00 UTC, so the PDFs' creation date is fixed


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text(x, y, s, size=3.2, anchor='start', weight='normal', fill=INK):
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{fill}">{esc(s)}</text>')


def svg(w, h, body, title):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}mm" height="{h:g}mm" viewBox="0 0 {w:g} {h:g}">\n'
            f'<title>{esc(title)}</title>\n<rect width="{w:g}" height="{h:g}" fill="white"/>\n'
            f'<g font-family="{FONT}">\n' + '\n'.join(body) + '\n</g>\n</svg>\n')


def scale_bar(x, y, length, label):
    return [f'<path d="M{x} {y}H{x+length}M{x} {y-3}V{y+3}M{x+length} {y-3}V{y+3}" stroke="{INK}" stroke-width="0.35" fill="none"/>',
            text(x + length / 2, y + 7, label, 3, 'middle')]


def write(name, content, folder=OUT):
    (folder / name).write_text(content, encoding='utf-8')


def to_pdf(name, folder=OUT):
    pdf = OUT / name.replace('.svg', '.pdf')
    subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', str(pdf), str(folder / name)], check=True,
                   env=dict(os.environ, SOURCE_DATE_EPOCH=PDF_TIME))


# ---------------------------------------------------------------- eye film
def eye_film():
    w, h = 215.9, 279.4  # US Letter; everything sits inside the A4 printable area too
    b = [text(20, 22, 'BlooglyBlob', 4, weight='bold'),
         text(20, 32, 'Eye film template', 8, weight='bold'),
         text(20, 42, 'Print at 100% (actual size). Turn off Fit, Shrink and Scale to page.', 3.6),
         text(20, 48, 'Check the 50 mm bar and the 20 mm square with a ruler before cutting.', 3.6),
         text(20, 58, 'Cut two windows from clear, flexible film (a transparency sheet works).', 3.6),
         text(20, 64, 'Start with size A. If A is loose in the groove, cut B; if A is tight, cut C.', 3.6),
         text(20, 70, 'Cut on the line, keep the corners smooth, and don’t crease the film.', 3.6)]
    sizes = [('A', 'Start here', 12.6, 8.6, 4.2), ('B', 'If A is loose', 12.7, 8.7, 4.25), ('C', 'If A is tight', 12.5, 8.5, 4.15)]
    for i, (k, note, ww, hh, r) in enumerate(sizes):
        y = 92 + i * 24
        b.append(text(20, y + 1.2, k, 7, weight='bold'))
        for cx in (45, 70):
            b.append(f'<rect x="{cx-ww/2:g}" y="{y-hh/2:g}" width="{ww:g}" height="{hh:g}" rx="{r:g}" ry="{r:g}" fill="none" stroke="black" stroke-width="0.1"/>')
        b.append(text(88, y - 1, f'{k}: {ww:g} × {hh:g} mm, corner radius {r:g} mm', 3.6))
        b.append(text(88, y + 5, note, 3.2, fill='#51606b'))
    b += scale_bar(20, 175, 50, '50 mm')
    b.append(f'<rect x="100" y="165" width="20" height="20" fill="none" stroke="{INK}" stroke-width="0.35"/>')
    b.append(text(126, 176, '20 × 20 mm square', 3.2))
    b.append(text(20, 200, 'Each window sits in the groove behind the goggle’s front lip, with a 14 × 10 mm piece', 3.4))
    b.append(text(20, 206, 'of 4 mm white foam behind it.', 3.4))
    write('eye-film-template.svg', svg(w, h, b, 'BlooglyBlob eye film template: cut two, actual size'))
    to_pdf('eye-film-template.svg')


# ---------------------------------------------------------------- body foam
def body_foam():
    notches = '0,0 0,15.1 1.0009,15.1 1.0009,33.5 0,33.5 0,59.1 1.0009,59.1 1.0009,77.5 0,77.5 0,83.1 1.0009,83.1 1.0009,101.5 0,101.5 0,114.3 224.8227,114.3 224.8227,101.5 223.8218,101.5 223.8218,83.1 224.8227,83.1 224.8227,77.5 223.8218,77.5 223.8218,59.1 224.8227,59.1 224.8227,33.5 223.8218,33.5 223.8218,15.1 224.8227,15.1 224.8227,0'
    b = [text(12, 9, 'BlooglyBlob body foam template', 4.2, weight='bold'),
         text(12, 15, 'Print at 100% (actual size) and check the 50 mm bar. Cut from 4 mm white foam.', 2.9),
         '<g transform="translate(20 20)" stroke-width="0.3">',
         f'<polygon points="{notches}" fill="none" stroke="{INK}"/>']
    for x in (46.5056, 159.9171):
        b.append(f'<rect x="{x:g}" y="11.3" width="18.4" height="36" rx="2" fill="#eee" stroke="{INK}"/>')
        b.append(text(x + 9.2, 31, 'shoulder', 2.6, 'middle'))
    b.append('<path d="M1.0009 24.3H46.5056M178.3171 24.3H223.8218" fill="none" stroke="#c55028" stroke-dasharray="2 1"/>')
    for i, s in enumerate(['FRONT CENTER', '224.8 × 114.3 mm, 4 mm foam',
                           'The two short edges meet at the back with a 2 mm gap.',
                           'Orange dashed lines: knife slits to each shoulder. Don’t remove any foam.',
                           'Edge notches, 1 mm deep × 18.4 mm tall: they clear the seam-cover clips.']):
        b.append(text(112.411, 59 + i * 7, s, 2.8, 'middle', 'bold' if i == 0 else 'normal'))
    b.append('</g>')
    b += scale_bar(20, 143, 50, '50 mm')
    b.append(text(84, 143, 'Round the notch corners slightly. Cut it a little long, dry-wrap it between the collars, then trim.', 2.7))
    b.append(text(84, 150, 'Keep the notches full size: the seam-cover screws and ribs pass through them.', 2.7))
    write('body-foam-template.svg', svg(270, 155, b, 'BlooglyBlob body foam template, actual size'))


# ---------------------------------------------------------------- service stand
def service_stand():
    W, H = 420, 297  # A3 landscape
    ox, oy = 12, 44  # bed origin: base end, top edge of the drawing = one long side
    L = lambda x: ox + x
    Y = lambda y: oy + 100 + y  # y across the bed, 0 on the centerline
    b = [text(12, 14, 'BlooglyBlob', 4, weight='bold'),
         text(12, 24, 'Wooden service stand: full-size template', 8, weight='bold'),
         text(12, 32, 'Print on A3 at 100% (actual size), or tile it, and check the 100 mm bar. All sizes are in millimetres,', 3.4),
         text(12, 37.5, 'so you can also mark the parts out with a ruler and square. The stand is a workbench fixture, not part of the robot.', 3.4)]
    bed = f'M{L(0)} {Y(-100)}H{L(100)}V{Y(-45)}H{L(280)}V{Y(45)}H{L(100)}V{Y(100)}H{L(0)}Z'
    b.append(f'<path d="{bed}" fill="#f6f1e7" stroke="black" stroke-width="0.4"/>')
    # footprints of the glued parts (top face of the bed)
    for sy in (-1, 1):
        b.append(f'<rect x="{L(22)}" y="{Y(sy*68-15)}" width="58" height="30" fill="none" stroke="#51606b" stroke-width="0.3" stroke-dasharray="2 1.2"/>')
        b.append(text(L(51), Y(sy * 68) + (-9 if sy < 0 else 12), 'base block', 3, 'middle', fill='#51606b'))
    b.append(f'<rect x="{L(213)}" y="{Y(-17)}" width="36" height="34" fill="none" stroke="#51606b" stroke-width="0.3" stroke-dasharray="2 1.2"/>')
    b.append(text(L(231), Y(-20), 'head riser', 3, 'middle', fill='#51606b'))
    holes = [(37, -68), (65, -68), (37, 68), (65, 68), (231, -10), (231, 10)]
    for hx, hy in holes:
        cx, cy = L(hx), Y(hy)
        b.append(f'<circle cx="{cx}" cy="{cy}" r="2.25" fill="white" stroke="black" stroke-width="0.3"/>')
        b.append(f'<path d="M{cx-4} {cy}h8M{cx} {cy-4}v8" stroke="black" stroke-width="0.15"/>')
    # dimensions along the bed (below it)
    dy = Y(100) + 8
    b.append(f'<path d="M{L(0)} {dy}H{L(280)}" stroke="{INK}" stroke-width="0.25"/>')
    for x in (0, 37, 65, 100, 231, 280):
        b.append(f'<path d="M{L(x)} {dy-2}V{dy+2}" stroke="{INK}" stroke-width="0.25"/>')
        b.append(text(L(x), dy + 6, str(x), 3, 'middle'))
    b.append(text(L(140), dy + 12, 'Distances from the base end (holes: 37, 65 and 231)', 3, 'middle'))
    # dimensions across (right of the crossbar)
    b.append(text(L(104), Y(-86), 'Crossbar 100 × 200', 3.2))
    b.append(text(L(104), Y(-80), 'Stem 180 long × 90 wide, centered', 3.2))
    b.append(text(L(104), Y(-74), 'Overall 280 × 200 × 18 plywood', 3.2))
    b.append(text(L(104), Y(76), 'Block holes: 68 each side of the centerline', 3.2))
    b.append(text(L(104), Y(82), 'Riser holes: 10 each side of the centerline', 3.2))
    b.append(text(L(104), Y(88), 'Six Ø4.5 holes, countersunk Ø8.5 × about 3 deep underneath', 3.2))
    b.append(text(L(5), Y(-93), 'BASE END', 3.2, weight='bold'))
    b.append(text(L(276), Y(-38), 'HEAD END', 3.2, 'end', 'bold'))
    b.append(text(L(50), Y(2), 'CUT OUTSIDE THE LINE', 3.2, 'middle', 'bold'))
    # the loose parts at full size
    px = 312
    b.append(text(px, 50, 'Base block, make 2 (top view)', 3.4, weight='bold'))
    b.append(f'<rect x="{px}" y="56" width="58" height="30" fill="#f6f1e7" stroke="black" stroke-width="0.35"/>')
    for x in (15, 43):
        b.append(f'<circle cx="{px+x}" cy="71" r="1.5" fill="white" stroke="black" stroke-width="0.25"/>')
    b.append(text(px, 92, '58 × 30 × 13 wood. Two Ø3 pilots, 28 apart,', 3))
    b.append(text(px, 97, '10 deep, in the face that sits on the bed.', 3))
    b.append(text(px, 102, 'Glue a 58 × 30 × 2 soft foam pad on top.', 3))
    b.append(text(px, 114, 'Head riser, make 1', 3.4, weight='bold'))
    b.append(text(px, 120, 'Bottom face', 3, fill='#51606b'))
    b.append(f'<rect x="{px}" y="123" width="36" height="34" fill="#f6f1e7" stroke="black" stroke-width="0.35"/>')
    for y in (7, 27):
        b.append(f'<circle cx="{px+18}" cy="{123+y}" r="1.5" fill="white" stroke="black" stroke-width="0.25"/>')
    b.append(text(px + 42, 120, 'Side', 3, fill='#51606b'))
    sx = px + 42
    b.append(f'<rect x="{sx}" y="123" width="34" height="70" fill="#f6f1e7" stroke="black" stroke-width="0.35"/>')
    for x in (7, 27):
        b.append(f'<path d="M{sx+x} 193V168M{sx+x} 123V141" stroke="black" stroke-width="0.25" stroke-dasharray="1 0.8"/>')
    b.append(text(sx + 37, 150, '70 tall', 3))
    b.append(text(sx + 37, 138, 'top pilots', 2.8, fill='#51606b'))
    b.append(text(sx + 37, 142, '18 deep', 2.8, fill='#51606b'))
    b.append(text(sx + 37, 183, 'bottom pilots', 2.8, fill='#51606b'))
    b.append(text(sx + 37, 187, '25 deep', 2.8, fill='#51606b'))
    b.append(text(px, 202, 'Wood 70 × 36 × 34. Two Ø3 pilots, 20 apart, in', 3))
    b.append(text(px, 207, 'each end, on the same centers. They don’t meet.', 3))
    b.append(text(px, 219, 'Printed saddle J05: two 4 × 20 pan-head', 3.4, weight='bold'))
    b.append(text(px, 225, 'wood screws into the riser’s top pilots.', 3))
    b.append(text(px, 230, 'Line its curved seat with about 4 mm soft foam.', 3))
    # screws and scale
    notes = ['Screws, from underneath through the countersunk holes: 4 × 25 countersunk (blocks, 4) and 4 × 40 countersunk (riser, 2).',
             'Glue every wood-to-wood joint too. Keep all screw tips buried in the wood.',
             'Place the robot on its left side: base on the two pads, clear of the speaker grille, head in the saddle.']
    for i, s in enumerate(notes):
        b.append(text(12, 276 + i * 6, s, 3.2))
    b += scale_bar(312, 262, 100, '100 mm')
    write('service-stand-template.svg', svg(W, H, b, 'BlooglyBlob service stand template, actual size'))


# ---------------------------------------------------------------- screw key
def hardware_totals():
    hardware = json.loads((OUT.parents[2] / 'assembly/hardware.json').read_text())
    return allocation_totals(indexed(hardware['allocations'], 'id', 'installed allocations'))



def screw_key(form, w, h):
    TOT = hardware_totals()
    supported = {f'M{d}x{n}' for d, lengths in [(2, [6,8,10,12]), (3, [6,8,10,12,14,16,18,20])] for n in lengths} | {'M3x10CS'}
    if {k for k in TOT if re.fullmatch(r'M[0-9]+x[0-9]+(?:CS)?', k)} != supported:
        raise ValueError('Review screw-key drawing dimensions/layout for the changed screw specification set')
    s = '#142b3d'
    ln = lambda d, sw=0.35: f'<path d="{d}" fill="none" stroke="{s}" stroke-width="{sw}"/>'
    rect = lambda x, y, ww, hh: f'<rect x="{x:g}" y="{y:g}" width="{ww:g}" height="{hh:g}" fill="none" stroke="{s}" stroke-width="0.25"/>'
    circ = lambda x, y, r: f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="none" stroke="{s}" stroke-width="0.25"/>'
    b = [text(14, 17, 'BlooglyBlob', 3.6, weight='bold'),
         text(14, 29, 'Actual-size screw key', 7),
         text(14, 38, 'Print at 100% (actual size). Turn off Fit, Shrink and Scale to page.', 3.6),
         text(14, 45, 'Check the 50 mm ruler and the 20 × 20 mm square with a real ruler before use.', 3.2),
         text(14, 51, 'Measure from the middle of the printed lines. A screen is not a size reference.', 3.2)]
    ticks = ''.join(f'M{16+i} 59V{59+(5 if i % 10 == 0 else 3 if i % 5 == 0 else 1.5)}' for i in range(51))
    b += [ln('M16 59H66' + ticks, 0.2), text(16, 69, '0', 3.2), text(59, 69, '50 mm', 3.2),
          rect(82, 56, 20, 20), text(109, 63, '20 × 20 mm', 3.2), text(109, 70, 'check square', 3.2),
          text(14, 85, 'Lay each screw on its drawing with the underside of the head on the start line.', 3.2),
          text(14, 91, 'The length doesn’t include the head. Outlines show the largest head that fits:', 3.2),
          text(14, 97, 'M2 heads up to 3.8 mm across and 2 mm tall; M3 socket heads up to 5.5 mm across and 3 mm tall.', 3.2)]
    y0 = 112
    for col, dia, lengths in [(0, 2, [6, 8, 10, 12]), (1, 3, [6, 8, 10, 12, 14, 16, 18, 20])]:
        bx = 15 + col * 97
        for i, L in enumerate(lengths):
            y = y0 + i * 13
            b.append(text(bx, y, f'M{dia} × {L} · {TOT[f"M{dia}x{L}"]} used', 3.2))
            x, hy = bx + 39, y - 1
            hd, hh = ((3.5, 1.3) if L == 8 else (3.8, 2)) if dia == 2 else (5.5, 3)
            b += [rect(x - hh, hy - hd / 2, hh, hd), rect(x, hy - dia / 2, L, dia), ln(f'M{x} {hy-5}V{hy+5}', 0.25)]
    b += [text(15, 161, f'Three of the {TOT["M2x8"]} M2 × 8 are button heads (drawn: 3.5 × 1.3 mm).', 2.7),
          text(15, 166, 'They fix the head to its shelf, without washers.', 2.7),
          text(15, 172, f'M3 × 10 countersunk · {TOT["M3x10CS"]} used', 3.2)]
    x, y = 54, 181
    b.append(ln(f'M{x} {y-3}L{x+1.5} {y-1.5}H{x+10}V{y+1.5}H{x+1.5}L{x} {y+3}Z', 0.25))
    b.append(ln(f'M{x} {y-5}V{y+5}', 0.25))
    b.append(text(15, 190, 'Length 10 mm including the head; 90° head, 6 mm across.', 2.9))
    b.append(text(15, 202, 'Nuts, seen from above (ordinary hex nuts)', 3))
    for xx, d, af in [(25, 2, 4), (57, 3, 5.5)]:
        r = af / math.sqrt(3)
        pts = ' '.join(f'{xx + r*math.cos(math.radians(i*60)):.4f},{213 + r*math.sin(math.radians(i*60)):.4f}' for i in range(6))
        b += [f'<polygon points="{pts}" fill="none" stroke="{s}" stroke-width="0.25"/>', circ(xx, 213, d / 2),
              text(xx - 10, 222, f'M{d} nuts · {TOT[f"N{d}"]} used', 2.9)]
    b.append(text(15, 235, 'Washers: inside and outside diameter', 3.2))
    for xx, di, do, label in [(28, 2.31, 4.37, f'M2 metal: {TOT["W2"]}, 0.25 mm thick'), (71, 3.20, 7.01, f'M3: {TOT["W3"]}, 0.53 mm thick')]:
        b += [circ(xx, 244, do / 2), circ(xx, 244, di / 2), text(xx - 15, 254, label, 2.7)]
    b += [text(15, 263, 'M2 nuts are 4 mm across the flats and 1.6 mm thick.', 2.7),
          text(110, 225, f'Servo center screws · {TOT["CENTER"]}', 3.2),
          text(110, 232, 'These come with the servos and aren’t drawn here.', 2.8),
          text(110, 238, 'Keep each one with its servo horn.', 2.8),
          text(110, 244, 'Don’t use M2 screws in their place.', 2.8)]
    name = f'screw-key-{form}.svg'
    # Only the PDF ships; its SVG is an intermediate.
    with tempfile.TemporaryDirectory() as tmp:
        write(name, svg(w, h, b, f'BlooglyBlob actual-size screw key ({form.upper() if form == "a4" else "US Letter"})'), Path(tmp))
        to_pdf(name, Path(tmp))


if __name__ == '__main__':
    eye_film()
    body_foam()
    service_stand()
    screw_key('letter', 215.9, 279.4)
    screw_key('a4', 210, 297)
