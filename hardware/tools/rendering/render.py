"""Current assembly renderer. cm source coordinates become assembly mm exactly once."""
import json,gzip,re,sys,os
sys.path.insert(0,str(__import__("pathlib").Path(__file__).resolve().parent))
from rasterizer import rasterize,vertex_normals,corner_normals
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[3]
REVISION='r22'
OUT=Path(os.environ['BGB_RENDER_OUTPUT'])
if not OUT.is_dir():raise ValueError('Renderer requires a newly created output directory')
from source import checked_source
mesh_source = Path(os.environ['BGB_RENDER_MESH_SOURCE']) if os.environ.get('BGB_RENDER_MESH_SOURCE') else checked_source()[0]
rows=json.load(gzip.open(mesh_source,'rt'))
arm={'R_Upper':'AR01','R_Forearm':'AR02','R_Hand':'AR03','L_Upper':'AR04','L_Forearm':'AR05','L_Hand':'AR06','R_Cover':'AR08','L_Cover':'AR09','R_ElbowCap':'AR10','L_ElbowCap':'AR11'}
refs=[('FS90MG','E01'),('Adafruit 5975','E03'),('Mouth1426','E04'),('Pebble','E05'),('WAGO221','E06'),('Schurter','E07'),('FBREF Fuse','E07'),('Panasonic','E08'),('FBREF Capacitor','E08'),('Pi3A','E09'),('Waveshare','E14'),('PixelShifter6066 - manufacturer','E15'),('Speaker1669','E16'),('Adafruit1479','E17'),('Switchcraft','E18'),('Rubber foot','E25'),('Foam wrap','FOAM'),('Eye Plastazote','EYEFOAM'),('Mouth Plastazote','MOUTHFOAM')]
meshes=[];counts={};paths={};render_audit={}
for r in rows:
 root=r['path'].split('+')[0];name=root.rsplit(':',1)[0]
 if r.get('part_id'):pid=r['part_id']
 elif name.startswith('ANDROID '):pid=arm[name[8:]]
 elif re.match(r'^(GS|FB)\d\d ',name):pid=name[:4]
 elif re.match(r'^[PAB]\d\d ',name):pid=name[:3]
 else:pid=next((id for frag,id in refs if frag in name),None)
 if not pid:continue
 if root not in paths:paths[root]=counts.get(pid,0);counts[pid]=paths[root]+1
 v=np.array(r['vertices_cm']).reshape(-1,3);T=np.array(r['transform']).reshape(4,4);v=(v@T[:3,:3].T+T[:3,3])*10
 f=np.array(r['faces']).reshape(-1,3)
 meshes.append({'id':pid,'occ':paths[root],'v':v,'f':f,'root':root,'source':r})
fontpath=os.environ['BGB_RENDER_FONT']
def font(n):return ImageFont.truetype(fontpath,n)
colors={'M3×14':(177,186,197),'M3 nut':(177,186,197),'E03':(38,81,72),'E04':(32,66,63),'E15':(46,104,86),'E01':(75,90,108),'E06':(225,133,48),'E08':(56,83,102),'E09':(80,155,115),'FOAM':(222,228,234),'EYEFOAM':(239,240,226),'MOUTHFOAM':(239,240,226)}
def col(m,highlight):
 if 'guide_color' in m:return m['guide_color']
 if highlight and m['id'] not in highlight:return (213,223,232)
 return colors.get(m['id'],(30,153,183) if highlight else (100,153,202))
def render(name,view,thumb=False):
 sel=view.get('select',['all']);hi=view.get('highlight');allsel='all' in sel
 chosen=[m for m in meshes if (allsel or m['id'] in sel) and (m['id'] not in view.get('occ',{}) or m['occ'] in view['occ'][m['id']])]
 chosen=[m for m in chosen if m['id'] not in view.get('exclude',[]) and (not view.get('roots') or m['root'] in view['roots'])]
 if not chosen:return
 if view.get('hardware'):
  from guide_fasteners import screw, hex_nut
  for hw in view['hardware']:
   axis=np.array(hw['axis'],float);seat=np.array(hw['seat'],float)
   screw_rows=screw(3,14,seat-axis*13,axis)
   for row in screw_rows:row.update(id='M3×14',root='M3×14')
   chosen += screw_rows
   chosen.append(hex_nut(3,np.array(hw['nut'])+axis*10,axis))
 W,H=view.get('size',(560,420) if thumb else (1200,1000))
 angle=view.get('angle','front');cam={'front':(-.85,-1.6,.85),'rear':(.9,1.6,.9),'top':(.3,-.65,1.7),'face':(-.25,-1.8,.35),'arm':(1.8,-1.2,.5),'underside':(.8,-1.5,-1.4)}[angle];cam=view.get('camera',cam);z=np.array(cam,dtype=float);z/=np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x);R=np.array([x,y,z]).T
 vs=[];cs=[];arrows=[];arrow_roots=set();face_roots=[];root_keys=[]
 for m in chosen:
  v=m['v'].copy();old=v.mean(axis=0);off=np.array(view.get('offset_occ',{}).get(m['id']+':'+str(m['occ']),view.get('offset',{}).get(m['id'],[0,0,0])),float)
  if m['id'] in view.get('offset_local',{}):off+=np.array(next(a for a in chosen if a['id']==view.get('basis_id',m['id']))['source']['transform']).reshape(4,4)[:3,:3]@np.array(view['offset_local'][m['id']])
  if view.get('explode'):
   ctr=np.concatenate([a['v'] for a in chosen]).mean(axis=0);u=old-ctr;n=np.linalg.norm(u)
   if n:off+=u/n*view['explode']
  v+=off
  if np.linalg.norm(off)>0 and m['root'] not in arrow_roots:
   arrows.append(((old+off)@R,old@R));arrow_roots.add(m['root'])
  f=m['f'];vv=v@R;tri=vv[f]
  if 'normals' not in m:m['normals']=vertex_normals(m['v'],f)
  normals=m['normals']@R
  normals=np.where(normals[:,2:3]<0,-normals,normals)
  key=np.array([-.4,.55,.73]);key/=np.linalg.norm(key)
  fill=np.array([.7,-.2,.65]);fill/=np.linalg.norm(fill)
  shade=.40+.46*np.clip(normals@key,0,1)+.14*np.clip(normals@fill,0,1)
  base=np.array(col(m,hi));c=np.clip(base[None,:]*shade[:,None],0,255)[f]
  if (REVISION in {'r14','r15','r16','r17','r18','r19','r20','r21','r22'} and m['id'].startswith('GS')) or (REVISION in {'r16','r17','r18','r19','r20','r21','r22'} and ('part_id' in m['source'] or m['id']=='J05')):
   if 'corner_normals' not in m:m['corner_normals']=corner_normals(m['v'],f)
   cn=m['corner_normals']@R
   cn=np.where(cn[:,:,2:3]<0,-cn,cn)
   csmooth=.40+.46*np.clip(cn@key,0,1)+.14*np.clip(cn@fill,0,1)
   c=np.clip(base[None,None,:]*csmooth[:,:,None],0,255)
  if m['id']=='P17' or m.get('flat_shading'):
   # The STL shares vertices across sharp CAD edges. Flat face normals avoid
   # interpolated dents across planar decks while preserving every triangle.
   face_normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
   face_normals/=np.maximum(np.linalg.norm(face_normals,axis=1,keepdims=True),1e-12)
   face_normals=np.where(face_normals[:,2:3]<0,-face_normals,face_normals)
   face_shade=.40+.46*np.clip(face_normals@key,0,1)+.14*np.clip(face_normals@fill,0,1)
   c=np.repeat(np.clip(base[None,:]*face_shade[:,None],0,255)[:,None,:],3,axis=1)
  vs.append(tri);cs.append(c)
  rk=(m['id'],m['root'])
  if rk not in root_keys:root_keys.append(rk)
  face_roots.extend([root_keys.index(rk)]*len(tri))
 tri=np.concatenate(vs);c=np.concatenate(cs);xy=tri[:,:,:2];lo=xy.min(axis=(0,1));up=xy.max(axis=(0,1));span=up-lo
 if 'frame_world_bounds' in view:
  # Camera framing crops the view only; source vertices/faces stay untouched.
  import itertools
  bounds=view['frame_world_bounds']
  corners=np.array(list(itertools.product(*zip(*bounds))))@R
  lo=corners[:,:2].min(0);up=corners[:,:2].max(0);span=up-lo
 margin=view.get('margin',60 if thumb else 175);scale=min((W-2*margin)/max(span[0],1),(H-2*margin)/max(span[1],1));center=(lo+up)/2
 def project(p):return np.array([(p[0]-center[0])*scale+W/2,H/2-(p[1]-center[1])*scale])
 screen=np.stack(((xy[:,:,0]-center[0])*scale+W/2,H/2-(xy[:,:,1]-center[1])*scale),axis=-1)
 # Resolve the closest surface independently at each subpixel, then antialias.
 ss=2
 projected=np.concatenate((screen*ss,tri[:,:,2:3]),axis=2)
 rgb,depth,owner=rasterize(projected,c,W*ss,H*ss,np.array([243,247,250],np.uint8))
 if 'frame_world_bounds' in view:
  # Keep clipped tank material inside the picture area, away from captions.
  for a,b in [(0,margin*ss),((H-margin)*ss,H*ss)]:
   rgb[a:b,:,:]=[243,247,250];owner[a:b,:]=-1
 im=Image.fromarray(rgb).resize((W,H),Image.Resampling.LANCZOS)
 draw=ImageDraw.Draw(im)
 if not thumb and not view.get('clean'):
  # Exploded offsets are diagram separation, not prescribed assembly travel.
  for start,end in arrows:
   p,q=project(start),project(end);vec=q-p;L=np.linalg.norm(vec)
   if L<18:continue
   u=vec/L;p=p+u*5;q=q-u*5;draw.line([tuple(p),tuple(q)],fill=(200,91,29),width=2)
   draw.ellipse((q[0]-3,q[1]-3,q[0]+3,q[1]+3),fill=(200,91,29))
  # Guide pictures carry no drawn title or footnote: the guide caption gives
  # the view and the actions give instructions. Review renders keep both.
  if not view.get('guide'):
   draw.text((25,24),view.get('title',REVISION.upper()+'  /  '+('SEPARATED PARTS' if arrows else 'ASSEMBLY VIEW')),font=font(23 if len(view.get('title',''))>65 else 25),fill=(34,56,78))
   draw.text((30,H-40),view.get('footer','Opaque CAD surfaces • spacing is illustrative, not installation travel'),font=font(19),fill=(65,85,102))
  # Direction compass follows the actual projection, not page conventions.
  origin=np.array([W-140,H-115])
  for vec,label in [([0,-1,0],'FRONT'),([0,1,0],'BACK'),([0,0,1],'UP')]:
   p=np.array(vec)@R;end=origin+np.array([p[0],-p[1]])*58
   draw.line([tuple(origin),tuple(end)],fill=(45,69,90),width=3)
   if REVISION in {'r13','r14','r15','r16','r17','r18','r19','r20','r21','r22'}:
    width=draw.textlength(label,font=font(15))
    offset=[-width/2,-22] if label=='UP' else ([7,-5] if end[0]>=origin[0] else [-width-7,-5])
   else:offset=[-40,8] if label=='FRONT' else [0,-25] if label=='BACK' else [-10,-20]
   offset=view.get('compass_label_offsets',{}).get(label,offset)
   draw.text(tuple(end+offset),label,font=font(15),fill=(20,44,67))
  # Located fastener symbols use recorded screw seat / nut centers, never screen guesses.
  for mark in view.get('markers',[]):
   h=project(np.array(mark['head'])@R);n=project(np.array(mark['nut'])@R)
   draw.line([tuple(h),tuple(n)],fill=(170,79,16),width=4)
   if not mark.get('nut_unknown'):draw.rectangle((n[0]-7,n[1]-7,n[0]+7,n[1]+7),fill=(216,223,231),outline=(72,85,100),width=2)
   draw.ellipse((h[0]-13,h[1]-13,h[0]+13,h[1]+13),fill=(255,248,221),outline=(161,74,15),width=3)
   draw.text((h[0]-6,h[1]-12),str(mark['n']),font=font(20),fill=(103,51,11))
  if view.get('markers'):
   draw.rectangle((20,57,W-25,107),fill=(243,247,250))
   if not view.get('guide'):
    draw.text((30,62),'Numbered circle = screw entry/head; square = nut. Installed positions; hidden joints shown.',font=font(20),fill=(109,62,25))
   for i,t in enumerate(view['legend']):draw.text((30,H-128+i*27),t,font=font(20),fill=(109,62,25))
  # Side rails keep identification outside geometry and avoid overlapping labels.
  labs=[]
  for feature in view.get('feature_labels',[]):
   labs.append((feature['text'],project(np.array(feature['point'])@R)))
  # Anchor only to visible rasterized material belonging to that occurrence.
  sample=owner[::6,::6];valid=sample>=0
  object_ids=np.full(sample.shape,-1);object_ids[valid]=np.asarray(face_roots)[sample[valid]]
  labeled=set()
  for idx,(pid,root) in enumerate(root_keys):
   if view.get('label_roots') and root not in view['label_roots']:continue
   if pid=='E09' and pid in labeled:continue
   yy,xx=np.where(object_ids==idx)
   if len(xx)<4:continue
   pixels=np.column_stack((xx*3.,yy*3.))
   middle=np.median(pixels,axis=0);p=pixels[np.argmin(np.sum((pixels-middle)**2,axis=1))]
   label=view.get('labels_by_root',{}).get(root,pid)
   labs.append((label,p));labeled.add(pid)
  if len(labs)>14:
   # Keep one real occurrence per ID in dense assemblies, never an empty centroid.
   labs=list({pid:next(a for a in labs if a[0]==pid) for pid,_ in labs}.values())
   if len(labs)>14:labs=[]
  left=sorted([a for a in labs if a[1][0]<W/2],key=lambda a:a[1][1]);right=sorted([a for a in labs if a[1][0]>=W/2],key=lambda a:a[1][1])
  for group,isleft in [(left,True),(right,False)]:
   for j,(pid,p) in enumerate(group):
    ty=125+j*min(78,650/max(1,len(group)));tx=20 if isleft else W-163
    draw.line([tuple(p),(tx+(143 if isleft else 0),ty+27)],fill=(103,126,146),width=2)
    draw.rounded_rectangle((tx,ty,tx+143,ty+54),7,fill=(255,255,255),outline=(137,159,178),width=1);draw.text((tx+10,ty+5),{'FOAM':'C04','EYEFOAM':'C02','MOUTHFOAM':'C03'}.get(pid,pid),font=font(29 if len(pid)>4 else 36),fill=(15,60,84))
 im.save(OUT/(name+'.png'),optimize=True)
 render_audit[name]={'renderer':'per-pixel depth buffer, opaque surfaces, 2× supersampling','triangles':len(tri),'labels':[] if thumb or view.get('clean') else [p for p,_ in labs],'width':W,'height':H,'camera':list(cam),'view':view}
