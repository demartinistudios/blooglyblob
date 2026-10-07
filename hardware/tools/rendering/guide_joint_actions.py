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
    parts=wall+[dict(m,v=m['v']+[0,0,10]) for m in v.parts(['P01'],0)]
    parts+=[dict(m,v=m['v']+[0,0,26]) for m in clipped(v.parts(['P02']),[[-6,-32,0],[6,32,45]])]
    arrows=[]
    for y in [-26.5,26.5]:
        parts+=hardware(3,16,[0,y,-30],[0,0,1])
        arrows+=[([0,y,-27],[0,y,-12]),([0,y,9],[0,y,21])]
    emit('frame-uprights-fastening',parts,[.9,-1,.5],
         'Both uprights and the lower collar on the top wall of the base, screwed up from inside',
         arrows=arrows,
         labels=[('2 × M3 × 16',[0,-26.5,-30],(28,395)),('P02 × 2',[5,26.5,60],(420,40)),
                 ('P01',[39.9,0,15],(490,215)),('Front',[0,-93,-6],(28,300)),
                 ('FB01 top wall',[30,40,-2],(330,395))],label_size=32)
    # Each nut well (X±4, |Y| 12 to 18) runs through P03 from Z58 to Z74, open
    # at both ends: the upper nut goes in from above, between the servos, and
    # the lower nut from below, so neither screw blocks the other nut.
    frame=v.parts(['P02'],1)+v.parts(['P02'],0)+v.parts(['P03'])+v.parts(['E01'],0)+v.parts(['E01'],1)
    frame=clipped(frame,[[-45,-35,40],[45,35,106]])
    for name,sign in [('front',-1),('rear',1)]:
        parts=list(frame);arrows=[]
        parts+=[m3_nut([0,sign*15,82]),m3_nut([0,sign*15,50])]
        arrows+=[([0,sign*15,78.5],[0,sign*15,73]),([0,sign*15,53.5],[0,sign*15,59])]
        for z in [62,70]:
            parts+=hardware(3,16,[0,sign*58,z],[0,-sign,0])
            arrows.append(([0,sign*41,z],[0,sign*33,z]))
        emit('shoulder-carrier-'+name,parts,[1,sign*.8,.3],
             f'Fasten P03 to the {name} upright: upper nut from above, lower nut from below',
             arrows=arrows,
             labels=[('2 × M3 × 16',[0,sign*58,70],(28,38)),
                     ('P02',[5,sign*26,48],(450,395)),
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
