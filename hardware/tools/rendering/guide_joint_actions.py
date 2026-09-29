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
    for name,sign,occ in [('front',-1,1),('rear',1,0)]:
        ymin,ymax=sorted([sign*10,sign*33])
        parts=clipped(v.parts(['P02'],occ)+v.parts(['P03']),[[-6,ymin,57],[0,ymax,75]])
        for m in parts:
            m['guide_color']=(111,136,170) if m['id']=='P02' else (137,128,170)
        arrows=[]
        for z in [62,70]:
            parts.append(m3_nut([0,sign*16.8,z]))
            parts+=hardware(3,16,[0,sign*52,z],[0,-sign,0])
            arrows.append(([0,sign*35.5,z],[0,sign*31,z]))
        emit('shoulder-carrier-'+name,parts,[1,sign*.55,.45],
             f'Fasten the {name} shoulder-carrier joints while holding the loose nuts',
             arrows=arrows,
             labels=[('2 × M3 × 16',None,(28,38)),
                     ('P02',[0,sign*26,73],(400,90)),
                     ('P03',[0,sign*12,73],(420,330)),
                     ('M3 nuts',[0,sign*16.8,62],(210,391))])
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
