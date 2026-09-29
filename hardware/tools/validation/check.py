#!/usr/bin/env python3
"""Compose offline current-input, recipe and guide checks; report honest pending work."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def module(name, path):
    sys.path.insert(0,str((ROOT/path).parent))
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def check(publication=False):
    result={'errors':[],'blockers':[],'stages':{}}
    try:
        dc=module('check_dc','hardware/cad/design_control.py')
        registry=dc.read(dc.REGISTRY);release,count=dc.validate(registry)
        if (dc.CAD/'CURRENT-DESIGN.md').read_text()!=dc.render(registry,release):
            raise ValueError('CURRENT-DESIGN.md is stale; run design_control.py render')
        result['stages']['cad']={'status':'verified','revision':release['design_revision'],'current_files':count}
        render=module('check_render','hardware/tools/rendering/source.py')
        render.checked_source()
        result['stages']['render-inputs']={'status':'verified','scope':'source identity and native occurrence composition; no image/physical review'}
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result['errors'].append('CAD/render: '+str(exc))
    try:
        projects=module('check_projects','hardware/tools/printing/projects.py')
        ready=projects.validate(quiet=True)['readiness']
        result['stages']['printing']=ready
        result['blockers'].extend(ready['publication_blockers'])
        if publication:
            authority=module('check_authority','hardware/tools/authority.py')
            path=ROOT/'hardware/printing/recipes/projects.json'
            authority.validate_input_authority(json.loads(path.read_text()),path,release=True)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        result['errors'].append('Printing: '+str(exc))
    guide=module('check_guide','hardware/tools/guide/consistency.py').check()
    result['stages']['guide']=guide['review']
    result['errors'].extend('Guide: '+x for x in guide['errors'])
    result['blockers'].extend(guide['blockers'])
    result['ok']=not result['errors'] and (not publication or not result['blockers'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publication',action='store_true')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args();report=check(args.publication)
    if args.json:print(json.dumps(report,indent=2))
    else:
        print('Offline hardware invariants: '+('FAIL' if report['errors'] else 'PASS'))
        for error in report['errors']:print('ERROR:',error)
        if args.publication:
            print('Publication readiness: '+('BLOCKED' if report['blockers'] or report['errors'] else 'eligible for release review'))
            for blocker in report['blockers']:print('REVIEW REQUIRED:',blocker)
        else:
            print('Publication review is separate: run this command with --publication for outstanding reviews.')
        print('No cloud save, slicing, printer operation or physical qualification performed.')
    raise SystemExit(0 if report['ok'] else 1)
