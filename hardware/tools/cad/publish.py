#!/usr/bin/env python3
"""Stage, install or recover an explicit local input selection; never saves CAD or prints.

A candidate directory mirrors repository paths. Stage records exact old/new bytes;
install requires the existing promotion lock and writes registry last. Keep the
journal until Git/tag and independent backup recovery have been verified.
"""
import argparse
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = 'hardware/cad/design-control/registry.json'
PAGE = 'hardware/cad/CURRENT-DESIGN.md'
LOCK = 'hardware/cad/design-control/promotion-lock.json'
MARKER = 'hardware/cad/design-control/publication-in-progress.json'


def control(root):
    spec = importlib.util.spec_from_file_location('publication_control', ROOT/'hardware/cad/design_control.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ROOT = Path(root).resolve(); module.CAD = module.ROOT/'hardware/cad'
    module.CONTROL = module.CAD/'design-control'
    return module


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique siblings let recovery proceed even after a process dies mid-write.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.',
                                         suffix='.publication-tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_marker(path, value):
    """Publish complete marker bytes atomically, without replacing another owner."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.publication-tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(value)+'\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_candidate(root, payload, paths):
    """Validate the selected union; copy only dependencies, never historical payloads."""
    dc = control(root)
    def source(name):
        dc.current_path(name)
        return payload/name if name in paths else root/name
    registry = json.loads(source(REGISTRY).read_text())
    if registry.get('schema_version') != 3:
        raise ValueError('Staged publication requires current schema 3')
    names = {REGISTRY, PAGE, registry['main']['release_manifest'], registry['current_inputs']['path']}
    inputs = json.loads(source(registry['current_inputs']['path']).read_text())
    names.update(r['path'] for r in inputs['files'])
    if registry.get('delivery'):
        names.add(registry['delivery']['path'])
        delivery = json.loads(source(registry['delivery']['path']).read_text())
        names.update(r['path'] for r in delivery['files'])
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        for name in names:
            target = tree/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source(name), target)
        selected = control(tree)
        release, _ = selected.validate(registry)
        if source(PAGE).read_text() != selected.render(registry, release):
            raise ValueError('Candidate CURRENT-DESIGN.md does not match registry')


def stage(root, candidate, output, owner, paths):
    root=Path(root).resolve(); candidate=Path(candidate).resolve(); output=Path(output).resolve()
    dc=control(root)
    if not owner or len(paths)!=len(set(paths)) or REGISTRY not in paths or PAGE not in paths:
        raise ValueError('Supply owner and unique explicit files including registry and current page')
    if output.exists(): raise ValueError('Use a new journal directory')
    for name in paths:
        dc.current_path(name)
        path=(candidate/name).resolve()
        if not path.is_relative_to(candidate) or not path.is_file(): raise ValueError('Candidate path missing or escaping: '+name)
        old=root/name
        if name.startswith(('hardware/cad/design-control/releases/','hardware/cad/design-control/deliveries/')) and old.exists() and dc.digest(old)!=dc.digest(path):
            raise ValueError('Cannot overwrite immutable manifest: '+name)
    verify_candidate(root,candidate,paths)
    output.mkdir(parents=True)
    journal={'owner':owner,'baseline_registry_sha256':dc.digest(root/REGISTRY),'status':'staged','files':[]}
    for name in paths:
        old=root/name; new=candidate/name
        before=dc.digest(old) if old.exists() else None
        for base, src in [('after',new),('before',old)]:
            if src.exists():
                target=output/base/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
        journal['files'].append({'path':name,'before':before,'after':dc.digest(new)})
    (output/'journal.json').write_text(json.dumps(journal,indent=2)+'\n')
    return journal


def install(root, output, owner, recover=False):
    root=Path(root).resolve(); output=Path(output).resolve();dc=control(root)
    journal=json.loads((output/'journal.json').read_text())
    lock=json.loads((root/LOCK).read_text())
    if journal['owner']!=owner or lock['owner']!=owner:
        raise ValueError('Only the recorded lock and journal owner may publish/recover')
    if lock['registry_sha256'] != journal['baseline_registry_sha256']:
        raise ValueError('Lock baseline differs from staged journal')
    rows=journal['files'];paths=[r['path'] for r in rows]
    if len(paths)!=len(set(paths)) or REGISTRY not in paths or PAGE not in paths:
        raise ValueError('Invalid journal file allowlist')
    marker=root/MARKER
    if recover:
        if json.loads(marker.read_text()) != {'owner':owner,'journal':str(output)}:
            raise ValueError('Recovery marker differs from this journal')
    else:
        if journal['status']!='staged' or dc.digest(root/REGISTRY)!=journal['baseline_registry_sha256']:
            raise ValueError('Publication baseline changed')
    for row in rows:
        name=row['path']; target=dc.current_path(name)
        current=dc.digest(target) if target.exists() else None
        allowed={row['before'],row['after']} if recover else {row['before']}
        if current not in allowed:raise ValueError('Concurrent edit; preserve and reconcile: '+name)
        which='before' if recover else 'after';expected=row[which]
        saved=(output/which/name).resolve()
        if not saved.is_relative_to(output/which):raise ValueError('Journal path escapes recovery directory')
        if expected and dc.digest(saved)!=expected:raise ValueError('Recovery/candidate bytes changed: '+name)
    if not recover:
        verify_candidate(root,output/'after',paths)
        marker.parent.mkdir(parents=True,exist_ok=True)
        create_marker(marker, {'owner':owner,'journal':str(output)})
    # Any interruption leaves the marker, so readers fail closed until recovery.
    for row in sorted(rows,key=lambda r:r['path']==REGISTRY):
        name=row['path'];target=root/name;which='before' if recover else 'after'
        if row[which] is None:
            if target.exists():target.unlink()
        else:save(target,(output/which/name).read_bytes())
    journal['status']='recovered' if recover else 'installed'
    save(output/'journal.json',(json.dumps(journal,indent=2)+'\n').encode())
    marker.unlink()
    return journal


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['stage','install','recover']);p.add_argument('--owner',required=True)
    p.add_argument('--journal',type=Path,required=True);p.add_argument('--candidate',type=Path)
    p.add_argument('--file',action='append',default=[])
    a=p.parse_args()
    if a.action=='stage':
        if not a.candidate:p.error('stage requires --candidate')
        result=stage(ROOT,a.candidate,a.journal,a.owner,a.file)
    else:result=install(ROOT,a.journal,a.owner,recover=a.action=='recover')
    print(result['status']+'; lock and recovery bytes retained; no cloud or machine operation')
