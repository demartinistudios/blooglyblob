"""Opaque orthographic triangle rasterizer with a per-sample depth buffer.

Larger camera-space z is nearer. No highlighting or triangle submission order can
change visibility. Supersampling is performed by the caller before final labels.
"""
import numpy as np
from numba import njit

@njit(cache=True)
def rasterize(triangles,colors,width,height,background):
 image=np.empty((height,width,3),np.uint8)
 image[:,:,:]=background
 depth=np.full((height,width),-np.inf)
 owner=np.full((height,width),-1,np.int32)
 for i in range(len(triangles)):
  a,b,c=triangles[i,0],triangles[i,1],triangles[i,2]
  area=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(area)<1e-10:continue
  x0=max(0,int(np.floor(min(a[0],b[0],c[0]))));x1=min(width-1,int(np.ceil(max(a[0],b[0],c[0]))))
  y0=max(0,int(np.floor(min(a[1],b[1],c[1]))));y1=min(height-1,int(np.ceil(max(a[1],b[1],c[1]))))
  for y in range(y0,y1+1):
   for x in range(x0,x1+1):
    px,py=x+.5,y+.5
    u=((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/area
    v=((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/area
    w=1-u-v
    if u < -1e-9 or v < -1e-9 or w < -1e-9:continue
    z=u*a[2]+v*b[2]+w*c[2]
    if z>depth[y,x]+1e-8:
     depth[y,x]=z;owner[y,x]=i
     for channel in range(3):
      image[y,x,channel]=np.uint8(min(255,max(0,u*colors[i,0,channel]+v*colors[i,1,channel]+w*colors[i,2,channel])))
 return image,depth,owner

def vertex_normals(vertices,faces):
 a=vertices[faces[:,0]];b=vertices[faces[:,1]];c=vertices[faces[:,2]]
 face=np.cross(b-a,c-a)
 normals=np.zeros_like(vertices)
 for k in range(3):np.add.at(normals,faces[:,k],face)
 normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
 return normals

def corner_normals(vertices,faces,crease_degrees=30):
 """Smooth shallow facets without blending across CAD hard edges.

 Each triangle corner has its own normal. Angle weighting avoids making the
 lighting depend on whether a neighboring planar face has large fan triangles.
 The source vertices and triangle winding are never changed.
 """
 tri=vertices[faces]
 normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
 normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
 angles=np.empty((len(faces),3))
 for k in range(3):
  a=tri[:,(k+1)%3]-tri[:,k];b=tri[:,(k+2)%3]-tri[:,k]
  denom=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
  angles[:,k]=np.arccos(np.clip(np.sum(a*b,axis=1)/np.maximum(denom,1e-12),-1,1))
 adjacent=[[] for _ in vertices]
 for face,row in enumerate(faces):
  for corner,vertex in enumerate(row):adjacent[vertex].append((face,corner))
 result=np.empty((len(faces),3,3))
 threshold=np.cos(np.deg2rad(crease_degrees))
 for entries in adjacent:
  if not entries:continue
  ids,corners=np.array(entries).T
  local=normal[ids]
  weights=(local@local.T>=threshold-1e-10)*angles[ids,corners][None,:]
  smooth=weights@local
  smooth/=np.maximum(np.linalg.norm(smooth,axis=1,keepdims=True),1e-12)
  result[ids,corners]=smooth
 return result
