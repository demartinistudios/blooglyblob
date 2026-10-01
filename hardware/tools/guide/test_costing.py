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
        self.prices = dict(schema_version=1, currency='USD', checked_date='2026-10-01', items=[
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

    def test_totals_round_after_summing(self):
        self.parts[0]['qty'] = 1
        self.parts[1]['qty'] = 1
        for item in self.prices['items'][:2]:
            item['quotes'][0].update(pack_price_usd='1', pack_quantity='3')
        self.assertEqual(self.calculate()['total'], '5.67')

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

    def test_included_accessory_does_not_add_to_parent_price(self):
        self.parts.append(dict(id='E02', name='Horn', category='Purchased', qty=3))
        self.prices['items'].append(dict(id='E02', quotes=[dict(pack_price_usd='0', pack_quantity='1',
            unit='each', pack_label='Included with E01', url='https://example.com/product', included_with='E01')]))
        self.assertEqual(self.calculate()['part_totals']['E02'], '0.00')
        self.assertEqual(self.calculate()['total'], '23.12')
