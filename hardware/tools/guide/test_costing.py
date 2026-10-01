"""Prices follow build demand without charging unused packs or double-counting filament."""
from copy import deepcopy
import unittest

import costing


class CostingTests(unittest.TestCase):
    def setUp(self):
        self.parts = [dict(id='E01', name='Servo', category='Purchased', qty=3),
                      dict(id='N2', name='Nut', category='Fastener', qty=4),
                      dict(id='C13', name='Filament', category='Consumable', qty='As used'),
                      dict(id='C18', name='Optional glue', category='Consumable', qty='As used'),
                      dict(id='P01', name='Printed part', category='Printed', qty=2),
                      dict(id='T01', name='Tool', category='Tool', qty=1)]
        self.plates = [dict(color='White', estimated_grams=125), dict(color='White', estimated_grams=125)]
        def quote(price, pack, **extra):
            return dict(pack_price_usd=price, pack_quantity=pack, unit='each',
                        url='https://example.com/product', pack_label='Pack', **extra)
        filament = quote('20', '1000', plate_color='White')
        filament['unit'] = 'g'
        self.prices = dict(schema_version=1, currency='USD', checked_date='2026-10-01', single_color='White', items=[
            dict(id='E01', quotes=[quote('6', '1')]),
            dict(id='N2', quotes=[quote('3', '100')]),
            dict(id='C13', quotes=[filament]),
            dict(id='C18', quotes=[quote('5', '20', used_quantity='0')])])

    def calculate(self):
        return costing.calculate(self.prices, self.parts, self.plates)

    def test_prorates_packs_and_counts_filament_once(self):
        result = self.calculate()
        self.assertEqual(result['part_totals'], {'E01': '18.00', 'N2': '0.12', 'C13': '5.00', 'C18': '0.00'})
        self.assertEqual(result['total'], '23.12')
        self.assertEqual(next(r for r in result['rows'] if r['id'] == 'C13')['used_quantity'], '250')

    def test_quantity_and_price_changes_flow_into_same_total(self):
        self.parts[0]['qty'] = 2
        self.prices['items'][0]['quotes'][0]['pack_price_usd'] = '7'
        self.assertEqual(self.calculate()['part_totals']['E01'], '14.00')
        self.assertEqual(self.calculate()['total'], '19.12')

    def test_totals_add_the_rounded_rows(self):
        self.parts[0]['qty'] = 1
        self.parts[1]['qty'] = 1
        for item in self.prices['items'][:2]:
            item['quotes'][0].update(pack_price_usd='1', pack_quantity='3')
        result = self.calculate()
        self.assertEqual([r['cost_used'] for r in result['rows'][:2]], ['0.33', '0.33'])
        self.assertEqual(result['categories']['Purchased parts'], '0.33')
        self.assertEqual(result['total'], '5.66')
        self.assertEqual(sum(float(v) for v in result['categories'].values()), 5.66)

    def test_missing_or_duplicate_item_fails(self):
        original = deepcopy(self.prices['items'])
        for items in (original[:-1], original + [original[0]]):
            self.prices['items'] = items
            with self.assertRaisesRegex(ValueError, 'every non-tool supply'):
                self.calculate()

    def test_unpriced_or_duplicate_plate_color_fails(self):
        self.plates.append(dict(color='Blue', estimated_grams=50))
        with self.assertRaisesRegex(ValueError, 'each selected plate color'):
            self.calculate()
        self.plates.pop()
        self.prices['items'][2]['quotes'] *= 2
        with self.assertRaisesRegex(ValueError, 'each selected plate color'):
            self.calculate()

    def test_invalid_price_or_pack_fails(self):
        quote = self.prices['items'][0]['quotes'][0]
        for field, value in [('pack_price_usd', '-1'), ('pack_price_usd', 'NaN'),
                             ('pack_price_usd', 'Infinity'), ('pack_quantity', '0')]:
            with self.subTest(field=field, value=value):
                old = quote[field]
                quote[field] = value
                with self.assertRaises(ValueError):
                    self.calculate()
                quote[field] = old

    def add_included(self, **changes):
        self.parts.append(dict(id='E02', name='Horn', category='Purchased', qty=3))
        quote = dict(pack_price_usd='0', pack_quantity='1', unit='each', pack_label='Included with E01',
                     url='https://example.com/product', included_with='E01')
        self.prices['items'].append(dict(id='E02', quotes=[quote | changes]))

    def test_included_accessory_does_not_add_to_parent_price(self):
        self.add_included()
        result = self.calculate()
        self.assertEqual(result['part_totals']['E02'], '0.00')
        self.assertEqual(result['total'], '23.12')
        self.assertEqual(next(r for r in result['rows'] if r['id'] == 'E02')['buy_packs'], 0)
        self.assertEqual(result['shopping_total'], '41.00')

    def test_invalid_included_accessory_fails(self):
        for changes in (dict(pack_price_usd='1'), dict(included_with='E99'), dict(included_with='E02')):
            with self.subTest(changes=changes):
                self.setUp()
                self.add_included(**changes)
                with self.assertRaisesRegex(ValueError, 'included-part price: E02'):
                    self.calculate()

    def test_non_https_purchase_or_alternative_url_fails(self):
        quote = self.prices['items'][0]['quotes'][0]
        for bad in ('http://example.com/product', 'javascript:alert(1)', '', None):
            with self.subTest(url=bad):
                quote.update(url=bad)
                with self.assertRaisesRegex(ValueError, 'purchase URL for E01'):
                    self.calculate()
                quote.update(url='https://example.com/product', alternative_links=[dict(label='Other', url=bad)])
                with self.assertRaisesRegex(ValueError, 'purchase URL for E01'):
                    self.calculate()
                del quote['alternative_links']

    def test_bad_quote_data_names_the_part(self):
        cases = [(0, lambda q: q.pop('pack_price_usd'), 'pack price for E01'),
                 (0, lambda q: q.pop('url'), 'purchase URL for E01'),
                 (2, lambda q: q.update(unit='kg'), 'grams: C13'),
                 (3, lambda q: q.pop('used_quantity'), "used quantity for C18: 'As used'")]
        for index, change, message in cases:
            with self.subTest(message=message):
                self.setUp()
                change(self.prices['items'][index]['quotes'][0])
                with self.assertRaisesRegex(ValueError, message):
                    self.calculate()
        self.setUp()
        self.prices['items'][0]['quotes'] = []
        with self.assertRaisesRegex(ValueError, 'Missing price quotes: E01'):
            self.calculate()

    def test_purchase_estimate_rounds_up_packs_and_excludes_optional_items(self):
        self.parts[1]['qty'] = 101
        result = self.calculate()
        self.assertEqual(result['shopping_categories']['Fasteners'], '6.00')
        self.assertEqual(result['shopping_categories']['Consumables'], '0.00')
        self.assertEqual(result['shopping_total'], '44.00')
        self.assertEqual(result['single_color_total'], '44.00')

    def test_shared_pack_is_rounded_after_combining_demand(self):
        self.prices['items'][1]['quotes'][0]['purchase_group'] = 'shared'
        self.parts.append(dict(id='N3', name='Other use', category='Fastener', qty=97))
        self.prices['items'].append(dict(id='N3', quotes=[deepcopy(self.prices['items'][1]['quotes'][0])]))
        result = self.calculate()
        self.assertEqual(result['shopping_categories']['Fasteners'], '6.00')
        shared = [r for r in result['rows'] if r.get('purchase_group') == 'shared']
        self.assertEqual(shared[0]['buy_packs'], 2)
        self.assertEqual(shared[1]['buy_shared_with'], 'N2')
        self.prices['items'][-1]['quotes'][0]['pack_price_usd'] = '4'
        with self.assertRaisesRegex(ValueError, 'Shared purchase'):
            self.calculate()

    def test_single_color_combines_filament_mass_but_full_palette_keeps_spools_separate(self):
        self.plates.append(dict(color='Blue', estimated_grams=900))
        quote = deepcopy(self.prices['items'][2]['quotes'][0])
        quote.update(plate_color='Blue', pack_price_usd='30')
        self.prices['items'][2]['quotes'].append(quote)
        result = self.calculate()
        self.assertEqual(result['shopping_categories']['Filament'], '50.00')
        self.assertEqual(result['single_color_filament'], '40.00')
        self.assertEqual(result['single_color_spools'], 2)
        self.assertEqual(result['palette_spools'], 2)
        self.assertEqual(result['single_color_total'], '61.00')
        self.assertEqual(result['shopping_total'], '71.00')
        self.prices['single_color'] = 'Missing'
        with self.assertRaisesRegex(ValueError, 'Single-color'):
            self.calculate()
