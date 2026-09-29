#!/usr/bin/env python3
"""Report affected outputs from current IDs and authored uses; review unknown relationships."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(name):
    return json.loads((ROOT/name).read_text())


def impact(item_id):
    catalog = read('hardware/catalog/parts.json')
    items = catalog['parts'] + catalog.get('optional_parts', [])
    guide = read('hardware/build-guide/src/guide-data.json')
    cards = read('hardware/build-guide/src/parts.json')
    part = next((p for p in items if p['part_id']==item_id), None)
    card = next((p for p in cards if p['id']==item_id), None)
    if part is None and card is None:
        raise ValueError('Unmapped changed input: '+item_id+'; review all relevant surfaces explicitly')
    steps = set(part.get('guide_review_step_ids', part.get('guide_step_ids', []))) if part else set()
    for step in guide['steps']:
        if item_id in step.get('parts', {}) or item_id in step.get('hardware', {}) or '{part:'+item_id+'}' in json.dumps(step):
            steps.add(step['id'])
    existing = {s['id'] for s in guide['steps']}
    stale_steps = sorted(steps-existing)
    scenes=read('hardware/rendering/scenes/views.json')
    views={k:v for k,v in scenes.items() if (ROOT/'hardware/build-guide/src'/v['output']).exists()
           and set(v['view'].get('select',[]))&{item_id,'all'} and item_id not in v['view'].get('exclude',[])} if part else {}
    # Include the maintained custom/full-model scenes, not just the original library.
    if part:
        path=ROOT/'hardware/tools/guide/render_models.py'
        spec=importlib.util.spec_from_file_location('impact_scenes',path)
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        renderer.ROOT=ROOT;renderer.SRC=ROOT/'hardware/build-guide/src'
        for output,scene in renderer.scenes().items():
            view=scene['view']
            if set(view.get('select',[]))&{item_id,'all'} and item_id not in view.get('exclude',[]):
                views[output]=dict(scene,output=output)
    images={v['output'] for v in views.values()}
    if card and card.get('image'):images.add(card['image'])
    if part:images.add('assets/r16/service-stand.png')
    if item_id in ('FB01','FB41','M3x6','N3'):
        images.update(['assets/community/front-nut-entry.png','assets/community/front-grille-fastening.png'])
    interfaces=[x for x in read('hardware/assembly/interfaces.json')['interfaces'] if item_id in x['parts']]
    return {'item_id':item_id,'geometry_sha256':part['geometry_sha256'] if part else None,
            'instances':part.get('instances',[]) if part else [],
            'plates':sorted({i['plate'] for i in part['instances']}) if part else [],
            'guide_step_ids':sorted(steps&existing),'unmapped_step_ids':stale_steps,
            'images_to_review':sorted(images),'render_views':sorted(views),
            'interfaces_to_review':interfaces,
            'other_surfaces_to_review':['parts/supplies cards','downloads and templates','service/repeat-build instructions','software/wiring promises','progress migration relevance'],
            'status':'impact leads, not complete proof; unknown relationships require explicit review',
            'unchanged_parts':'Verify relevant dependencies unchanged; never clear unrelated browser progress'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('item_id',help='Printed part, supply or fastener ID')
    print(json.dumps(impact(parser.parse_args().item_id),indent=2))
