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


def purchases(rows, single_color):
    """Round shared demand to whole retail packs; keep filament variants separate."""
    groups = defaultdict(list)
    categories = {name: Decimal(0) for name in COST_CATEGORIES}
    for index, row in enumerate(rows):
        groups[row.get('purchase_group', index)].append(row)
    for group in groups.values():
        first = group[0]
        fields = ('pack_price_usd', 'pack_quantity', 'unit', 'url', 'category', 'included_with')
        if any(any(row.get(key) != first.get(key) for key in fields) for row in group[1:]):
            raise ValueError(f"Shared purchase quotes must describe the same pack: {first['id']}")
        used = sum((Decimal(row['used_quantity']) for row in group), Decimal(0))
        packs = 0 if first.get('included_with') else int((used / Decimal(first['pack_quantity'])).to_integral_value(rounding=ROUND_CEILING))
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
        for quote in item['quotes']:
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
            included = quote.get('included_with')
            if included and (included not in expected or included == part['id'] or price != 0):
                raise ValueError(f"Invalid included-part price: {part['id']}")
            cost = cents(price * used / pack)
            totals[part['id']] += cost
            categories[category] += cost
            rows.append({**quote, 'id': part['id'], 'name': quote.get('name', part['name']),
                         'category': category, 'used_quantity': format(used.normalize(), 'f'),
                         'cost_used': money(cost)})
    if len(priced_colors) != len(set(priced_colors)) or set(priced_colors) != {p['color'] for p in plates}:
        raise ValueError('Filament prices must cover each selected plate color exactly once')
    return {key: value for key, value in prices.items() if key != 'items'} | purchases(rows, prices.get('single_color')) | {
        'rows': rows, 'part_totals': {key: money(value) for key, value in totals.items()},
        'categories': {key: money(value) for key, value in categories.items()},
        'total': money(sum(categories.values())),
    }
