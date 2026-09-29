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
        parts += screw(3,20,[31,y,97.8],[-1,0,0]) + [hex_nut(3,[-15,y,97.8],[1,0,0])]
    emit('head-carrier-fastening', parts, [1,-.85,.95],
         'Fasten P04 through both uprights from robot-left',
         arrows=[([29,y,97.8],[12,y,97.8]) for y in [-26.5,26.5]],
         labels=[('2 × M3 × 20',None,(28,36)), ('P04',[7,0,101],(405,100)),
                 ('P02',[0,-26.5,102],(45,315)), ('M3 nuts',[-15,26.5,97.8],(360,387))])
    parts = v.parts(['P01'],1) + clipped(v.parts(['P02']),[[-6,-32,103],[0,32,114.3]])
    for y in [-26.5,26.5]:
        parts += screw(3,10,[0,y,136],[0,0,-1]) + [hex_nut(3,[0,y,107.9],[0,0,1])]
    emit('upper-collar-fastening',parts,[.9,-1,.9],
         'Fasten the upper P01 collar from above into the upright nuts',
         arrows=[([0,y,125],[0,y,118]) for y in [-26.5,26.5]],
         labels=[('2 × M3 × 10',None,(28,36)),('P01',[30,0,114.3],(465,250)),
                 ('P02',[0,-29,109],(90,387))])
    parts=clipped(v.parts(['GS20','P08']),[[30,0,121],[44,6,130]])
    parts+=screw(2,8,[53,0,125.3],[-1,0,0],head='button')
    parts+=[hex_nut(2,[34.1,0,125.3],[1,0,0])]
    emit('head-shell-fastening',parts,[1,-1,.6],
         'Remove the head shell screw while leaving the shelf assembly intact',
         arrows=[([44,0,125.3],[50,0,125.3])],
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
