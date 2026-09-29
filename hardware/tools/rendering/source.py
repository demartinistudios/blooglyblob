"""Resolve reviewed render inputs without private paths or historical payloads."""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'hardware/tools'))
from authority import digest, inside, validate_input_authority


def selected():
    path = ROOT / 'hardware/rendering/source-lock.json'
    lock = json.loads(path.read_text())
    registry = validate_input_authority(lock, path)
    for row in lock['files']:
        if digest(inside(row['path'])) != row['sha256']:
            raise ValueError('Changed render source: ' + row['path'])
    roles = lock['roles']
    bound = {r['path'] for r in lock['files']}
    if not set(roles.values()) <= bound:
        raise ValueError('Unbound render source role')
    release = json.loads(inside(registry['main']['release_manifest']).read_text())
    original = {r['path']: r['sha256'] for r in release['artifacts']}
    for role, provenance in lock.get('release_sources', {}).items():
        if original.get(provenance) != digest(inside(roles[role])):
            raise ValueError('Render input differs from accepted native export: ' + role)
    return lock, registry


def checked_source(selection=None):
    lock, registry = selection if selection is not None else selected()
    roles = lock['roles']
    source = inside(roles['mesh'])
    # Independent native export catches a bad composition even when its hash was updated.
    native = json.loads(inside(roles['native_meshes']).read_text())
    with gzip.open(source, 'rt') as stream:
        composed = {r['path']: r for r in json.load(stream)}
    for row in native:
        actual = composed.get(row['path'])
        if actual is None:
            raise ValueError('Native occurrence absent from render mesh: ' + row['path'])
        faces = 'triangles' if 'triangles' in row else 'faces'
        for old, new in [('vertices_cm', 'vertices_cm'), (faces, 'faces'), ('transform', 'transform')]:
            if row[old] != actual[new]:
                raise ValueError(f'Native/composed mismatch: {row["path"]} {old}')
    return source, registry, digest(ROOT / 'hardware/cad/design-control/registry.json')
