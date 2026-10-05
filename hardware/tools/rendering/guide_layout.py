"""Cover-off locators from accepted CAD; labels are not wire cut dimensions."""
import base64
import html
import itertools
import numpy as np


def render_layout(render, output):
    original=render.meshes
    selected={'FB01','FB24','E06','E07','E08','E09','E14','E15','E16','E18'}
    parts=[dict(m) for m in original if m['id'] in selected]
    for m in parts:
        if m['id']=='FB01':m['guide_color']=(197,207,215)
    camera=np.array([0,.001,-1.]);camera/=np.linalg.norm(camera)
    x=np.cross([0,0,1],camera);x/=np.linalg.norm(x)
    basis=np.array([x,np.cross(camera,x),camera]).T
    bounds=np.array([[-112,-102,-68],[112,102,1]])
    corners=np.array(list(itertools.product(*zip(*bounds))))@basis
    lo=corners[:,:2].min(0);hi=corners[:,:2].max(0);mid=(hi+lo)/2
    scale=min(960/(hi[0]-lo[0]),960/(hi[1]-lo[1]))*.75
    def project(p):
        q=np.array(p)@basis
        return [450+(q[0]-mid[0])*scale,450-(q[1]-mid[1])*scale]
    render.meshes=parts
    render.render('layout-background',dict(select=['all'],camera=camera.tolist(),clean=True,
                  size=[1200,1200],margin=120,frame_world_bounds=bounds.tolist()))
    png=base64.b64encode((output/'layout-background.png').read_bytes()).decode()
    def label(text,p,xy,anchor='start'):
        q=project(p);a,b=xy
        return (f'<path d="M{a},{b+8}L{q[0]:.1f},{q[1]:.1f}" stroke="#526576" stroke-width="2"/>'
                f'<text x="{a}" y="{b}" text-anchor="{anchor}" font-family="Arial,sans-serif" font-size="30" font-weight="bold" fill="#22384e" stroke="#f3f7fa" stroke-width="7" paint-order="stroke">{html.escape(text)}</text>')
    body=f'<image width="900" height="900" href="data:image/png;base64,{png}"/>'
    body+='<g font-family="Arial,sans-serif" font-size="30" font-weight="bold" text-anchor="middle" fill="#22384e"><text x="450" y="45">REAR</text><text x="450" y="864">FRONT · audio cradle</text></g>'
    for name,y in [('W1',52),('W3',22),('W2',-8),('W4',-38)]:
        body+=label(name,[48,y,-22],[100,project([48,y,-22])[1]],'end')
    for name,p,xy in [('S1',[-18,-17,-25],[620,515]),('S2',[-18,-39,-25],[620,585]),
                      ('Pi',[-50,32,-25],[790,285]),('SD',[-50,66,-15],[785,140]),
                      ('USB data',[-53.5,-3,-22],[725,470]),('POWER',[-22,53.4,-22],[425,225]),
                      ('F2',[34,74,-22],[270,145]),('C1',[24,0,-20],[400,425]),
                      ('C2',[24,32,-20],[400,322]),('J1',[80,72,-40],[65,195]),('Harness',[0,0,-2],[420,395])]:body+=label(name,p,xy)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" role="img"><title>Base viewed through its open bottom: Pi USB toward front, SD toward rear, S1 above S2, W1 W3 W2 W4 rear to front</title><rect width="900" height="900" fill="#f3f7fa"/>{body}</svg>'
    (output/'base-electrical-layout.svg').write_text(svg)
    # The installation locator shows only the boards being positioned, not
    # components that the builder will install in later steps.
    render.meshes=[m for m in parts if m['id'] in ('FB01','E09','E15')]
    render.render('board-layout-background',dict(select=['all'],camera=camera.tolist(),clean=True,
                  size=[1200,1200],margin=120,frame_world_bounds=bounds.tolist()))
    png=base64.b64encode((output/'board-layout-background.png').read_bytes()).decode()
    body=f'<image width="900" height="900" href="data:image/png;base64,{png}"/>'
    body+='<g font-family="Arial,sans-serif" font-size="30" font-weight="bold" text-anchor="middle" fill="#22384e"><text x="450" y="45">REAR · microSD card end</text><text x="450" y="864">FRONT · microphone opening</text></g>'
    for name,p,xy in [('S1',[-18,-17,-25],[390,515]),('S2',[-18,-39,-25],[390,585]),
                      ('Pi',[-50,32,-25],[790,285]),('SD',[-50,66,-15],[785,140]),
                      ('USB data',[-53.5,-3,-22],[725,470]),('POWER',[-22,53.4,-22],[425,225])]:body+=label(name,p,xy)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" role="img"><title>Locate the Pi and both shifters through the open bottom; USB front, SD rear</title><rect width="900" height="900" fill="#f3f7fa"/>{body}</svg>'
    (output/'board-layout.svg').write_text(svg)
    render.meshes=original
    from guide_routing import render_routes
    routes = render_routes(render, output, parts)
    return ['assets/community/base-electrical-layout.svg','assets/community/board-layout.svg', *routes]
