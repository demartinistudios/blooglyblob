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
    for y in [-26.5, 26.5]:
        check_circle('P04', 0, 9, [y, 97.8], 1.7)
        check_circle('P01', 2, 116.3, [0, y], 1.7)
    parts = clipped(v.parts(['P04', 'P02']), [[-7,-32,93],[11,32,103]])
    for m in parts: m['guide_color'] = (126,135,169) if m['id']=='P04' else (140,159,179)
    for y in [-26.5,26.5]:
        parts += screw(3,20,[9,y,97.8],[-1,0,0]) + [hex_nut(3,[-6.2,y,97.8],[1,0,0])]
    emit('head-carrier-fastening', parts, [-1,-.85,.95],
         'Fasten P04 through both uprights from robot-left',
         labels=[('2 × M3 × 20',None,(28,36)), ('P04',[-1.27,6.6,99.3],(405,100)),
                 ('P02',[0,-26.5,102],(45,315)), ('M3 nuts',[-6.2,26.5,97.8],(360,387))])
    # Nuts slide into the upright slots from the outer faces; the collar is
    # lifted 14 mm to show its tabs going down onto the upright tops.
    parts = [dict(m, v=m['v']+[0,0,14]) for m in v.parts(['P01'],1)]
    parts += clipped(v.parts(['P02']),[[-6,-32,88],[6,32,114.3]])
    arrows = [([0,26.5*s,141],[0,26.5*s,134]) for s in [-1,1]]
    arrows += [([0,26.5*s,127],[0,26.5*s,119]) for s in [-1,1]]
    for s in [-1,1]:
        parts += screw(3,10,[0,26.5*s,152],[0,0,-1]) + [hex_nut(3,[0,41*s,107.9],[0,0,1])]
        arrows.append(([0,38*s,107.9],[0,31.5*s,107.9]))
    emit('upper-collar-fastening',parts,[1,-.75,.55],
         'Slide a nut into the slot near each upright top, then screw the upper P01 collar down onto the uprights',
         arrows=arrows,
         labels=[('2 × M3 × 10',[0,-26.5,152],(28,36)),('P01',[39,0,128.3],(480,150)),
                 ('P02',[5,-26.5,95],(60,395)),('2 × M3 nuts',[0,41,107.9],(390,395))],label_size=32)
    parts=clipped(v.parts(['GS20','P08']),[[30,0,121],[44,6,130]])
    parts+=screw(2,8,[40.45,0,125.3],[-1,0,0],head='button')
    parts+=[hex_nut(2,[34.1,0,125.3],[1,0,0])]
    emit('head-shell-fastening',parts,[1,-1,.6],
         'Head shell screw engages the nut in the shelf',
         labels=[('M2 × 8',None,(410,45)),('Head',[42,4,128],(420,365)),
                 ('P08',[32,4,128],(36,62)),('M2 nut',[34.1,0,125.3],(32,385))])
    parts=v.parts(['P03'])+v.parts(['E01'],0)
    for z in [71,98.7]:
        parts+=screw(2,6,[39,0,z],[-1,0,0])+[hex_nut(2,[23.9,0,z],[1,0,0])]
    emit('shoulder-servo-removal',parts,[1,1,.55],
         'Remove the two ear screws and slide the servo out of its bracket',
         arrows=[([29,0,z],[38,0,z]) for z in [71,98.7]],
         labels=[('2 × M2 × 6',None,(28,36)),('Servo',[32,0,84],(420,320)),
                 ('P03',[20,15,95],(32,360))])
    render.meshes=v.original
    return v.paths
