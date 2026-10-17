"""Calculate guide prices from catalog quotes and current build demand."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from urllib.parse import urlsplit


COST_CATEGORIES = ('Purchased parts', 'Fasteners', 'Consumables', 'Filament')


def amount(value, field, part_id, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'Invalid {field} for {part_id}: {value!r}') from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError(f'Invalid {field} for {part_id}: {value!r}')
    return number


def https_url(value, part_id):
    url = urlsplit(str(value or ''))
    if url.scheme != 'https' or not url.netloc:
        raise ValueError(f'Invalid purchase URL for {part_id}: {value!r}')


def cents(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def money(value):
    return str(cents(value))


def validate_kits(kits):
    """A kit's total allocates material value; its components determine coverage."""
    for kit_id, kit in kits.items():
        components = kit.get('components')
        if not isinstance(components, dict) or not components:
            raise ValueError(f'Missing kit components: {kit_id}')
        for component, quantity in components.items():
            if type(quantity) is not int or quantity <= 0:
                raise ValueError(f'Invalid kit component quantity: {kit_id} / {component}')
        if sum(components.values()) != amount(kit.get('pack_quantity'), 'pack quantity', kit_id, positive=True):
            raise ValueError(f'Kit piece count must equal component counts: {kit_id}')
        if not kit.get('purchase_name') or kit.get('unit') != 'each':
            raise ValueError(f'Kit needs a purchase name and each unit: {kit_id}')
        date.fromisoformat(str(kit.get('checked_date')))
        amount(kit.get('pack_price_usd'), 'pack price', kit_id)
        https_url(kit.get('url'), kit_id)
        if any(key in kit for key in ('purchase_group', 'included_with', 'used_quantity', 'plate_color')):
            raise ValueError(f'Kit cannot override demand or purchase grouping: {kit_id}')


def purchases(rows, single_color):
    """Round shared demand to whole retail packs; keep filament variants separate."""
    groups = defaultdict(list)
    categories = {name: Decimal(0) for name in COST_CATEGORIES}
    for index, row in enumerate(rows):
        key = ('kit', row['kit']) if row.get('kit') else ('pack', row.get('purchase_group', index))
        groups[key].append(row)
    for group in groups.values():
        first = group[0]
        fields = ('pack_price_usd', 'pack_quantity', 'unit', 'url', 'category', 'included_with')
        if any(any(row.get(key) != first.get(key) for key in fields) for row in group[1:]):
            raise ValueError(f"Shared purchase quotes must describe the same pack: {first['id']}")
        if first.get('kit'):
            # Unlike foam or a bag of identical nuts, spare sizes cannot cover a shortage.
            demand = max(Decimal(row['used_quantity']) / row['component_quantity'] for row in group)
        else:
            used = sum((Decimal(row['used_quantity']) for row in group), Decimal(0))
            demand = used / Decimal(first['pack_quantity'])
        packs = 0 if first.get('included_with') else int(demand.to_integral_value(rounding=ROUND_CEILING))
        cost = cents(packs * Decimal(first['pack_price_usd']))
        categories[first['category']] += cost
        first.update(buy_packs=packs, buy_cost=money(cost))
        for row in group[1:]:
            row.update(buy_packs=0, buy_cost='0.00', buy_shared_with=first['id'])
    filament = [row for row in rows if row['category'] == 'Filament']
    grams = sum((Decimal(row['used_quantity']) for row in filament), Decimal(0))
    spools, single_cost = 0, Decimal(0)
    if filament:
        selected = next((row for row in filament if row['plate_color'] == single_color), None)
        if selected is None:
            raise ValueError('Single-color estimate must select a priced filament color')
        spools = int((grams / Decimal(selected['pack_quantity'])).to_integral_value(rounding=ROUND_CEILING))
        single_cost = cents(spools * Decimal(selected['pack_price_usd']))
    non_filament = sum(value for key, value in categories.items() if key != 'Filament')
    return {'shopping_categories': {key: money(value) for key, value in categories.items()},
            'shopping_total': money(sum(categories.values())), 'non_filament_purchase': money(non_filament),
            'single_color_total': money(non_filament + single_cost), 'single_color_filament': money(single_cost),
            'single_color_spools': spools, 'palette_spools': sum(row['buy_packs'] for row in filament),
            'filament_grams': format(grams.normalize(), 'f')}


def calculate(prices, parts, plates):
    """Use installed counts unless a quote states a consumption allowance or plate color.

    Each row is rounded to cents before summing, so every displayed subtotal adds up.
    """
    if prices.get('schema_version') != 1 or prices.get('currency') != 'USD':
        raise ValueError('Unsupported price catalog schema or currency')
    date.fromisoformat(str(prices.get('checked_date')))
    kits = prices.get('kits', {})
    validate_kits(kits)
    part_map = {p['id']: p for p in parts}
    expected = {p['id'] for p in parts if p['category'] not in ('Printed', 'Tool')}
    ids = [item.get('id') for item in prices['items']]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError('Price catalog must cover every non-tool supply exactly once')
    categories = {name: Decimal(0) for name in COST_CATEGORIES}
    totals = defaultdict(Decimal)
    rows, priced_colors = [], []
    for item in prices['items']:
        part = part_map[item['id']]
        if not item.get('quotes'):
            raise ValueError(f"Missing price quotes: {part['id']}")
        if any('kit' in quote for quote in item['quotes']) and len(item['quotes']) != 1:
            raise ValueError(f"Supply must have exactly one kit quote: {part['id']}")
        for quote in item['quotes']:
            if 'kit' in quote:
                if set(quote) != {'kit'}:
                    raise ValueError(f"Kit quote must only reference its kit: {part['id']}")
                kit_id = quote['kit']
                if kit_id not in kits:
                    raise ValueError(f'Unknown kit: {kit_id}')
                kit = kits[kit_id]
                if part['id'] not in kit['components']:
                    raise ValueError(f"Missing kit component: {kit_id} / {part['id']}")
                quote = {key: value for key, value in kit.items() if key != 'components'} | {
                    'kit': kit_id, 'component_quantity': kit['components'][part['id']]}
            checked = str(quote.get('checked_date', prices['checked_date']))
            date.fromisoformat(checked)
            price = amount(quote.get('pack_price_usd'), 'pack price', part['id'])
            pack = amount(quote.get('pack_quantity'), 'pack quantity', part['id'], positive=True)
            for url in [quote.get('url')] + [link.get('url') for link in quote.get('alternative_links', [])]:
                https_url(url, part['id'])
            if part['id'] == 'C13':
                color = quote.get('plate_color')
                priced_colors.append(color)
                used = sum((amount(p['estimated_grams'], 'plate grams', part['id']) for p in plates if p['color'] == color), Decimal(0))
                if quote.get('unit') != 'g':
                    raise ValueError(f"Filament quotes must use grams: {part['id']} {color}")
                category = 'Filament'
            else:
                used = amount(quote.get('used_quantity', part['qty']), 'used quantity', part['id'])
                category = {'Purchased': 'Purchased parts', 'Fastener': 'Fasteners', 'Consumable': 'Consumables'}[part['category']]
            if quote.get('kit') and used != used.to_integral_value():
                raise ValueError(f"Kit demand must use whole pieces: {part['id']}")
            included = quote.get('included_with')
            if included and (included not in expected or included == part['id'] or price != 0):
                raise ValueError(f"Invalid included-part price: {part['id']}")
            cost = cents(price * used / pack)
            totals[part['id']] += cost
            categories[category] += cost
            rows.append({**quote, 'checked_date': checked, 'id': part['id'], 'name': quote.get('name', part['name']),
                         'category': category, 'used_quantity': format(used.normalize(), 'f'),
                         'cost_used': money(cost)})
    if len(priced_colors) != len(set(priced_colors)) or set(priced_colors) != {p['color'] for p in plates}:
        raise ValueError('Filament prices must cover each selected plate color exactly once')
    return {key: value for key, value in prices.items() if key != 'items'} | purchases(rows, prices.get('single_color')) | {
        'rows': rows, 'part_totals': {key: money(value) for key, value in totals.items()},
        'categories': {key: money(value) for key, value in categories.items()},
        'total': money(sum(categories.values())),
    }
