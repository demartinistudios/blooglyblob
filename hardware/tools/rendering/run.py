#!/usr/bin/env python3
"""Render a selected current scene into a fresh output directory; never changes release images."""
import argparse,hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--view',required=True,help='scene key such as r22/part-GS11, or eye-details');p.add_argument('--output',type=Path,required=True);p.add_argument('--font',type=Path,required=True);a=p.parse_args()
from source import checked_source, selected
lock, registry = selected()
if lock.get('scene_review_cad') != registry['main']:
    raise ValueError('Review scene dimensions against the selected CAD before rendering')
source, registry, _ = checked_source((lock, registry))
os.environ['BGB_RENDER_MESH_SOURCE'] = str(source)
if not a.font.is_file():raise ValueError('Supply a licensed local TrueType font')
a.output.mkdir(parents=True,exist_ok=False)
os.environ['BGB_RENDER_OUTPUT']=str(a.output.resolve());os.environ['BGB_RENDER_FONT']=str(a.font.resolve())
if a.view=='eye-details':
 import eye_details
else:
 import render
 views=json.loads((ROOT/'hardware/rendering/scenes/views.json').read_text());scene=views[a.view]
 palette={(r['path'],r['body']):r['chosen_rgb'] for r in json.loads((ROOT/'hardware/rendering/r22-colors.json').read_text())['assignments']};base=render.col
 render.col=lambda m,h:tuple(palette.get((m['source'].get('path'),m['source'].get('body'))) or base(m,h))
 render.render(Path(scene['output']).stem,scene['view'],scene['thumbnail'])
 (a.output/'render-audit.json').write_text(json.dumps(render.render_audit,indent=2)+'\n')
import importlib.metadata as metadata
(a.output/'runtime.json').write_text(json.dumps({'font_sha256':hashlib.sha256(a.font.read_bytes()).hexdigest(),'packages':{n:metadata.version(n) for n in ['numpy','pillow','numba','trimesh']},'view':a.view,'status':'candidate image; review before promotion'},indent=2)+'\n')
print('Rendered',a.view,'to',a.output)
