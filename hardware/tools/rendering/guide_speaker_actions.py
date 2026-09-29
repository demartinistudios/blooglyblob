"""Speaker assembly drawings: accepted FB19 mesh and product-based recognition model.

Adafruit 1669: 70 x 30 x 17 mm, Ø3.1 holes on 64 x 24 mm centers.
Housing, cone and tab styling follow the manufacturer's front/back photographs;
2 mm tab thickness is illustrative, not vendor CAD or a fit qualification.
Source: https://www.adafruit.com/product/1669 (reviewed 2026-09-27).
"""
import numpy as np
import trimesh
from guide_closeups import Views, item, hardware
from guide_fasteners import washer, hex_nut


def _prism(outline, front, back, name, color):
    # Star-shaped cross section, fan triangulated about its interior center.
    yz = np.asarray(outline, float)
    count = len(yz)
    vertices = np.vstack([np.column_stack([np.full(count, x), yz]) for x in (front, back)])
    vertices = np.vstack([vertices, [front, *yz.mean(0)], [back, *yz.mean(0)]])
    faces = []
    for i in range(count):
        j = (i+1) % count
        faces.extend([[2*count, i, j], [2*count+1, count+j, count+i],
                      [i, count+i, count+j], [i, count+j, j]])
    return item(trimesh.Trimesh(vertices, faces, process=False), name, color)


def speaker(offset=0):
    """+X-facing speaker aligned with accepted E16 bounds and FB19 inner bores."""
    dark = (48, 51, 56)
    # Cross-shaped housing leaves all four corner mounting tabs accessible.
    outline = [(-43,-40),(-33,-40),(-33,-46),(17,-46),(17,-40),(27,-40),
               (27,-22),(17,-22),(17,-16),(-33,-16),(-33,-22),(-43,-22)]
    rows = [_prism(outline, 100.8, 85.2, 'Speaker enclosure', dark)]
    # Thin corner tabs with genuine through-holes. The square perimeter joins
    # the housing; eccentric hole position leaves 3 mm to the outside edge.
    for y in (-40,24):
        for z in (-43,-19):
            angles = np.linspace(0, 2*np.pi, 64, endpoint=False)
            dy,dz=np.cos(angles),np.sin(angles)
            yl,yh=(-3,7) if y<0 else (-7,3)
            zl,zh=(-3,7) if z<-31 else (-7,3)
            ry=np.divide(np.where(dy>=0,yh,yl),dy,out=np.full(64,np.inf),where=abs(dy)>1e-9)
            rz=np.divide(np.where(dz>=0,zh,zl),dz,out=np.full(64,np.inf),where=abs(dz)>1e-9)
            radius=np.minimum(ry,rz)
            vertices=[];faces=[]
            for x,r in [(102.2,radius),(102.2,np.full(64,1.55)),(100.2,radius),(100.2,np.full(64,1.55))]:
                vertices.extend(np.column_stack([np.full(64,x),y+r*dy,z+r*dz]))
            for a,b in [(0,64),(128,0),(64,192),(192,128)]:
                for i in range(64):
                    j=(i+1)%64;faces.extend([[a+i,a+j,b+j],[a+i,b+j,b+i]])
            rows.append(item(trimesh.Trimesh(vertices,faces,process=False),'Speaker mounting tab', (62,65,70)))
    # Curved oval surround and cone, recessed behind the tab bearing plane.
    angles=np.linspace(0,2*np.pi,96,endpoint=False)
    profile=[(1,100.85),(.95,101.4),(.9,101.9),(.85,101.5),(.8,101.0),
             (.67,100.9),(.5,100.86),(.39,100.9),(.3,101.3),(.15,101.7),(0,101.85)]
    vertices=[];faces=[]
    for radius,x in profile:
        vertices.extend(np.column_stack([np.full(96,x),-8+19*radius*np.cos(angles),-31+12.7*radius*np.sin(angles)]))
    for k in range(len(profile)-1):
        for i in range(96):
            j=(i+1)%96;faces.extend([[k*96+i,k*96+j,(k+1)*96+j],[k*96+i,(k+1)*96+j,(k+1)*96+i]])
    cone=item(trimesh.Trimesh(vertices,faces,process=False),'Speaker cone',(76,80,85))
    cone['flat_shading']=False
    rows.append(cone)
    for z,color in [(-30,(150,39,33)),(-32,(29,32,37))]:
        cable=trimesh.creation.cylinder(radius=.8,height=14,sections=16)
        cable.apply_transform(trimesh.geometry.align_vectors([0,0,1],[0,1,0]))
        cable.apply_translation([91,-49,z])
        rows.append(item(cable,'Speaker lead',color))
    # Back label makes the rear orientation unmistakable.
    rows.append(_prism([(-28,-20),(-8,-20),(-8,-26),(-28,-26)],85.15,85.1,'Speaker rear label',(221,224,218)))
    return [dict(m,v=m['v']+[offset,0,0]) for m in rows]


def render_speaker_actions(render, output):
    from guide_context_actions import _compact
    v=Views(render,output)
    try:
        grille=v.parts(['FB19'],0)
        for m in grille: m['guide_color']=(174,99,52)
        separated=[dict(m,v=m['v']+[36,0,0]) for m in grille]
        _compact(v,'speaker-placement',speaker()+separated,[.85,1.4,.75],
                 'Align the speaker face with the inside of the loose grille',
                 arrows=[([107,-40,-19],[131,-40,-19]),([107,24,-43],[131,24,-43])],
                 labels=[('Sound side', [102.4,-8,-31], (345,390)),
                         ('FB19 grille', [141,7,-31], (20,40))])
        # Show the completed joint in the full assembly, not detached layers.
        # Bearing planes: grille X107, tab X102.2..100.2, washer X100.2..99.67.
        parts=grille+speaker()
        for y in (-40,24):
            for z in (-43,-19):
                parts+=hardware(3,12,[107,y,z],[-1,0,0])
                parts.append(washer([99.935,y,z],[1,0,0],3.505,1.6,.53))
                parts.append(hex_nut(3,[98.47,y,z],[1,0,0]))
        _compact(v,'speaker-fastening-action',parts,[-1,.06,.08],
                 'Rear of the speaker seated against FB19: washer and nut on each of the four screws',
                 labels=[('Washer against speaker', [99.935,24,-15.8], (20,40)),
                         ('M3 nut', [97.27,-40,-19], (430,385))])
    finally:
        render.meshes=v.original
    return v.paths
