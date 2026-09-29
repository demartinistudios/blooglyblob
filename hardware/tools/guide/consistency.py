#!/usr/bin/env python3
"""Check guide quantities, references and commands; report manual release review.

Ordinary checks validate usable inputs. --publication additionally requires the
release checklist. Review revisions are human declarations, not inferred approval.
"""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
RECEIPT = 'hardware/build-guide/review-status.json'
GUIDE = 'hardware/build-guide/src'
REFERENCE = 'hardware/references/community-20260925/catalog.json'
SURFACES = ('instructions', 'part-supply-cards', 'print-cards-downloads',
            'assembly-visuals', 'diagrams-templates', 'references',
            'software-commands', 'progress-and-navigation')


def read(root, path):
    return json.loads((root / path).read_text())


def indexed(rows, key, label):
    result = {}
    for row in rows:
        if row[key] in result:
            raise ValueError(f'{label}: duplicate {key} {row[key]}')
        result[row[key]] = row
    return result


def counts(value, label):
    if not isinstance(value, dict) or any(type(n) is not int or n <= 0 for n in value.values()):
        raise ValueError(f'{label}: quantities must be positive integers')
    return Counter(value)


def allocation_totals(allocations):
    totals = Counter()
    for key, row in allocations.items():
        totals.update(counts(row['hardware'], key))
    return dict(totals)


def check_panels(guide):
    """Each action has one readable illustration panel, in assembly order."""
    for step in guide['steps']:
        panels = step.get('panels')
        if not isinstance(panels, list) or not panels:
            raise ValueError(f"{step['id']}: action panels are required")
        covered = []
        for panel in panels:
            indices = panel.get('actions')
            if not panel.get('title') or not (panel.get('image') or panel.get('commands') or panel.get('codeBlocks') or panel.get('textOnly') is True):
                raise ValueError(f"{step['id']}: panel needs a title and image, commands/codeBlocks, or explicit textOnly")
            if (not isinstance(indices, list) or not 1 <= len(indices) <= 3
                    or any(type(i) is not int or not 0 <= i < len(step['actions']) for i in indices)):
                raise ValueError(f"{step['id']}: panel must reference one to three valid actions")
            if 'commands' in panel and (not isinstance(panel['commands'], list)
                    or any(not isinstance(c, str) or not c.strip() for c in panel['commands'])):
                raise ValueError(f"{step['id']}: panel commands must be nonempty strings")
            if 'codeBlocks' in panel:
                blocks = panel['codeBlocks']
                if not isinstance(blocks, list) or not blocks:
                    raise ValueError(f"{step['id']}: codeBlocks must be a nonempty list")
                for block in blocks:
                    if not isinstance(block, dict) or block.get('kind') not in ('command', 'config', 'output'):
                        raise ValueError(f"{step['id']}: code block kind must be command, config or output")
                    lines = block.get('lines')
                    if (not isinstance(lines, list) or not lines
                            or any(not isinstance(line, str) for line in lines)
                            or not any(line.strip() for line in lines)):
                        raise ValueError(f"{step['id']}: code block lines must contain text")
                    if block['kind'] == 'command':
                        if block.get('context') not in ('computer', 'pi'):
                            raise ValueError(f"{step['id']}: command block needs computer or pi context")
                    elif 'context' in block:
                        raise ValueError(f"{step['id']}: only command blocks have machine context")
                    if 'label' in block and (not isinstance(block['label'], str) or not block['label'].strip()):
                        raise ValueError(f"{step['id']}: code block label must contain text")
                    if 'copy' in block and block['copy'] is not False:
                        raise ValueError(f"{step['id']}: optional copy override must be false")
            if 'links' in panel:
                if not isinstance(panel['links'], list):
                    raise ValueError(f"{step['id']}: panel links must be a list")
                for link in panel['links']:
                    if (not isinstance(link, dict) or any(
                            not isinstance(link.get(k), str) or not link[k].strip()
                            for k in ('label', 'url'))):
                        raise ValueError(f"{step['id']}: panel link needs label and url")
                    url = urlsplit(link['url'])
                    if (url.scheme and url.scheme != 'https') or (url.netloc and not url.scheme):
                        raise ValueError(f"{step['id']}: panel link must be local or HTTPS")
                    if link['url'].startswith('#step-'):
                        target = link['url'][6:].split('/')[0]
                        if target not in {s['id'] for s in guide['steps']}:
                            raise ValueError(f"{step['id']}: panel link has unknown step {target}")
            if 'detail' in panel:
                detail = panel['detail']
                if (not isinstance(detail, dict) or any(
                        not isinstance(detail.get(k), str) or not detail[k].strip()
                        for k in ('title', 'image'))):
                    raise ValueError(f"{step['id']}: panel detail needs a title and image")
            covered.extend(indices)
        if covered != list(range(len(step['actions']))):
            raise ValueError(f"{step['id']}: panels must cover every action exactly once in order")


def check_quantities(hardware, supplies, catalog, guide, parts):
    """Technical allocations and editorial preparation/service references stay distinct."""
    allocations = indexed(hardware['allocations'], 'id', 'installed allocations')
    totals = allocation_totals(allocations)
    steps = indexed(guide['steps'], 'id', 'guide steps')
    presented = indexed(parts, 'id', 'guide parts')
    technical = indexed(catalog['parts'], 'part_id', 'part catalog')
    supply = indexed(supplies['supplies'], 'id', 'supply catalog')
    if set(supply) != {key for key, row in presented.items() if row['category'] != 'Printed'}:
        raise ValueError('Supply catalog IDs differ from nonprinted guide part IDs')
    if set(totals) != {key for key, row in supply.items() if row['category'] == 'Fastener'}:
        raise ValueError('Installed fastener IDs differ from supply catalog fastener IDs')
    consumed = {key: Counter() for key in allocations}
    for sid, step in steps.items():
        projected = Counter()
        for ref in step.get('hardware_allocations', []):
            aid, role = ref['allocation_id'], ref['role']
            if aid not in allocations or role not in ('install', 'preload', 'service'):
                raise ValueError(f'{sid}: unknown allocation or role: {aid}/{role}')
            quantity = counts(ref['hardware'], sid)
            if quantity - Counter(allocations[aid]['hardware']):
                raise ValueError(f'{sid}: references more hardware than allocated to {aid}')
            if role == 'service':
                if step['kind'] != 'service':
                    raise ValueError(f'{sid}: service reuse must be a service step')
                continue  # service refers to existing hardware; it never adds installed demand
            if step['kind'] != 'build':
                raise ValueError(f'{sid}: service step cannot consume installed demand')
            consumed[aid].update(quantity)
            projected.update(quantity)
        if dict(projected) != step['hardware']:
            raise ValueError(f'{sid}: guide hardware differs from allocation/preload projection')
        unknown = set(step['parts']) - set(presented)
        if unknown:
            raise ValueError(f'{sid}: unknown part IDs {sorted(unknown)}')
    for aid, allocation in allocations.items():
        if dict(consumed[aid]) != allocation['hardware']:
            raise ValueError(f'{aid}: guide allocation counted twice or missing: {dict(consumed[aid])}')
    if guide['totals'] != totals:
        raise ValueError('Guide fastener totals differ from installed allocation totals')
    for key, row in supply.items():
        expected = {field: row[field] for field in ('category', 'exact', 'optional')}
        expected['qty'] = totals[key] if row['category'] == 'Fastener' else row['qty']
        for field, value in expected.items():
            if presented[key].get(field) != value:
                raise ValueError(f'{key}: guide {field} differs from canonical supply/allocation')
    for key, row in technical.items():
        if key not in presented or presented[key]['category'] != 'Printed' or presented[key]['qty'] != row['quantity']:
            raise ValueError(f'{key}: guide installed quantity differs from part catalog')
    extra_installed = {key for key, row in presented.items()
                       if row['category'] == 'Printed' and row['qty'] and key not in technical}
    if extra_installed:
        raise ValueError(f'Guide has uncatalogued installed printed parts: {sorted(extra_installed)}')
    return totals


def check_references(root, technical, presentation):
    for directory in ('hardware/references', 'hardware/servos'):
        for path in (root / directory).rglob('*'):
            if path.is_file() and path.suffix.lower() == '.pdf':
                raise ValueError(f'Publisher PDFs must remain external links: {path}')
    source = indexed(technical['references'], 'id', 'reference catalog')
    rows = indexed(presentation['references'], 'reference_id', 'guide references')
    if set(source) != set(rows):
        raise ValueError('Guide reference IDs differ from technical catalog')
    for rid, ref in source.items():
        row = rows[rid]
        expected = {'parts': ref['part_ids'], 'publisher': ref['publisher'],
                    'url': ref.get('download_url') or ref['official_url'], 'checked': ref['checked_date']}
        for field, value in expected.items():
            if row.get(field) != value:
                raise ValueError(f'{rid}: guide reference {field} differs from technical catalog')
        if ref.get('local_path') or row.get('saved_copy'):
            raise ValueError(f'{rid}: publisher documents must use external links')
        for url in (ref['official_url'], expected['url']):
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError(f'{rid}: reference needs a public HTTPS URL')


def check_reference_page(html, presentation):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = set()

        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.urls.add(dict(attrs).get('href'))

    links = Links()
    links.feed(html)
    for ref in presentation['references']:
        if ref['url'] not in links.urls:
            raise ValueError(f"{ref['reference_id']}: reference page omits catalog URL")


def missing_commands(root):
    """Inspect declared make commands; never execute them or move hardware."""
    targets = set()
    for match in re.finditer(r'^([A-Za-z0-9_.% /-]+)\s*:(?!=)', (root / 'Makefile').read_text(), re.M):
        targets.update(match.group(1).split())
    commands = set()
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)

    for path in (root / GUIDE).rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.html', '.js', '.md', '.txt'):
            text = path.read_text()
            if path.suffix == '.json':
                # Decode escaped whitespace in authored command/config/output cards.
                text += '\n' + '\n'.join(strings(json.loads(text)))
            commands.update(re.findall(r'\bmake\s+([A-Za-z][A-Za-z0-9_]*-[A-Za-z0-9_-]+)', text))
            commands.update(re.findall(r'(?:`|<code[^>]*>|[\"\']|\n)\s*make\s+([A-Za-z][A-Za-z0-9_-]*)', text))
    return sorted(commands - targets)


def review_status(root):
    """Read the manual release checklist; changes require an affected-scope review."""
    receipt_path = root / RECEIPT
    rows = indexed(read(root, RECEIPT)['surfaces'], 'surface', 'guide review') if receipt_path.exists() else {}
    if set(rows) - set(SURFACES):
        raise ValueError('Review record contains unknown surfaces')
    result = {}
    for surface in SURFACES:
        row = rows.get(surface, {})
        state = row.get('status', 'pending')
        if state not in ('pending', 'blocked', 'verified'):
            raise ValueError(f'{surface}: invalid review status {state}')
        if state == 'verified' and not all(row.get(key) for key in ('reviewed_revision', 'reviewer', 'evidence')):
            raise ValueError(f'{surface}: verified review requires revision, reviewer and evidence')
        result[surface] = {'status': state, 'reason': row.get('reason', 'Review required')}
    return result


def check(root=ROOT, publication=False):
    root = Path(root).resolve()
    result = {'errors': [], 'blockers': [], 'review': {}}
    try:
        guide = read(root, f'{GUIDE}/guide-data.json')
        check_panels(guide)
        check_quantities(read(root, 'hardware/assembly/hardware.json'), read(root, 'hardware/catalog/supplies.json'),
                         read(root, 'hardware/catalog/parts.json'), guide,
                         read(root, f'{GUIDE}/parts.json'))
        check_references(root, read(root, REFERENCE), read(root, f'{GUIDE}/references/catalog.json'))
        check_reference_page((root / GUIDE / 'references.html').read_text(),
                             read(root, f'{GUIDE}/references/catalog.json'))
        result['errors'] = [f'Guide command make {target} has no Makefile target' for target in missing_commands(root)]
        result['review'] = review_status(root)
        for surface, row in result['review'].items():
            if row['status'] != 'verified':
                result['blockers'].append(f"{surface}: {row['status']} — {row['reason']}")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result['errors'].append(str(exc))
    result['ok'] = not result['errors'] and (not publication or not result['blockers'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check',))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--publication', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    report = check(args.root, args.publication)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print('Guide invariants: ' + ('FAIL' if report['errors'] else 'PASS'))
        for error in report['errors']:
            print('ERROR: ' + error)
        if args.publication:
            for blocker in report['blockers']:
                print('REVIEW REQUIRED: ' + blocker)
        if not report['errors']:
            print('Preview build allowed. Review status is independent of CAD acceptance and deployment.')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
