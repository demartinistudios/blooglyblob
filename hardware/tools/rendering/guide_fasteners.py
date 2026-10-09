"""Recognizable, nominal metal hardware for assembly illustrations.

These are drawing solids, not vendor CAD or manufacturing models. Screw length
is measured from its bearing face to its tip. Head envelopes are M2 Ø3.8 × 2
and M3 Ø5.5 × 3; an M3 countersunk head is Ø6 with a 90° cone and its
length is overall, measured from the flush head face; external thread pitches are 0.4 and 0.5 mm respectively.
Hex sockets illustrate a recessed drive, without specifying a purchased drive.
All dimensions are millimetres; washer outer/inner arguments are radii.
"""
import math

import numpy as np

STEEL = (177, 186, 197)
HEAD_STEEL = (197, 204, 213)
RECESS = (66, 77, 91)
_SCREWS = {2: (0.4, 3.8, 2.0, 1.5), 3: (0.5, 5.5, 3.0, 2.5)}
_NUTS = {2: (4.0, 1.6), 3: (5.5, 2.4)}
_SECTIONS = 72


def axis_basis(axis):
    """Right-handed frame; preserve world X when the axis lies in the YZ plane.

    In particular, Z and ±Y nuts retain flats at world X = ±AF/2. An
    unconstrained axis alignment can introduce a 30° hex phase error.
    """
    z = np.asarray(axis, dtype=float)
    if z.shape != (3,) or not np.all(np.isfinite(z)) or np.linalg.norm(z) == 0:
        raise ValueError('A finite, nonzero three-dimensional axis is required')
    z = z / np.linalg.norm(z)
    ref = np.array([1., 0., 0.]) if abs(z[0]) < .95 else np.array([0., 1., 0.])
    x = ref - np.dot(ref, z) * z
    x /= np.linalg.norm(x)
    return np.column_stack([x, np.cross(z, x), z])


def _row(vertices, faces, name, center, axis, color=STEEL):
    center = np.asarray(center, dtype=float)
    if center.shape != (3,) or not np.all(np.isfinite(center)):
        raise ValueError('A finite three-dimensional center is required')
    return dict(id=name, occ=0, root=name,
                v=np.asarray(vertices, dtype=float) @ axis_basis(axis).T + center,
                f=np.asarray(faces, dtype=int), source={}, flat_shading=True,
                guide_color=color)


def _bridge(faces, lower, upper, count, reverse=False):
    for i in range(count):
        j=(i+1)%count
        triangles=[[lower+i, lower+j, upper+j], [lower+i, upper+j, upper+i]]
        faces.extend([tri[::-1] for tri in triangles] if reverse else triangles)


def _hex_radius(angles, af):
    # Angular phase keeps flat normals at 0°,60°,...; corners at 30°,90°,...
    return af / (2*np.cos((angles+np.pi/6) % (np.pi/3)-np.pi/6))


def _circle(vertices, angles, radius, z):
    radii=np.broadcast_to(radius, angles.shape)
    vertices.extend(np.column_stack([radii*np.cos(angles), radii*np.sin(angles),
                                    np.full(len(angles), z)]).tolist())


def _cap(vertices, faces, start, count, z, reverse=False):
    middle=len(vertices);vertices.append([0.,0.,z])
    for i in range(count):
        tri=[middle,start+i,start+(i+1)%count]
        faces.append(tri[::-1] if reverse else tri)


def screw(d, length, seat, axis, *, head="socket"):
    """Return shaft, socket-head and dark socket-floor renderer rows.

    The thread is a continuous helical radial surface, not stacked rings.
    ISO-style truncated 60° flanks are illustrative; the major diameter and
    pitch are nominal. Recess dimensions describe the drawn socket only.
    """
    if d not in _SCREWS or length <= 0 or not math.isfinite(length):
        raise ValueError('Screws require M2 or M3 and a positive finite length')
    if head not in ('socket','button','countersunk'):
        raise ValueError('Head must be socket, button or countersunk')
    if head=='countersunk' and d!=3:
        raise ValueError('Only M3 countersunk screws are drawn')
    pitch, head_d, head_h, socket_af = _SCREWS[d]
    if head=='button':head_h=.55*d
    major=d/2; depth=.61343*pitch
    angles=np.linspace(0,2*np.pi,_SECTIONS,endpoint=False)
    # Eight axial samples per pitch resolve both crest and root flats.
    levels=np.linspace(0,length,max(2,math.ceil(length/pitch*8))+1)
    vertices=[];faces=[]
    for z in levels:
        phase=(z/pitch-angles/(2*np.pi))%1
        distance=np.abs(phase-.5)
        profile=np.clip((distance-.0625)/.375,0,1)
        radius=major-depth*profile
        # Chamfer the final half-pitch to a broad, flat, non-pointed tip.
        tip=np.clip((length-z)/(.5*pitch),0,1)
        radius*=.72+.28*tip
        _circle(vertices,angles,radius,z)
    for level in range(len(levels)-1):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS)
    _cap(vertices,faces,0,_SECTIONS,0,reverse=True)
    _cap(vertices,faces,(len(levels)-1)*_SECTIONS,_SECTIONS,length)
    rows=[_row(vertices,faces,f'M{d} screw thread',seat,axis)]

    if head=='countersunk':
        return rows+_countersunk_head(seat,axis,angles,major)
    # Head outer wall, bearing face and top annulus all join a blind hex socket.
    bevel=min(.25,head_h*.12);outer=head_d/2
    vertices=[];faces=[]
    if head=='button':
        # Low, rounded head within the nominal M2 Ø3.8 × 1.1 envelope.
        profile=[(outer-bevel,0),(outer,-head_h*.1)]
        for t in np.linspace(.18,math.acos(.64),6):
            profile.append((outer*math.cos(t),-head_h*(.1+.9*math.sin(t)/math.sqrt(1-.64**2))))
    else:
        profile=[(outer-bevel,0),(outer,-bevel),
                 (outer,-head_h+bevel),(outer-bevel,-head_h)]
    for radius,z in profile:
        _circle(vertices,angles,radius,z)
    for level in range(len(profile)-1):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS,reverse=True)
    # Chamfered socket mouth, then a straight wall and a recessed floor.
    start=len(profile)*_SECTIONS
    for af,z in [(socket_af+.20,-head_h),(socket_af,-head_h+min(.16,head_h*.14)),
                 (socket_af,-head_h+head_h*.62)]:
        _circle(vertices,angles,_hex_radius(angles,af),z)
    _bridge(faces,start-_SECTIONS,start,_SECTIONS,reverse=True)
    _bridge(faces,start,start+_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,start+_SECTIONS,start+2*_SECTIONS,_SECTIONS,reverse=True)
    _cap(vertices,faces,start+2*_SECTIONS,_SECTIONS,-head_h+head_h*.62,reverse=True)
    _cap(vertices,faces,0,_SECTIONS,0)
    rows.append(_row(vertices,faces,f'M{d} {head} head',seat,axis,HEAD_STEEL))
    # A dark floor makes the physical recess legible in a small illustration;
    # it lies just above the actual closed floor and stays inside the socket.
    vertices=[];faces=[]
    _circle(vertices,angles,_hex_radius(angles,socket_af*.96),-head_h+head_h*.62-.01)
    _cap(vertices,faces,0,_SECTIONS,-head_h+head_h*.62-.01,reverse=True)
    rows.append(_row(vertices,faces,f'M{d} socket recess',seat,axis,RECESS))
    return rows


def _countersunk_head(seat, axis, angles, major, outer=3.0, socket_af=2.0, depth=1.1):
    """Ø6 × 90° M3 head with its flush face at the seat, cone along +axis."""
    vertices=[];faces=[]
    profile=[(major,outer-major),(outer,.12),(outer-.08,0)]
    for radius,z in profile:
        _circle(vertices,angles,radius,z)
    for level in range(len(profile)-1):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS,reverse=True)
    start=len(profile)*_SECTIONS
    for af,z in [(socket_af+.2,0),(socket_af,.12),(socket_af,depth)]:
        _circle(vertices,angles,_hex_radius(angles,af),z)
    _bridge(faces,start-_SECTIONS,start,_SECTIONS,reverse=True)
    _bridge(faces,start,start+_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,start+_SECTIONS,start+2*_SECTIONS,_SECTIONS,reverse=True)
    _cap(vertices,faces,start+2*_SECTIONS,_SECTIONS,depth,reverse=True)
    _cap(vertices,faces,0,_SECTIONS,outer-major)
    rows=[_row(vertices,faces,'M3 countersunk head',seat,axis,HEAD_STEEL)]
    vertices=[];faces=[]
    _circle(vertices,angles,_hex_radius(angles,socket_af*.96),depth-.01)
    _cap(vertices,faces,0,_SECTIONS,depth-.01)
    rows.append(_row(vertices,faces,'M3 socket recess',seat,axis,RECESS))
    return rows


def hex_nut(d, center, axis, *, af=None, thickness=None, bore=None):
    """Return a chamfered hex nut with an open bore and deterministic flats.

    Overrides support supplied retaining hardware, e.g. af=11, thickness=1.8,
    bore=7.94 for an illustrative jack nut. Bore is a diameter, not radius.
    """
    defaults=_NUTS.get(d)
    if defaults is None and (af is None or thickness is None):
        raise ValueError('Provide AF and thickness for a non-M2/M3 nut')
    af=defaults[0] if af is None else af
    thickness=defaults[1] if thickness is None else thickness
    bore=d if bore is None else bore
    if not all(math.isfinite(x) and x>0 for x in (af,thickness,bore)) or bore>=af:
        raise ValueError('Nut dimensions must be positive and bore smaller than AF')
    angles=np.linspace(0,2*np.pi,_SECTIONS,endpoint=False)
    bevel=min(.2,thickness*.12,(af-bore)/8)
    vertices=[];faces=[]
    levels=[-thickness/2,-thickness/2+bevel,thickness/2-bevel,thickness/2]
    for i,z in enumerate(levels):
        _circle(vertices,angles,_hex_radius(angles,af-2*bevel if i in (0,3) else af),z)
    for level in range(3):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS)
    for i,z in enumerate(levels):
        _circle(vertices,angles,bore/2+bevel if i in (0,3) else bore/2,z)
    for level in range(4,7):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,0,4*_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,3*_SECTIONS,7*_SECTIONS,_SECTIONS)
    return _row(vertices,faces,f'M{d} nut',center,axis)


def washer(center, axis, outer, inner, height, name='Washer', color=None):
    """Return an open annular washer, with small beveled metal edges.

    outer and inner are radii. Supply color for an insulating washer.
    """
    if not all(math.isfinite(x) and x>0 for x in (outer,inner,height)) or inner>=outer:
        raise ValueError('Washer dimensions must be positive; inner < outer')
    angles=np.linspace(0,2*np.pi,_SECTIONS,endpoint=False)
    bevel=min(.08,height*.2,(outer-inner)*.12)
    levels=[-height/2,-height/2+bevel,height/2-bevel,height/2]
    vertices=[];faces=[]
    for i,z in enumerate(levels):
        _circle(vertices,angles,outer-bevel if i in (0,3) else outer,z)
    for level in range(3):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS)
    for i,z in enumerate(levels):
        _circle(vertices,angles,inner+bevel if i in (0,3) else inner,z)
    for level in range(4,7):
        _bridge(faces,level*_SECTIONS,(level+1)*_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,0,4*_SECTIONS,_SECTIONS,reverse=True)
    _bridge(faces,3*_SECTIONS,7*_SECTIONS,_SECTIONS)
    return _row(vertices,faces,name,center,axis,color or HEAD_STEEL)
