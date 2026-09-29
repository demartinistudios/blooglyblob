#!/usr/bin/env python3
"""Build the guide from hardware/build-guide/src/ into hardware/build-guide/dist/.

dist is uncommitted build output, replaced only after a staged build validates.
src holds only what the guide authors. The guide keeps no copies of CAD, print or
assembly files; it reads them from their own homes at build time:
  hardware/cad/current/stl/                          STL downloads and the STL ZIP
  hardware/printing/current/manifest.json selects 3MFs, thumbnails and settings  public 3MFs, CSV and print-set ZIP
  hardware/assembly/electrical.json                  power and signal tables (data.js)
"""
import json, posixpath, re, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import packages  # noqa: E402
import consistency  # noqa: E402

SRC = ROOT / 'hardware/build-guide/src'
DIST = ROOT / 'hardware/build-guide/dist'
# External inputs, read but never modified.
ELECTRICAL = ROOT / 'hardware/assembly/electrical.json'
INPUTS = [*packages.INPUTS, ELECTRICAL]

DATA = {'guide-data.json': 'guide', 'parts.json': 'parts', 'print-data.json': 'prints'}
CORE = ['.nojekyll', 'index.html', 'app.js', 'style.css', 'references.html', 'repeat-build.html']
PRIVATE = {'exact', 'status', 'source', 'sources'}
REF = re.compile(r'(?<![\w/.-])((?:\.\./)*(?:assets|downloads|references)/[A-Za-z0-9_./%-]+?)(?=[\'"`)\s#?,;<]|$)')
TEXT = ('.html', '.js', '.css', '.json', '.svg', '.md', '.txt')
IGNORED = {'.DS_Store'}


def authored():
    return sorted(str(p.relative_to(SRC)) for p in SRC.rglob('*') if p.is_file() and p.name not in IGNORED)


def references(text, base):
    for m in REF.finditer(text):
        ref = m.group(1).rstrip('.')
        yield posixpath.normpath(posixpath.join(base, ref)) if ref.startswith('../') else ref


def check_links(files, plate_numbers, output=None):
    """Every referenced path must exist in dist; every authored file must be referenced."""
    output = output or DIST
    reached, missing, queue = set(), set(), CORE + list(DATA) + [f'assets/plates/plate-{n}.png' for n in plate_numbers]
    while queue:
        rel = queue.pop()
        if rel in reached or rel in missing:
            continue
        path = (SRC if rel in DATA else output) / rel
        if not path.is_file():
            missing.add(rel)
            continue
        reached.add(rel)
        if rel.endswith(TEXT):
            queue += references(path.read_text(errors='replace'), posixpath.dirname(rel))
    unreferenced = set(files) - reached
    if missing or unreferenced:
        raise SystemExit('Guide build failed.\n'
                         + ''.join(f'  referenced but missing: {p}\n' for p in sorted(missing))
                         + ''.join(f'  in src but not referenced: {p}\n' for p in sorted(unreferenced)))


def check_print_data(prints, manifest):
    """Keep authored plate cards consistent with the selected print downloads."""
    plates = sorted(manifest['plates'], key=lambda p: p['plate_number'])
    expected = [(p['id'], p['plate_number']) for p in plates]
    actual = [(p['id'], p['settings'].get('Plate number')) for p in prints]
    # app.js uses display order for plate-N.png, so order matters as well as IDs.
    if actual != expected:
        raise ValueError(f'Print metadata plate IDs/numbers/order differ: expected {expected}, got {actual}')
    for authored, selected in zip(prints, plates):
        fields = {
            'quantities': (authored['quantities'], selected['parts']),
            'part IDs': (sorted(authored['parts']), sorted(selected['parts'])),
            'estimate.time': (authored['estimate']['time'], packages.duration(selected['estimated_seconds'])),
            'estimate.grams': (authored['estimate']['grams'], selected['estimated_grams']),
        }
        for field, (actual, expected) in fields.items():
            if actual != expected:
                raise ValueError(f"Print metadata {authored['id']} {field} differs: expected {expected!r}, got {actual!r}")


def publish_staged(output, destination, backup):
    """Swap a validated same-filesystem tree; roll back a failed final rename."""
    had_previous = destination.exists()
    if had_previous:
        destination.rename(backup)
    try:
        output.rename(destination)
    except OSError:
        if had_previous:
            backup.rename(destination)
        raise


def recover_preview(destination, backup):
    if backup.exists():
        if destination.exists():
            shutil.rmtree(backup)
        else:
            backup.rename(destination)


def plate_settings_html(source):
    """Reuse the authored settings inside the guide, without a second document shell."""
    match = re.search(r'<main id="content">(.*?)<footer>', source, re.S)
    if not match:
        raise ValueError('Plate settings page is missing its main content or footer')
    content = match.group(1).replace('<h1>Plate settings</h1>', '').replace('href="./#', 'href="#')
    # Put the useful plate catalog first; retain the detailed printer notes on demand.
    notes = content.find('<h2>Material numbers are not AMS slots</h2>')
    plates = content.find('<h2>The ten plates</h2>')
    if 0 <= notes < plates:
        machine = re.search(r'<p class="eyebrow">.*?</p>', content, re.S)
        setup = (machine.group(0) if machine else '') + content[notes:plates]
        content = content[plates:] + '<details><summary>Printer and material notes</summary>' + setup + '</details>'
    content = re.sub(r'(<a href="#parts/([A-Z0-9]+)">[^<]+</a>)',
                     r'\1 <a href="downloads/stl/\2.stl" download aria-label="Download \2 STL">STL</a>', content)
    return re.sub(r'<a href="(assets/plates/[^"]+)">(<img[^>]+>)</a>',
                  r'<button data-zoom="\1" aria-label="Enlarge plate layout">\2</button>', content)


def build():
    backup = DIST.with_name('.guide-previous')
    recover_preview(DIST, backup)
    missing = [str(p.relative_to(ROOT)) for p in INPUTS if not p.exists()]
    if missing:
        raise SystemExit('Missing guide inputs: ' + ', '.join(missing))
    selected = packages.sources()  # fail before removing dist if a project or thumbnail is missing
    files = authored()
    data = {DATA[f]: json.loads((SRC / f).read_text()) for f in DATA}
    check_print_data(data['prints'], selected['manifest'])
    electrical = json.loads(ELECTRICAL.read_text())

    report = consistency.check(ROOT)
    if report['errors']:
        raise ValueError('Guide consistency failed: ' + '; '.join(report['errors']))
    if report['blockers']:
        print('Guide checks passed. Manual publication review is separate; see hardware/build-guide/review-status.json.')

    DIST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.guide-stage-', dir=DIST.parent) as folder:
        staging = Path(folder)
        output = staging / 'site'
        output.mkdir()
        for rel in files:
            if rel not in DATA:
                (output / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SRC / rel, output / rel)
        packages.write(output / 'downloads', selected)

        # The page gets only rendered fields; contract/provenance metadata stays in src.
        for step in data['guide']['steps']:
            step.pop('source', None)
            step.pop('hardware_allocations', None)
        parts = [{k: v for k, v in p.items() if k not in PRIVATE} for p in data['parts']]
        bundle = {'guide': data['guide'], 'parts': parts, 'prints': data['prints'],
                  'electrical': {k: electrical[k] for k in ('power', 'signal')},
                  'plateSettingsHTML': plate_settings_html((SRC / 'repeat-build.html').read_text())}
        (output / 'data.js').write_text('window.BGB = ' + json.dumps(bundle, ensure_ascii=False, separators=(',', ':')) + ';\n')
        check_links(files, [p['plate_number'] for p in selected['manifest']['plates']], output)
        count = sum(1 for p in output.rglob('*') if p.is_file())
        publish_staged(output, DIST, backup)
        if backup.exists():
            shutil.rmtree(backup)
    print(f'Built {count} files into {DIST.relative_to(ROOT)}')


if __name__ == '__main__':
    build()
