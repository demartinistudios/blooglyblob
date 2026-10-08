"""Current-CAD replacements for retired gold hardware closeups."""
import numpy as np
from guide_closeups import Views, clipped, compact_view
from guide_fasteners import screw, hex_nut


def render_legacy_actions(render, output):
    v = Views(render, output)
    def emit(*args, **kwargs):
        v.paths.append(compact_view(render, output, *args, **kwargs))
    def check_circle(pid, axis, face, center, radius):
        points = np.concatenate([m['v'] for m in v.parts([pid])])
        other = [i for i in range(3) if i != axis]
        radial = np.linalg.norm(points[:, other] - center, axis=1)
        count = np.count_nonzero((abs(points[:, axis] - face) < .001) & (abs(radial - radius) < .001))
        if count < 20:
            raise ValueError(f'{pid}: fastening bore changed at {face}/{center}')
    # R33: the front screw is countersunk into P04's tab (X 1 to 5, Ø6.8 seat
    # at X 5) and its nut sits in P43's robot-right recess (X -5 to -2.35).
    # The rear screw still runs X 9 to the nut outside P02.
    check_circle('P04', 0, 1, [-26.5, 97.8], 1.7)
    check_circle('P04', 0, 5, [-26.5, 97.8], 3.4)
    check_circle('P04', 0, 9, [26.5, 97.8], 1.7)
    check_circle('P43', 0, -2.35, [-26.5, 97.8], 1.7)
    for y in [-26.5, 26.5]:
        check_circle('P01', 2, 116.3, [0, y], 1.7)
    parts = clipped(v.parts(['P04', 'P43', 'P02']), [[-7,-32,93],[11,32,103]])
    for m in parts: m['guide_color'] = (126,135,169) if m['id']=='P04' else (140,159,179)
    parts += screw(3,10,[5,-26.5,97.8],[-1,0,0],head='countersunk') + [hex_nut(3,[-3.525,-26.5,97.8],[1,0,0])]
    parts += screw(3,20,[9,26.5,97.8],[-1,0,0]) + [hex_nut(3,[-6.2,26.5,97.8],[1,0,0])]
    emit('head-carrier-fastening', parts, [-1,-.85,.95],
         'Fasten P04 to both uprights from robot-left: countersunk M3 x 10 at the front, M3 x 20 at the rear',
         labels=[('M3 × 20 + nut',[-11,26.5,97.8],(28,40)), ('P04',[-1.27,6.6,99.3],(405,100)),
                 ('P02',[-5,24,101],(40,250)), ('P43',[-5,-29,95],(500,240)),
                 ('M3 × 10 countersunk + nut',[-4.7,-26.5,97.8],(150,400))])
    # Nuts slide into the upright slots from the outer faces; the collar is
    # lifted 14 mm to show its tabs going down onto the upright tops.
    parts = [dict(m, v=m['v']+[0,0,14]) for m in v.parts(['P01'],1)]
    parts += clipped(v.parts(['P43','P02']),[[-6,-32,88],[6,32,114.3]])
    arrows = [([0,26.5*s,141],[0,26.5*s,134]) for s in [-1,1]]
    arrows += [([0,26.5*s,127],[0,26.5*s,119]) for s in [-1,1]]
    for s in [-1,1]:
        parts += screw(3,10,[0,26.5*s,152],[0,0,-1]) + [hex_nut(3,[0,41*s,107.9],[0,0,1])]
        arrows.append(([0,38*s,107.9],[0,31.5*s,107.9]))
    emit('upper-collar-fastening',parts,[1,-.75,.55],
         'Slide a nut into the slot near each upright top, then screw the upper P01 collar down onto the uprights',
         arrows=arrows,
         labels=[('2 × M3 × 10',[0,-26.5,152],(28,36)),('P01',[39,0,128.3],(480,150)),
                 ('P43',[5,-26.5,95],(60,395)),('2 × M3 nuts',[0,41,107.9],(390,395))],label_size=32)
    parts=clipped(v.parts(['GS20','P08']),[[30,0,121],[44,6,130]])
    parts+=screw(2,8,[40.45,0,125.3],[-1,0,0],head='button')
    parts+=[hex_nut(2,[34.1,0,125.3],[1,0,0])]
    emit('head-shell-fastening',parts,[1,-1,.6],
         'Head shell screw engages the nut in the shelf',
         labels=[('M2 × 8',None,(410,45)),('Head',[42,4,128],(420,365)),
                 ('P08',[32,4,128],(36,62)),('M2 nut',[34.1,0,125.3],(32,385))])
    render.meshes=v.original
    return v.paths
