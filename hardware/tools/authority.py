"""Bind independent current build inputs to the exact registry-selected CAD release."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inside(value):
 path=(ROOT/value).resolve()
 if Path(value).is_absolute() or not path.is_relative_to(ROOT):raise ValueError('Authority path escapes repository')
 rel=path.relative_to(ROOT)
 if '.git' in rel.parts or '.work' in rel.parts or rel.as_posix().startswith(('hardware/cad/preservation/','hardware/cad/releases/')):raise ValueError('Forbidden current input: '+str(value))
 return path
def validate_input_authority(lock, lock_path, release=False):
 if (ROOT/'hardware/cad/design-control/publication-in-progress.json').exists():raise ValueError('Incomplete publication; inspect recovery journal')
 registry=json.loads((ROOT/'hardware/cad/design-control/registry.json').read_text());main=registry['main']
 keys=('design_revision','cloud_file_id','cloud_version','release_manifest','release_manifest_sha256')
 if lock.get('cad')!={k:main[k] for k in keys}:raise ValueError('Input lock does not match exact accepted CAD authority')
 manifest=inside(main['release_manifest'])
 if digest(manifest)!=main['release_manifest_sha256']:raise ValueError('Accepted CAD manifest changed')
 if release:
  binding=registry.get('delivery')
  if not binding:raise ValueError('Release output requires a selected delivery')
  path=inside(binding['path'])
  if digest(path)!=binding['sha256']:raise ValueError('Selected delivery changed')
  delivery=json.loads(path.read_text())
  if any(delivery.get(k)!=main[k] for k in keys[3:]) or delivery['cad']!={k:main[k] for k in keys[:3]}:raise ValueError('Delivery does not match exact accepted CAD authority')
  expected=next((r['sha256'] for r in delivery['files'] if r['path']==str(lock_path.relative_to(ROOT))),None)
  if expected!=digest(lock_path):raise ValueError('Input lock is not bound by selected delivery')
 return registry
