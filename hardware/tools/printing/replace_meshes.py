"""Write a separate, unsliced 3MF candidate from independently reviewed STL frames.

Usage: python3 hardware/tools/printing/replace_meshes.py --project BASE.3mf
       --review REVIEW.json --review-sha256 SHA256 --output NEW_DIRECTORY

Review schema 1: reviewer, method, project_sha256, a full instance_map mapping
stable recipe IDs to object ID strings, and replacements containing
recipe_instance_id, source {path, sha256}, and a proper rigid stl_to_mesh [12].
Source paths are absolute or relative to the review file. The supplied review
hash binds the independent review, including frames; this tool cannot establish
that a reviewer chose the correct orientation. No alignment, repair, slicing,
promotion, source modification or lock updates are performed.

Only the current external-component layout, one unshared normal mesh per selected
object, unannotated mesh XML and zero repair counters are supported. Other cases
require a separately reviewed method. Unchanged ZIP member content and XML outside
the selected meshes/counts are retained byte-for-byte. Affected plate previews
and slice_info are removed; complete affected plates require new slice review.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile

try:
    from . import semantics as s
except ImportError:
    import semantics as s


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Missing/duplicate review key: ' + key)
        result[key] = value
    return result


def rigid_frame(value):
    if not isinstance(value, list) or len(value) != 12 or any(type(x) not in (int, float) for x in value):
        raise ValueError('Source frame must contain 12 finite numbers')
    frame = s.matrix(' '.join(map(str, value)))
    a = [frame[i:i+3] for i in (0, 3, 6)]
    if any(abs(sum(a[i][k]*a[j][k] for k in range(3)) - (i == j)) > 1e-6 for i in range(3) for j in range(3)):
        raise ValueError('Source frame must be rigid; scale/shear is unsupported')
    determinant = (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1]) - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0]) + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
    if abs(determinant - 1) > 1e-6:
        raise ValueError('Reflected source frame is unsupported')
    return frame


def patch_xml(data, select):
    """Patch selected complete elements by parser byte offsets, retaining all else."""
    if b'\x00' in data:
        raise ValueError('Unsupported XML encoding')
    parser = expat.ParserCreate(namespace_separator='}')
    stack, patches = [], []
    active = None

    def start(name, attributes):
        nonlocal active
        stack.append((('{' + name if '}' in name else name), attributes))
        replacement = select(stack)
        if replacement is not None:
            if active is not None:
                raise ValueError('Unsupported overlapping XML replacements')
            begin = parser.CurrentByteIndex
            tag_end = data.index(b'>', begin) + 1
            active = (len(stack), begin, tag_end if data[begin:tag_end].rstrip().endswith(b'/>') else None, replacement)

    def end(name):
        nonlocal active
        if active is not None and active[0] == len(stack):
            _, begin, finish, replacement = active
            finish = finish or data.index(b'>', parser.CurrentByteIndex) + 1
            patches.append((begin, finish, replacement(data[begin:finish]) if callable(replacement) else replacement))
            active = None
        stack.pop()

    def reject_dtd(*args):
        raise ValueError('Unsupported XML DTD declaration')

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = reject_dtd
    parser.Parse(data, True)
    for begin, finish, replacement in reversed(patches):
        data = data[:begin] + replacement + data[finish:]
    return data, len(patches)


def plain_mesh(raw, cid):
    # Preserve comments elsewhere, but reject any unmodeled target information.
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    model = ET.fromstring(raw, parser=parser)
    objects = s.unique(model.findall(s.N+'resources/'+s.N+'object'), lambda x: x.get('id'), 'mesh object')
    target = objects[cid]
    if set(target.attrib) - {'id', 'type', s.P+'UUID'} or target.get('type', 'model') != 'model':
        raise ValueError('Unsupported target object attributes/annotations')
    if [x.tag for x in target] != [s.N+'mesh']:
        raise ValueError('Unsupported target object structure/annotations')
    mesh = target[0]
    if [x.tag for x in mesh] != [s.N+'vertices', s.N+'triangles']:
        raise ValueError('Unsupported mesh structure/annotations')
    allowed = {s.N+'mesh': set(), s.N+'vertices': set(), s.N+'triangles': set(),
               s.N+'vertex': set('xyz'), s.N+'triangle': {'v1', 'v2', 'v3'}}
    for element in mesh.iter():
        if element.tag not in allowed or set(element.attrib) != allowed[element.tag] or (element.text or '').strip() or (element.tail or '').strip():
            raise ValueError('Unsupported mesh attributes/annotations')
    for container, child in ((mesh[0], s.N+'vertex'), (mesh[1], s.N+'triangle')):
        if any(x.tag != child or len(x) for x in container):
            raise ValueError('Unsupported mesh child structure/annotations')


def mesh_xml(vertices, faces):
    return (f'<mesh xmlns="{s.N[1:-1]}"><vertices>' +
            ''.join('<vertex x="%.17g" y="%.17g" z="%.17g"/>' % tuple(v) for v in vertices) +
            '</vertices><triangles>' +
            ''.join('<triangle v1="%s" v2="%s" v3="%s"/>' % tuple(f) for f in faces) +
            '</triangles></mesh>').encode()


def replace_meshes(project, review_path, review_sha256, output):
    project, review_path, output = map(Path, (project, review_path, output))
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; choose a new candidate directory')
    review_raw = review_path.read_bytes()
    if hashlib.sha256(review_raw).hexdigest() != review_sha256:
        raise ValueError('Review hash mismatch; reviewed frames may have changed')
    review = json.loads(review_raw, object_pairs_hook=unique_json)
    if not isinstance(review, dict) or type(review.get('schema_version')) is not int or review.get('schema_version') != 1 or any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('reviewer', 'method')):
        raise ValueError('Review requires schema_version 1, reviewer and method')
    if sha(project) != review.get('project_sha256'):
        raise ValueError('Project hash mismatch; review is stale')
    with zipfile.ZipFile(project) as archive:
        s.unique(archive.namelist(), lambda x: x, 'ZIP member')
        if any('.gcode' in name.lower() for name in archive.namelist()):
            raise ValueError('Pre-sliced .gcode project is unsupported')
        infos = archive.infolist()
        members = {info.filename: archive.read(info) for info in infos}
        comment = archive.comment
    baseline = s.load(project)
    mapping = review.get('instance_map')
    if not isinstance(mapping, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in mapping.items()) or len(set(mapping.values())) != len(mapping) or set(mapping.values()) != set(baseline['objects']):
        raise ValueError('Instance map must be a full stable-ID/object-ID bijection')
    rows = review.get('replacements')
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Review requires explicit replacements')
    s.unique(rows, lambda row: row.get('recipe_instance_id'), 'replacement instance')
    root = ET.fromstring(members['3D/3dmodel.model'])
    cfg = ET.fromstring(members['Metadata/model_settings.config'])
    refs = Counter((c.get(s.P+'path', '').lstrip('/'), c.get('objectid')) for c in root.iter(s.N+'component'))
    selected, changes, bindings = {}, {}, [(project, review['project_sha256']), (review_path, review_sha256)]
    for row in rows:
        rid = row['recipe_instance_id']
        if rid not in mapping:
            raise ValueError('Replacement instance absent from reviewed map: ' + str(rid))
        oid = mapping[rid]
        obj = baseline['objects'][oid]
        normals = [p for p in obj['parts'] if p['type'] == 'normal_part']
        if len(normals) != 1:
            raise ValueError('Replacement requires exactly one normal component: ' + rid)
        normal = normals[0]; cid = normal['id']
        component = root.find(f'{s.N}resources/{s.N}object[@id="{oid}"]/{s.N}components/{s.N}component[@objectid="{cid}"]')
        member = component.get(s.P+'path', '').lstrip('/')
        if refs[(member, cid)] != 1:
            raise ValueError('Shared target mesh reference is unsupported: ' + rid)
        if not re.fullmatch(r'3D/Objects/[^/]+\.model', member):
            raise ValueError('Unsupported component member path')
        # Parse before byte patching; DTDs and alternate encodings are rejected.
        patch_xml(members[member], lambda stack: None)
        plain_mesh(members[member], cid)
        source = row.get('source', {})
        source_path = review_path.parent / source['path']
        if sha(source_path) != source.get('sha256'):
            raise ValueError('Source hash mismatch: ' + rid)
        frame = rigid_frame(row.get('stl_to_mesh'))
        vertices, faces = s.read_stl(source_path)
        if not vertices or not faces:
            raise ValueError('Empty STL is unsupported: ' + rid)
        vertices = s.transform(vertices, frame)
        if not all(math.isfinite(x) for v in vertices for x in v):
            raise ValueError('Nonfinite transformed STL coordinates')
        bindings.append((source_path, source['sha256']))
        co = cfg.find(f'object[@id="{oid}"]')
        part = co.find(f'part[@id="{cid}"]')
        stats = part.findall('mesh_stat')
        counts = [x for x in co.findall('metadata') if 'face_count' in x.attrib]
        if len(stats) != 1 or len(counts) != 1 or set(counts[0].attrib) != {'face_count'}:
            raise ValueError('Unsupported/missing target face_count records: ' + rid)
        if any(len(x) or (x.text or '').strip() for x in (stats[0], counts[0])):
            raise ValueError('Unsupported target count record annotations: ' + rid)
        if set(part.attrib) != {'id', 'subtype'} or any(x.tag not in {'metadata', 'mesh_stat'} for x in part):
            raise ValueError('Unsupported target part structure/annotations: ' + rid)
        repair = {'edges_fixed', 'degenerate_facets', 'facets_removed', 'facets_reversed', 'backwards_edges'}
        if set(stats[0].attrib) - (repair | {'face_count'}) or any(stats[0].get(k, '0') != '0' for k in repair):
            raise ValueError('Unsupported nonzero/unknown target mesh repair counters: ' + rid)
        if any(x.get('face_count') != str(len(normal['faces'])) for x in (stats[0], counts[0])):
            raise ValueError('Stale target face_count records: ' + rid)
        changes.setdefault(member, {})[cid] = mesh_xml(vertices, faces)
        selected[oid] = {'cid': cid, 'vertices': vertices, 'faces': faces, 'plate': obj['plate']}
    for member, meshes in changes.items():
        def select_mesh(stack):
            if len(stack) == 4 and [x[0] for x in stack] == [s.N+'model', s.N+'resources', s.N+'object', s.N+'mesh']:
                return meshes.get(stack[-2][1].get('id'))
        members[member], count = patch_xml(members[member], select_mesh)
        if count != len(meshes):
            raise ValueError('Unsupported/missing target mesh spans')
    def select_count(stack):
        if len(stack) not in (3, 4) or stack[0][0] != 'config' or stack[1][0] != 'object':
            return None
        target = selected.get(stack[1][1].get('id'))
        if target is None:
            return None
        name, attrs = stack[-1]
        if (len(stack) == 3 and name == 'metadata' and 'face_count' in attrs) or (len(stack) == 4 and stack[2][0] == 'part' and stack[2][1].get('id') == target['cid'] and name == 'mesh_stat'):
            new_count = str(len(target['faces'])).encode()
            return lambda raw: re.sub(rb'''(\bface_count\s*=\s*)(["'])(.*?)\2''', lambda match: match[1] + match[2] + new_count + match[2], raw, count=1)
    members['Metadata/model_settings.config'], count = patch_xml(members['Metadata/model_settings.config'], select_count)
    if count != 2 * len(selected):
        raise ValueError('Unsupported/missing target count spans')
    plates = sorted({x['plate'] for x in selected.values()})
    removed = sorted(set(members) & ({'Metadata/slice_info.config'} | {f'Metadata/{prefix}_{plate}{suffix}.png' for plate in plates for prefix in ('plate', 'plate_no_light', 'top', 'pick') for suffix in ('', '_small')}))
    with tempfile.TemporaryDirectory(prefix='mesh-candidate-') as temporary:
        candidate = Path(temporary) / 'candidate.3mf'
        with zipfile.ZipFile(candidate, 'w') as archive:
            archive.comment = comment
            for info in infos:
                if info.filename not in removed:
                    archive.writestr(info, members[info.filename])
        result = s.load(candidate)
        if result['settings'] != baseline['settings'] or result['plates'] != baseline['plates']:
            raise ValueError('Candidate global/plate settings changed')
        for oid, original in baseline['objects'].items():
            actual = result['objects'][oid]
            target = selected.get(oid)
            if target is None:
                if actual != original:
                    raise ValueError('Unaffected instance changed: ' + oid)
                continue
            # Replace only expected numeric geometry for the preservation comparison.
            expected = dict(original, parts=[dict(p, vertices=target['vertices'], faces=target['faces']) if p['id'] == target['cid'] else p for p in original['parts']])
            normal = next(p for p in actual['parts'] if p['id'] == target['cid'])
            s.compare_mesh((target['vertices'], target['faces']), (normal['vertices'], normal['faces']))
            if actual != expected:
                raise ValueError('Selected instance settings/modifier/transform or geometry changed: ' + oid)
        # Recheck reviewed inputs before creating any user-visible output.
        for path, expected_hash in bindings:
            if sha(path) != expected_hash:
                raise ValueError('Input hash changed during replacement: ' + str(path))
        receipt = {'schema_version': 1, 'result': 'verified_candidate', 'project_sha256': review['project_sha256'],
                   'review_sha256': review_sha256, 'candidate_sha256': sha(candidate),
                   'instance_map': mapping, 'replacements': rows, 'affected_plates': plates,
                   'removed_members': removed,
                   'limitations': ['Candidate only; independently reviewed frames are input declarations.',
                                   'Affected complete plates require slicing and review before promotion; no physical qualification.']}
        payloads = {'candidate.3mf': candidate.read_bytes(),
                    'receipt.json': (json.dumps(receipt, indent=2) + '\n').encode()}
        output.mkdir(parents=True, exist_ok=False)
        created = []
        try:
            for name, data in payloads.items():
                path = output / name
                with path.open('xb') as stream:
                    created.append(path)
                    stream.write(data)
        except BaseException as error:
            # Remove only files created by this call; preserve unexpected entries.
            for path in reversed(created):
                try:
                    path.unlink()
                except OSError as cleanup_error:
                    error.add_note(f'Could not remove partial output {path}: {cleanup_error}')
            try:
                output.rmdir()
            except OSError as cleanup_error:
                error.add_note(f'Could not remove output directory {output}: {cleanup_error}')
            raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--review-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        replace_meshes(args.project, args.review, args.review_sha256, args.output)
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError, expat.ExpatError, zipfile.BadZipFile) as error:
        parser.exit(1, 'Replacement refused: ' + str(error) + '\n')
    print('PASS: candidate.3mf and receipt.json written; affected plates still require slicing and review')


if __name__ == '__main__':
    main()
