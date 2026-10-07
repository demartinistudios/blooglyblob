"""Recognizable purchased parts at the accepted reference-envelope positions.

These are presentation geometry, not replacement CAD or measured fit models.
Body placement/size comes from the accepted row. Small lead stubs identify exit
ends only; they do not prescribe routing, cut lengths or capacitor rotation.

References: guide/cartoons.py capacitor(), fuse_holder(), wago(), panel_jack();
community-20260925 catalog refs 018, 020/021 and 032/033. SCHURTER FDI drawing:
48 mm maximum body length, 16 mm diameter, dark-pink 18 AWG factory leads.
Panasonic EEUFR1A102: 10 x16 mm body, 5 mm lead pitch. The jack detail uses the
same front opening/2.1 mm center-pin recognition aids as guide_closeups.
Adafruit 1669 speakers reuse the product-based guide_speaker_actions model.
"""
import numpy as np
import trimesh

DARK = (43, 46, 52)
RIB = (72, 77, 84)
METAL = (192, 201, 208)


def _cylinder(radius, length, center, axis=(1, 0, 0), sections=64):
    mesh = trimesh.creation.cylinder(radius, length, sections=sections)
    mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], axis))
    mesh.apply_translation(center)
    return mesh


def _box(size, center):
    mesh = trimesh.creation.box(size)
    mesh.apply_translation(center)
    return mesh


def _band(x0, x1, radius, center_yz, start, end):
    """Curved sleeve marking on an X-axis cylinder, in radians."""
    angles = np.linspace(start, end, 24)
    vertices = [[x, center_yz[0]+radius*np.cos(a), center_yz[1]+radius*np.sin(a)]
                for x in (x0, x1) for a in angles]
    n = len(angles)
    faces = [[i, i+1, n+i+1] for i in range(n-1)]
    faces += [[i, n+i+1, n+i] for i in range(n-1)]
    return trimesh.Trimesh(vertices, faces, process=False)


def _row(original, mesh, color, feature):
    row = dict(original, v=np.asarray(mesh.vertices), f=np.asarray(mesh.faces),
               guide_color=color, flat_shading=False, component_detail=feature)
    # Preserve id/root/occ/source exactly for scene filters and labels. Source
    # metadata records authority, while these derived vertices are display only.
    row.pop('normals', None)
    row.pop('corner_normals', None)
    return row


def _fuse(original):
    lo, hi = original['v'].min(0), original['v'].max(0)
    center = (lo+hi)/2; length = hi[0]-lo[0]
    if not np.isclose(length, 48, atol=.05):
        raise ValueError('Review fuse recognition geometry against changed envelope')
    rows = []
    # Same stepped recognition profile used by the reviewed product cartoon.
    for left, right, radius in [(0,8.2,4.2),(8,13.2,5.4),(13,16.2,8),
                                (16,22.2,6.9),(22,30.2,6.4),(30,40.2,5.6),(40,46,3.6)]:
        x0, x1 = lo[0]+left*length/46, lo[0]+right*length/46
        rows.append(_row(original, _cylinder(radius,x1-x0,[(x0+x1)/2,*center[1:]]), DARK, 'holder body'))
    for position in (1.5,3.2,4.9,6.6):
        x = lo[0]+position*length/46
        rows.append(_row(original,_cylinder(4.32,.35,[x,*center[1:]]),RIB,'cap grip rib'))
    # Ends are short presentation stubs, not a proposed fuse-to-WAGO route.
    for x in (lo[0]-3,hi[0]+3):
        rows.append(_row(original,_cylinder(1,6,[x,*center[1:]]),(155,53,82),'factory lead stub'))
    return rows


def _capacitor(original):
    # R28 rotates the accepted capacitor envelopes +90 degrees about Z.
    # Build detail in the original X-axis frame, then rotate it back as a unit.
    span=np.ptp(original['v'],axis=0)
    if np.allclose(span,[16,10,10],atol=.05):return _capacitor_x(original)
    if not np.allclose(span,[10,16,10],atol=.05):
        raise ValueError('Review capacitor recognition geometry against changed envelope')
    center=(original['v'].min(0)+original['v'].max(0))/2
    rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]])
    normalized=dict(original,v=(original['v']-center)@rotation+center)
    return [dict(row,v=(row['v']-center)@rotation.T+center)
            for row in _capacitor_x(normalized)]


def _capacitor_x(original):
    lo, hi = original['v'].min(0), original['v'].max(0)
    center = (lo+hi)/2; length = hi[0]-lo[0]
    if not np.allclose(hi-lo,[16,10,10],atol=.05):
        raise ValueError('Review capacitor recognition geometry against changed envelope')
    rows = [_row(original,_cylinder(5,length-.4,center),DARK,'sleeve')]
    rows.append(_row(original,_cylinder(4.6,.18,[lo[0]+.09,*center[1:]]),METAL,'vent end'))
    rows.append(_row(original,_cylinder(4.5,.18,[hi[0]-.09,*center[1:]]),(31,34,39),'rubber seal'))
    # Exposed scored metal vent; markings lie within the accepted body envelope.
    for axis in [(0,1,0),(0,0,1)]:
        rows.append(_row(original,_cylinder(.08,6,[lo[0]+.02,*center[1:]],axis,16),(108,119,129),'vent score'))
    rows.append(_row(original,_band(lo[0]+.6,hi[0]-.6,5.015,center[1:],-1.95,-1.19),(160,170,178),'negative stripe'))
    for x in np.linspace(lo[0]+2,hi[0]-2,4):
        rows.append(_row(original,_band(x-.55,x+.55,5.035,center[1:],-1.73,-1.41),DARK,'minus marking'))
    # Five-millimeter pitch; stripe and negative leg correspond. Straight,
    # short ends only: this scene does not prescribe a soldered wiring route.
    for dz in (-2.5,2.5):
        rows.append(_row(original,_cylinder(.3,4,[hi[0]+2,center[1],center[2]+dz]),METAL,'lead stub'))
    return rows


def _wago(original):
    lo, hi = original['v'].min(0), original['v'].max(0)
    center = (lo+hi)/2
    if not np.allclose(hi-lo,[30,18.6,8.4],atol=.05):
        raise ValueError('Review WAGO recognition geometry against changed envelope')
    # Retain the full accepted outside height by carving lever depth out of the
    # housing, rather than adding levers outside the reference envelope.
    rows = [_row(original,_box([30,18.6,7.2],center+[0,0,.6]),(208,221,227),'housing')]
    for dx in [-12,-6,0,6,12]:
        x = center[0]+dx
        rows.append(_row(original,_box([4.8,12,1.2],[x,center[1]+1,lo[2]+.6]),(238,133,38),'lever'))
        for dy in (-2.5,0,2.5):
            rows.append(_row(original,_box([3.8,.35,.06],[x,center[1]+1+dy,lo[2]-.015]),(179,91,28),'lever grip'))
        rows.append(_row(original,_cylinder(1.15,.1,[x,lo[1]-.015,center[2]-.3],(0,1,0)),(39,44,51),'wire entry'))
    return rows


def _jack(original):
    # Keep the actual accepted body silhouette, adding only front recognition
    # details; the already-reviewed inlet action carries terminal identification.
    lo,hi = original['v'].min(0),original['v'].max(0)
    center=(lo+hi)/2
    front=hi[1]
    # Retain the envelope's stepped silhouette; distinguish its metal nose.
    face_y=original['v'][original['f']][:,:,1].mean(axis=1)
    rows=[]
    for selected,color,feature in [(face_y < 92.5,DARK,'jack body'),
                                   (face_y >= 92.5,METAL,'metal nose')]:
        mesh=trimesh.Trimesh(original['v'],original['f'][selected],process=False)
        mesh.remove_unreferenced_vertices()
        rows.append(_row(original,mesh,color,feature))
    ring=trimesh.creation.annulus(r_min=3.45,r_max=3.95,height=.2,sections=64)
    ring.apply_transform(trimesh.geometry.align_vectors([0,0,1],[0,1,0]))
    ring.apply_translation([center[0],front+.12,center[2]])
    mouth=_cylinder(3.45,.12,[center[0],front+.235,center[2]],(0,1,0))
    pin=_cylinder(1.05,.15,[center[0],front+.32,center[2]],(0,1,0))
    return rows+[_row(original,ring,METAL,'socket rim'),
            _row(original,mouth,(12,17,22),'socket opening'),
            _row(original,pin,METAL,'center pin')]


def _speaker(original):
    """Place the reviewed 1669 recognition model on either side of the base."""
    from guide_speaker_actions import speaker
    lo,hi=original['v'].min(0),original['v'].max(0)
    center=(lo+hi)/2
    if not np.allclose(hi-lo,[17,70,30],atol=.05) or abs(center[0]) < 1:
        raise ValueError('Review speaker recognition geometry against changed envelope')
    # The accepted references are axis-aligned, with sound faces pointing out
    # along +X / -X. Reflect the opposite side and reverse its triangle winding.
    direction=1 if center[0]>0 else -1
    rows=[]
    for feature in speaker():
        vertices=(feature['v']-[93.7,-8,-31])*[direction,1,1]+center
        faces=feature['f'] if direction>0 else feature['f'][:,::-1]
        mesh=trimesh.Trimesh(vertices,faces,process=False)
        row=_row(original,mesh,feature['guide_color'],feature['id'])
        row['flat_shading']=feature.get('flat_shading',False)
        rows.append(row)
    return rows


def _rounded_box(width, depth, height, radius, center):
    """Rounded rectangle prism, with straight walls and planar end faces."""
    points=[]
    for x,y,start in [(width/2-radius,depth/2-radius,0),
                      (-width/2+radius,depth/2-radius,90),
                      (-width/2+radius,-depth/2+radius,180),
                      (width/2-radius,-depth/2+radius,270)]:
        for angle in np.linspace(start,start+90,9):
            a=np.deg2rad(angle);points.append([x+radius*np.cos(a),y+radius*np.sin(a)])
    points=np.array(points);n=len(points)
    vertices=np.concatenate([np.c_[points,np.full(n,-height/2)],np.c_[points,np.full(n,height/2)]])
    faces=[]
    for i in range(1,n-1):faces.extend([[0,i+1,i],[n,n+i,n+i+1]])
    for i in range(n):
        j=(i+1)%n;faces.extend([[i,j,n+j],[i,n+j,n+i]])
    return trimesh.Trimesh(vertices+center,faces,process=False)


def _button(original):
    """Adafruit 1479 / R16: white lens, black bezel, nut and four rear tabs.

    Source: https://www.adafruit.com/product/1479 and its R16diagram.jpg.
    The accepted envelope includes the tabs (29.4 mm overall); do not extend
    a 29.4 mm solid body and then add terminals beyond it. Mounting face Z=-2.
    Nut is seated behind the actual 2 mm FB20 plate, against Z=-4.
    """
    lo,hi=original['v'].min(0),original['v'].max(0)
    if not np.allclose([lo,hi],[[75.97,-85.03,-26.4],[94.03,-66.97,3]],atol=.05):
        raise ValueError('Review button recognition geometry against changed envelope')
    cx,cy=(lo[:2]+hi[:2])/2;rows=[]
    def add(mesh,color,feature):rows.append(_row(original,mesh,color,feature))
    def barrel(radius,length,z):
        mesh=_cylinder(radius,length,[cx,cy,z],(0,0,1))
        # The shaft has two flats (14.89 across them); the FB20 cutout is
        # 15.2 across those flats. A full 15.6mm round cylinder would collide.
        mesh.vertices[:,1]=np.clip(mesh.vertices[:,1],cy-7.445,cy+7.445)
        return mesh
    add(barrel(7.45,18.9,-11.45),DARK,'button barrel')
    # M16 barrel thread ridges, kept inside the accepted 18 mm face outline.
    for z in np.arange(-17.5,-2.5,1):
        add(barrel(7.8,.25,z),RIB,'button thread')
    add(_rounded_box(18.06,18,2,3,[cx,cy,-1]),(29,32,36),'button bezel')
    add(_cylinder(7.4,.5,[cx,cy,.25],(0,0,1)),(176,185,195),'lens rim')
    add(_cylinder(6.5,2.5,[cx,cy,1.75],(0,0,1)),(246,246,240),'white lens')
    nut=trimesh.creation.annulus(r_min=7.85,r_max=9,height=7,sections=64)
    nut.apply_translation([cx,cy,-7.5]);add(nut,DARK,'button retaining nut')
    for a in np.linspace(0,2*np.pi,36,endpoint=False):
        add(_cylinder(.18,6.5,[cx+8.88*np.cos(a),cy+8.88*np.sin(a),-7.5],(0,0,1),8),RIB,'nut grip')
    # Rear face: LED pair is closer, switch pair wider (R16 drawing).
    for x,y in [(-2.5,2.7),(2.5,2.7),(-4,-3),(4,-3)]:
        add(_box([2,.6,5.5],[cx+x,cy+y,-23.65]),METAL,'button terminal')
    return rows


def _audio(original):
    from guide_closeups import audio_module_model
    if not np.allclose([original['v'].min(0),original['v'].max(0)],
                       [[-14.5,-87.3,-37.75],[38.5,-72.7,-14.25]],atol=.05):
        raise ValueError('Review audio recognition geometry against changed envelope')
    return [_row(original,trimesh.Trimesh(m['v'],m['f'],process=False),m['guide_color'],m['id'])
            for m in audio_module_model()]


def _servo(original):
    """Keep all accepted ear holes/case surfaces; detail them in the local frame.

    Kitronik 25105 drawing and the reviewed product cartoon define the blue case,
    brass output spline, label and three lead colors. The lead leaves the case
    end nearest the shaft, low on the case (owner bench build and
    reference-photos/kitronik-25105-servo-and-horns.jpg). Stubs identify the
    exit; they do not establish a route or prescribe cut lengths.
    """
    t=np.array(original['source']['transform']).reshape(4,4)
    local=(original['v']-t[:3,3]*10)@t[:3,:3]
    if not np.allclose([local.min(0),local.max(0)],
                       [[-6.05,-21.3,0],[6.05,11,30.7]],atol=.05):
        raise ValueError('Review servo recognition geometry against changed envelope')
    rows=[]
    def add(mesh,color,feature):
        mesh.vertices=mesh.vertices@t[:3,:3].T+t[:3,3]*10
        rows.append(_row(original,mesh,color,feature))
    centers=local[original['f']].mean(axis=1)
    for mask,color,feature in [(centers[:,2]<=26.7+1e-5,(53,81,160),'servo case and ears'),
                               (centers[:,2]>26.7+1e-5,(192,151,63),'servo output spline')]:
        mesh=trimesh.Trimesh(local,original['f'][mask],process=False);mesh.remove_unreferenced_vertices();add(mesh,color,feature)
    for angle in np.linspace(0,2*np.pi,21,endpoint=False):
        add(_cylinder(.11,3.6,[2.38*np.cos(angle),2.38*np.sin(angle),28.7],(0,0,1),8),
            (147,111,41),'spline tooth')
    add(_cylinder(.7,.06,[0,0,30.71],(0,0,1)),DARK,'center screw opening')
    # Label on the broad side, matching the existing Kitronik product drawing.
    add(_box([.05,16,13],[6.075,-5,9]),(240,240,229),'servo label')
    add(_box([.055,15.5,6],[6.11,-5,6]),(43,143,79),'servo label green')
    for z in [2,20.8]:
        add(_box([12.12,22.3,.25],[0,-5.2,z]),(36,53,104),'case seam')
    # Brown, red, orange from the case bottom up, out of the shaft-end face (Y=6.1).
    for z,color in [(5.8,(124,73,44)),(7,(184,53,42)),(8.2,(221,138,38))]:
        add(_cylinder(.46,5,[0,8.6,z],(0,1,0),16),color,'servo lead stub')
    return rows


def _pi(original):
    """Detail the existing Pi reference parts without relocating its connectors."""
    lo,hi=original['v'].min(0),original['v'].max(0);center=(lo+hi)/2
    path=original['source']['path'];rows=[]
    def add(mesh,color,feature):rows.append(_row(original,mesh,color,feature))
    if 'GPIO' in path:
        if not np.allclose(hi-lo,[5,51,8.5],atol=.05):raise ValueError('Review Pi GPIO envelope')
        add(_box([5,51,2.5],[*center[:2],hi[2]-1.25]),DARK,'GPIO insulator')
        for x in [center[0]-1.27,center[0]+1.27]:
            for y in center[1]+(np.arange(20)-9.5)*2.54:
                add(_box([.64,.64,6],[x,y,lo[2]+3]),(194,155,72),'GPIO pin')
    elif 'USB' in path:
        if not np.allclose(hi-lo,[14,15,7],atol=.05):raise ValueError('Review Pi USB envelope')
        # Socket opening at the existing outward-facing -Y edge.
        for z in [lo[2]+.2,hi[2]-.2]:add(_box([14,15,.4],[*center[:2],z]),METAL,'USB shell')
        for x in [lo[0]+.2,hi[0]-.2]:add(_box([.4,15,6.2],[x,center[1],center[2]]),METAL,'USB shell side')
        add(_box([13,1,6],[center[0],hi[1]-.5,center[2]]),DARK,'USB socket back')
        add(_box([11,12,1.4],[center[0],center[1]+1,hi[2]-2]),DARK,'USB tongue')
        for x in center[0]+np.array([-3,-1,1,3]):
            add(_box([.7,8,.1],[x,center[1]-.5,hi[2]-2.75]),(190,152,65),'USB contact')
    else:
        color=(39,111,75) if 'PCB' in path else (155,166,177)
        add(trimesh.Trimesh(original['v'],original['f'],process=False),color,'Pi board' if 'PCB' in path else 'SD slot')
        if 'PCB' in path:
            # The reviewed pi3a cartoon uses a 65 x56 drawing frame. Map that
            # frame onto the accepted upside-down PCB, relative to its current bounds.
            def part(u,v,w,d,h,c,feature):
                add(_box([d,w,h],[lo[0]+v+d/2,hi[1]-u-w/2,lo[2]-h/2]),c,feature)
            part(5.5,7,12,11.5,1.6,METAL,'wireless shield')
            part(19.3,17.1,15,15,.5,DARK,'processor substrate')
            part(20.2,18,13.2,13.2,1.9,METAL,'processor lid')
            part(9.5,36.5,6,6,.9,DARK,'power IC')
            for u,v,w,d in [(1.8,16.5,3.4,23),(43.4,33.5,2.6,21.5)]:
                part(u,v,w,d,3.5,(225,220,203),'ribbon socket')
                part(u+.4,v+.5,w-.8,d-1,4.5,(94,74,53),'ribbon latch')
            # Connector housings retain the photo/drawing silhouette. Small
            # dark end faces show openings; this is not connector-fit CAD.
            part(24.2,45.8,15.4,10.2,6.1,METAL,'HDMI housing')
            part(25.2,55.95,13.4,.12,4.5,DARK,'HDMI opening')
            part(6.9,51.5,7.4,4.5,2.8,METAL,'micro USB housing')
            part(7.5,55.95,6.2,.12,1.8,DARK,'micro USB opening')
            part(50.2,44,6.6,12,6,DARK,'audio socket')
    return rows


def _shifter(original):
    """Color the real source's connected bodies; do not replace their shapes."""
    parents=list(range(len(original['v'])))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for a,b,c in original['f']:
        a=root(a)
        for i in (b,c):parents[root(i)]=a
    groups={}
    for face in original['f']:groups.setdefault(root(face[0]),[]).append(face)
    rows=[]
    for faces in groups.values():
        ids=np.unique(faces);points=original['v'][ids];span=points.max(0)-points.min(0)
        color=((36,42,47) if span[0]>20 else (46,127,84) if span[1]>10 and span[2]>8 else
               METAL if span[2]>2 else (63,70,76))
        mesh=trimesh.Trimesh(original['v'],faces,process=False);mesh.remove_unreferenced_vertices()
        rows.append(_row(original,mesh,color,'shifter source body'))
    return rows


def replace_envelopes(meshes):
    """Return recognizable rows without mutating accepted mesh/source records.

    Run after source/occurrence checks. One source occurrence becomes several
    display rows, preserving its identity; repeated invocation is harmless.
    """
    makers={'E15':_shifter,'E17':_button,'E14':_audio,'E01':_servo,'E09':_pi,'E07':_fuse,'E08':_capacitor,'E06':_wago,'E18':_jack,'E16':_speaker}
    result=[]
    for row in meshes:
        maker=makers.get(row['id'])
        if maker and not row.get('component_detail'):
            result.extend(maker(row))
        else:
            result.append(row)
    return result
