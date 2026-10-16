"""Make the guide's print downloads at build time from the CAD and printing homes.

The guide keeps no copies of these. It copies catalog-selected STLs, writes public
copies of the two Bambu Studio projects with neutral internal names and license
metadata, and zips the STLs and the print set. Output is byte-stable: the ZIPs use
a fixed timestamp.
"""
import csv, io, json, re, sys, tempfile, zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'hardware/tools/printing'))
from privacy import sanitize_project

STL = ROOT / 'hardware/cad/current/stl'
PRINTING = ROOT / 'hardware/printing/current'
MANIFEST = PRINTING / 'manifest.json'
OBJECT_SETTINGS = PRINTING / 'object-settings.csv'
CATALOG = ROOT / 'hardware/catalog/parts.json'
LICENSE = ROOT / 'LICENSE'
SAFETY = ROOT / 'hardware/SAFETY.md'
LICENSING = ROOT / 'LICENSING.md'
INPUTS = [STL, MANIFEST, OBJECT_SETTINGS, CATALOG, LICENSE, SAFETY, LICENSING]
REPO_FILES = 'https://github.com/demartinistudios/blooglyblob/blob/main/'
NOTICE_FILES = {LICENSE: 'LICENSE.txt', SAFETY: 'SAFETY.md', LICENSING: 'LICENSING.md'}
ZIP_TIME = (2026, 9, 25, 0, 0, 0)

# Display names inside the public 3MF copies; geometry, settings and entry order are kept.
NAMES = {
    'BlooglyBlob-R23-Review.3mf': 'BlooglyBlob-PLA.3mf',
    'R24 rear nut cup and bore': 'Rear nut cup and bore',
    'R23 front nut channel': 'Front nut channel',
    'R23 front screw bore': 'Front screw bore',
    'BlooglyBlob R22 per-object production settings': 'BlooglyBlob per-object settings',
    'BlooglyBlob-R22-PLA-All-Plates-v4.3mf': 'BlooglyBlob-PLA.3mf',
    'P03 - Twin shoulder side-entry carrier r1.stl': 'P03 - Shoulder servo bracket.stl',
    'P04 - Head side-entry carrier r1.stl': 'P04 - Head servo bracket.stl',
    'Fork opening - bridge test': 'Fork opening',
    'Optional clear PETG ball - unqualified': 'Optional clear PETG ball',
    'Clear PETG - optional unqualified': 'Clear PETG',
}
TEXT = ('.config', '.json', '.model', '.xml', '.rels')

# Fills these fields in the public 3MF model only where the source leaves them empty.
# Copyright and Designer are standard 3MF names; License is Bambu Studio's own field.
PROJECT_METADATA = {
    'Copyright': 'Copyright (c) 2026 DeMartini Studios LLC. MIT License.',
    'Designer': 'DeMartini Studios LLC',
    'License': 'MIT',
}


def portable_markdown(path):
    """Keep bundled notice links local; point other repository links to public sources."""
    def link(match):
        label, target = match.groups()
        if target.startswith(('https://', 'http://', '#')):
            return match.group(0)
        filename, separator, anchor = target.partition('#')
        source = (path.parent / filename).resolve()
        destination = NOTICE_FILES.get(source)
        if destination is None:
            destination = REPO_FILES + source.relative_to(ROOT).as_posix()
        return f'[{label}]({destination}{separator}{anchor})'
    return re.sub(r'\[([^]]+)\]\(([^)]+)\)', link, path.read_text())


def notice_entries():
    return [(name, path.read_bytes() if path == LICENSE else portable_markdown(path))
            for path, name in NOTICE_FILES.items()]


def sources(printing=PRINTING):
    """Resolve only the projects selected by the current printing manifest."""
    manifest = json.loads((printing / 'manifest.json').read_text())
    selected = {'manifest': manifest}
    for name, field in (('pla', 'master_project'), ('petg', 'optional_petg_project')):
        filename = manifest[field]
        if Path(filename).name != filename or not filename.endswith('.3mf'):
            raise ValueError(f'{field} must name a 3MF in {printing}')
        path = printing / filename
        if not path.is_file():
            raise FileNotFoundError(f'Missing selected print project: {path}')
        selected[name] = path
    selected['csv'] = printing / 'object-settings.csv'
    if not selected['csv'].is_file():
        raise FileNotFoundError(f'Missing object settings: {selected["csv"]}')
    plates = manifest['plates']
    numbers = [p['plate_number'] for p in plates]
    if sorted(numbers) != list(range(1, len(plates) + 1)):
        raise ValueError('Print plate numbers must be unique and contiguous from 1')
    with zipfile.ZipFile(selected['pla']) as project:
        members = set(project.namelist())
        for number in numbers:
            image = f'Metadata/plate_{number}.png'
            if image not in members:
                raise ValueError(f'Missing plate thumbnail: {image} in {selected["pla"]}')
    return selected


def duration(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    return f'{hours} h {minutes:02d} min' if hours else f'{minutes} min'


def print_set_readme(manifest):
    plates = sorted(manifest['plates'], key=lambda p: p['plate_number'])
    pieces = sum(sum(p['parts'].values()) for p in plates)
    part_types = len({part for p in plates for part in p['parts']})
    rows = []
    for plate in plates:
        color = 'Copper silk' if plate['color'] == 'Copper' else plate['color']
        parts = ', '.join(part + (f' ×{count}' if count > 1 else '')
                          for part, count in plate['parts'].items())
        rows.append(f"| {plate['plate_number']} | {color} ({plate['id']}) | "
                    f"{sum(plate['parts'].values())} | {duration(plate['estimated_seconds'])}, "
                    f"{plate['estimated_grams']:.2f} g | {parts} |")
    return PRINT_SET_README.format(
        plates=len(plates), pieces=pieces, part_types=part_types,
        duration=duration(sum(p['estimated_seconds'] for p in plates)),
        grams=sum(p['estimated_grams'] for p in plates), plate_rows='\n'.join(rows))


def project_metadata(data):
    """Fill empty PROJECT_METADATA fields by byte replacement, leaving other bytes intact."""
    for name, value in PROJECT_METADATA.items():
        filled = f'<metadata name="{name}">{escape(value)}</metadata>'.encode()
        for empty in (f'<metadata name="{name}"></metadata>', f'<metadata name="{name}" />',
                      f'<metadata name="{name}"/>'):
            data = data.replace(empty.encode(), filled, 1)
    return data


def public_3mf(src, dest):
    def display_names(name, data):
        if name.endswith(TEXT):
            text = data.decode('utf-8')
            for old, new in NAMES.items():
                text = text.replace(old, new)
            data = text.encode('utf-8')
        if name == '3D/3dmodel.model':
            data = project_metadata(data)
        return data

    sanitize_project(src, dest, transform=display_names)


def check_metadata(path):
    """Fail the build when a public 3MF model lacks a PROJECT_METADATA value."""
    with zipfile.ZipFile(path) as project:
        root = ET.fromstring(project.read('3D/3dmodel.model'))
    values = {e.get('name'): (e.text or '').strip() for e in root
              if e.tag.rsplit('}', 1)[-1] == 'metadata'}
    missing = [name for name in PROJECT_METADATA if not values.get(name)]
    if missing:
        raise ValueError(f'{path.name} lacks license metadata: {", ".join(missing)}')


def zip_write(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, data in entries:
            info = zipfile.ZipInfo(arc, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)


STL_README = """BlooglyBlob printable parts (STL)

Before buying parts, printing, building or powering a robot, read SAFETY.md.
It includes project status, support limits and physical/AI precautions. One
prototype has been built and operated; this is not comprehensive safety testing
or certification. No support, individual responses, maintenance or updates are
promised. See LICENSING.md for license scope; these notices add no license terms.

One STL per part type, in millimetres, named by part ID. The build guide's
Parts page lists what each part is, how many to print and which colour.

Most people should print from the Bambu Studio project instead
(BlooglyBlob-PLA.3mf): it has every part placed on {plates} plates with its
orientation, supports, brims and per-part settings. Use these STLs if you
use another slicer or want to reprint a single part.

- {part_types} part types make up the robot ({pieces} pieces in total).
- AR07, the pointing hand, is optional and not on any plate.
- Print hands fingers up with the wrist peg down, and keep the support
  blockers from the 3MF in mind: some holes and threads must stay clean.
- Check each part as it comes off the plate, and dry-fit before gluing.

Copyright (c) 2026 DeMartini Studios LLC. Released under the MIT License;
the full text is in LICENSE.txt.

BlooglyBlob: https://github.com/demartinistudios/blooglyblob
"""

PRINT_SET_README = """# BlooglyBlob print set

Print projects and settings for the robot's parts in Bambu Studio.

Before buying parts, printing, building or powering a robot, read
[Safety and responsibility](SAFETY.md), including project status and support
limits. One prototype has been built and operated; this is not comprehensive
safety testing or certification. No support, individual responses, maintenance
or updates are promised. See [license scope](LICENSING.md); these notices add
no license terms.

| File | What it is |
| --- | --- |
| `BlooglyBlob-PLA.3mf` | The main project: {plates} plates, {pieces} pieces, {part_types} part types, all PLA. |
| `BlooglyBlob-PETG-ball.3mf` | Optional: the clear antenna ball (A05) in PETG, instead of plate 10. |
| `BlooglyBlob-object-settings.csv` | Each part's layer height, walls, infill, brim, supports and speeds. |
| `LICENSE.txt` | The MIT License for these files. |
| `SAFETY.md` | Project status, support limits and safety precautions. |
| `LICENSING.md` | License scope and third-party exceptions. |

The projects were prepared for a **Bambu Lab X1 Carbon with a 0.4 mm nozzle and a
Textured PEI plate**. Estimated total: {duration} and {grams:.2f} g of filament,
including supports and brims (slicer estimates).

## Before you print

1. Open `BlooglyBlob-PLA.3mf` as a project and select one plate. Keep the part
   orientations, per-part settings, support blockers and brims. The brim around
   each part's base is for bed adhesion; it isn't part of the design.
2. The material names are profiles, not AMS slots: "05 Blue PLA - B1" is the blue
   arm plate's profile. When you send a plate, map its profile to the slot that
   holds a suitable spool. Don't use "Synchronize filament list from AMS", which
   replaces the profiles.
3. Check that your printer, nozzle, plate and filament match; then re-slice and
   look at the first layer, the supports and any holes that must fit hardware.
4. Turn bed leveling on and timelapse off. For plate 2 (black), turn flow dynamics
   calibration off: the calibration line runs through that plate's front brim.
5. Let parts cool before removing them, and support fingers, goggle lips and horn
   seats during cleanup. Check each part as it comes off the plate.

## The {plates} plates

| Plate | Colour | Pieces | Estimate | Parts |
| --- | --- | ---: | --- | --- |
{plate_rows}

Plate numbers aren't a print order. To start building sooner, print 2 and 7, then
1, 3, 4, 6, 8, 5, 10 and 9.

The optional PETG ball uses Bambu's Generic PETG profile (255 °C nozzle, 70 °C
bed). Check your spool's label before printing, and check the thread fit and
clarity on your first print.

The build guide's Printing page has each plate's material settings and pictures.

Copyright (c) 2026 DeMartini Studios LLC. Released under the MIT License;
the full text is in `LICENSE.txt`.

BlooglyBlob: https://github.com/demartinistudios/blooglyblob
"""


def stl_sources(directory=STL, catalog_path=CATALOG):
    """Include only current required and optional parts, not retired export files."""
    catalog = json.loads(catalog_path.read_text())
    ids = {row['part_id'] for row in catalog['parts'] + catalog.get('optional_parts', [])}
    stls = sorted(directory / f'{part_id}.stl' for part_id in ids)
    missing = [p.stem for p in stls if not p.is_file()]
    if missing:
        raise ValueError(f'Missing catalog STL downloads: {missing}')
    return stls


def write(downloads, selected=None):
    """Write both print ZIPs and their notices; keep raw print files inside ZIPs."""
    selected = selected or sources()
    stls = stl_sources()
    required = Counter()
    for plate in selected['manifest']['plates']:
        required.update(plate['parts'])
    missing = set(required) - {p.stem for p in stls}
    if missing:
        raise ValueError(f'Missing selected STL downloads: {sorted(missing)}')
    readme = STL_README.format(plates=len(selected['manifest']['plates']),
                               part_types=len(required), pieces=sum(required.values()))
    downloads.mkdir(parents=True, exist_ok=True)
    notices = notice_entries()
    for name, content in notices:
        (downloads / name).write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))
    zip_write(downloads / 'BlooglyBlob-STL.zip',
              [('BlooglyBlob-STL/README.txt', readme)]
              + [(f'BlooglyBlob-STL/{name}', content) for name, content in notices]
              + [(f'BlooglyBlob-STL/{p.name}', p.read_bytes()) for p in stls])
    csv_path = selected['csv']
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text())))
    actual = Counter(row['part'] for row in rows)
    if actual != required:
        raise ValueError(f'Object-settings CSV quantities differ from selected plates: {dict(actual)} != {dict(required)}')
    projects = []
    with tempfile.TemporaryDirectory(prefix='blooglyblob-print-projects-') as folder:
        for key, name in [('pla', 'BlooglyBlob-PLA.3mf'), ('petg', 'BlooglyBlob-PETG-ball.3mf')]:
            project = Path(folder) / name
            public_3mf(selected[key], project)
            check_metadata(project)
            projects.append((f'BlooglyBlob-print-set/{name}', project.read_bytes()))
    zip_write(downloads / 'BlooglyBlob-print-set.zip', [
        ('BlooglyBlob-print-set/README.md', print_set_readme(selected['manifest'])),
        ('BlooglyBlob-print-set/BlooglyBlob-object-settings.csv', csv_path.read_bytes()),
        ] + projects + [(f'BlooglyBlob-print-set/{name}', content) for name, content in notices])

    previews = downloads.parent / 'assets/plates'
    previews.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(selected['pla']) as project:
        for plate in selected['manifest']['plates']:
            number = plate['plate_number']
            (previews / f'plate-{number}.png').write_bytes(project.read(f'Metadata/plate_{number}.png'))
