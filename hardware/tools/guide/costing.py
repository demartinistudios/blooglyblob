"""Calculate guide prices from catalog quotes and current build demand."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit


def amount(value, field, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'Invalid {field}: {value!r}') from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError(f'Invalid {field}: {value!r}')
    return number


def money(value):
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate(prices, parts, plates):
    """Use installed counts unless a quote states a consumption allowance or plate color."""
    if prices['schema_version'] != 1 or prices['currency'] != 'USD':
        raise ValueError('Unsupported price catalog schema or currency')
    date.fromisoformat(prices['checked_date'])
    part_map = {p['id']: p for p in parts}
    expected = {p['id'] for p in parts if p['category'] not in ('Printed', 'Tool')}
    ids = [item['id'] for item in prices['items']]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError('Price catalog must cover every non-tool supply exactly once')
    categories = {name: Decimal(0) for name in ('Purchased parts', 'Fasteners', 'Consumables', 'Filament')}
    totals = defaultdict(Decimal)
    rows, priced_colors = [], []
    for item in prices['items']:
        part = part_map[item['id']]
        if not item['quotes']:
            raise ValueError(f"Missing price quotes: {part['id']}")
        for quote in item['quotes']:
            price = amount(quote['pack_price_usd'], 'pack price')
            pack = amount(quote['pack_quantity'], 'pack quantity', positive=True)
            purchase_url = urlsplit(quote['url'])
            if purchase_url.scheme != 'https' or not purchase_url.netloc:
                raise ValueError(f"Invalid purchase URL: {part['id']}")
            if part['id'] == 'C13':
                color = quote['plate_color']
                priced_colors.append(color)
                used = sum((amount(p['estimated_grams'], 'plate grams') for p in plates if p['color'] == color), Decimal(0))
                if quote['unit'] != 'g':
                    raise ValueError('Filament quotes must use grams')
                category = 'Filament'
            else:
                used = amount(quote.get('used_quantity', part['qty']), 'used quantity')
                category = {'Purchased': 'Purchased parts', 'Fastener': 'Fasteners', 'Consumable': 'Consumables'}[part['category']]
            included = quote.get('included_with')
            if included and (included not in expected or included == part['id'] or price != 0):
                raise ValueError(f"Invalid included-part price: {part['id']}")
            cost = price * used / pack
            totals[part['id']] += cost
            categories[category] += cost
            rows.append({**quote, 'id': part['id'], 'name': quote.get('name', part['name']),
                         'category': category, 'used_quantity': format(used.normalize(), 'f'),
                         'cost_used': money(cost)})
    if len(priced_colors) != len(set(priced_colors)) or set(priced_colors) != {p['color'] for p in plates}:
        raise ValueError('Filament prices must cover each selected plate color exactly once')
    return {key: value for key, value in prices.items() if key != 'items'} | {
        'rows': rows, 'part_totals': {key: money(value) for key, value in totals.items()},
        'categories': {key: money(value) for key, value in categories.items()},
        'total': money(sum(categories.values())),
    }
