"""Compact carrier and belt actions from accepted assembly surfaces."""
import numpy as np

from guide_closeups import Views, clipped, compact_view, hardware, nut


def m3_nut(center):
    from guide_fasteners import hex_nut
    return hex_nut(3, center, [0,1,0])


def render_joint_actions(render, output):
    """Show actual carrier access wells and one real B02/B02 belt joint.

    The accepted carrier bores are X0/Z62,70. The uprights' outer faces
    are Y±31, with counterbore seats at Y±29; P03 joins them at Y±22.
    The loose nuts bear at Y±18.
    Half sections expose those otherwise hidden nut wells; screws are nominal.
    """
    v=Views(render,output)
    def emit(*args,**kwargs):
        v.paths.append(compact_view(render,output,*args,**kwargs))
    # Robot upright, so up and front read at a glance; the builder works with
    # the base on its side. Collar and uprights lifted to show the screw path
    # (screws at X0/Y±26.5 up through the FB01 top wall into the foot nuts).
    wall=clipped(v.parts(['FB01']),[[-40,-95,-10],[40,95,-1.9]])
    for m in wall:m['guide_color']=(180,191,202)
    # Only the front upright goes on here; the rear one follows the
    # shoulder-servo bracket.
    parts=wall+[dict(m,v=m['v']+[0,0,10]) for m in v.parts(['P01'],0)]
    parts+=[dict(m,v=m['v']+[0,0,26]) for m in clipped(v.parts(['P43']),[[-6,-32,0],[6,-20,45]])]
    parts+=hardware(3,16,[0,-26.5,-30],[0,0,1])
    arrows=[([0,-26.5,-27],[0,-26.5,-12]),([0,-26.5,9],[0,-26.5,21])]
    emit('frame-uprights-fastening',parts,[.9,-1,.5],
         'The front upright and the lower collar on the top wall of the base, screwed up from inside',
         arrows=arrows,
         labels=[('M3 × 16',[0,-26.5,-30],(28,395)),('P43',[5,-26.5,60],(420,40)),
                 ('P01',[39.9,0,15],(490,215)),('Front',[0,-93,-6],(28,300)),
                 ('FB01 top wall',[30,40,-2],(330,395))],label_size=32)
    # R33 light brackets sit behind the front upright: P11 on the Z22 bore,
    # P42 on the Z90 bore. Each bore is countersunk into P43's front face
    # (Y-31), so a 14 mm overall countersunk screw ends at Y-17. The nut drops
    # into the bracket's top slot (Y-20 to -17.6) and rests on its ledge.
    from guide_fasteners import screw
    for name,bracket,z,post_z,pad in [('lower','P11',22,[0,34],[23.15,3,20]),
                                     ('upper','P42',90,[78,114.3],[14.3,-2.3,90])]:
        parts=clipped(v.parts(['P43']),[[-6,-32,post_z[0]],[6,-21,post_z[1]]])
        parts+=[dict(m,v=m['v']+[0,10,0]) for m in v.parts([bracket])]
        parts+=screw(3,14,[0,-44,z],[0,1,0],head='countersunk')
        parts+=[m3_nut([0,-8.8,z+13])]
        emit(f'front-light-bracket-{name}',parts,[1,-.55,.8],
             f'Fasten {bracket} behind the front upright: nut into the top slot, countersunk screw from the front',
             arrows=[([0,-8.8,z+9],[0,-8.8,z+3]),([0,-40,z-6],[0,-33,z-6]),([0,-3,z-12],[0,-13,z-12])],
             labels=[('M3 × 14 countersunk',[0,-40,z],(28,40)),('M3 nut',[0,-8.8,z+15],(420,40)),
                     (bracket,pad,(450,330)),('P43',[5,-26.5,z-10],(40,330))],label_size=32)
    # P12 bears on P02's rear face (Y31) and its own rear face is Y38.4. One
    # backpack-carrier M3x18 holds it on the Z46 nut until the carrier is fitted.
    parts=clipped(v.parts(['P02']),[[-6,21,26],[6,32,66]])
    parts+=[dict(m,v=m['v']+[0,16,0]) for m in v.parts(['P12'])]
    parts+=hardware(3,18,[0,70,46],[0,-1,0])
    emit('middle-light-bracket',parts,[.55,1.2,.9],
         'Hold P12 on the back of the rear upright and screw it into the middle nut',
         arrows=[([0,84,46],[0,75,46]),([-12,52,46],[-12,40,46])],
         labels=[('M3 × 18',[0,73,46],(420,40)),('P12',[25,45,52],(40,60)),
                 ('P02',[5,26.5,30],(40,380))],label_size=32)
    # Each nut well (X±4, |Y| 12 to 18) runs through P03 from Z58 to Z74, open
    # at both ends: the upper nut goes in from above, between the servos, and
    # the lower nut from below, so neither screw blocks the other nut.
    servos=v.parts(['P03'])+v.parts(['E01'],0)+v.parts(['E01'],1)
    # P03 slides in from behind, under the upper light bracket P42, before the
    # rear upright P02 is fitted.
    behind=[dict(m,v=m['v']+[0,45,0]) for m in servos]
    parts=v.parts(['P01'],0)+v.parts(['P43'])+v.parts(['P11'])+v.parts(['P42'])+behind
    emit('shoulder-carrier-insertion',parts,[1,1.3,.6],
         'Slide P03 with both servos forward under P42 until it meets the front upright P43',
         arrows=[([0,75,52],[0,30,52])],
         labels=[('P03',[10,60,62],(470,300)),('P42',[0,-15,95],(40,60)),
                 ('P43',[0,-26.5,40],(40,330)),('P11',[25,-10,20],(300,400))],label_size=32)
    for name,sign,upright in [('front',-1,'P43'),('rear',1,'P02')]:
        frame=v.parts(['P43'])+v.parts(['P42'])+servos+(v.parts(['P02']) if name=='rear' else [])
        parts=clipped(frame,[[-45,-35,40],[45,35,106]]);arrows=[]
        parts+=[m3_nut([0,sign*15,82]),m3_nut([0,sign*15,50])]
        arrows+=[([0,sign*15,78.5],[0,sign*15,73]),([0,sign*15,53.5],[0,sign*15,59])]
        for z in [62,70]:
            parts+=hardware(3,16,[0,sign*58,z],[0,-sign,0])
            arrows.append(([0,sign*41,z],[0,sign*33,z]))
        emit('shoulder-carrier-'+name,parts,[1,sign*.8,.3],
             f'Fasten P03 to the {name} upright: upper nut from above, lower nut from below',
             arrows=arrows,
             labels=[('2 × M3 × 16',[0,sign*58,70],(28,38)),
                     (upright,[5,sign*26,48],(450,395)),
                     ('P03',[8,0,70],(440,250)),
                     ('2 × M3 nuts',[0,sign*15,82],(28,395))],label_size=32)
    links=v.parts(['B02'],0)+v.parts(['B02'],1)
    for i,m in enumerate(links):m['guide_color']=(164,176,194) if i==0 else (131,132,168)
    pin=v.parts(['B09'],2)
    for m in pin:
        m['guide_color']=(119,135,157)
        m['v']=m['v']+[0,0,18]
    # Pin occurrence 2 has an unrotated local vertical axis; its transform
    # supplies the joint's exact center, rather than a hand-estimated point.
    transform=np.array(pin[0]['source']['transform']).reshape(4,4)
    x,y=transform[:2,3]*10
    emit('belt-pin-insertion',links+pin,[.8,-1,.9],
         'Nest the two link ends and push the B09 pin down through the aligned joint',
         arrows=[([x,y,69.7],[x,y,60.4])],
         labels=[('B09',[x,y,77],(360,40)),('B02',links[0]['v'].mean(0),(420,330)),
                 ('B02',links[1]['v'].mean(0),(48,335))])
    # The rear pin uses its unchanged assembly transform; only P35's roots changed.
    shell=clipped(v.parts(['P35']),[[24,22,46],[39,37,65]])
    rear=clipped(v.parts(['B01']),[[24,12,48],[42,32,63]])
    for m in shell:m['guide_color']=(224,221,203)
    for m in rear:m['guide_color']=(131,132,168)
    rear_pin=v.parts(['B09'],0)
    transform=np.array(rear_pin[0]['source']['transform']).reshape(4,4)
    x,y=transform[:2,3]*10
    for m in rear_pin:
        m['guide_color']=(119,135,157)
        m['v']=m['v']+[0,0,16]
    emit('backpack-belt-pin',shell+rear+rear_pin,[1,-1,.65],
         'Nest the rear link between the backpack tabs and insert its pin from above',
         arrows=[([x,y,68],[x,y,60.4])],
         labels=[('B09',[x,y,75],(350,40)),('P35',[30,32,61],(38,345)),
                 ('B01',[35,17,56],(400,345))])
    parts=v.parts(['B01','B02','B03','B04'])
    for m in parts:m['guide_color']=(157,168,184)
    # No pin explosion or backpack hides the arrangement being selected here.
    # The action closeup separately explains the fastening operation.
    labels=[]
    for m in parts:
        center=m['v'].mean(0)
        if m['id']=='B01':labelpos=(455,110)
        elif m['id']=='B04':labelpos=(54,110)
        elif m['id']=='B03':labelpos=(272,398)
        elif m['occ']==0:labelpos=(480,265)
        elif m['occ']==1:labelpos=(400,363)
        elif m['occ']==2:labelpos=(130,363)
        else:labelpos=(55,265)
        labels.append((m['id'],center,labelpos))
    emit('belt-link-order',parts,[0,-.3,1.8],
         'Arrange B01, B02, B02, B03, B02, B02 and B04 into the belt',labels=labels)
    render.meshes=v.original
    return v.paths
