"""Narrow assembly views from accepted meshes, with nominal fastening hardware."""
import base64
import html
import itertools
import numpy as np
import trimesh

INK = '#22384e'
BG = '#f3f7fa'


def item(mesh, name, color=None):
    row = dict(id=name, occ=0, root=name, v=mesh.vertices, f=mesh.faces,
               source={}, flat_shading=True)
    if color: row['guide_color'] = color
    return row


def hardware(d, length, seat, axis):
    from guide_fasteners import screw
    return screw(d, length, seat, axis)


def ring(center, axis, outer, inner, height, name='Nut', sections=48):
    from guide_fasteners import washer
    return washer(center, axis, outer, inner, height, name=name)


def nut(center, axis):
    from guide_fasteners import hex_nut
    return hex_nut(2, center, axis)


class Views:
    def __init__(self, render, output):
        self.render=render;self.output=output;self.original=render.meshes;self.paths=[]

    def parts(self, ids, occurrence=None):
        return [dict(m) for m in self.original if m['id'] in ids and
                (occurrence is None or m['occ']==occurrence)]

    def emit(self, name, parts, camera, title, notes, arrows=(), marks=()):
        self.render.meshes=parts
        points=np.concatenate([m['v'] for m in parts]);bounds=[points.min(0)-2,points.max(0)+2]
        self.render.render('closeup-'+name,dict(select=['all'],camera=camera,clean=True,
                    size=[840,720],margin=55,frame_world_bounds=np.array(bounds).tolist()))
        png=(self.output/('closeup-'+name+'.png')).read_bytes()
        z=np.array(camera,float);z/=np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x);R=np.array([x,y,z]).T
        corners=np.array(list(itertools.product(*zip(*bounds))))@R
        lo=corners[:,:2].min(0);hi=corners[:,:2].max(0);span=hi-lo;mid=(lo+hi)/2
        scale=min(730/max(span[0],1),610/max(span[1],1))
        def project(p):
            q=np.array(p)@R
            return ((q[0]-mid[0])*scale/2+210,240-(q[1]-mid[1])*scale/2)
        body=f'<image x="0" y="60" width="420" height="360" href="data:image/png;base64,{base64.b64encode(png).decode()}"/>'
        for a,b in arrows:
            a,b=project(a),project(b)
            body+=f'<path d="M{a[0]:.2f},{a[1]:.2f}L{b[0]:.2f},{b[1]:.2f}" fill="none" stroke="#a95522" stroke-width="3" marker-end="url(#arrow)"/>'
        for label,p in marks:
            x,y=project(p);body+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="14" fill="#fff5d4" stroke="#8b4c22"/>'+text(x,y+8,label,anchor='middle')
        self.save(name,title,body,notes)

    def save(self,name,title,body,notes):
        height=466+30*len(notes)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 {height}" role="img"><title>{html.escape(title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#a95522"/></marker></defs><rect width="420" height="{height}" fill="{BG}"/><g font-family="Arial, sans-serif">'+text(18,32,title)+body
        svg+=''.join(text(18,450+i*30,note) for i,note in enumerate(notes))+'</g></svg>'
        (self.output/(name+'.svg')).write_text(svg)
        self.paths.append('assets/community/'+name+'.svg')


def text(x,y,value,anchor='start'):
    return f'<text x="{x}" y="{y}" fill="{INK}" font-size="22" text-anchor="{anchor}">{html.escape(str(value))}</text>'


def clipped(parts, bounds):
    result=[]
    for m in parts:
        mesh=trimesh.Trimesh(m['v'],m['f'],process=False)
        for axis in range(3):
            for side,sign in [(0,1),(1,-1)]:
                normal=np.zeros(3);normal[axis]=sign;origin=np.zeros(3);origin[axis]=bounds[side][axis]
                vertices,faces,_=trimesh.intersections.slice_faces_plane(mesh.vertices,mesh.faces,normal,origin)
                mesh=trimesh.Trimesh(vertices,faces,process=False)
        if len(mesh.faces):
            row=dict(m,v=mesh.vertices,f=mesh.faces,flat_shading=True)
            row.pop('normals',None);row.pop('corner_normals',None);result.append(row)
    return result


def pose_parts(parts, rotation):
    """Rigid display rotation; source triangles and assembly coordinates stay intact."""
    result=[]
    for mesh in parts:
        row=dict(mesh,v=mesh['v']@rotation.T)
        row.pop('normals',None);row.pop('corner_normals',None)
        result.append(row)
    return result


def render_closeups(render, output):
    v=Views(render,output)
    ref=next(m for m in v.original if m['id']=='P06' and m['occ']==0)
    T=np.array(ref['source']['transform']).reshape(4,4);basis=T[:3,:3];origin=T[:3,3]*10
    # Eye-local X is horizontal, Y points down the face, Z points inside the head.
    # Put head-up along drawing Z, so upper-edge channels are actually at the top.
    orient=np.array([[1,0,0],[0,0,-1],[0,1,0]])
    def ep(p):return np.array(p)@orient
    def eye(ids,offset=None):
        out=[]
        for m in v.parts(ids,0):
            p=(m['v']-origin)@basis+np.array((offset or {}).get(m['id'],[0,0,0]))
            r=dict(m,v=p@orient)
            if m['id']=='EYEFOAM':r['guide_color']=(239,240,226)
            r.pop('normals',None);r.pop('corner_normals',None);out.append(r)
        return out
    # Film is a zero-thickness rounded blank, shown above the recess for access.
    outline=[]
    for cx,cy,start in [(2.1,.1,0),(-2.1,.1,90),(-2.1,-.1,180),(2.1,-.1,270)]:
        for a in np.linspace(start,start+90,16):
            a=np.deg2rad(a);outline.append([cx+4.2*np.cos(a),cy+4.2*np.sin(a),10])
    fv=np.array([[0,0,10]]+outline);ff=[[0,i+1,(i+1)%len(outline)+1] for i in range(len(outline))]
    film=item(trimesh.Trimesh(ep(fv),ff,process=False),'Clear film',(168,210,230))
    v.emit('eye-film-insertion',eye(['GS11'])+[film],[.45,1,.55],'Seat the clear film first',
           ['12.6 × 8.6 mm blank · R4.2 corners','Bow gently beneath the front lip','One film piece per eye'],arrows=[(ep([0,0,9]),ep([0,0,-1]))])
    v.emit('eye-foam-insertion',eye(['GS11','EYEFOAM'],{'EYEFOAM':[0,0,12]}),[.45,1,.55],'Place foam behind the film',
           ['14 × 10 mm patch · 4 mm thick','Foam sits inside the housing','Keep the mounting holes clear'],arrows=[(ep([0,0,12]),ep([0,0,2]))])
    parts=eye(['GS11'])+[nut(ep([x,-15,-1.8]),ep([0,0,1])) for x in [-9,9]]
    v.emit('eye-housing-nuts',parts,[.25,1,.65],'Load the two housing nuts',
           ['2 × M2 nuts · enter at the top','Slide beneath each retaining roof','Keep the broad faces flat · no glue'],arrows=[(ep([x,-13,-1.8]),ep([x,-1,-1.8])) for x in [-9,9]])
    parts=eye(['P06'])+[nut(ep([0,y,0]),ep([0,0,1])) for y in [-4.318,4.318]]
    v.emit('eye-board-nuts',parts,[.35,-1,.55],'Load the two board nuts',
           ['2 × M2 nuts in P06','This side faces the foam','Seat the nuts in the rectangular slots'],arrows=[(ep([0,y,.8]),ep([0,y,5])) for y in [-4.318,4.318]])
    parts=eye(['P06','E03'])
    for y in [-4.318,4.318]:parts+=hardware(2,6,ep([0,y,17]),ep([0,0,-1]))+[nut(ep([0,y,5]),ep([0,0,1]))]
    v.emit('eye-board-fastening',parts,[.45,1,.5],'Screw the LED board to P06',
           ['2 × M2 × 6 · no washers','LED faces the foam opening','Both sockets face inside the head'],arrows=[(ep([0,y,16]),ep([0,y,10.57])) for y in [-4.318,4.318]])
    wall=clipped(eye(['GS20']),[[-20,-1,-14],[20,8,14]])
    for m in wall:m['guide_color']=(110,141,203)
    parts=wall+eye(['GS11'],{'GS11':[0,0,-8]})
    parts += [nut(ep([x,0,-9.8]),ep([0,0,1])) for x in [-9,9]]
    v.emit('eye-housing-seating',parts,[.75,-1,.45],'Seat the eye housing from outside',
           ['GS11 · one housing shown','Blue: head wall cutaway','Housing nuts already in place'],
           arrows=[(ep([0,0,-7]),ep([0,0,-1]))])
    parts=eye(['GS11','P06','E03'],{'GS11':[0,0,-5],'P06':[0,0,9],'E03':[0,0,9]})
    wall=clipped(eye(['GS20']),[[-16,-1,-12],[16,8,12]])
    for m in wall:
        m['flat_shading']=False;m['guide_color']=(110,141,203)
    parts+=wall
    for x in [-9,9]:parts+=hardware(2,10,ep([x,0,23]),ep([0,0,-1]))+[ring(ep([x,0,19]),ep([0,0,1]),2.185,1.155,.25,'Thin washer'),nut(ep([x,0,-6.8]),ep([0,0,1]))]
    v.emit('eye-cassette-fastening',parts,[.9,1,.45],'Fit the cassette from inside',
           ['2 × M2 × 10 + thin washers','Through P06 and the head wall','Into the two housing nuts','Blue: a cutaway of the head wall'],arrows=[(ep([x,0,22]),ep([x,0,8])) for x in [-9,9]])
    parts=v.parts(['GS20','GS11','GS12','P06','E03'])
    for ref in v.parts(['P06']):
        t=np.array(ref['source']['transform']).reshape(4,4)
        def world(p):return np.array(p)@t[:3,:3].T+t[:3,3]*10
        axis=t[:3,:3]@np.array([0,0,-1])
        for x in [-9,9]:parts+=hardware(2,10,world([x,0,7.75]),axis)+[ring(world([x,0,7.625]),axis,2.185,1.155,.25,'Thin washer')]
        for yy in [-4.318,4.318]:parts+=hardware(2,6,world([0,yy,10.57]),axis)
    v.emit('eye-installed-inside',parts,[0,1,-1.3],'Both eyes, seen from inside',
           ['Fit the eyes before the mouth','Short screws hold each LED board','Outer screws hold each cassette','Keep all four sockets accessible'])
    # Servo-ear coordinates come from accepted carrier bores and reference ears.
    # Show whole purchased reference envelopes; never slice them into hollow boxes.
    parts=clipped(v.parts(['P03']),[[20,-30,65],[28,25,104]])+[nut([16,0,z],[1,0,0]) for z in [71,98.7]]
    v.emit('shoulder-servo-nuts',parts,[-1,1,.6],'Load the shoulder-servo nuts',
           ['2 × M2 nuts per servo · 4 total','Press into the inner hex pockets','One side shown · repeat opposite'],arrows=[([17,0,z],[23.9,0,z]) for z in [71,98.7]])
    parts=v.parts(['P03'])+v.parts(['E01'],0)
    for z in [71,98.7]:parts+=hardware(2,6,[36,0,z],[-1,0,0])+[nut([23.9,0,z],[1,0,0])]
    v.emit('shoulder-servo-fastening',parts,[1,1,.55],'Fasten both shoulder servos',
           ['2 × M2 × 6 per servo · 4 total','Screw → servo ear → P03 → nut','Fit before mounting P03 to frame'],arrows=[([35,0,z],[28.5,0,z]) for z in [71,98.7]])
    parts=v.parts(['P04'])+[nut([0,y,94],[0,0,1]) for y in [-19,8.7]]
    v.emit('head-servo-nuts',parts,[1,-.7,-1],'Load the head-servo nuts',
           ['2 × M2 nuts in P04','Press into underside hex pockets','View from beneath the bracket'],arrows=[([0,y,95],[0,y,100.2]) for y in [-19,8.7]])
    parts=v.parts(['P04'])+v.parts(['E01'],2)
    for y in [-19,8.7]:parts+=hardware(2,6,[0,y,112],[0,0,-1])+[nut([0,y,100.2],[0,0,1])]
    v.emit('head-servo-fastening',parts,[.9,-1,1.2],'Fasten the head servo',
           ['2 × M2 × 6 enter from above','Screw → servo ear → P04 → nut','Fit before mounting P04 to frame'],arrows=[([0,y,111],[0,y,104.8]) for y in [-19,8.7]])
    # Horn product geometry is not in CAD: use an explicitly schematic outline.
    body='<circle cx="210" cy="240" r="140" fill="#e3dccb" stroke="#675d4b" stroke-width="3"/>'
    body+='<circle cx="210" cy="240" r="25" fill="'+BG+'" stroke="#675d4b" stroke-width="2"/>'
    for x in [103,317]:body+=f'<circle cx="{x}" cy="240" r="13" fill="{BG}" stroke="#a95522" stroke-width="3"/>'
    body+='<path d="M103 285V320M317 285V320M103 305H317" fill="none" stroke="#22384e" stroke-width="2"/>'+text(210,348,'≈18 mm hole centers',anchor='middle')
    v.save('horn-drill-pair','Drill one opposite pair',body,
           ['3 original round servo horns','Open only the selected pair to Ø2.2','Keep the center opening unchanged','Drill off the servo · support the disk'])
    body='<path d="M65 195H355V220H253V325H167V220H65Z" fill="#e3dccb" stroke="#675d4b" stroke-width="3"/>'
    body+='<path d="M194 195V308L201 299L210 308L219 299L226 308V195" fill="'+BG+'" stroke="#675d4b" stroke-width="2"/>'
    body+='<path d="M105 185V230M315 185V230" stroke="'+BG+'" stroke-width="12"/>'
    body+=text(210,145,'Flat disk against printed recess',anchor='middle')+text(210,368,'Long splined hub → servo shaft',anchor='middle')
    v.save('horn-side-orientation','Which side faces the servo?',body,
           ['Side section · shape is schematic','Two offset screws attach the print','Center screw attaches to the shaft','Fit on the shaft only at the fit position'])
    render.meshes=v.original
    return v.paths


def _audio_case(x0,x1,z0,z1,y0,y1,radius,name,color):
    outline=[]
    for x,z,start in [(x1-radius,z1-radius,0),(x0+radius,z1-radius,90),
                      (x0+radius,z0+radius,180),(x1-radius,z0+radius,270)]:
        for angle in np.linspace(start,start+90,12,endpoint=False):
            a=np.deg2rad(angle);outline.append([x+radius*np.cos(a),z+radius*np.sin(a)])
    n=len(outline);cx=(x0+x1)/2;cz=(z0+z1)/2
    vertices=[[x,y,z] for y in [y0,y1] for x,z in outline]+[[cx,y0,cz],[cx,y1,cz]]
    faces=[]
    for i in range(n):
        j=(i+1)%n;faces.extend([[2*n,i,j],[2*n+1,n+j,n+i],[i,n+i,n+j],[i,n+j,j]])
    return item(trimesh.Trimesh(vertices,faces,process=False),name,color)


def audio_module_model():
    """Waveshare 18833 recognition geometry; envelope/placement stays CAD-derived.

    Rounded case, USB-A shell and opposite four-pin header follow the official
    usb-to-audio-2_2.jpg photo. Connector details are illustrative, not fit CAD.
    """
    def box(size, center, name, color):
        mesh=trimesh.creation.box(size);mesh.apply_translation(center)
        return item(mesh,name,color)
    rows=[]
    # Rounded X/Z outline, extruded in Y; seam separates the two case halves.
    for y0,y1,color in [(-87.3,-80.2,(40,43,48)),(-80.2,-79.9,(17,19,22)),(-79.9,-72.7,(46,49,55))]:
        rows.append(_audio_case(-14.5,38.5,-37.75,-14.25,y0,y1,3,'Audio case',color))
    metal=(188,198,207);cream=(222,222,206);gold=(186,143,62)
    # USB-A male: thin metal walls, hollow end, tongue and four contact strips.
    # The two retention windows are open mesh gaps, not painted cubes.
    for y in [-82.1,-77.9]:
        for xa,xb,za,zb in [(-26.5,-22,-32,-20),(-19.5,-14.5,-32,-20),
                            (-22,-19.5,-32,-29.8),(-22,-19.5,-27.4,-24.6),(-22,-19.5,-22.2,-20)]:
            rows.append(box([xb-xa,.3,zb-za],[(xa+xb)/2,y,(za+zb)/2],'USB metal shell',metal))
    for z in [-31.85,-20.15]:
        rows.append(box([12,4.2,.3],[-20.5,-80,z],'USB metal edge',metal))
    rows.append(box([10,1.2,10.5],[-19.5,-79.1,-26],'USB insulator',cream))
    for z in [-29,-27,-25,-23]:
        rows.append(box([7,.12,1],[-21,-79.76,z],'USB contact',gold))
    # Four-pin output socket at +X: shroud, recessed dark opening and pins.
    rows.append(box([.15,4.4,10.6],[38.58,-80,-26],'Speaker socket opening',(19,22,26)))
    for y in [-82.4,-77.6]:rows.append(box([1.8,.65,11.8],[38.3,y,-26],'Speaker socket rim',cream))
    for z in [-31.6,-20.4]:rows.append(box([1.8,4.8,.65],[38.3,-80,z],'Speaker socket rim',cream))
    for z in [-29,-27,-25,-23]:rows.append(box([1,.6,.6],[39,-80,z],'Speaker contact',metal))
    for z in [-17.05,-34.95]:
        mesh=trimesh.creation.cylinder(1,.18,sections=32)
        mesh.apply_transform(trimesh.geometry.align_vectors([0,0,1],[0,1,0]));mesh.apply_translation([35.1,-87.4,z])
        rows.append(item(mesh,'Microphone opening',(7,9,12)))
    rows.append(box([4.5,.1,16],[-10.3,-87.4,-26],'USB label',(102,166,57)))
    return rows


def audio_cable_ends(separated=True):
    """USB-A extension socket and keyed four-wire plug; short leads show exits only."""
    def box(size,center,name,color):
        mesh=trimesh.creation.box(size);mesh.apply_translation(center)
        return item(mesh,name,color)
    rows=[];dark=(39,42,47);metal=(183,193,203);cream=(228,226,212)
    # Socket mouth faces +X, mating with the module's -X USB-A plug.
    front=-34 if separated else -15
    rows.append(_audio_case(front-19,front,-34,-18,-84.25,-75.75,1.2,'USB extension housing',dark))
    rows.append(box([.2,6,13],[front+.12,-80,-26],'USB socket opening',(8,10,13)))
    for y in [-83,-77]:rows.append(box([.35,.35,13.4],[front+.25,y,-26],'USB socket lip',metal))
    for z in [-32.7,-19.3]:rows.append(box([.35,6,.35],[front+.25,-80,z],'USB socket lip',metal))
    rows.append(box([.35,1.2,10.5],[front+.4,-81.4,-26],'USB socket tongue',cream))
    for z in [-29,-27,-25,-23]:rows.append(box([.42,.2,1],[front+.45,-80.72,z],'USB socket contact',(186,143,62)))
    for x,r,length in [(front-21,3.2,4),(front-26,1.8,6)]:
        mesh=trimesh.creation.cylinder(r,length,sections=24);mesh.apply_transform(trimesh.geometry.align_vectors([0,0,1],[1,0,0]));mesh.apply_translation([x,-80,-26])
        rows.append(item(mesh,'USB cable strain relief' if r>2 else 'USB cable',dark))
    for x in [front-20,front-21.5,front-23]:
        rows.append(box([.45,6.8,6.8],[x,-80,-26],'USB strain-relief rib',(58,62,68)))
    # White four-position cable housing, with key rib and four wire exits.
    tip=49 if separated else 39
    rows.append(box([6,4,9.4],[tip+3,-80,-26],'Four-wire speaker plug',cream))
    rows.append(box([4,.65,4],[tip+3,-82.25,-26],'Speaker plug key',(198,199,186)))
    for z,color in zip([-29,-27,-25,-23],[(43,45,49),(169,48,35),(43,45,49),(169,48,35)]):
        mesh=trimesh.creation.cylinder(.62,14,sections=16);mesh.apply_transform(trimesh.geometry.align_vectors([0,0,1],[1,0,0]));mesh.apply_translation([tip+13,-80,z])
        rows.append(item(mesh,'Speaker cable lead',color))
        rows.append(box([.2,1.2,1.2],[tip-.1,-80,z],'Speaker plug contact opening',(54,56,53)))
    return rows


def render_audio_closeups(render, output):
    """Accepted cradle/lid surfaces and nominal case/fasteners, viewed from below."""
    from guide_context_actions import _compact
    v=Views(render,output)
    def shift(parts, dz):
        result=[]
        for m in parts:
            row=dict(m,v=m['v']+np.array([0,0,dz]))
            row.pop('normals',None);row.pop('corner_normals',None)
            result.append(row)
        return result
    def rearward(parts, distance):
        result=[]
        for m in parts:
            row=dict(m,v=m['v']+np.array([0,distance,0]))
            row.pop('normals',None);row.pop('corner_normals',None)
            result.append(row)
        return result
    def box(size, center, name, color):
        mesh=trimesh.creation.box(size);mesh.apply_translation(center)
        return item(mesh,name,color)
    cradle=v.parts(['FB24'])
    for m in cradle:m['guide_color']=(232,230,216)
    # The lid nut slots open toward the cradle's central interior, not upward.
    # Show the right pocket; the left receives its nut in the opposite X direction.
    pocket=clipped(cradle, [[36,-86,-40],[58,-71,-29]])
    center=np.array([40,-78.35,-35.2])
    loose=nut(center,[0,0,1])
    # Slot width is 4.3 mm in Y; align the M2 nut's 4 mm flats with those walls.
    turn=trimesh.transformations.rotation_matrix(np.pi/6,[0,0,1])[:3,:3]
    loose['v']=(loose['v']-center)@turn.T+center
    _compact(v,'audio-cradle-lid-nuts',pocket+[loose],[-1,1,-.7],
        'Slide an M2 nut sideways from the cradle interior into the right lid pocket; repeat mirrored at the left end',
        arrows=[([43,-78.35,-35.2],[48.5,-78.35,-35.2])],
        labels=[('M2',[40,-78.35,-35.2],(20,390)),
                ('FB24',[53,-77,-33],(460,45))],label_size=32)
    # Keep the front of the enclosure visible: FB24 mounts inside it, rather
    # than being a loose bench assembly. Cut away unrelated rear/side walls.
    base=clipped(v.parts(['FB01']), [[-76,-96,-54],[76,-63,0]])
    for m in base:m['guide_color']=(164,178,189)
    grille=v.parts(['FB41'])
    for m in grille:m['guide_color']=(151,95,62)
    context=base+grille
    camera=[.35,1,-1.6]
    mount=context+cradle
    arrows=[]
    for x in [-62,0,62]:
        mount+=hardware(3,6,[x,-78.2,-25.2],[0,0,1])
        arrows.append(([x,-78.2,-18.6],[x,-78.2,-10.2]))
    _compact(v,'audio-cradle-base-mount',mount,camera,
        'Mount the empty cradle inside the base behind the front grille; insert three M3 by 6 screws from the open bottom',
        arrows=arrows,
        labels=[('3 × M3 × 6',[-62,-78.2,-25.2],(20,390)),
                ('Base',[69,-93,-32],(465,55)),
                ('FB24',[38,-72.5,-9.2],(20,55))],label_size=32)
    source_points=np.concatenate([m['v'] for m in v.parts(['E14']) if m.get('component_detail') in (None, 'Audio case')])
    if not np.allclose([source_points.min(0),source_points.max(0)],
                       [[-14.5,-87.3,-37.75],[38.5,-72.7,-14.25]],atol=.01):
        raise ValueError('Review audio recognition geometry against changed E14 envelope')
    module=audio_module_model()
    # Explicit illustrative tape thickness: the original case/wall gap is2.9mm.
    # Move the case2.4mm rearward for0.5mm tape; never bridge that gap with thin tape.
    tape=box([35,.5,14],[12,-72.45,-26],'Audio mounting tape',(197,142,77))
    _compact(v,'audio-tape-back',module+rearward([tape],10),[.5,1,.3],
        'Apply mounting tape under one millimetre thick to the back of the audio case, opposite its microphones',
        arrows=[([12,-65,-26],[12,-72.2,-26])],
        labels=[('Back of case',[27,-72.7,-20],(330,45)),
                ('Tape <1 mm',[12,-62.45,-26],(20,390))],label_size=32)
    lid=v.parts(['FB32'])
    for m in lid:m['guide_color']=(219,218,204)
    mounted=context+cradle
    for x in [-62,0,62]:mounted+=hardware(3,6,[x,-78.2,-9.2],[0,0,1])
    for x in [-47,50]:
        center=np.array([x,-78.35,-35.2])
        seated=nut(center,[0,0,1])
        seated['v']=(seated['v']-center)@turn.T+center
        mounted.append(seated)
    _compact(v,'audio-module-seating',mounted+shift(module+[tape],-22),camera,
        'Lift the unplugged audio module into the mounted cradle, microphones facing the front grille; connect cables afterward through the end openings',
        arrows=[([12,-80,-50],[12,-80,-30])],
        labels=[('Front grille',[0,-94,-33],(20,45)),
                ('Audio module',[12,-80,-52],(315,390))],label_size=32)
    # Lid bore centers from accepted FB32 sections: Ø2.3 at X=-47 and50,
    # Y=-78.35. Outer screw bearing face is Z=-41.5; screws enter along +Z.
    taped=rearward(module+[tape],2.4)
    contact=clipped(mounted+taped,[[-2,-96,-45],[58,-62,0]])
    # The clipping helper leaves open sections. Cap the tape at its exact
    # cut plane so its true 0.5 mm edge remains visible in the side view.
    tape_section=trimesh.Trimesh(
        vertices=[[-2.01,-70.3,-33],[-2.01,-69.8,-33],
                  [-2.01,-69.8,-19],[-2.01,-70.3,-19]],
        faces=[[0,1,2],[0,2,3]],process=False)
    contact.append(item(tape_section,'Tape section',(226,153,62)))
    _compact(v,'audio-tape-contact',contact,[-1,.15,-.3],
        'Side cutaway: press the case back onto the inside rear cradle wall; example shows0.5mm tape and2.4mm rearward seating',
        arrows=[([-3,-82,-26],[-3,-70.3,-26])],
        labels=[('Tape',[-1.8,-70.05,-26],(20,45)),
                ('Rear wall',[0,-68.9,-26],(370,390))],label_size=32)
    parts=mounted+taped+rearward(audio_cable_ends(False),2.4)+shift(lid,-22)
    arrows=[]
    for x in [-47,50]:
        parts+=hardware(2,8,[x,-78.35,-77.5],[0,0,1])
        arrows.append(([x,-78.35,-69],[x,-78.35,-64]))
    _compact(v,'audio-lid-fastening',parts,camera,'Fasten the lid from below',
        arrows=arrows,labels=[('2 × M2 × 8',[-47,-78.35,-77.5],(20,390))],label_size=32)
    # Connector identification only: the nominal extension housing is not
    # measured fit geometry and must not be drawn passing through FB24.
    _compact(v,'audio-module-connections',module+audio_cable_ends(),[.35,-1,.5],
             'USB and speaker connection detail; cradle omitted, connector housing clearance must be checked separately',
             arrows=[([-32,-80,-26],[-27,-80,-26]),([47,-80,-26],[41,-80,-26])],
             labels=[('USB-A extension',[-34,-80,-26],(20,45)),
                     ('Microphones',[35.1,-87.4,-17.05],(335,45)),
                     ('4-wire cable',[53,-80,-26],(350,390))],label_size=32)
    render.meshes=v.original
    return v.paths



def compact_view(render,output,name,parts,camera,title,arrows=(),labels=(),label_size=24):
    if name in ('button-enclosure-nuts','button-plate-fastening'):
        rotation=np.diag([1,-1,-1])
        parts=pose_parts(parts,rotation);camera=(rotation@camera).tolist()
        arrows=[(rotation@a,rotation@b) for a,b in arrows]
        labels=[(label,None if point is None else rotation@point,xy) for label,point,xy in labels]
    render.meshes=parts
    points=np.concatenate([m['v'] for m in parts]);bounds=[points.min(0)-2,points.max(0)+2]
    render.render('closeup-'+name,dict(select=['all'],camera=camera,clean=True,
                  size=[1200,840],margin=64,frame_world_bounds=np.array(bounds).tolist()))
    z=np.array(camera,float);z/=np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x);R=np.array([x,y,z]).T
    corners=np.array(list(itertools.product(*zip(*bounds))))@R
    lo=corners[:,:2].min(0);hi=corners[:,:2].max(0);mid=(lo+hi)/2
    scale=min(1072/max(hi[0]-lo[0],1),712/max(hi[1]-lo[1],1))/2
    def project(p):
        q=np.array(p)@R;return ((q[0]-mid[0])*scale+300,210-(q[1]-mid[1])*scale)
    png=(output/('closeup-'+name+'.png')).read_bytes()
    body=f'<image width="600" height="420" href="data:image/png;base64,{base64.b64encode(png).decode()}"/>'
    for a,b in arrows:
        a,b=project(a),project(b)
        path=f'M{a[0]:.2f},{a[1]:.2f}L{b[0]:.2f},{b[1]:.2f}'
        body+=f'<path d="{path}" stroke="white" stroke-width="7"/><path d="{path}" stroke="#a95522" stroke-width="3.5" marker-end="url(#arrow)"/>'
    for label,p,xy in labels:
        if p is not None:
            q=project(p)
            body+=f'<path d="M{xy[0]},{xy[1]+6}L{q[0]:.2f},{q[1]:.2f}" stroke="#526576" stroke-width="1.5"/>'
        body+=f'<text x="{xy[0]}" y="{xy[1]}" font-family="Arial, sans-serif" font-size="{label_size}" font-weight="bold" fill="{INK}" stroke="{BG}" stroke-width="5" paint-order="stroke">{html.escape(label)}</text>'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 420" role="img"><title>{html.escape(title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#a95522"/></marker></defs>{body}</svg>'
    (output/(name+'.svg')).write_text(svg)
    return 'assets/community/'+name+'.svg'

def render_inlet_closeups(render, output):
    """FB21/FB01 mating surfaces from CAD, with nominal supplied jack hardware.

    Plate bores: X80, Z−27/−53, Ø3.4; center bore X80/Z−40, Ø8.2.
    FB01 open slots face inward at Y84 and end at Y86.8. The plate's outer face
    is Y94.5, so its M3×12 screws enter along −Y. E18 is only a clearance
    envelope; the socket opening and supplied washer/nut are recognition aids.
    """
    v=Views(render,output)
    def moved(parts, dy):
        return [dict(m,v=m['v']+[0,dy,0]) for m in parts]
    def hexagon(center, af, bore, thickness):
        from guide_fasteners import hex_nut
        return hex_nut(3, center, [0,1,0], af=af, bore=bore, thickness=thickness)
    def compact(*args, **kwargs):
        v.paths.append(compact_view(render,output,*args,**kwargs))
    plate=v.parts(['FB21']);jack=v.parts(['E18'])
    for m in plate:m['guide_color']=(172,99,55)
    for m in jack:
        if not m.get('component_detail'):m['guide_color']=(161,170,177)
    # The accepted E18 envelope has a solid end. Show the recognizable socket
    # mouth and 2.1 mm center pin without changing the authoritative envelope.
    if not all(m.get('component_detail') for m in jack):
        jack.append(ring([80,97.12,-40],[0,1,0],3.45,1.05,.12,'Socket mouth'))
        jack[-1]['guide_color']=(29,34,40)
    washer=ring([80,107,-40],[0,1,0],5.4,4,.5,'Supplied washer')
    jacknut=hexagon([80,116,-40],11,7.94,1.8)
    washer['guide_color']=jacknut['guide_color']=(183,191,198)
    compact('inlet-jack-mounting',plate+moved(jack,-18)+[washer,jacknut],[1,1,.25],
        'Fit the prepared jack through FB21, then its supplied washer and nut',
        arrows=[([80,79.5,-40],[80,91.3,-40]),([80,113,-40],[80,109,-40]),([80,105,-40],[80,96,-40])],
        labels=[('J1',[80,64,-40],(33,106)),('FB21',[91,94,-34],(270,45)),('Washer',[80,107,-35],(330,390)),('Nut',[80,116,-35],(510,295))])
    shell=clipped(v.parts(['FB01']),[[61,80,-64],[99,96,-16]])
    for m in shell:m['guide_color']=(179,191,203)
    nuts=[hexagon([80,72,z],5.5,3,2.4) for z in [-27,-53]]
    compact('inlet-plate-nuts',shell+nuts,[.6,-1,.25],
        'Place two M3 nuts into the power jack slots from inside the base; hold each until its screw catches',
        arrows=[([80,74,z],[80,84,z]) for z in [-27,-53]],
        labels=[('2 × M3 nuts',[80,72,-27],(40,55)),('FB01',[94,86,-42],(450,350))])
    parts=shell+plate+jack+moved([washer],94.75-107)+moved([jacknut],95.9-116)
    for z in [-27,-53]:parts+=hardware(3,12,[80,122.5,z],[0,-1,0])
    compact('inlet-plate-fastening',parts,[.85,1,.25],
        'Fasten the fitted power jack plate with two M3 by 12 mm screws from outside',
        arrows=[([80,110,z],[80,96,z]) for z in [-27,-53]],
        labels=[('2 × M3 × 12',[80,122.5,-27],(355,52)),('FB21',[90,94,-42],(310,368))])
    render.meshes=v.original
    return v.paths


def render_board_closeups(render, output):
    """Actual board mounting holes/supports, viewed through the open bottom."""
    v=Views(render,output)
    def compact(*args, **kwargs):
        v.paths.append(compact_view(render,output,*args,**kwargs))
    # Preserve all real surfaces of the local support. Cropping removes the
    # rest of the enclosure so the screw/board stack remains visible.
    support=clipped(v.parts(['FB01']),[[-85,-7,-20],[-15,71,-1.9]])
    for m in support:m['guide_color']=(177,189,202)
    pi=v.parts(['E09'])
    for m in pi:
        name=m['source']['path']
        if not m.get('component_detail'):
            m['guide_color']=((36,109,74) if 'PCB' in name else
                              (40,44,49) if 'GPIO' in name else (180,188,193))
    parts=support+pi;arrows=[]
    for x in [-74.5,-25.5]:
        for y in [2.5,60.5]:
            parts+=hardware(2,12,[x,y,-45],[0,0,1])
            parts.append(nut([x,y,-16],[0,0,1]))
            arrows.append(([x,y,-32.5],[x,y,-26]))
    compact('pi-board-fastening',parts,[.55,-.7,-1.2],
        'Fit four M2 by 12 screws through the Pi into its captive nuts',
        arrows=arrows,
        labels=[('4 × M2 × 12',None,(32,40)),
                ('USB · front',[-53.5,-3,-22],(330,385)),
                ('SD · rear',[-50,66,-15],(35,84))])
    support=clipped(v.parts(['FB01']),[[-36,-52,-17],[0,-4,-1.9]])
    for m in support:m['guide_color']=(177,189,202)
    board=v.parts(['E15'])
    # Shared source-body materials also apply to overview/service scenes.
    colored=board
    parts=support+colored;arrows=[]
    for y in [-22.08,-11.92,-44.08,-33.92]:
        parts+=hardware(2,10,[-18,y,-39],[0,0,1])
        parts.append(nut([-18,y,-14],[0,0,1]))
        arrows.append(([-18,y,-28.5],[-18,y,-17]))
    compact('shifter-board-fastening',parts,[.65,-.7,-1.7],
        'Fit S1 nearer the Pi and S2 nearer the front; two M2 by10 screws per board',
        arrows=arrows,
        labels=[('2 × M2 × 10 each',None,(32,40)),
                ('S1',[-18,-17,-25],(55,110)),('S2',[-18,-39,-25],(455,350))])
    render.meshes=v.original
    return v.paths
