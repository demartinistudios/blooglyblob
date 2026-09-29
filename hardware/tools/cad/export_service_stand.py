"""Read-only tessellation of accepted, hidden R23 service-stand bodies."""
import adsk.core as ac
import adsk.fusion as af
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'hardware/rendering/r23-service-stand-meshes.json.gz'
PROVENANCE = ROOT / 'hardware/rendering/r23-service-stand-provenance.json'
FILE_ID = 'urn:adsk.wipprod:dm.lineage:nkM4P_10T7yYk-tasXlhbg'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(context):
    assert not OUTPUT.exists() and not PROVENANCE.exists()
    registry = json.loads((ROOT / 'hardware/cad/design-control/registry.json').read_text())
    assert registry['main']['design_revision'] == 'R23'
    assert registry['main']['cloud_file_id'] == FILE_ID
    assert registry['main']['cloud_version'] == 18
    release = ROOT / registry['main']['release_manifest']
    assert sha(release) == registry['main']['release_manifest_sha256']
    native = ROOT / registry['accepted_native']['path']
    assert sha(native) == registry['accepted_native']['sha256']
    doc = next(d for d in ac.Application.get().documents if d.dataFile and d.dataFile.id == FILE_ID)
    source = doc.dataFile
    assert source.versionNumber == source.latestVersionNumber == 18 and source.isComplete and not doc.isModified
    design = af.Design.cast(doc.products.itemByProductType('DesignProductType'))
    occurrences = list(design.rootComponent.allOccurrences)
    def state():
        return [(o.fullPathName, list(o.transform2.asArray()), o.isVisible, o.isLightBulbOn,
                 [(b.name, b.volume, b.isVisible, b.isLightBulbOn) for b in o.component.bRepBodies]) for o in occurrences]
    before = state()
    stand = [o for o in occurrences if o.component.name.startswith('FBJIG ')]
    assert len(stand) == 8 and all(not o.isVisible and not o.isLightBulbOn for o in stand)
    rows = []
    facts = []
    for occurrence in stand:
        assert '+' not in occurrence.fullPathName  # Top-level occurrence transforms are world transforms.
        assert occurrence.component.bRepBodies.count == 1
        body = occurrence.component.bRepBodies.item(0)
        calculator = body.meshManager.createMeshCalculator()
        calculator.surfaceTolerance = .002
        calculator.maxSideLength = .15
        mesh = calculator.calculate()
        assert mesh
        vertices = list(mesh.nodeCoordinatesAsFloat)
        faces = list(mesh.nodeIndices)
        assert len(vertices) % 3 == 0 and len(faces) % 3 == 0
        assert faces and min(faces) >= 0 and max(faces) < len(vertices) // 3
        transform = list(occurrence.transform2.asArray())
        world = []
        for i in range(0, len(vertices), 3):
            point = ac.Point3D.create(*vertices[i:i+3])
            point.transformBy(occurrence.transform2)
            world.append([v * 10 for v in point.asArray()])
        row = dict(path=occurrence.fullPathName, component=occurrence.component.name,
                   part_id=occurrence.component.name.split()[1], body=body.name,
                   volume_cm3=body.volume, transform=transform, vertices_cm=vertices, faces=faces)
        rows.append(row)
        facts.append(dict(path=row['path'], part_id=row['part_id'], transform=transform,
            visible=occurrence.isVisible, body_visible=body.isVisible,
            vertices=len(vertices)//3, triangles=len(faces)//3, native_volume_cm3=body.volume,
            world_bounds_mm=[[min(v[i] for v in world) for i in range(3)],
                             [max(v[i] for v in world) for i in range(3)]],
            row_sha256=hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()))
    assert before == state() and not doc.isModified
    assert source.versionNumber == source.latestVersionNumber == 18 and source.isComplete
    OUTPUT.write_bytes(gzip.compress(json.dumps(rows, separators=(',', ':')).encode(), mtime=0))
    provenance = dict(cad=registry['main'], native_source=dict(path=str(native.relative_to(ROOT)), sha256=sha(native)),
        mesh=dict(path=str(OUTPUT.relative_to(ROOT)), sha256=sha(OUTPUT), bytes=OUTPUT.stat().st_size),
        export_script=dict(path='hardware/tools/cad/export_service_stand.py',
                           sha256=sha(ROOT / 'hardware/tools/cad/export_service_stand.py')),
        purpose='Supplemental accepted CAD geometry for documentation rendering; no design or print change.',
        coordinates='vertices_cm are body-local; apply row-major 4x4 world occurrence transform once, then multiply cm by 10 for assembly mm.',
        face_format='faces contains flat triangle vertex indices, zero-based.',
        tessellation=dict(surface_tolerance_cm=.002, maximum_side_length_cm=.15),
        occurrence_count=len(stand), body_count=len(rows), parts=sorted(set(row['part_id'] for row in rows)),
        occurrences=facts, unchanged=dict(visibility=True, transforms=True, body_volumes=True, document_clean=True, cloud_version=18),
        guide_notified=False, document_saved=False, print_files_changed=False)
    PROVENANCE.write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(dict(mesh=provenance['mesh'], provenance=str(PROVENANCE.relative_to(ROOT)), occurrences=len(stand), parts=provenance['parts'], document_modified=doc.isModified)))
