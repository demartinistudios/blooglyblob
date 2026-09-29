"""Physical route views: accepted parts and reviewed nominal cable paths.

These drawings explain the route and endpoints. Actual cable flexibility,
overmolds and service access still need checking during the build.
"""
import base64
import html
import itertools
import json
from pathlib import Path

import numpy as np
import trimesh

from guide_closeups import item, audio_cable_ends, _audio_case


def cable(points, radius, color):
    pieces = []
    for start, end in zip(points, points[1:]):
        start, end = np.asarray(start), np.asarray(end)
        axis = end - start
        if np.linalg.norm(axis) < .001:
            continue
        mesh = trimesh.creation.cylinder(radius, np.linalg.norm(axis), sections=16)
        mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], axis))
        mesh.apply_translation((start + end) / 2)
        pieces.append(mesh)
    return item(trimesh.util.concatenate(pieces), 'Cable', color)


def plug(start, end, width, height):
    """Nominal installed overmold with chamfered corners and grip ribs."""
    start, end = np.array(start), np.array(end)
    length = np.linalg.norm(end - start)
    row = _audio_case(0, length, -height/2, height/2, -width/2, width/2,
                      min(1.2, height/4), 'Cable plug', (40, 44, 49))
    transform = trimesh.geometry.align_vectors([1, 0, 0], (end-start)/length)
    transform[:3, 3] = start
    rows = [row]
    for position in np.linspace(length*.68, length*.88, 4):
        mesh = trimesh.creation.box([.6, width+.25, height+.25])
        mesh.apply_translation([position, 0, 0])
        rows.append(item(mesh, 'Plug grip', (62, 68, 75)))
    for row in rows:
        row['v'] = trimesh.transform_points(row['v'], transform)
    return rows


def render_routes(render, output, parts):
    original = render.meshes
    data = json.loads((Path(__file__).resolve().parents[2] / 'rendering/guide-routes.json').read_text())
    routes = {row['id']: row for row in data['routes']}
    # Fail on moved socket/terminal references rather than reusing stale routes.
    usb_vertices=np.concatenate([m['v'] for m in parts if m['id']=='E09' and
                                 m.get('component_detail')=='USB shell'])
    assert np.allclose(usb_vertices.min(0),[-60.5,-3,-25.6],atol=.05)
    for y in [52,22]:
        housings=[m for m in parts if m['id']=='E06' and
                  m.get('component_detail')=='housing' and
                  abs(m['v'].mean(0)[1]-y)<.05]
        assert len(housings)==1 and abs(housings[0]['v'].mean(0)[0]-48)<.05
    # The plan view reverses world X: WAGO port 1 is on the picture's right.
    assert routes['H2-positive']['to'] == 'W1/2'
    assert routes['H2-return']['to'] == 'W3/2'
    assert np.allclose(routes['H2-positive']['points_mm'][-1], [42, 42.7, -17.2])
    assert np.allclose(routes['H2-return']['points_mm'][-1], [42, 12.7, -17.2])
    camera = np.array([0, .001, -1.]); camera /= np.linalg.norm(camera)
    x = np.cross([0, 0, 1], camera); x /= np.linalg.norm(x)
    basis = np.array([x, np.cross(camera, x), camera]).T
    bounds = [[-112, -102, -68], [112, 102, 1]]
    corners = np.array(list(itertools.product(*zip(*bounds)))) @ basis
    mid = (corners[:, :2].min(0) + corners[:, :2].max(0))/2
    scale = min(720 / np.ptp(corners[:, :2], axis=0))

    def project(p):
        q = np.array(p) @ basis
        return [450+(q[0]-mid[0])*scale, 450-(q[1]-mid[1])*scale]

    def label(text, p, xy, anchor='start'):
        q = project(p); a, b = xy
        return (f'<path d="M{a},{b+7} L{q[0]:.1f},{q[1]:.1f}" stroke="#526576" stroke-width="2"/>'
                f'<text x="{a}" y="{b}" text-anchor="{anchor}" font-size="30" font-weight="bold" '
                f'fill="#22384e" stroke="#f3f7fa" stroke-width="7" paint-order="stroke">{html.escape(text)}</text>')

    def emit(name, title, extra, labels, overlay='', crop=None):
        render.meshes = parts + extra
        render.render(name+'-background', dict(select=['all'], camera=camera.tolist(), clean=True,
                      size=[1200,1200], margin=120, frame_world_bounds=bounds))
        png = base64.b64encode((output/(name+'-background.png')).read_bytes()).decode()
        body = f'<image width="900" height="900" href="data:image/png;base64,{png}"/>'
        body += '<g font-family="Arial,sans-serif">'
        body += '<g font-size="30" font-weight="bold" text-anchor="middle" fill="#22384e"><text x="450" y="45">REAR</text><text x="450" y="864">FRONT · audio cradle</text></g>'
        body += overlay + ''.join(label(*args) for args in labels) + '</g>'
        view_box = ' '.join(map(str,crop)) if crop else '0 0 900 900'
        (output/(name+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" role="img"><title>{html.escape(title)}</title><rect width="900" height="900" fill="#f3f7fa"/>{body}</svg>')
        return 'assets/community/'+name+'.svg'

    power = plug([-22,53.4,-22],[8,53.4,-22],9,5)
    for name in ['H2-jacket','H2-positive','H2-return']:
        row = routes[name]
        power.append(cable(row['points_mm'],row['diameter_mm']/2,row['color']))
    paths = [emit('pi-power-route', 'Route H2 from the Pi power socket to W1 port 2 and W3 port 2', power, [
        ('Pi POWER',[-22,53.4,-22],[480,150]),
        ('W1 / 2',[42,42.7,-17.2],[70,285]),
        ('W3 / 2',[42,12.7,-17.2],[70,430]),
        ('+5 V',[30,45,-46.5],[370,250]),
        ('GND',routes['H2-return']['points_mm'][15],[400,380]),
    ], crop=[50,110,810,410])]
    usb = routes['USB-data']
    cables = [cable(usb['points_mm'],usb['diameter_mm']/2,(45,79,113))]
    cables += plug([-53.5,-3,-22],[-53.5,-38,-22],14,7)
    cables += [m for m in audio_cable_ends(False) if m['id'].startswith('USB')]
    # Continue from the reviewed path into the known extension strain relief.
    cables.append(cable([[-46.5,-80,-26],[-44,-80,-26]],2.25,(45,79,113)))
    paths.append(emit('usb-audio-route', 'Route the USB cable below the audio cradle, clear of the bottom cover', cables, [
        ('Pi USB',[-53.5,-3,-22],[750,430]),
        ('Audio USB',[-34,-80,-26],[350,790]),
        ('Cable bend',[-63.75,-79.25,-48.5],[700,650]),
    ], crop=[330,385,560,435]))
    # Access guide highlights real openings rather than inventing a complete,
    # physically untested wire harness or fixed adhesive-anchor locations.
    overlay=''
    for p,r in [([0,0,-2],17),([0,26.5,-2],8),([0,-26.5,-2],8)]:
        a,b=project(p)
        overlay+=f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r*scale:.1f}" fill="none" stroke="#a65b35" stroke-width="4" stroke-dasharray="9 7"/>'
    paths.append(emit('base-routing-access', 'Keep the central harness opening, frame screw access, SD card, WAGO levers and fuse caps accessible', [], [
        ('Harness opening',[0,0,-2],[515,805]),
        ('Frame screw',[0,26.5,-2],[530,100]),
        ('Frame screw',[0,-26.5,-2],[675,600]),
        ('SD card',[-50,66,-15],[700,140]),
        ('WAGO levers',[48,22,-22],[45,410]),
        ('F2 cap',[12,74,-22],[180,120]),
        ('F1 cap',[-10,-58,-22],[100,785]),
    ], overlay))
    from guide_closeups import Views, clipped
    render.meshes=original
    detail=Views(render,output)
    usb_parts=clipped([m for m in parts if m['id'] in ('E09','E14','FB24')],
                      [[-80,-90,-65],[44,14,0]]) + cables
    detail.emit('usb-audio-route-depth',usb_parts,[.55,.85,-1.4],
        'Route USB below the cradle',
        ['Detail · Pi/enclosure partly omitted','1 Pi USB · 2 audio USB',
         'Keep the cable clear of the cover'],
        marks=[('1',[-53.5,-3,-22]),('2',[-34,-80,-26])])
    power_parts=[m for m in parts if m['id']=='E09' or
                 (m['id']=='E06' and np.mean(m['v'],axis=0)[1]>10)] + power
    detail.emit('pi-power-route-depth',power_parts,[.6,.75,-1.3],
        'Route the short power lead',
        ['Oblique view · enclosure omitted','1 Pi POWER · 2 W1/2 · 3 W3/2',
         'Gentle bends; no extra service loop'],
        marks=[('1',[-22,53.4,-22]),('2',[42,42.7,-17.2]),('3',[42,12.7,-17.2])])
    paths.extend(detail.paths)
    parts=[m for m in parts if m['id'] in ('FB01','E06')]
    paths.append(emit('wago-finished-layout', 'Label the WAGO row W1 W3 W2 W4 from rear to front', [],
        [(name,[48,y,-22],[130,project([48,y,-22])[1]])
         for name,y in [('W1',52),('W3',22),('W2',-8),('W4',-38)]],
        '<text x="130" y="190" font-size="28" fill="#22384e">REAR ↑</text>',
        crop=[105,160,340,490]))
    # A separate connector close-up makes the custom port numbering visible.
    from guide_closeups import Views
    render.meshes=original
    v=Views(render,output)
    wago=[m for m in parts if m['id']=='E06' and np.mean(m['v'],axis=0)[1]>40]
    v.emit('wago-port-order',wago,[0,.001,-1.4],'Number the WAGO ports',
           ['Same open-bottom view','1 is on the picture’s right',
            'Front = wire-entry edge'],
           marks=[(str(i+1),[x,42.7,-17.2]) for i,x in enumerate([36,42,48,54,60])])
    paths.extend(v.paths)
    render.meshes=original
    return paths
