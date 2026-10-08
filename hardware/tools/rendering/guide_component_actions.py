"""Bench assembly views using accepted printed surfaces and component details."""
import numpy as np
from guide_closeups import Views, compact_view, clipped
from guide_fasteners import screw, hex_nut


def button_leads(parts):
    """Four illustrative soldered lead ends; no length or installed route implied."""
    import trimesh
    from guide_closeups import item
    result=[]
    for tab in parts:
        if tab.get('component_detail') != 'button terminal':continue
        center=tab['v'].mean(0)
        joint=trimesh.creation.icosphere(subdivisions=2,radius=.85)
        joint.apply_translation(center+[0,0,-1.5])
        wire=trimesh.creation.cylinder(.65,16,sections=20)
        wire.apply_translation(center+[0,0,-9.5])
        sleeve=trimesh.creation.cylinder(1.05,6,sections=20)
        sleeve.apply_translation(center+[0,0,-2.5])
        for geometry,color in [(joint,(180,188,195)),(wire,(74,94,118)),(sleeve,(43,49,56))]:
            row=item(geometry,'E17',color);row['component_detail']='illustrative button lead';row['root']=tab['root'];row['source']=tab['source'];result.append(row)
    return result


def render_component_actions(render, output):
    v=Views(render,output)
    def emit(*args,**kwargs):v.paths.append(compact_view(render,output,*args,label_size=32,**kwargs))
    def moved(rows,offset):return [dict(m,v=m['v']+offset) for m in rows]
    button=v.parts(['E17']);button+=button_leads(button);plate=v.parts(['FB20'])
    # Accepted FB01 pockets: top Z=-6.2, mouth Z=-9.0. The foot column
    # blocks the right axial path; load that nut laterally from smaller X.
    shell=clipped(v.parts(['FB01']),[[67,-84,-15],[104,-68,0]])
    for m in shell:m['guide_color']=(173,187,199)
    left=hex_nut(3,[73,-76,-18],[0,0,1]);right=hex_nut(3,[88,-76,-7.4],[0,0,1])
    # Align nut Y flats to the source recess; keep X-corner orientation.
    for m in [left,right]:
        center=m['v'].mean(0);a=np.pi/6
        rotation=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
        m['v']=(m['v']-center)@rotation.T+center
    emit('button-enclosure-nuts',shell+[left,right],[.6,1,-1.2],
         'Load the inner M3 nut from the open bottom; slide the foot-post-side M3 nut sideways from the button opening',
         arrows=[([73,-76,-15],[73,-76,-9]),([90,-76,-7.4],[96,-76,-7.4])],
         labels=[('2 × M3 nuts',None,(28,36)),('Inner nut',[73,-76,-18],(425,385)),
                 ('Sideways',[88,-76,-7.4],(28,385))])
    shell=clipped(v.parts(['FB01']),[[65,-92,-13],[105,-60,1]])
    for m in shell:m['guide_color']=(173,187,199)
    # Show the actual installed plate; screws separated only to reveal their
    # entry direction. Their installed seats are Z=-2, 8mm tips at Z=-10.
    parts=shell+plate+button
    for x in [73,97]:parts+=screw(3,8,[x,-76,20],[0,0,-1])
    emit('button-plate-fastening',parts,[.6,-1,1.7],
         'Fit the button plate and insert two M3 by 8 screws from the outside into the base nuts',
         arrows=[([x,-76,9],[x,-76,-1]) for x in [73,97]],
         labels=[('2 × M3 × 8',None,(28,36)),('FB20',[96,-68,-2],(425,385))])
    # Brackets are still loose on the bench. Only the three servos move;
    # Shoulders enter from the open rear (+Y): each P03 arm closes at the front
    # (Y -10 to -6.5). Head enters from the open +X side. Each floor slot
    # (X 10 to 21, Y -3 to 3) takes that servo's cable down to the base.
    shoulders=v.parts(['P03'])+moved([m for m in v.parts(['E01']) if m['occ'] in (0,1)],[0,25,0])
    emit('shoulder-servo-insertion',shoulders,[.35,1,1.25],
         'Slide both shoulder servos into loose P03 from its open rear side',
         arrows=[([25,40,83],[25,26,83]),([-25,40,83],[-25,26,83])],
         labels=[('LEFT',[37,25,96],(30,40)),('RIGHT',[-37,25,96],(470,40)),
                 ('P03',[0,-14,74],(250,40)),('Cable slot',[-15.5,0,68],(400,395))])
    head=v.parts(['P04'])+moved(v.parts(['E01'],2),[25,0,0])
    emit('head-servo-insertion',head,[1.4,-1,.7],
         'Slide the head servo into loose P04 from the open side',
         arrows=[([21,-5,98],[7,-5,98])],
         labels=[('P04',[-5,-22,99],(25,45)),('Slide in',None,(430,385))])
    render.meshes=v.original
    return v.paths
