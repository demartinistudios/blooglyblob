"""Focused grille and base fastening views from accepted meshes."""
import base64
import html
import itertools

import numpy as np

from guide_closeups import BG, INK, Views, clipped, hardware, nut, pose_parts


def _compact(v, name, parts, camera, title, arrows=(), labels=(), label_size=24):
    if name in ('front-grille-nut-loading','side-grille-nut-loading'):
        rotation=np.diag([1,-1,-1])
        parts=pose_parts(parts,rotation);camera=(rotation@camera).tolist()
        arrows=[(rotation@a,rotation@b) for a,b in arrows]
        labels=[(label,rotation@point,xy) for label,point,xy in labels]
    render = v.render
    render.meshes = parts
    points = np.concatenate([m['v'] for m in parts])
    bounds = np.array([points.min(0)-2, points.max(0)+2])
    render.render('closeup-'+name, dict(select=['all'], camera=camera, clean=True,
                  size=[1200, 840], margin=76, frame_world_bounds=bounds.tolist()))
    z = np.array(camera, float); z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z); x /= np.linalg.norm(x)
    y = np.cross(z, x); rotation = np.array([x, y, z]).T
    corners = np.array(list(itertools.product(*zip(*bounds)))) @ rotation
    low, high = corners[:, :2].min(0), corners[:, :2].max(0)
    middle = (low+high)/2
    scale = min(1048/max(high[0]-low[0], 1), 688/max(high[1]-low[1], 1))/2
    def project(point):
        p = np.array(point) @ rotation
        return ((p[0]-middle[0])*scale+300, 210-(p[1]-middle[1])*scale)
    png = (v.output/('closeup-'+name+'.png')).read_bytes()
    body = f'<image width="600" height="420" href="data:image/png;base64,{base64.b64encode(png).decode()}"/>'
    for a, b in arrows:
        a, b = project(a), project(b)
        path = f'M{a[0]:.2f},{a[1]:.2f}L{b[0]:.2f},{b[1]:.2f}'
        body += f'<path d="{path}" stroke="white" stroke-width="7"/><path d="{path}" stroke="#a95522" stroke-width="3.5" marker-end="url(#arrow)"/>'
    for label, point, xy in labels:
        p = project(point)
        body += f'<path d="M{xy[0]},{xy[1]+6}L{p[0]:.2f},{p[1]:.2f}" stroke="#526576" stroke-width="1.5"/>'
        body += f'<text x="{xy[0]}" y="{xy[1]}" font-family="Arial, sans-serif" font-size="{label_size}" fill="{INK}" stroke="{BG}" stroke-width="5" paint-order="stroke">{html.escape(label)}</text>'
    _save(v, name, title, body)


def _save(v, name, title, body, height=420):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 {height}" role="img"><title>{html.escape(title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#a95522"/></marker></defs><rect width="600" height="{height}" fill="{BG}"/>{body}</svg>'
    (v.output/(name+'.svg')).write_text(svg)
    v.paths.append('assets/community/'+name+'.svg')


def render_context_actions(render, output):
    v = Views(render, output)
    try:
        # Accepted FB19 +X grille: the four outer Ø3.4 bores are at
        # Y=-48/+32, Z=-12.5/-49.5, bearing X107. FB01 nut channels
        # span X96.6..99.4 with 5.8 mm flat separation in Y; load from -Z.
        shell = clipped(v.parts(['FB01']), [[94, -58, -60], [106, 42, 0]])
        for m in shell: m['guide_color'] = (177, 190, 202)
        grille = v.parts(['FB19'], 0)
        for m in grille:
            m['v'] = m['v'] + [14, 0, 0]
            m['guide_color'] = (174, 99, 52)
        from guide_speaker_actions import speaker
        parts = shell+grille+speaker(offset=14)
        # The four inner joints were completed on the bench in the prior step.
        from guide_fasteners import washer, hex_nut
        for yy in (-40, 24):
            for zz in (-43, -19):
                parts += hardware(3, 12, [121, yy, zz], [-1, 0, 0])
                parts += [washer([113.935, yy, zz], [1, 0, 0], 3.505, 1.6, .53),
                          hex_nut(3, [112.47, yy, zz], [1, 0, 0])]

        arrows = []
        for yy in [-48, 32]:
            for zz in [-12.5, -49.5]:
                parts += hardware(3, 12, [142, yy, zz], [-1, 0, 0])
                # M3 nut, phase-preserving rotation: local flat-X -> world Y.
                from guide_fasteners import hex_nut
                row = hex_nut(3, [98, yy, zz], [1, 0, 0])
                parts.append(row)
                if yy == 32 and zz == -12.5: upper_nut = row
                arrows.append(([130, yy, zz], [122, yy, zz]))
        _compact(v, 'side-grille-fastening', parts, [1.5, .75, -.7],
                 'Fasten the assembled speaker grille through its four outer holes; repeat opposite',
                 arrows=arrows,
                 labels=[('4 × M3 × 12', [142, 32, -12.5], (375, 42)),
                         ('FB19', [121, -8, -31], (340, 390)),
                         ('Base', [101, 38, -30], (30, 45))])
        # Show the nut loading separately rather than hide it behind the grille.
        inset = clipped(v.parts(['FB01']), [[94, 25, -25], [104, 39, -4]])
        for m in inset: m['guide_color'] = (177, 190, 202)
        loose = dict(upper_nut, v=upper_nut['v']+[0, 0, -10])
        _compact(v, 'side-grille-nut-loading', inset+[loose], [-1, .6, -.55],
                 'Load the M3 nut into its channel',
                 arrows=[([98,32,-20.5],[98,32,-14])],
                 labels=[('4 × M3 per side', [98,32,-22.5], (25,40)),
                         ('Base', [101,38,-15], (370,385))])
        # R27: fully exposed ceiling recess, mouth Z=-7, floor Z=-4.2.
        # Load directly along +Z; no rear well or hidden transfer tunnel.
        from guide_fasteners import hex_nut
        cradle_seat = clipped(v.parts(['FB01']), [[-69,-85,-10],[-55,-63,0]])
        for m in cradle_seat: m['guide_color'] = (118,132,146)
        loose = hex_nut(3, [-62,-78.2,-14], [0,0,1])
        _compact(v, 'audio-cradle-nut-loading', cradle_seat+[loose], [.65,1,-1.1],
                 'Place an M3 nut directly into the exposed ceiling recess from the open bottom; glue its outside edges',
                 arrows=[([-62,-78.2,-11],[-62,-78.2,-5.4])],
                 labels=[('3 × M3 nuts', [-62,-78.2,-14], (25,40)),
                         ('Open recess', [-62,-78.2,-5.4], (335,390))], label_size=32)
        front_seat = clipped(v.parts(['FB01']), [[-33,-95,-49],[-21,-83,-32]])
        for m in front_seat: m['guide_color'] = (118,132,146)
        _compact(v, 'front-support-cleanup', front_seat, [.8,1,-.15],
                 'Front nut-entry channel, seen from inside the base',
                 labels=[('Nut channel',[-27,-90.6,-40.5],(25,40)),
                         ('Entry',[-27,-90.6,-46],(410,385))],label_size=32)
        loose = hex_nut(3, [-27,-90.6,-47.5], [0,1,0])
        _compact(v, 'front-grille-nut-loading', front_seat+[loose], [.8,1,-.15],
                 'Slide four front grille nuts into their channels from inside the base',
                 arrows=[([-27,-90.6,-46],[-27,-90.6,-40.5])],
                 labels=[('4 × M3 nuts', [-27,-90.6,-47.5], (25,40)),
                         ('Channel', [-27,-90.6,-40.5], (400,385))])
        # Whole front/rear grilles with the four actual CAD bore axes.
        # Show a local wall cutaway so the fastened part remains readable.
        for name, part_id, side, xs, zs, face, length in [
            ('front-grille-installation', 'FB41', -1, [-27, 51], [-10.7, -40.5], -95, 6),
            ('rear-vent-installation', 'FB03', 1, [-26, 58], [-12.5, -49.5], 94.5, 12),
        ]:
            wall_bounds = [[min(xs)-9, -95 if side < 0 else 82, min(zs)-9],
                           [max(xs)+9, -82 if side < 0 else 95, 0]]
            shell = clipped(v.parts(['FB01']), wall_bounds)
            for m in shell: m['guide_color'] = (68, 75, 83)
            grille = v.parts([part_id])
            for m in grille:
                m['v'] = m['v'] + [0, side*12, 0]
                m['guide_color'] = (174, 99, 52)
            parts = shell + grille
            arrows = []
            seat_y = face + side*(length+24)
            for xx in xs:
                for zz in zs:
                    parts += hardware(3, length, [xx, seat_y, zz], [0, -side, 0])
                    arrows.append(([xx, face+side*23, zz], [xx, face+side*14, zz]))
            _compact(v, name, parts, [.65, side*1.5, .55],
                     'Fit '+part_id+' with four M3 by '+str(length)+' screws from outside',
                     arrows=arrows,
                     labels=[('4 × M3 × '+str(length), [xs[1], seat_y, zs[0]], (350, 36)),
                             (part_id, [sum(xs)/2, face+side*12, min(zs)+6], (240, 399)),
                             ('Base · cutaway', [min(xs)-5, side*92, -3], (18, 37))])
    finally:
        render.meshes = v.original
    from guide_speaker_actions import render_speaker_actions
    v.paths.extend(render_speaker_actions(render, output))
    from guide_component_actions import render_component_actions
    v.paths.extend(render_component_actions(render, output))
    return v.paths
