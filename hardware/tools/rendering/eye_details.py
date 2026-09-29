"""Read-only illustrations from accepted R22 meshes; optical interfaces retained from R15.
No Fusion edits. Film is a dimensioned outline (thickness remains unspecified).
"""
import os,json,hashlib
from pathlib import Path
os.environ['BGB_RENDER_REVISION']='r22'
import render
import numpy as np
from PIL import Image,ImageDraw
from rasterizer import rasterize,corner_normals
S=Path(__file__).resolve().parents[3];OUT=render.OUT
palette={(a['path'],a['body']):a['chosen_rgb'] for a in json.loads((S/'hardware/rendering/r22-colors.json').read_text())['assignments']}
ref=next(m for m in render.meshes if m['id']=='P06' and m['occ']==0)
T=np.array(ref['source']['transform']).reshape(4,4);basis=T[:3,:3];origin=T[:3,3]*10
meshes=[]
for m in render.meshes:
 if m['id'] in ['GS11','P06','EYEFOAM','E03'] and m['occ']==0:
  meshes.append(dict(m,v=(m['v']-origin)@basis))
BG=(247,247,250);INK=(35,43,66);COPPER=(159,82,39)
audit={}
def picture(name,ids,cam,title,subtitle,offset=None,marks=(),footer=(),film=False,arrows=()):
 offset=offset or {};W,H=1400,1100
 z=np.array(cam,float);z/=np.linalg.norm(z);x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x);R=np.array([x,y,z]).T
 selected=[m for m in meshes if m['id'] in ids];vs=[];cs=[]
 for m in selected:
  v=m['v']+np.array(offset.get(m['id'],[0,0,0]));f=m['f'];tri=(v@R)[f]
  n=corner_normals(m['v'],f)@R;n=np.where(n[:,:,2:3]<0,-n,n)
  light=np.array([-.3,.6,.75]);light/=np.linalg.norm(light)
  c=(240,240,230) if m['id']=='EYEFOAM' else palette.get((m['source'].get('path'),m['source'].get('body')),render.col(m,None))
  shade=.47+.53*np.clip(n@light,0,1)
  vs.append(tri);cs.append(np.clip(np.array(c)[None,None,:]*shade[:,:,None],0,255))
 tri=np.concatenate(vs);colors=np.concatenate(cs)
 # A zero-thickness outline preserves the documented blank dimensions without inventing thickness.
 filmpts=[]
 if film:
  for cx,cy,start in [(2.1,.1,0),(-2.1,.1,90),(-2.1,-.1,180),(2.1,-.1,270)]:
   for a in np.linspace(start,start+90,20):
    a=np.deg2rad(a);filmpts.append([cx+4.2*np.cos(a),cy+4.2*np.sin(a),-13.2])
 allpts=tri.reshape(-1,3)
 if film:allpts=np.concatenate([allpts,np.array(filmpts)@R])
 lo=allpts[:,:2].min(0);hi=allpts[:,:2].max(0);span=hi-lo;center=(lo+hi)/2
 scale=min(1050/span[0],620/span[1]);mid=np.array([700,510])
 def proj(p):
  p=np.array(p)@R;return np.array([(p[0]-center[0])*scale+mid[0],mid[1]-(p[1]-center[1])*scale])
 xy=np.stack(((tri[:,:,0]-center[0])*scale+mid[0],mid[1]-(tri[:,:,1]-center[1])*scale),axis=-1)
 rgb,_,_=rasterize(np.concatenate([xy*2,tri[:,:,2:3]],axis=2),colors,W*2,H*2,np.array(BG,np.uint8))
 im=Image.fromarray(rgb).resize((W,H),Image.Resampling.LANCZOS);d=ImageDraw.Draw(im)
 d.text((45,28),title,font=render.font(35),fill=INK);d.text((45,80),subtitle,font=render.font(24),fill=INK)
 # Source-local +Y is downward on the robot. Keep bench access views, but show actual head-up.
 up=(np.array([0,0,1])@basis)@R;vec=np.array([up[0],-up[1]]);vec=vec/np.linalg.norm(vec)*42
 start=np.array([1310.,32.]);end=start+vec;unit=vec/np.linalg.norm(vec);side=np.array([-unit[1],unit[0]])
 d.line([tuple(start),tuple(end)],fill=INK,width=3)
 d.polygon([tuple(end),tuple(end-unit*10+side*5),tuple(end-unit*10-side*5)],fill=INK)
 d.text((1230,90),'HEAD TOP',font=render.font(19),fill=INK)
 if film:
  ps=[tuple(proj(p)) for p in filmpts];d.polygon(ps,fill=(207,233,247),outline=(66,133,172),width=3)
 for a,b in arrows:
  p,q=proj(a),proj(b);u=(q-p)/np.linalg.norm(q-p);side=np.array([-u[1],u[0]])
  d.line([tuple(p),tuple(q)],fill=(30,137,164),width=5)
  d.polygon([tuple(q),tuple(q-u*16+side*8),tuple(q-u*16-side*8)],fill=(30,137,164))
 for label,p,tx,ty in marks:
  p=proj(p);tw=d.textlength(label,font=render.font(25));end=(tx+tw/2,ty+34)
  d.line([tuple(p),end],fill=COPPER,width=3);d.ellipse((p[0]-5,p[1]-5,p[0]+5,p[1]+5),fill=COPPER)
  d.rounded_rectangle((tx-9,ty-5,tx+tw+9,ty+34),7,fill=BG)
  d.text((tx,ty),label,font=render.font(25),fill=INK)
 d.line([(45,890),(1355,890)],fill=(207,205,215),width=2)
 for i,line in enumerate(footer):d.text((45,915+i*39),line,font=render.font(25),fill=INK)
 im.save(OUT/(name+'.png'))
 audit[name]=dict(source=str(render.mesh_source.relative_to(S)),eye='GS11 / robot-right',coordinate_basis='P06 occurrence 1 local mm',camera=cam,offsets_mm=offset,parts=ids,film='dimensioned zero-thickness illustration' if film else None,marks=marks)

picture('eye-exploded',['GS11','EYEFOAM','P06','E03'],[-1,.52,1],
 'ONE EYE / how the real parts fit together','Robot-right GS11 shown; repeat with GS12 on robot-left.',
 offset={'GS11':[0,0,-23],'P06':[0,0,13],'E03':[0,0,29]},film=True,
 marks=[('1  Housing',[-10,0,-23],80,170),('2  Clear film',[0,0,-13.2],380,760),('3  Foam',[0,0,2],540,170),('4  P06 cassette',[9,0,19],780,760),('5  LED board',[0,0,39],1030,170)],
 footer=['Outside / face → housing, film, foam, cassette opening, LED board → inside head.',
 'The LED faces the foam. The two cable sockets face into the head.',
 'Parts are spaced apart for visibility. Blue film outline shows shape, not thickness.',
 'Main mounting screws and the head shell are omitted here; see the rear screw view.'])
picture('eye-housing-rear',['GS11'],[-.35,-1.0,1.4],
 'R22 EYE / slide nuts in from the upper edge',
 'Housing off the head. Load both nuts under the roofs; do not push through the round bores.',
 marks=[('Nut channel',[-9,-5,-1.8],70,160),('Nut channel',[9,-5,-1.8],1030,160),('Short tapered locator',[-9,4,1],40,755),('1 mm bearing roof',[9,0,-.5],975,755)],
 arrows=[([-9,-15,-1.8],[-9,-1,-1.8]),([9,-15,-1.8],[9,-1,-1.8])],
 footer=['Rotated bench view: HEAD TOP points down. Slide nuts toward the screw centers.',
 'Keep the nut broad faces parallel to the housing front, flats aligned to the channel.',
 'The nut bears against the roof when the screw engages. No glue is part of this joint.',
 'Use M2 × 10 screws and 0.25 mm washers; actual fit and roof strength remain untested.'])
picture('eye-cassette-front',['P06'],[-.4,.45,-1.7],
 'P06 / the side that faces the foam','Load the two board nuts into these rectangular pockets before assembly.',
 marks=[('M2 board nut',[0,4.318,5.2],70,160),('M2 board nut',[0,-4.318,5.2],930,745),('Light opening',[0,0,4.2],1030,160),('Main mounting hole',[9,0,4.2],40,745)],
 footer=['The small central opening lets LED light reach the foam.',
 'The LED recess and board supports are on the opposite side.',
 'These two nuts take the M2 × 6 board screws. No washers on those screws.',
 'Each outer ear has a separate hole for an M2 × 10 main mounting screw.'])
picture('eye-board-rear',['P06','E03'],[.15,.35,1.8],
 'INSIDE THE HEAD / two different screw pairs','Board and cassette in their actual fitted positions; head shell omitted.',
 marks=[('M2 × 6 · board',[0,4.318,10.57],540,160),('M2 × 6 · board',[0,-4.318,10.57],535,770),('M2 × 10 + washer',[-9,0,7.5],45,335),('M2 × 10 + washer',[9,0,7.5],1030,335)],
 footer=['Short pair: through the PCB into the two nuts in P06. No board washers.',
 'Long pair: 0.25 mm washer → P06 ear → head → side-loaded housing nut.',
 'Fit eyes before the mouth. Actual outer-screw overlap and roof strength need checking.',
 'Keep both cable sockets accessible. Callouts mark screw axes; hardware is not shown.'])
picture('eye-led-front',['E03'],[-.2,.3,-1.8],
 'LED BOARD / the side that faces the foam','Adafruit 5975: the single LED fits into the recess at the back of P06.',
 marks=[('Single LED',[0,0,7.6],1050,340),('Board screw hole',[0,4.318,9],70,170)],
 footer=['This LED faces the cassette opening and foam; do not mount the board backward.',
 'The two cable sockets are on the opposite side, facing into the head.',
 'Fit the M2 × 6 screws from that opposite side. No washers on this board pair.',
 'Manufacturer CAD reference; the actual board may differ in surface markings.'])
(OUT/'eye-render-audit.json').write_text(json.dumps(dict(mesh_sha256=hashlib.sha256(render.mesh_source.read_bytes()).hexdigest(),views=audit),indent=2)+'\n')
print('Rendered',len(audit),'eye detail views')
