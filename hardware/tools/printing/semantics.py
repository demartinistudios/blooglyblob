"""Bounded, stdlib-only Bambu 3MF comparison; never slices or modifies a project.

Only millimetre, one-build-item-per-object component meshes are supported. Unknown
hierarchies fail closed. Identity is supplied by an explicit stable recipe map,
never inferred from names, plate labels, numeric Bambu IDs or array position.
"""
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

N = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
P = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
# Historical roundtrip error was < 5e-6 mm. 1e-4 allows float32 serialization,
# while being far below the 0.3 mm smallest clearance cited by the print review.
TOLERANCE_MM = 1e-4


def unique(rows, key, what):
    result = {}
    for row in rows:
        value = key(row)
        if value is None or value in result:
            raise ValueError('Missing/duplicate ' + what + ': ' + str(value))
        result[value] = row
    return result


def metadata(element):
    rows = element.findall('metadata')
    if any(x.get('key') is None and set(x.attrib) != {'face_count'} for x in rows):
        raise ValueError('Unsupported metadata without key')
    return {k: v.get('value') for k, v in unique([x for x in rows if x.get('key') is not None], lambda x: x.get('key'), 'metadata key').items()}


def matrix(value):
    result = IDENTITY[:] if value is None else list(map(float, value.split()))
    if len(result) != 12 or not all(math.isfinite(x) for x in result):
        raise ValueError('Unsupported/nonfinite transform')
    return result


def transform(vertices, t):
    return [tuple(sum(v[i] * t[3*i+j] for i in range(3)) + t[9+j] for j in range(3)) for v in vertices]


def load_meshes(stream):
    """Release each component XML tree after converting its numeric geometry."""
    result = {}
    events = ET.iterparse(stream, events=('start', 'end'))
    _, root = next(events)
    if root.get('unit', 'millimeter') != 'millimeter':
        raise ValueError('Unsupported component units')
    for event, element in events:
        if event != 'end' or element.tag != N+'object':
            continue
        cid = element.get('id')
        if cid is None or cid in result:
            raise ValueError('Missing/duplicate mesh object')
        mesh = element.find(N+'mesh')
        if mesh is None:
            raise ValueError('Unsupported nested component; manual review required')
        vertices = [tuple(float(x.get(k)) for k in 'xyz') for x in mesh.findall(N+'vertices/'+N+'vertex')]
        faces = [tuple(int(x.get(k)) for k in ('v1', 'v2', 'v3')) for x in mesh.findall(N+'triangles/'+N+'triangle')]
        if not vertices or not faces or not all(math.isfinite(c) for v in vertices for c in v):
            raise ValueError('Empty/nonfinite mesh')
        if any(i < 0 or i >= len(vertices) for f in faces for i in f):
            raise ValueError('Invalid triangle index')
        result[cid] = (vertices, faces)
        element.clear()
    return result


def project_selection(root, manifest, contract):
    roles = unique(contract['projects'], lambda p: p['role'], 'project role')
    expected_roles = {'required'} | ({'replacement'} if manifest.get('optional_petg_project') else set())
    if set(roles) != expected_roles:
        raise ValueError('Missing/duplicate or unexpected selected project role')
    for role, field in [('required', 'master_project'), ('replacement', 'optional_petg_project')]:
        if role not in roles:
            continue
        filename = manifest.get(field)
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError('Selected project must be a filename in printing/current')
        path = root / 'hardware/printing/current' / filename
        if path.resolve() != (root / roles[role]['path']).resolve():
            raise ValueError('Manifest selects an unchecked project: '+field)


def reviewed_inputs(contract):
    return {p['path']: {'project_sha256': p['project_sha256'],
                       'sources': {r['recipe_instance_id']: r['source_sha256'] for r in p['instances']}}
            for p in contract['projects']}


def load(path):
    with zipfile.ZipFile(path) as z:
        unique(z.namelist(), lambda x: x, 'ZIP member')
        if z.testzip(): raise ValueError('Corrupt 3MF')
        root = ET.fromstring(z.read('3D/3dmodel.model'))
        if root.get('unit', 'millimeter') != 'millimeter': raise ValueError('Unsupported 3MF units')
        cfg = ET.fromstring(z.read('Metadata/model_settings.config'))
        resources = unique(root.findall(N+'resources/'+N+'object'), lambda x: x.get('id'), 'resource ID')
        builds = unique(root.findall(N+'build/'+N+'item'), lambda x: x.get('objectid'), 'build object (multi-instance requires review)')
        configs = unique(cfg.findall('object'), lambda x: x.get('id'), 'object config')
        if set(builds) != set(configs): raise ValueError('Build/config object mismatch')
        plates, placement, models = {}, {}, {}
        for plate in cfg.findall('plate'):
            md = metadata(plate); pid = md['plater_id']
            if pid in plates: raise ValueError('Duplicate plate')
            plates[pid] = {k: v for k, v in md.items() if k not in {'plater_id', 'plater_name', 'thumbnail_file', 'thumbnail_no_light_file', 'top_file', 'pick_file'}}
            for instance in plate.findall('model_instance'):
                im = metadata(instance); oid = im['object_id']
                if oid in placement or im.get('instance_id') != '0': raise ValueError('Ambiguous plate instance')
                placement[oid] = pid
        if set(placement) != set(builds): raise ValueError('Plate/build membership mismatch')
        objects = {}
        for oid, co in configs.items():
            ob = resources[oid]; build = matrix(builds[oid].get('transform'))
            printable = builds[oid].get('printable', '1')
            if printable not in ('0', '1'): raise ValueError('Invalid build printability')
            components = unique(ob.findall(N+'components/'+N+'component'), lambda x: x.get('objectid'), 'component')
            parts = unique(co.findall('part'), lambda x: x.get('id'), 'part')
            if not components or set(components) != set(parts): raise ValueError('Component/part count or identity mismatch')
            loaded = []
            for cid, part in parts.items():
                component = components[cid]; member = component.get(P+'path', '').lstrip('/')
                if not member: raise ValueError('Unsupported local/nested component')
                if member not in models:
                    with z.open(member) as stream:
                        models[member] = load_meshes(stream)
                vertices, faces = models[member][cid]
                loaded.append({'id': cid, 'type': part.get('subtype'), 'settings': {k: v for k, v in metadata(part).items() if k not in {'name', 'source_file', 'source_object_id', 'source_volume_id'}}, 'vertices': vertices, 'faces': faces, 'transform': matrix(component.get('transform'))})
            md = metadata(co)
            objects[oid] = {'printable': printable == '1', 'plate': placement[oid], 'label': md.get('name'), 'settings': {k: v for k, v in md.items() if k != 'name'}, 'parts': loaded, 'build': build}
        return {'objects': objects, 'plates': plates, 'settings': json.loads(z.read('Metadata/project_settings.config'))}


def compare_mesh(a, b, tolerance=TOLERANCE_MM):
    """Compare oriented triangle multisets, allowing vertex/triangle reindexing.

A spatial lookup bounds candidates by coordinate tolerance, then selects the
unique Euclidean nearest coordinate. Equal/numerically tied nearest candidates
fail closed; topology is never used to guess a different correspondence. The
complete oriented triangle multiset must still match, including multiplicity.
"""
    av, af = a; bv, bf = b
    if len(af) != len(bf): raise ValueError('Triangle count changed')
    cells = collections.defaultdict(list); coords = []; ids = {}
    def cell(v): return tuple(math.floor(x / tolerance) for x in v)
    for v in av:
        if v not in ids:
            ids[v] = len(coords); coords.append(v); cells[cell(v)].append(ids[v])
    mapping = []
    for v in bv:
        if v in ids: mapping.append(ids[v]); continue
        c = cell(v); matches = []
        for delta in itertools.product((-1, 0, 1), repeat=3):
            for idx in cells.get(tuple(c[i]+delta[i] for i in range(3)), ()):
                if max(abs(v[i]-coords[idx][i]) for i in range(3)) <= tolerance: matches.append(idx)
        if not matches: raise ValueError('Mesh coordinates differ or tolerance match is ambiguous; review required')
        if len(matches) > 1:
            # Finely tessellated meshes can have distinct vertices closer than
            # the serialization tolerance. A unique nearest coordinate is a
            # candidate correspondence, not evidence of mesh equivalence: the
            # full triangle comparison below must prove that separately.
            distances = sorted((sum((v[i]-coords[idx][i])**2 for i in range(3)), idx) for idx in matches)
            if math.isclose(distances[0][0], distances[1][0], rel_tol=1e-12, abs_tol=0.):
                raise ValueError('Mesh tolerance match is ambiguous; review required')
            matches = [distances[0][1]]
        mapping.append(matches[0])
    def oriented(f): return min(f, f[1:]+f[:1], f[2:]+f[:2])
    expected = collections.Counter(oriented(tuple(ids[av[i]] for i in f)) for f in af)
    actual = collections.Counter(oriented(tuple(mapping[i] for i in f)) for f in bf)
    if expected != actual: raise ValueError('Triangle topology/winding changed')


def read_stl(path):
    raw = path.read_bytes()
    if len(raw) < 84: raise ValueError('Unsupported STL; binary STL required')
    count = struct.unpack_from('<I', raw, 80)[0]
    if len(raw) != 84 + 50*count: raise ValueError('Unsupported/corrupt STL; binary STL required')
    vertices, faces, index = [], [], {}
    for offset in range(84, len(raw), 50):
        points = struct.unpack_from('<9f', raw, offset+12); face = []
        for i in range(0, 9, 3):
            v = points[i:i+3]
            if not all(math.isfinite(x) for x in v): raise ValueError('Nonfinite STL')
            if v not in index: index[v] = len(vertices); vertices.append(v)
            face.append(index[v])
        faces.append(tuple(face))
    return vertices, faces


def compare(a, b, mapping_a, mapping_b, plates_a=None, plates_b=None):
    for data, mapping in ((a, mapping_a), (b, mapping_b)):
        if len(set(mapping.values())) != len(mapping) or set(mapping.values()) != set(data['objects']): raise ValueError('Instance map must be a bijection')
    if set(mapping_a) != set(mapping_b): raise ValueError('Stable instance identities changed')
    if a['settings'] != b['settings']: raise ValueError('Global settings changed; explicit review required')
    plates_a = {k: k for k in a['plates']} if plates_a is None else plates_a
    plates_b = {k: k for k in b['plates']} if plates_b is None else plates_b
    for data, mapping in ((a, plates_a), (b, plates_b)):
        if len(set(mapping.values())) != len(mapping) or set(mapping.values()) != set(data['plates']): raise ValueError('Plate map must be a bijection')
    if {k: a['plates'][v] for k, v in plates_a.items()} != {k: b['plates'][v] for k, v in plates_b.items()}: raise ValueError('Plate settings changed; explicit review required')
    inverse_a = {v: k for k, v in plates_a.items()}; inverse_b = {v: k for k, v in plates_b.items()}
    for rid in mapping_a:
        x = a['objects'][mapping_a[rid]]; y = b['objects'][mapping_b[rid]]
        if x['printable'] != y['printable']: raise ValueError(rid + ': printability changed')
        if x['settings'] != y['settings'] or inverse_a[x['plate']] != inverse_b[y['plate']]: raise ValueError(rid + ': settings/plate changed')
        if len(x['parts']) != len(y['parts']): raise ValueError(rid + ': component count changed')
        # Component ordering is bounded: reordered components require an explicit review.
        for p, q in zip(x['parts'], y['parts']):
            if p['type'] != q['type'] or p['settings'] != q['settings']: raise ValueError(rid + ': modifier subtype/part settings changed')
            pv = transform(transform(p['vertices'], p['transform']), x['build'])
            qv = transform(transform(q['vertices'], q['transform']), y['build'])
            compare_mesh((pv, p['faces']), (qv, q['faces']))


def check_manifest(manifest, catalog):
    rows = manifest['objects']; unique(rows, lambda x: x['recipe_instance_id'], 'recipe instance')
    required = unique(catalog['parts'], lambda x: x['part_id'], 'catalog part')
    if any(type(p['quantity']) is not int or p['quantity'] <= 0 for p in required.values()): raise ValueError('Required catalog quantities must be positive integers')
    if collections.Counter(x['part'] for x in rows) != {k: v['quantity'] for k, v in required.items()}: raise ValueError('Catalog/project quantities disagree')
    plates = unique(manifest['plates'], lambda x: x['id'], 'manifest plate')
    if {x['plate_id'] for x in rows} != set(plates): raise ValueError('Manifest plate membership differs')
    for pid, plate in plates.items():
        counts = collections.Counter(x['part'] for x in rows if x['plate_id'] == pid)
        if counts != plate['parts'] or sum(counts.values()) != plate['piece_count']: raise ValueError('Plate quantity mismatch: '+pid)


def check_alternative(alternative, catalog):
    parts = {p['part_id']: p for p in catalog['parts']}
    target = parts.get(alternative['replaces'])
    if not target or type(alternative['quantity']) is not int or not 0 < alternative['quantity'] <= target['quantity']: raise ValueError('Invalid replacement quantity')
    if alternative['part'] != alternative['replaces']:
        optional = next((p for p in catalog['optional_parts'] if p['part_id'] == alternative['part']), None)
        if not optional or optional['replaces'] != alternative['replaces'] or optional['alternative_quantity'] != alternative['quantity'] or optional['quantity'] != 0: raise ValueError('Optional catalog replacement mismatch')


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def object_contract(obj):
    """Snapshot semantic invariants independently of transient numeric IDs."""
    return {'printable': obj['printable'], 'settings_sha256': signature(obj['settings']), 'build': obj['build'],
            'parts': [{'type': p['type'], 'settings_sha256': signature(p['settings']),
                       'mesh_sha256': signature([p['vertices'], p['faces']]),
                       'transform': p['transform']} for p in obj['parts']]}


def validate_source_review(root, project, row):
    """Check a reviewed exception's identity/evidence, never grant a new approval.

    Review records and their evidence belong in tracked recipes/reviews. File
    checks intentionally work in an exported Git tree without requiring .git.
    """
    review_dir = root.resolve() / 'hardware/printing/recipes/reviews'
    def bound_file(binding):
        if not isinstance(binding, dict) or not isinstance(binding.get('path'), str):
            raise ValueError('Missing manual source review binding')
        path = root.resolve() / binding['path']
        # Require literal repository paths, not symlink or scratch/archive inputs.
        if Path(binding['path']).is_absolute():
            raise ValueError('Manual review path must be repository relative')
        if not path.resolve().is_relative_to(review_dir) or path.resolve() != path.absolute():
            raise ValueError('Manual source review/evidence must live in recipes/reviews')
        if not path.is_file(): raise ValueError('Missing manual source review/evidence file')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != binding.get('sha256'):
            raise ValueError('Manual source review/evidence hash mismatch')
        return raw
    binding = row.get('source_review')
    raw = bound_file(binding)
    if not binding['path'].endswith('.json'): raise ValueError('Manual source review must be JSON')
    review = json.loads(raw)
    if not isinstance(review, dict) or review.get('schema_version') != 1 or review.get('result') != 'equivalent':
        raise ValueError('Manual source review must explicitly establish equivalence')
    expected = {'project_sha256': project['project_sha256'],
                'source_sha256': row['source_sha256'], 'recipe_instance_id': row['recipe_instance_id']}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('Stale manual source review identity')
    def text(value): return isinstance(value, str) and bool(value.strip())
    if not text(review.get('reviewer')) or not text(review.get('method')):
        raise ValueError('Manual source review needs reviewer and method')
    limitations = review.get('limitations')
    if not isinstance(limitations, list) or not limitations or not all(text(x) for x in limitations):
        raise ValueError('Manual source review must declare limitations')
    frame = review.get('frame_evidence')
    if not isinstance(frame, dict) or not text(frame.get('description')):
        raise ValueError('Manual source review needs explicit frame evidence')
    artifacts = frame.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError('Manual source review needs bound frame evidence artifacts')
    for artifact in artifacts:
        bound_file(artifact)
        if artifact['path'] == binding['path']: raise ValueError('Review cannot cite itself as frame evidence')


def validate_current(root, lock, manifest, catalog, contract):
    """Return pending manual reviews; invariant violations always raise."""
    by_part = unique(catalog['parts'] + catalog['optional_parts'], lambda x: x['part_id'], 'catalog part')
    for optional in catalog['optional_parts']:
        check_alternative({'part': optional['part_id'], 'replaces': optional['replaces'], 'quantity': optional['alternative_quantity']}, catalog)
    if contract.get('schema_version', 1) != 1: raise ValueError('Unsupported semantic contract schema')
    by_project = unique(contract['projects'], lambda x: x['path'], 'contract project')
    if set(by_project) != {p['path'] for p in lock['projects']}: raise ValueError('Contract project set differs')
    project_selection(root, manifest, contract)
    enriched = []
    pending = []
    sources = {}
    for locked in lock['projects']:
        pc = by_project[locked['path']]
        if pc['project_sha256'] != locked['sha256']: raise ValueError('Stale project semantic receipt')
        data = load(root / locked['path'])
        rows = pc['instances']; unique(rows, lambda x: x['recipe_instance_id'], 'stable recipe instance')
        mapped = unique(rows, lambda x: x['object_id'], 'mapped object')
        if set(mapped) != set(data['objects']): raise ValueError('Instance mapping must cover project exactly')
        if signature(data['settings']) != pc['global_settings_sha256'] or signature(data['plates']) != pc['plate_settings_sha256']: raise ValueError('Global/plate settings drift')
        for row in rows:
            rid = row['recipe_instance_id']; obj = data['objects'][row['object_id']]
            if not obj['printable']: raise ValueError(rid + ': demanded instance is not printable')
            if object_contract(obj) != row['invariants']: raise ValueError(rid + ': settings, mesh, modifier or orientation drift')
            if obj['plate'] != str(row['plate_number']): raise ValueError(rid + ': project plate changed')
            part = by_part[row['part']]
            if row['source_sha256'] != part['geometry_sha256']: raise ValueError(rid + ': selected source changed; source review stale')
            if row['part'] not in sources:
                path = (root / part['geometry_path']).resolve()
                if not path.is_relative_to(root.resolve()) or '.work' in path.parts: raise ValueError('Unsafe current source path')
                if hashlib.sha256(path.read_bytes()).hexdigest() != row['source_sha256']: raise ValueError('Selected STL hash mismatch')
                sources[row['part']] = read_stl(path)
            normal = [p for p in obj['parts'] if p['type'] == 'normal_part']
            if len(normal) != 1: raise ValueError('Source check supports one normal component; explicit review required')
            frame = row.get('stl_to_mesh')
            if frame is None:
                if row.get('source_status') == 'reviewed_source_equivalence':
                    validate_source_review(root, pc, row)
                elif row.get('source_status') == 'pending_manual_review' and row.get('source_review_reason'):
                    if row.get('source_review'): raise ValueError('Unapplied source review; disposition must be explicit')
                    pending.append(rid + ': ' + row['source_review_reason'])
                else:
                    raise ValueError('Missing source frame disposition')
            else:
                if row.get('source_status') != 'verified_triangle_geometry': raise ValueError('Invalid source verification status')
                frame = matrix(' '.join(map(str, frame)))
                axes = [frame[i:i+3] for i in (0, 3, 6)]
                if any(abs(sum(axes[i][k]*axes[j][k] for k in range(3)) - (1 if i == j else 0)) > 1e-6 for i in range(3) for j in range(3)):
                    raise ValueError('Source frame must be rigid; scale/shear requires review')
                determinant = (axes[0][0]*(axes[1][1]*axes[2][2]-axes[1][2]*axes[2][1]) - axes[0][1]*(axes[1][0]*axes[2][2]-axes[1][2]*axes[2][0]) + axes[0][2]*(axes[1][0]*axes[2][1]-axes[1][1]*axes[2][0]))
                if abs(determinant - 1) > 1e-6: raise ValueError('Reflected source frame requires review')
                v, f = sources[row['part']]
                compare_mesh((transform(v, matrix(' '.join(map(str, frame)))), f), (normal[0]['vertices'], normal[0]['faces']))
        if pc['role'] == 'required':
            manifest_rows = unique(manifest['objects'], lambda x: x['object_id'], 'manifest object')
            if set(manifest_rows) != set(mapped): raise ValueError('Manifest/project object mismatch')
            for oid, row in mapped.items():
                mr = manifest_rows[oid]
                if (mr['part'], mr['plate_id'], mr['plate']) != (row['part'], row['plate_id'], row['plate_number']): raise ValueError('Manifest/project part or plate mismatch')
                if dict(mr['settings'], extruder=str(mr['filament_index'])) != data['objects'][oid]['settings']:
                    raise ValueError('Manifest settings/filament differ from editable project')
                enriched.append(dict(mr, recipe_instance_id=row['recipe_instance_id']))
        elif pc['role'] == 'replacement':
            check_alternative(pc['replacement'], catalog)
            if collections.Counter(r['part'] for r in rows) != {pc['replacement']['part']: pc['replacement']['quantity']}: raise ValueError('Replacement project quantity mismatch')
        else: raise ValueError('Unknown recipe role')
    unique([r for p in contract['projects'] for r in p['instances']], lambda x: x['recipe_instance_id'], 'global recipe instance')
    check_manifest(dict(manifest, objects=enriched), catalog)
    receipt = contract['review_evidence']
    if receipt.get('inputs') != reviewed_inputs(contract):
        pending.append('Slice/support review and estimates stale: reviewed project/source inputs changed')
    estimates = [{k: p[k] for k in ('id', 'estimated_seconds', 'estimated_grams')} for p in manifest['plates']]
    if signature(estimates) != receipt['estimates_sha256']: raise ValueError('Estimates changed without input-bound review')
    for record in receipt['files']:
        if hashlib.sha256((root / record['path']).read_bytes()).hexdigest() != record['sha256']: raise ValueError('Review evidence changed: ' + record['path'])
    return pending


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--baseline-map', required=True, type=Path, help='JSON: instances and plates maps from stable IDs to Bambu numeric strings')
    parser.add_argument('--candidate-map', required=True, type=Path)
    args = parser.parse_args()
    am = json.loads(args.baseline_map.read_text()); bm = json.loads(args.candidate_map.read_text())
    compare(load(args.baseline), load(args.candidate), am['instances'], bm['instances'], am['plates'], bm['plates'])
    print('PASS: mapped instance geometry, modifiers, orientation, object/global/plate settings unchanged; no slice or physical qualification claim')


if __name__ == '__main__':
    main()
