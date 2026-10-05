#!/usr/bin/env python3
"""Check guide quantities, references and commands; report manual release review.

Ordinary checks validate usable inputs. --publication additionally requires the
release checklist. Review revisions are human declarations, not inferred approval.
Writing-standard violations are errors, so they make ok false in every mode.
`facts` prints each step's and part card's technical tokens for before/after diffs.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
RECEIPT = 'hardware/build-guide/review-status.json'
GUIDE = 'hardware/build-guide/src'
REFERENCE = 'hardware/references/community-20260925/catalog.json'
PRESENTATION = 'hardware/rendering/presentation-front.json'
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


SAFETY_LEVELS = ('warning', 'caution', 'notice')
# The guide shows the level label itself (INSTRUCTION-DESIGN.md, "Safety messages").
SAFETY_LABEL = re.compile(r'^\W*(?:warning|caution|notice|danger)\b|\*\*', re.I)


def check_safety(value, where):
    """A safety value is one {level, text} entry or a nonempty list of them."""
    entries = value if isinstance(value, list) else [value]
    if not entries:
        raise ValueError(f'{where}: safety must be an entry or a nonempty list of entries')
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {'level', 'text'}:
            raise ValueError(f'{where}: safety entries have only a level and text')
        if entry.get('level') not in SAFETY_LEVELS:
            raise ValueError(f'{where}: safety level must be warning, caution or notice')
        text = entry.get('text')
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'{where}: safety text must contain text')
        if SAFETY_LABEL.search(text):
            raise ValueError(f'{where}: safety text must not repeat the level label or add bold')


def check_panels(guide):
    """Each action has one readable illustration panel, in assembly order."""
    for step in guide['steps']:
        panels = step.get('panels')
        if not isinstance(panels, list) or not panels:
            raise ValueError(f"{step['id']}: action panels are required")
        if 'safety' in step:
            check_safety(step['safety'], step['id'])
        covered = []
        for j, panel in enumerate(panels):
            if 'safety' in panel:
                check_safety(panel['safety'], f"{step['id']} panels[{j}]")
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


# Writing standard: hardware/build-guide/INSTRUCTION-DESIGN.md ("Limits" and
# "Banned terms"). This is the one place the checks read their limits and terms.
WRITING = {
    'sentence_words': 20,
    'action_words': 35,
    'step_panels': 6,
    # Labels written on parts. W2 and W3 are always WAGO labels here, never the
    # washer fastener IDs; fastener IDs are sizes and need no plain name.
    'labels': ('W1', 'W2', 'W3', 'W4', 'F2', 'C1', 'C2', 'S1', 'S2', 'R1', 'R2', 'J1'),
    # (term, pattern, case-sensitive, scope). Scope 'text' applies everywhere,
    # 'unsafe' everywhere except safety entries and quoted software messages,
    # 'caption' only in captions.
    'banned': (
        ('land', r'\b(?:land|lands|landed|landing)\b', False, 'text'),
        ('dry-route', r'\bdry-rout(?:e|es|ed|ing)\b', False, 'text'),
        ('dry-fit', r'\bdry-fit(?:s|ted|ting)?\b', False, 'text'),
        ('pull-check', r'\bpull-check(?:s|ed|ing)?\b', False, 'text'),
        ('fit pose', r'\bfit poses?\b', False, 'text'),
        ('rest pose', r'\brest poses?\b', False, 'text'),
        ('dress', r'\bdress(?:es|ed|ing)?\b', False, 'text'),
        ('enclosure', r'\benclosures?\b', False, 'text'),
        ('inlet', r'\binlets?\b', False, 'text'),
        ('panel jack', r'\bpanel jacks?\b', False, 'text'),
        ('central opening', r'\bcentral openings?\b', False, 'text'),
        ('central wire hole', r'\bcentral wire holes?\b', False, 'text'),
        ('BASE→BODY', r'BASE\s*→\s*BODY', True, 'text'),
        ('H2', r'\bH2\b', True, 'text'),
        ('H3', r'\bH3\b', True, 'text'),
        ('BODY (connector)', r'(?<!→)\bBODY\b(?! LIGHT)', True, 'text'),
        ('HEAD (connector)', r'\bHEAD (?:tails?|plugs?|latch(?:es)?|connectors?|power|lighting)\b', True, 'text'),
        ('pigtail', r'\bpigtails?\b', False, 'text'),
        ('service stand', r'\bservice stands?\b|\bstand (?:board|blocks?)\b', False, 'text'),
        ('simply', r'\bsimply\b', False, 'text'),
        ('just', r'\bjust\b', False, 'text'),
        ('easily', r'\beasily\b', False, 'text'),
        ('carefully', r'\bcarefully\b', False, 'text'),
        ('please', r'\bplease\b', False, 'text'),
        ('make sure', r'\bmake sure\b', False, 'text'),
        ('note that', r'\bnote that\b', False, 'text'),
        ('warning', r'\bwarnings?\b', False, 'unsafe'),
        ('caution', r'\bcautions?\b', False, 'unsafe'),
        ('be careful', r'\bbe careful\b', False, 'unsafe'),
        ('danger', r'\bdanger\b', False, 'unsafe'),
        ('not to scale', r'\bnot to scale\b', False, 'caption'),
        ('illustrative', r'\billustrative(?:ly)?\b', False, 'caption'),
        ('does not show', r'\bdoes not show\b', False, 'caption'),
    ),
    # Two instructions joined in one sentence: a semicolon, or "then" after the start.
    # Only code spans and software messages in curly quotes are skipped; a straight "
    # is an inch mark as often as a quote, so it exempts nothing.
    'joined': r';|\s\bthen\b',
    'card_fields': ('name', 'description', 'status', 'verification'),
}
WRITING_RULES = ('panel-count', 'sentence-length', 'one-instruction', 'action-length', 'banned-term', 'first-use',
                 'caption-repeats-action')
STEP_LINK = re.compile(r'\{step:[^}]+\}')
MAKE = re.compile(r'\bmake\s+[A-Za-z][A-Za-z0-9_]*-[A-Za-z0-9_-]+')
QUOTED = re.compile(r'“[^”]*”|"[^"]*"')
CODE = re.compile(r'`[^`]*`')
MESSAGE = re.compile(r'“[^”]*”')


def sentences(text):
    """Split prose after . ! or ? (with any closing quote) when the next word is not lowercase."""
    parts = re.split(r'(?<=[.!?])\s+(?=[^a-z\s])|(?<=[.!?][”"’)])\s+(?=[^a-z\s])', text.strip())
    return [p for p in parts if p]


def word_count(text):
    """Split on spaces; a command, step link or backtick span is one word, and symbols are not words."""
    text = re.sub(r'`[^`]*`', 'code', MAKE.sub('command', STEP_LINK.sub('link', text)))
    return sum(1 for token in text.split() if re.search(r'\w', token))


def step_texts(step):
    """Yield (location, field, text) for a step's prose in reading order."""
    sid = step['id']

    def safety(entry, where):
        for i, row in enumerate(entry if isinstance(entry, list) else [entry]):
            if isinstance(row, dict) and isinstance(row.get('text'), str):
                yield f'{where}.safety' + (f'[{i}]' if isinstance(entry, list) else ''), 'safety', row['text']

    yield f'{sid} title', 'title', step.get('title', '')
    if 'safety' in step:
        yield from safety(step['safety'], sid)
    actions = step.get('actions', [])
    for j, panel in enumerate(step.get('panels', [])):
        where = f'{sid} panels[{j}]'
        yield f'{where}.title', 'title', panel.get('title', '')
        if 'safety' in panel:
            yield from safety(panel['safety'], where)
        for i in panel.get('actions', []):
            if type(i) is int and 0 <= i < len(actions):
                yield f'{sid} actions[{i}]', 'action', actions[i]
        yield f'{where}.caption', 'caption', panel.get('caption', '')
        if isinstance(panel.get('detail'), dict):
            yield f'{where}.detail.title', 'title', panel['detail'].get('title', '')
    yield f'{sid} check', 'check', step.get('check', '')
    yield f'{sid} note', 'note', step.get('note', '')


def card_texts(parts):
    for part in parts:
        for field in WRITING['card_fields']:
            if isinstance(part.get(field), str):
                yield f"part {part['id']} {field}", 'card', part[field]


def banned_terms(text, field):
    found = []
    unquoted = QUOTED.sub(' ', text)
    for term, pattern, case, scope in WRITING['banned']:
        if (scope == 'caption' and field != 'caption') or (scope == 'unsafe' and field == 'safety'):
            continue
        if re.search(pattern, unquoted if scope == 'unsafe' else text, 0 if case else re.I):
            found.append(term)
    return found


def named_in_parentheses(text, start):
    """True when the ID at start sits in parentheses directly after a name."""
    opening = text.rfind('(', 0, start)
    return (opening > 0 and ')' not in text[opening:start] and ')' in text[start:]
            and re.search(r'\w\s*$', text[:opening]) is not None)


def check_writing(guide, parts):
    """Return writing-standard violations, each starting with its rule name; check() reports them as errors."""
    limits = WRITING
    ids = {p['id'] for p in parts if p.get('category') != 'Fastener'} | set(limits['labels'])
    id_pattern = re.compile(r'(?<![\w.])(' + '|'.join(sorted(map(re.escape, ids), key=len, reverse=True)) + r')(?!\w)')
    warnings = []
    for step in guide['steps']:
        sid = step['id']
        panels = step.get('panels', [])
        if len(panels) > limits['step_panels']:
            warnings.append(f"panel-count: {sid}: {len(panels)} panels (limit {limits['step_panels']})")
        seen = set()
        for where, field, text in step_texts(step):
            if not text:
                continue
            for n, sentence in enumerate(sentences(text), 1):
                count = word_count(sentence)
                if count > limits['sentence_words']:
                    warnings.append(f"sentence-length: {where}: sentence {n} has {count} words "
                                    f"(limit {limits['sentence_words']})")
                if field == 'action' and re.search(limits['joined'], CODE.sub(' ', MESSAGE.sub(' ', sentence)).strip(), re.I):
                    warnings.append(f'one-instruction: {where}: sentence {n} joins instructions')
            if field == 'action':
                count = word_count(text)
                if count > limits['action_words']:
                    warnings.append(f"action-length: {where}: {count} words (limit {limits['action_words']})")
            for term in banned_terms(text, field):
                warnings.append(f'banned-term: {where}: {term}')
            clean = QUOTED.sub(lambda m: ' ' * len(m.group()), STEP_LINK.sub(lambda m: ' ' * len(m.group()), text))
            for match in id_pattern.finditer(clean):
                label = match.group(1)
                if label in seen:
                    continue
                seen.add(label)
                if not named_in_parentheses(clean, match.start()):
                    warnings.append(f'first-use: {where}: {label} needs its plain name first, ID in parentheses')
        actions = step.get('actions', [])
        for j, panel in enumerate(panels):
            caption = panel.get('caption', '')
            covered = [actions[i] for i in panel.get('actions', []) if type(i) is int and 0 <= i < len(actions)]
            if caption and set(map(normal, sentences(caption))) & {normal(s) for a in covered for s in sentences(a)}:
                warnings.append(f'caption-repeats-action: {sid} panels[{j}].caption: repeats its action text')
    for where, field, text in card_texts(parts):
        for term in banned_terms(text, field):
            warnings.append(f'banned-term: {where}: {term}')
    return warnings


def normal(text):
    return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower()).split())


# Fact inventory (KTD7): technical tokens a rewrite must keep, per step and part card.
UNITS = r'(?:mm|cm|µm|m|inches|inch|mV|V|mA|A|W|kΩ|Ω|µF|uF|nF|AWG|°C|°|ms|s|min|h|g|kg|GB|MB|kHz|Hz|%)'
NUMBER = r'\d+(?:\.\d+)?(?:/\d+)?'
COUNTS = ('two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve')
FACTS = (  # (kind, pattern, case-sensitive); earlier patterns claim their text first
    ('command', MAKE.pattern, True),
    ('quote', QUOTED.pattern, True),
    ('literal', r'`[^`]+`|\b[\w.]+=\S*\w', True),
    ('fuse', r'\bT\d+(?:\.\d+)?\s?A\b', True),
    ('port', r'\bW[1-4]/\d(?:\s?[–-]\s?\d)?', True),
    ('pin', r'\b[Pp]ins?\s+\d+(?:(?:,\s*|,?\s+and\s+|,?\s+or\s+)\d+)*', True),
    ('pin', r'\bS[12] !?[A-Z]{1,3}\d?\b|!?\b[CD]5\b|\bGPIO\s?\d+\b', True),
    ('id', r'\bM\d(?:\.\d)?\s?[×x]\s?\d+(?:\s?countersunk|CS)?\b', True),
    ('id', None, True),  # part IDs and written labels, filled in from parts.json
    ('value', rf'(?<![\w.])[+−]?{NUMBER}(?:\s?[–-]\s?{NUMBER})?(?:\s?×\s?{NUMBER})*\s?{UNITS}(?![\w])', True),
    ('signal', r'\b(?:GND|DATA|DAT|CLK|DIN|DOUT|VIN|VCC)\b', True),
    ('label', r'BASE\s*→\s*BODY|\b(?:BODY LIGHT|HEAD LIGHT|PI POWER|LEFT|RIGHT|HEAD|BODY|INPUT|SERVO)\b', True),
    ('polarity', r'\b(?:positive|negative|striped?|red|black|center|sleeve|polarity|robot-left|robot-right)\b', False),
    ('count', r'\b(?:' + '|'.join(COUNTS) + r')\b', False),
    ('number', r'(?<![\w.])\d+(?:\.\d+)?(?![\w])', True),
)


def normalize_fact(kind, token):
    token = ' '.join(token.split())
    if kind == 'id':
        token = re.sub(r'\s?[×x]\s?', '×', token, count=1)
    elif kind == 'value':
        token = re.sub(r'\s?×\s?', ' × ', token)
        token = re.sub(r'\s?([–-])\s?', r'\1', token)
        token = re.sub(rf'(\d)\s?({UNITS})$', r'\1 \2', token)
    elif kind == 'fuse':
        token = re.sub(r'\s?A$', ' A', token)
    elif kind == 'pin':
        numbers = re.findall(r'\d+', token) if token.lower().startswith('pin') else None
        return [f'pin {n}' for n in numbers] if numbers else [token]
    elif kind in ('polarity', 'count'):
        token = token.lower()
    return [token]


def text_facts(text, ids):
    """Return the set of (kind, token) facts in one piece of text."""
    found = set()
    text = STEP_LINK.sub(lambda m: ' ' * len(m.group()), text)
    for kind, pattern, case in FACTS:
        pattern = pattern or ids
        def claim(match):
            found.update((kind, t) for t in normalize_fact(kind, match.group()))
            return ' ' * len(match.group())
        text = re.sub(pattern, claim, text, flags=0 if case else re.I)
    return found


def fact_inventory(guide, parts):
    """Map each step, then each part card, to its sorted technical tokens."""
    names = sorted({p['id'] for p in parts if not re.match(r'M\d', p['id'])} | set(WRITING['labels']),
                   key=len, reverse=True)
    ids = r'(?<![\w.])(?:' + '|'.join(map(re.escape, names)) + r')(?!\w)'
    inventory = {}
    for step in guide['steps']:
        facts = set()
        for _, _, text in step_texts(step):
            facts |= text_facts(text, ids)
        commands = list(step.get('commands', []))
        for panel in step.get('panels', []):
            commands += panel.get('commands', [])
            for block in panel.get('codeBlocks', []):
                facts.update((block.get('kind', 'code'), line.strip()) for line in block.get('lines', []) if line.strip())
        facts.update(('command', ' '.join(c.split())) for c in commands if isinstance(c, str) and c.strip())
        for row in step.get('workshop_supplies', []):
            for cell in row:
                facts |= text_facts(str(cell), ids)
        if isinstance(step.get('workshop_tools'), str):
            facts |= text_facts(step['workshop_tools'], ids)
        inventory[step['id']] = sorted(facts)
    for part in parts:
        facts = set()
        for field in ('name', 'exact', 'description', 'status', 'verification'):
            if isinstance(part.get(field), str):
                facts |= text_facts(part[field], ids)
        inventory[f"part {part['id']}"] = sorted(facts)
    return inventory


def format_facts(inventory):
    return ''.join(f'{key}\t{kind}\t{token}\n' for key, facts in inventory.items() for kind, token in facts)


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


def check_tools(guide, parts):
    """Each step lists the tools its work needs, once each; tool cards list those steps in order."""
    tools = {p['id']: p for p in parts if p.get('category') == 'Tool'}
    for step in guide['steps']:
        for tid, n in step.get('parts', {}).items():
            if tid in tools and n != 1:
                raise ValueError(f"{step['id']}: tool {tid} must have quantity 1")
    for tid, card in tools.items():
        used = [step['id'] for step in guide['steps'] if tid in step.get('parts', {})]
        if card.get('steps') != used:
            raise ValueError(f'{tid}: tool card steps differ from the steps that use it: {used}')


def check_animation_assets(root):
    """Check current authored animation assets, without requiring historical sources."""
    assets = read(root, PRESENTATION)['homepage_animation']['assets']
    if not isinstance(assets, list) or not assets:
        raise ValueError(f'{PRESENTATION}: homepage_animation assets must be a nonempty list')
    for asset in assets:
        path = asset['path']
        source = root / path
        if not source.is_file():
            raise ValueError(f'Homepage animation asset missing: {path}')
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != asset['sha256']:
            raise ValueError(f'Homepage animation asset SHA-256 mismatch: {path}; '
                             f"declared {asset['sha256']}, actual {actual}")


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
        parts = read(root, f'{GUIDE}/parts.json')
        check_panels(guide)
        check_quantities(read(root, 'hardware/assembly/hardware.json'), read(root, 'hardware/catalog/supplies.json'),
                         read(root, 'hardware/catalog/parts.json'), guide, parts)
        check_tools(guide, parts)
        check_animation_assets(root)
        result['errors'] = list(check_writing(guide, parts))
        check_references(root, read(root, REFERENCE), read(root, f'{GUIDE}/references/catalog.json'))
        check_reference_page((root / GUIDE / 'references.html').read_text(),
                             read(root, f'{GUIDE}/references/catalog.json'))
        result['errors'] += [f'Guide command make {target} has no Makefile target' for target in missing_commands(root)]
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
    parser.add_argument('command', choices=('check', 'facts'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--publication', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.command == 'facts':
        root = Path(args.root).resolve()
        inventory = fact_inventory(read(root, f'{GUIDE}/guide-data.json'), read(root, f'{GUIDE}/parts.json'))
        print(json.dumps(inventory, indent=2, ensure_ascii=False) if args.json else format_facts(inventory), end='')
        return 0
    report = check(args.root, args.publication)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print('Guide invariants: ' + ('FAIL' if report['errors'] else 'PASS'))
        for error in report['errors']:
            print('ERROR: ' + error)
        rules = Counter(e.split(':', 1)[0] for e in report['errors'] if e.split(':', 1)[0] in WRITING_RULES)
        if rules:
            print(f"Writing errors: {sum(rules.values())} ("
                  + ', '.join(f'{rule} {n}' for rule, n in sorted(rules.items())) + ')')
        if args.publication:
            for blocker in report['blockers']:
                print('REVIEW REQUIRED: ' + blocker)
        if not report['errors']:
            print('Preview build allowed. Review status is independent of CAD acceptance and deployment.')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
