#!/usr/bin/env python3
"""Validate or stage whole editable projects without slicing or dispatch."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from authority import digest, validate_input_authority
try:
    from . import semantics, privacy
except ImportError:  # Direct script execution.
    import semantics
    import privacy

ROOT = Path(__file__).resolve().parents[3]
CURRENT = ROOT / 'hardware/printing/current'


def validate(release=False, quiet=False):
    lock_path = ROOT / 'hardware/printing/recipes/projects.json'
    lock = json.loads(lock_path.read_text())
    validate_input_authority(lock, lock_path, release=release)
    contract_path = ROOT / lock['semantic_contract']['path']
    if digest(contract_path) != lock['semantic_contract']['sha256']:
        raise ValueError('Changed semantic contract; reviewed lock update required')
    for project in lock['projects']:
        path = ROOT / project['path']
        privacy.check_project(path)
        if digest(path) != project['sha256']:
            raise ValueError('Changed project: ' + str(path))
        with zipfile.ZipFile(path) as z:
            if len(z.namelist()) != len(set(z.namelist())):
                raise ValueError('Duplicate ZIP members')
            if z.testzip():
                raise ValueError('Corrupt 3MF')
            model = ET.fromstring(z.read('3D/3dmodel.model'))
            items = model.findall(semantics.N+'build/'+semantics.N+'item')
            if len(items) != project['instances']:
                raise ValueError('Unexpected build instance count')
            for name in z.namelist():
                if name.endswith(('.model', '.xml', '.rels', '.config')) and name != 'Metadata/project_settings.config':
                    ET.fromstring(z.read(name))
    manifest = json.loads((CURRENT / 'manifest.json').read_text())
    catalog = json.loads((ROOT / 'hardware/catalog/parts.json').read_text())
    contract = json.loads(contract_path.read_text())
    pending = semantics.validate_current(ROOT, lock, manifest, catalog, contract)
    lock['readiness'] = {
        'immutable_recipe_identity': 'verified',
        'independent_source_geometry': 'pending' if pending else 'verified',
        'required_instances': sum(p['quantity'] for p in catalog['parts']),
        'required_types': len(catalog['parts']),
        'required_plates': len(manifest['plates']),
        'publication_blockers': pending,
        'physical_qualification': 'unchanged; not established by this check',
    }
    if not quiet:
        r = lock['readiness']
        print(f"PASS: exact project bytes and semantic invariants; {r['required_instances']} required instances / {r['required_types']} types / {r['required_plates']} plates; replacement demand checked")
        if pending:
            print(f'PENDING: independent selected-STL review for {len(pending)} instances; prior digital acceptance preserved. Use --json for actionable blockers.')
    if release and pending:
        raise ValueError('Publication blocked: independent selected-STL geometry review pending')
    return lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'prepare'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--json', action='store_true', help='Print structured readiness and pending review reasons')
    args = parser.parse_args()
    lock = validate(args.release, quiet=args.json)
    if args.json:
        print(json.dumps(lock['readiness'], indent=2))
    if args.action == 'prepare':
        if not args.output:
            raise ValueError('--output is required')
        args.output.mkdir(parents=True, exist_ok=False)
        for project in lock['projects']:
            shutil.copyfile(ROOT / project['path'], args.output / Path(project['path']).name)
        (args.output / 'baseline.json').write_text(json.dumps({'status': 'candidate copy; no slicing or dispatch', 'projects': lock['projects'], 'readiness': lock['readiness']}, indent=2)+'\n')


if __name__ == '__main__':
    main()
