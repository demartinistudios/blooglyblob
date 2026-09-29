"""Technical fastening sections from accepted mesh cuts and nominal fastener profiles.
No CAD mutations. SVG vectors preserve true section contours; explosion translations only.
"""
import os,sys,json,html,hashlib
from pathlib import Path
import numpy as np,trimesh
import argparse
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--speaker-only',action='store_true');args=parser.parse_args()
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=False);WORK=OUT
for row in json.loads((ROOT/'hardware/rendering/source-lock.json').read_text())['files']:
    assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
os.environ['BGB_RENDER_OUTPUT']=str(OUT);os.environ['BGB_RENDER_FONT']='/System/Library/Fonts/Supplemental/Arial.ttf'
sys.path.insert(0,str(ROOT/'hardware/tools/rendering'));import render
INK='#292b3b';COPPER='#ac7254';BLUE='#697bba';METAL='#c5cbd4';BG='#fbfaf7'
def text(x,y,s,size=22,anchor='start',color=INK):return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{color}">{html.escape(s)}</text>'
def line(a,b,color=INK,width=2,dash=None):return f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}" fill="none" stroke="{color}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'
def poly(points,fill=METAL):return '<path d="M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in points)+' Z" fill="'+fill+'" stroke="'+INK+'" stroke-width="2"/>'
def arrow(a,b):return f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}" stroke="#755cb0" stroke-width="3" marker-end="url(#arrow)"/>'
def label(x,y,ls,point=None):
 s=''.join(text(x,y+i*27,t,21,'middle') for i,t in enumerate(ls))
 if point:s=line((x,y-17 if point[1]<y else y+len(ls)*27-10),point,'#746b62',1.4)+s
 return s
counter=0;AUDIT={}
def section(pid,occ,normal,origin,transform,xy,clip,name,color):
 global counter
 m=next(m for m in render.meshes if m['id']==pid and m['occ']==occ);v=transform(m['v']) if transform else m['v']
 seg=trimesh.intersections.mesh_plane(trimesh.Trimesh(v,m['f'],process=False),plane_normal=normal,plane_origin=origin)
 # Endpoint joining only; no smoothing, hulls, repairs or new geometry.
 coords={};adj={}
 for a,b in seg:
  ka=tuple(np.round(a,5));kb=tuple(np.round(b,5))
  if ka==kb:continue
  coords[ka]=a;coords[kb]=b;adj.setdefault(ka,set()).add(kb);adj.setdefault(kb,set()).add(ka)
 unused={frozenset((a,b)) for a,bs in adj.items() for b in bs};loops=[]
 while unused:
  e=next(iter(unused));a,b=tuple(e);unused.remove(e);chain=[a,b]
  while chain[-1]!=chain[0]:
   nxt=next((q for q in adj[chain[-1]] if frozenset((chain[-1],q)) in unused),None)
   if nxt is None:break
   unused.remove(frozenset((chain[-1],nxt)));chain.append(nxt)
  loops.append(chain)
 closed=[l for l in loops if l[-1]==l[0]]
 assert len(closed)==len(loops),(pid,'open section contour')
 d=' '.join('M'+' L'.join(f'{xy(coords[k])[0]:.3f},{xy(coords[k])[1]:.3f}' for k in loop)+' Z' for loop in loops)
 counter+=1;cid='clip'+str(counter);x,y,w,h=clip
 AUDIT[name]={'part':pid,'occurrence':occ,'plane_normal':normal,'plane_origin':origin,'closed_contours':len(loops),'source_path':m['source']['path'],'crop_pixels':clip}
 return f'<defs><clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath></defs><path d="{d}" fill="{color}" fill-rule="evenodd" stroke="{INK}" stroke-width="2" clip-path="url(#{cid})"/>'
def screw(x,y,d,length,scale=24,head=1.8):
 # Side elevation: shank length measured from bearing face; nominal head envelope only.
 rr=d/2*scale;h=head*scale;hr=d*.87*scale;L=length*scale
 s=poly([(x-h,y-hr*.7),(x-h*.72,y-hr),(x,y-hr),(x,y+hr),(x-h*.72,y+hr),(x-h,y+hr*.7)])
 s+=poly([(x,y-rr),(x+L-4,y-rr),(x+L,y-rr+4),(x+L,y+rr-4),(x+L-4,y+rr),(x,y+rr)])
 pitch=(.4 if d==2 else .5)*scale
 for t in np.arange(3,L-3,pitch):s+=line((x+t,y-rr+1),(x+t-4,y+rr-1),'#727b8b',1)
 s+=line((x-h,y-hr*.36),(x-h*.48,y-hr*.36),INK,2)+line((x-h,y+hr*.36),(x-h*.48,y+hr*.36),INK,2)
 return s

def washer(x,y,id,od,th,scale=24):
 s=''
 for sign in [-1,1]:s+=poly([(x,y+sign*id/2*scale),(x+th*scale,y+sign*id/2*scale),(x+th*scale,y+sign*od/2*scale),(x,y+sign*od/2*scale)])
 return s

def nut(x,y,d,af,th,scale=24):
 s='';w=th*scale;rr=af/2*scale;hole=d/2*scale;c=min(7,w*.17)
 for sign in [-1,1]:
  s+=poly([(x,y+sign*hole),(x,y+sign*(rr-c)),(x+c,y+sign*rr),(x+w-c,y+sign*rr),(x+w,y+sign*(rr-c)),(x+w,y+sign*hole)])
  s+=line((x+4,y+sign*(hole+4)),(x+w-4,y+sign*(hole+4)),'#737d8d',1)
 return s

def ring_section(x,y,th,outer,hole,scale,fill):return washer(x,y,hole,outer,th,scale).replace(METAL,fill)
def write(name,title,subtitle,body,height=850):
 s=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" role="img"><title>{html.escape(title)}</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#755cb0"/></marker></defs><rect width="1200" height="{height}" fill="{BG}"/><g font-family="Arial, sans-serif">'+text(36,48,title,29)+text(36,86,subtitle,20)+body+'</g></svg>'
 (OUT/name).write_text(s)
# Speaker: actual FB19 plane through one of four inner axes.
s=24;y=365
body=text(36,140,'OUTSIDE · screwdriver',23)+text(940,140,'INSIDE · hold nut',23)
body+=line((45,y),(1150,y),'#8e92a1',1.4,'10 5')+arrow((98,180),(1020,180))
body+=screw(100,y,3,12,s,2.6)
body+=section('FB19',0,[0,1,0],[0,-40,0],None,lambda p:(485+(107-p[0])*s,y-(p[2]+43)*s),(475,205,220,320),'speaker-boss',COPPER)
# Purchased tab local section only: no invented whole speaker model.
body+=ring_section(805,y,2,10,3.4,s,'#4e5664')
body+=washer(920,y,3.20,7.01,.53,s)+nut(1050,y,3,5.5,2.4,s)
for x,ly,ls,point in [(210,575,['M3 × 12','no head washer'],(210,330)),(550,575,['FB19 boss','4.8 mm'],(540,280)),(829,655,['Speaker tab','measure yours'],(829,260)),(933,575,['W3 washer','0.53 mm'],(927,280)),(1080,575,['M3 nut','ordinary hex'],(1080,295))]:body+=label(x,ly,ls,point)
body+=text(36,750,'Cut through ONE inner screw axis; parts are pulled apart along that axis.',23)
body+=text(36,790,'The copper outline comes from FB19. The tab section shows the required joint,',22)+text(36,820,'not a measured speaker profile. Check screw-tip clearance on your actual speaker.',22)
body+=text(36,870,'Use this stack at all 4 inner mounts per speaker. The 4 outer holes mount the grille.',22)
write('speaker-fastening-section.svg','SPEAKER / FOLLOW THE SCREW THROUGH THE JOINT','Exploded section · actual grille cut · nominal fastener profiles',body,915)
# Public speaker action views are generated by guide_speaker_actions.py.
if args.speaker_only:
 (WORK/'section-audit.json').write_text(json.dumps(AUDIT,indent=2)+'\n');sys.exit(0)
# Eye main joint and separate board joint: cut actual mating bodies.
ref=next(m for m in render.meshes if m['id']=='P06' and m['occ']==0);T=np.array(ref['source']['transform']).reshape(4,4);basis=T[:3,:3];org=T[:3,3]*10
local=lambda v:(v-org)@basis
s=28;y=330
body=text(36,135,'A · TWO OUTER HOUSING SCREWS PER EYE',24)
body+=line((45,y),(1150,y),'#8e92a1',1.4,'10 5')+arrow((90,177),(1080,177))+screw(95,y,2,10,s,1.8)
body+=washer(425,y,2.31,4.37,.25,s)
body+=section('P06',0,[0,1,0],[0,0,0],local,lambda p:(505+(7.5-p[2])*s,y-(p[0]-9)*s),(495,205,145,240),'eye-ear', '#e2decf')
body+=section('GS20',0,[0,1,0],[0,0,0],local,lambda p:(690+(4.2-p[2])*s,y-(p[0]-9)*s),(677,205,138,240),'eye-head', BLUE)
body+=section('GS11',0,[0,1,0],[0,0,0],local,lambda p:(925-p[2]*s,y-(p[0]-9)*s),(857,205,195,240),'eye-housing',COPPER)
# Captive nut stays in its actual side-channel axial location (-1 to -2.6).
body+=nut(925+28,y,2,4,1.6,s)
for x,ls,pt in [(235,['M2 × 10'],(230,295)),(431,['W2 · 0.25 mm'],(431,270)),(560,['P06 ear'],(560,255)),(755,['Head wall'],(752,247)),(986,['Housing +','side-loaded nut'],(975,274))]:body+=label(x,486,ls,pt)
body+=text(36,566,'Screw enters from inside the head. The nut sits under the housing’s 1 mm roof.',21)
body+=text(36,598,'Load that nut through the upper-edge channel before fitting the housing.',21)
s=32;y=910
body+=line((36,640),(1164,640),'#d1cbd5',1)+text(36,686,'B · TWO CENTRAL LED-BOARD SCREWS PER EYE',24)
body+=arrow((90,730),(1050,730))+line((45,y),(1140,y),'#8e92a1',1.4,'10 5')+screw(115,y,2,6,s,1.8)
body+=section('E03',0,[1,0,0],[0,0,0],local,lambda p:(455+(10.57-p[2])*s,y-(p[1]-4.318)*s),(427,775,160,250),'eye-board','#335b55')
body+=section('P06',0,[1,0,0],[0,0,0],local,lambda p:(750+(9-p[2])*s,y-(p[1]-4.318)*s),(725,775,200,250),'eye-board-carrier','#e2decf')
# Board nut pocket foam-facing at z4.2..5.8, held in P06.
body+=nut(750+(9-5.8)*s,y,2,4,1.6,s)
for x,ls,pt in [(210,['M2 × 6','NO washer'],(210,868)),(490,['LED board','rear face'],(480,855)),(829,['P06 + board nut','foam-facing pocket'],(848,850))]:body+=label(x,1072,ls,pt)
body+=text(36,1170,'The LED faces the foam; both cable sockets face inside the head.',22)
body+=text(36,1203,'Sections use the actual eye meshes. Hardware profiles are nominal; verify engagement.',21)
write('eye-fastening-sections.svg','EYES / TWO DIFFERENT FASTENING PATHS','Exploded mesh sections · parts move only along their screw axes',body,1245)
(WORK/'section-audit.json').write_text(json.dumps(AUDIT,indent=2)+'\n')
print('Wrote speaker and eye true sections')
# Horn: current AR01 axial section and a separate face view of the selected holes.
s=32;y=345
body=text(36,135,'A · FASTEN THE HORN TO THE ARM OFF THE SERVO',23)+arrow((85,180),(1090,180))
body+=line((45,y),(1130,y),'#8e92a1',1.4,'10 5')+screw(115,y,2,6,s,2)
# Supplied round horn: local material at the drilled hole; thickness is not established.
body+=ring_section(480,y,1.6,7,2.2,s,'#e3dccb')
body+=section('AR01',0,[0,0,1],[0,0,90],None,lambda p:(720+(p[0]-40.64)*s,y-(p[1]-9)*s),(705,213,285,260),'arm-horn-axis',BLUE)
body+=nut(720+(43.84-40.64)*s,y,2,4,1.6,s)
for x,ls,pt in [(207,['M2 × 6'],(210,306)),(501,['Original disk horn','drilled Ø2.2 mm hole'],(500,256)),(835,['AR01 core +','side-loaded M2 nut'],(845,288))]:body+=label(x,515,ls,pt)
body+=text(36,597,'The arm profile is the actual Z = 90 cut. Horn section thickness is illustrative;',21)+text(36,627,'seat the actual disk flat in the recess and verify screw engagement. No washer.',21)
body+=line((36,661),(1164,661),'#d1cbd5',1)+text(36,708,'B · TWO OFFSET SCREWS — KEEP THE CENTER FOR LATER',24)
# Actual face outline of the measured disk and selected pair. Other factory holes omitted.
cx,cy=294,949;r=23.55/2*15
body+=f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#e3dccb" stroke="{INK}" stroke-width="2"/>'
for xx in [cx-9*15,cx+9*15]:body+=f'<circle cx="{xx}" cy="{cy}" r="{1.1*15}" fill="{BG}" stroke="{INK}" stroke-width="2"/>'
body+=f'<circle cx="{cx}" cy="{cy}" r="29" fill="{BG}" stroke="{INK}" stroke-width="2"/>'
body+=line((cx-135,cy+64),(cx+135,cy+64),'#746b62',1)+text(cx,cy+98,'~18 mm selected pair',20,'middle')
body+=label(cx,761,['Original disk · Ø23.55 mm'],(cx,774))
body+=label(778,838,['Two M2 × 6 screws go through the offset holes','and into the arm’s side-loaded nuts.'],(cx+135,cy))
body+=label(808,1003,['Center opening is a SEPARATE screw path.','Use the supplied servo center screw later,','after the shaft has been centered.'],(cx,cy))
body+=text(36,1163,'The long splined hub faces the servo. Do not replace its center screw with an M2.',22)
body+=text(36,1195,'AR01 shown; AR04 has the same joint on the opposite side. Head adapter P14 is separate.',21)
write('horn-fastening-section.svg','ARM HORN / OFFSET FIXINGS AND CENTER SCREW','Actual arm section · disk diameter / hole pair measured; center opening illustrative',body,1245)
# WAGOs use tape on R24; retired pressure-pad geometry is intentionally not rendered.
(WORK/'section-audit.json').write_text(json.dumps(AUDIT,indent=2)+'\n')
render.render('pebble-bracket-detail',{'select':['P11'],'occ':{'P11':[0]},'camera':[-.3,-1.8,.9],'title':'BODY LIGHTS / ONE P11 BRACKET','footer':'Two pebbles per P11 bracket • light faces toward the diffuser'})
