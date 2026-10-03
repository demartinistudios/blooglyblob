#!/usr/bin/env python3
"""Validate local CAD release records and render their human-readable index.

No Fusion mutation or network access. Promotion locks are cooperative, never expired.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

CAD = Path(__file__).resolve().parent
ROOT = CAD.parents[1]
CONTROL = CAD / 'design-control'
REGISTRY = CONTROL / 'registry.json'
LOCK = CONTROL / 'promotion-lock.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def artifact_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'Artifact outside workspace: {value}')
    return path


def checked(artifact):
    path = artifact_path(artifact['path'])
    if not path.is_file() or digest(path) != artifact['sha256']:
        raise ValueError(f'Missing or changed artifact: {artifact["path"]}')
    return path


def current_path(value):
    """Resolve a maintained input, excluding scratch work and Git internals."""
    path = artifact_path(value)
    rel = path.relative_to(ROOT).as_posix()
    forbidden = ('hardware/.work/', 'hardware/cad/preservation/', 'hardware/cad/releases/')
    if Path(value).is_absolute() or rel.startswith(forbidden) or '.git' in path.relative_to(ROOT).parts:
        raise ValueError(f'Forbidden current input: {value}')
    return path


def validate_current(registry):
    """Validate current inputs against the accepted native and selected delivery."""
    main = registry['main']
    release = read(checked({'path': main['release_manifest'], 'sha256': main['release_manifest_sha256']}))
    keys = ('design_revision', 'cloud_file_id', 'cloud_version')
    if any(main[k] != release[k] for k in keys):
        raise ValueError('MAIN and accepted release disagree')
    current_path(registry['current_inputs']['path'])
    current = read(checked(registry['current_inputs']))
    if not current['files']:
        raise ValueError('Empty mandatory current set')
    required = {}
    for row in current['files']:
        path = current_path(row['path'])
        if path in required:
            raise ValueError(f'Duplicate current input: {row["path"]}')
        checked(row)
        required[path] = row['sha256']
    native = registry['accepted_native']
    path = current_path(native['path'])
    originals = {r['path']: r['sha256'] for r in release['artifacts']}
    if (originals.get(native['original_path']) != native['sha256']
            or required.get(path) != native['sha256']):
        raise ValueError('The accepted native must match the release and mandatory current set')
    if registry.get('delivery'):
        delivery = read(checked(registry['delivery']))
        if delivery['cad'] != {k: main[k] for k in keys}:
            raise ValueError('Delivery does not match accepted CAD')
        if any(delivery.get(k) != main[k] for k in ('release_manifest', 'release_manifest_sha256')):
            raise ValueError('Delivery must bind the exact accepted manifest')
        for row in delivery['files']:
            path = current_path(row['path'])
            checked(row)
            if required.get(path) != row['sha256']:
                raise ValueError(f'Delivery input absent from current set: {row["path"]}')
    return release, len(required)


def validate(registry):
    if (CONTROL / 'publication-in-progress.json').exists():
        raise ValueError('Incomplete publication; inspect the recorded recovery journal before use')
    if registry['schema_version'] != 3:
        raise ValueError('Unsupported registry schema')
    return validate_current(registry)


def render(registry, release):
    main = registry['main']
    lines = ['# Current Blue Glee Blob design', '',
        f'Open **{main["cloud_name"]}** in Fusion → {main["project"]}.', '',
        f'Accepted design **{main["design_revision"]}**, exact cloud version **v{main["cloud_version"]}**.',
        f'Permanent file ID: `{main["cloud_file_id"]}`.', '']
    if registry.get('delivery'):
        delivery = read(checked(registry['delivery']))
        lines += ['## Selected delivery', '',
            delivery.get('summary', delivery.get('scope', '')), '',
            f'[Delivery record]({os.path.relpath(artifact_path(registry["delivery"]["path"]), CAD)})', '']
    lines += ['## CAD acceptance record', '',
        'Recorded when this CAD revision was accepted; delivery status above may supersede downstream status below.', '',
        release['summary'], '',
        '## Current inputs', '',
        '[Fusion assembly (.f3d)](current/assembly.f3d) · '
        '[STEP assembly (.step)](current/assembly.step) for other CAD applications.', '',
        '[Native assembly and selected exports](current/) · [Parts catalog](../catalog/parts.json) · '
        '[Print projects](../printing/current/) · [Build guide](../build-guide/README.md)', '',
        'The registry selects CAD authority. Its mandatory input lock is checked even without a delivery. '
        'A delivery binds the print recipes, parts catalog and renders to that CAD; it does not approve physical fit. '
        'The build guide is not part of the release: it reads these files when it is built.', '',
        '## Checks', '',
        '`python3 hardware/cad/design_control.py check` validates the mandatory current set, '
        'accepted native and any selected delivery.', '',
        'The [workflow](DESIGN-WORKFLOW.md) defines experiments, promotion and recovery.', '',
        'No local check queries live Fusion or establishes print completion, fit, strength or optical acceptance.', '',
        'Generated from [registry.json](design-control/registry.json); use the render command after a reviewed registry update.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'render', 'lock', 'unlock'])
    parser.add_argument('--owner')
    args = parser.parse_args()
    registry = read(REGISTRY)
    # Unlock must remain possible after a failed check; only the recorded owner may do it.
    if args.action == 'unlock':
        if not args.owner or read(LOCK)['owner'] != args.owner:
            raise ValueError('Only the recorded promotion owner can release the lock')
        LOCK.unlink()
        print('Promotion lock released')
        return
    release, count = validate(registry)
    expected = render(registry, release)
    current = CAD / 'CURRENT-DESIGN.md'
    if args.action == 'render':
        pending = current.with_suffix('.md.tmp')
        pending.write_text(expected)
        pending.replace(current)
        print('Updated CURRENT-DESIGN.md')
    elif args.action == 'lock':
        if not args.owner:
            raise ValueError('--owner is required')
        payload = {'owner': args.owner, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'registry_sha256': digest(REGISTRY), 'baseline': registry['main']}
        with LOCK.open('x') as stream:
            stream.write(json.dumps(payload, indent=2) + '\n')
        print('Promotion reserved; recheck live Fusion before editing')
    else:
        if not current.exists() or current.read_text() != expected:
            raise ValueError('CURRENT-DESIGN.md is stale; run render')
        print(f'PASS: {release["design_revision"]}; {count} artifact hashes; current page matches registry')
        if LOCK.exists():
            print('Active promotion owner: ' + read(LOCK)['owner'])
        print('Local records only; live Fusion state is not queried.')


if __name__ == '__main__':
    main()
