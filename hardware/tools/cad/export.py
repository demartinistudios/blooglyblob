"""Read-only Fusion export with explicit identity and a new output directory.

Run inside Fusion's Python environment: export(request). A request contains
cloud_file_id, cloud_version, output, part_ids and include_hidden. No document
is opened, saved, closed or modified. Offline --validate-request checks the
request only; it cannot establish live CAD state or native reimport correctness.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import zipfile


def validate_request(request):
    if not isinstance(request.get('cloud_file_id'), str) or not request['cloud_file_id']:
        raise ValueError('An explicit permanent document ID is required')
    if type(request.get('cloud_version')) is not int or request['cloud_version'] < 1:
        raise ValueError('An exact positive cloud version is required')
    parts=request.get('part_ids')
    if not isinstance(parts,list) or not parts or any(not isinstance(p,str) or not re.fullmatch(r'[A-Z]+[0-9]+',p) for p in parts) or len(parts)!=len(set(parts)):
        raise ValueError('Provide unique explicit part IDs')
    if type(request.get('include_hidden')) is not bool:
        raise ValueError('Declare whether hidden occurrences are included')
    if not isinstance(request.get('output'),str) or not request['output']:
        raise ValueError('A new output directory is required')
    output=Path(request['output']).expanduser().resolve()
    if output.exists():raise ValueError('Export output must not exist')
    return output


def export(request):
    output=validate_request(request)
    import adsk.core
    import adsk.fusion
    app=adsk.core.Application.get()
    docs=[d for d in app.documents if d.dataFile and d.dataFile.id==request['cloud_file_id']]
    if len(docs)!=1:raise ValueError('Open exactly one document with the requested permanent ID')
    doc=docs[0]; file=doc.dataFile
    if doc.isModified or not file.isComplete or file.versionNumber!=request['cloud_version'] or file.latestVersionNumber!=request['cloud_version']:
        raise ValueError('Live CAD differs, is unsaved, incomplete or superseded; preserve and reconcile')
    design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
    if not design:raise ValueError('Requested document has no Fusion design')
    root=design.rootComponent
    def snapshot():
        return [{'path':o.fullPathName,'transform':list(o.transform2.asArray()),'visible':o.isVisible,
                 'bodies':[{'name':b.name,'visible':b.isVisible,'volume_cm3':b.volume} for b in o.component.bRepBodies]}
                for o in root.allOccurrences]
    before=snapshot();rows=[];found=set()
    for occurrence in root.allOccurrences:
        part=occurrence.component.name.split()[0]
        if part not in request['part_ids']:continue
        if not request['include_hidden'] and not occurrence.isVisible:continue
        found.add(part)
        for body in occurrence.component.bRepBodies:
            if not request['include_hidden'] and not body.isVisible:continue
            calc=body.meshManager.createMeshCalculator()
            calc.surfaceTolerance=.002;calc.maxSideLength=.15
            mesh=calc.calculate()
            if not mesh:raise ValueError('Tessellation failed: '+occurrence.fullPathName)
            rows.append({'part_id':part,'path':occurrence.fullPathName,'body':body.name,
                         'vertices_cm':list(mesh.nodeCoordinatesAsFloat),'faces':list(mesh.nodeIndices),
                         'transform':list(occurrence.transform2.asArray()),'volume_cm3':body.volume,
                         'visible':occurrence.isVisible,'body_visible':body.isVisible})
    if found!=set(request['part_ids']):raise ValueError('Missing selected parts: '+str(set(request['part_ids'])-found))
    if not rows:raise ValueError('No selected bodies')
    output.mkdir(parents=True)
    native=output/'assembly.f3d'
    manager=design.exportManager
    if not manager.execute(manager.createFusionArchiveExportOptions(str(native))):
        raise ValueError('Native export failed; preserve the partial run')
    with zipfile.ZipFile(native) as archive:
        if archive.testzip():raise ValueError('Native export ZIP integrity failed')
    (output/'assembly.json').write_text(json.dumps({'occurrences':before,'joint_count':len(root.allJoints)},indent=2)+'\n')
    (output/'meshes.json.gz').write_bytes(gzip.compress(json.dumps(rows,separators=(',',':')).encode(),mtime=0))
    if snapshot()!=before or doc.isModified or file.versionNumber!=request['cloud_version'] or file.latestVersionNumber!=request['cloud_version']:
        raise ValueError('Live CAD changed during export; preserve output and reconcile')
    files=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in output.iterdir() if p.is_file()]
    receipt={'request':request,'files':files,'units':'body-local cm; row-major occurrence transform once, then cm to mm',
             'tessellation':{'surface_tolerance_cm':.002,'maximum_side_length_cm':.15},
             'status':'read-only export; native reimport, STL bed frames and acceptance require separate verification'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-request',type=Path,required=True)
    args=parser.parse_args()
    print('Request valid; no Fusion connection:',validate_request(json.loads(args.validate_request.read_text())))
