#!/usr/bin/env python3
"""Draw the guide's printable templates into hardware/build-guide/src/downloads/.

Rerunnable and byte-stable. Needs rsvg-convert for the PDFs. The outputs are
committed guide source; the build copies them like any other authored file.
The print packages (3MFs and ZIPs) are made at build time by packages.py.
"""
import argparse, json, math, os, re, subprocess, tempfile
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


def write(name, content, folder=None):
    folder = OUT if folder is None else folder
    (folder / name).write_text(content, encoding='utf-8')


def to_pdf(name, folder=None):
    folder = OUT if folder is None else folder
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


# ---------------------------------------------------------------- head bearing film
def head_bearing_film():
    # Accepted collar: Ø82.6 outside, Ø62 opening, two 3.2 × 2.5 mm fold tabs.
    w, h = 215.9, 279.4
    b = [text(20, 22, 'BlooglyBlob', 4, weight='bold'),
         text(20, 32, 'Head bearing film · P44', 8, weight='bold'),
         text(20, 43, 'Print at 100% (actual size). Turn off Fit, Shrink and Scale to page.', 3.6),
         text(20, 50, 'Check the 50 mm bar before cutting clear film about 0.17–0.19 mm thick.', 3.6)]
    cx, cy = 107.95, 108
    y = math.sqrt(31**2 - 1.6**2)
    a = math.acos(-1.6 / 31)
    points = [(1.6,y),(1.6,28.5),(-1.6,28.5),(-1.6,y)]
    for i in range(1,601):
        theta = a + (2*math.pi-2*a)*i/600
        points.append((31*math.cos(theta),31*math.sin(theta)))
    points += [(-1.6,-28.5),(1.6,-28.5),(1.6,-y)]
    for i in range(1,601):
        theta = -(math.pi-a) + 2*(math.pi-a)*i/600
        points.append((31*math.cos(theta),31*math.sin(theta)))
    path = 'M' + ' L'.join(f'{cx+x:.5f},{cy+y:.5f}' for x,y in points) + ' Z'
    b += [f'<circle cx="{cx}" cy="{cy}" r="41.3" fill="none" stroke="black" stroke-width="0.1"/>',
          f'<path d="{path}" fill="none" stroke="black" stroke-width="0.1"/>']
    for dy in (-31,31):
        b.append(f'<path d="M{cx-1.6} {cy+dy}h3.2" stroke="black" stroke-width="0.15" stroke-dasharray="1.2 .7"/>')
    b += [text(cx, cy, 'REMOVE CENTER', 3.6, 'middle', 'bold'),
          text(cx, cy+7, 'Keep both small tabs', 3.2, 'middle'),
          text(20, 169, 'Cut the solid lines. Fold both tabs down 90° along the dashed lines.', 3.6),
          text(20, 177, 'Lay the disc on the collar and insert the tabs into its two slots.', 3.6),
          text(20, 187, 'Outer diameter 82.6 mm · inner circle 62 mm · tabs 3.2 mm wide, 2.5 mm deep', 3.2)]
    b += scale_bar(20, 213, 50, '50 mm · actual size')
    write('head-bearing-film-template.svg', svg(w,h,b,'BlooglyBlob head bearing film template: actual size'))
    to_pdf('head-bearing-film-template.svg')


# ---------------------------------------------------------------- body foam
SHOULDER_HOLE = 14  # mm: the servo's round top is 12.1 mm across (Kitronik 25105 envelope)


def body_foam():
    # US Letter landscape; everything also sits inside an A4 landscape page.
    w, h = 279.4, 215.9
    ox, oy = 27, 62  # foam outline origin: top-left corner, top edge at the upper collar
    b = [text(20, 20, 'BlooglyBlob', 4, weight='bold'),
         text(20, 30, 'Body foam template', 8, weight='bold'),
         text(20, 40, 'Print at 100% (actual size), landscape. Turn off Fit, Shrink and Scale to page.', 3.6),
         text(20, 46, 'Check the 50 mm bar with a ruler before cutting. Cut from 4 mm white foam.', 3.6),
         f'<g transform="translate({ox} {oy})" stroke-width="0.3">',
         f'<rect width="224.8227" height="114.3" fill="none" stroke="{INK}"/>']
    for x in (55.7056, 169.1171):
        r = SHOULDER_HOLE / 2
        b.append(f'<circle cx="{x:g}" cy="24.3" r="{r:g}" fill="none" stroke="{INK}"/>')
        b.append(f'<path d="M{x-2:g} 24.3H{x+2:g}M{x:g} 22.3V26.3" stroke="{INK}" stroke-width="0.2"/>')
        b.append(text(x, 24.3 + r + 4.5, f'Shoulder hole, {SHOULDER_HOLE} mm', 2.8, 'middle'))
    b.append(text(112.411, -2.5, 'TOP EDGE · upper collar', 2.8, 'middle', 'bold'))
    for i, s in enumerate(['FRONT CENTER', '224.8 × 114.3 mm',
                           'The two short edges meet at the back with a 2 mm gap.']):
        b.append(text(112.411, 56 + i * 7, s, 2.8, 'middle', 'bold' if i == 0 else 'normal'))
    b.append('</g>')
    b += scale_bar(20, 196, 50, '50 mm')
    b.append(text(84, 193, 'Cut the outline a little long. Trim the ends after a test-fit between the collars.', 3.2))
    b.append(text(84, 199, 'At the test-fit, mark each hole center over its shoulder servo shaft.', 3.2))
    write('body-foam-template.svg', svg(w, h, b, 'BlooglyBlob body foam template, actual size'))
    to_pdf('body-foam-template.svg')


# ---------------------------------------------------------------- screw key
def hardware_totals():
    hardware = json.loads((Path(__file__).resolve().parents[3] / 'hardware/assembly/hardware.json').read_text())
    return allocation_totals(indexed(hardware['allocations'], 'id', 'installed allocations'))



def screw_key(form, w, h):
    TOT = hardware_totals()
    supported = {f'M{d}x{n}' for d, lengths in [(2, [6,8,10,12]), (3, [6,8,10,12,14,16,20])] for n in lengths}
    if {k for k in TOT if re.fullmatch(r'M[0-9]+x[0-9]+(?:CS)?', k)} != supported:
        raise ValueError('Review screw-key drawing dimensions/layout for the changed screw specification set')
    s = '#142b3d'
    ln = lambda d, sw=0.35: f'<path d="{d}" fill="none" stroke="{s}" stroke-width="{sw}"/>'
    rect = lambda x, y, ww, hh: f'<rect x="{x:g}" y="{y:g}" width="{ww:g}" height="{hh:g}" fill="none" stroke="{s}" stroke-width="0.25"/>'
    b = [text(14, 17, 'BlooglyBlob', 3.6, weight='bold'),
         text(14, 29, 'Actual-size screw length key', 7),
         text(14, 38, 'Print at 100% (actual size). Turn off Fit, Shrink and Scale to page.', 3.6),
         text(14, 45, 'Check the 50 mm ruler and the 20 × 20 mm square with a real ruler before use.', 3.2),
         text(14, 51, 'Measure from the middle of the printed lines. A screen is not a size reference.', 3.2)]
    ticks = ''.join(f'M{16+i} 59V{59+(5 if i % 10 == 0 else 3 if i % 5 == 0 else 1.5)}' for i in range(51))
    b += [ln('M16 59H66' + ticks, 0.2), text(16, 69, '0', 3.2), text(59, 69, '50 mm', 3.2),
          rect(82, 56, 20, 20), text(109, 63, '20 × 20 mm', 3.2), text(109, 70, 'check square', 3.2),
          text(14, 85, 'Place the underside of each head on the start line. Match the tip to the end.', 3.2),
          text(14, 91, 'All lengths below exclude the head. Head outlines identify the style only.', 3.2),
          text(14, 97, 'These outlines are not recess-fit gauges; the M2 kit head dimensions are unmeasured.', 3.0)]
    def profile(x, y, dia, length, button):
        hd, hh = ((3.5, 1.3) if dia == 2 else (5.5, 1.53)) if button else (5.33, 3.03)
        if button:
            head = ln(f'M{x} {y-hd/2}Q{x-hh} {y-hd/2} {x-hh} {y}Q{x-hh} {y+hd/2} {x} {y+hd/2}Z', .25)
        else:
            head = rect(x-hh,y-hd/2,hh,hd)
        return [head,rect(x,y-dia/2,length,dia),ln(f'M{x} {y-5}V{y+5}',.25)]
    b += [text(15, 108, 'M2 button heads · Kadrick M2 kit', 3.2, weight='bold'),
          text(112, 108, 'M3 socket heads · Kadrick M3 kit', 3.2, weight='bold')]
    for bx, dia, lengths in [(15, 2, [6,8,10,12]), (112, 3, [6,8,10,12,16,20])]:
        for i, length in enumerate(lengths):
            y = 120 + i*13
            b.append(text(bx,y,f'M{dia} × {length} · {TOT[f"M{dia}x{length}"]} used',3.2))
            b += profile(bx+39,y-1,dia,length,dia==2)
    b += [text(15, 179, 'M3 button heads · extra pack', 3.2, weight='bold'),
          text(15, 191, f'M3 × 14 · {TOT["M3x14"]} used',3.2)]
    b += profile(54,190,3,14,True)
    b += [text(15, 204, 'Use these five button heads at the elbows (2), front light brackets (2),',3.0),
          text(15, 210, 'and sideways front head-servo carrier joint (1). No flatheads are required.',3.0),
          text(15, 224, 'Nuts and washers supplied by the kits',3.3,weight='bold'),
          text(15, 232, f'M2 nuts: {TOT["N2"]} · M3 nuts: {TOT["N3"]} · M2 washers: {TOT["W2"]}',3.2),
          text(15, 239, 'The four M2 washers go under the eye-housing screw heads. No speaker washers.',3.0),
          text(15, 246, 'Kit washers are not drawn to scale: their dimensions have not been measured.',3.0),
          text(15, 259, f'Servo center screws: {TOT["CENTER"]} · supplied with the servos.',3.2),
          text(15, 266, 'Keep each center screw with its servo horn. Do not substitute an M2 screw.',3.0)]
    name = f'screw-key-{form}.svg'
    # Only the PDF ships; its SVG is an intermediate.
    with tempfile.TemporaryDirectory() as tmp:
        write(name, svg(w, h, b, f'BlooglyBlob actual-size screw key ({form.upper() if form == "a4" else "US Letter"})'), Path(tmp))
        to_pdf(name, Path(tmp))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--screw-keys-only', action='store_true')
    args = parser.parse_args()
    if args.output:
        OUT = args.output
        OUT.mkdir(parents=True, exist_ok=False)
    if not args.screw_keys_only:
        eye_film()
        head_bearing_film()
        body_foam()
    screw_key('letter', 215.9, 279.4)
    screw_key('a4', 210, 297)
