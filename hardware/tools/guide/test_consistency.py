"""Small fixtures exercise drift and failure gates without touching a live preview."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build
import consistency as c


class QuantityTests(unittest.TestCase):
    def setUp(self):
        self.hardware = {'allocations': [{'id': 'eye-joint', 'hardware': {'N2': 4, 'M2x6': 4}}]}
        self.supplies = {'supplies': [dict(id=k, category='Fastener', exact=k, optional=0) for k in ('N2', 'M2x6')]}
        self.catalog = {'parts': [{'part_id': 'EYE', 'quantity': 1}]}
        self.parts = [dict(id=k, category='Fastener', exact=k, optional=0, qty=4) for k in ('N2', 'M2x6')]
        self.parts += [dict(id='EYE', category='Printed', qty=1)]
        self.guide = {'totals': {'N2': 4, 'M2x6': 4}, 'steps': [
            {'id': 'load', 'kind': 'build', 'parts': {}, 'hardware': {'N2': 4},
             'hardware_allocations': [{'allocation_id': 'eye-joint', 'role': 'preload', 'hardware': {'N2': 4}}]},
            {'id': 'fit', 'kind': 'build', 'parts': {'EYE': 1}, 'hardware': {'M2x6': 4},
             'hardware_allocations': [{'allocation_id': 'eye-joint', 'role': 'install', 'hardware': {'M2x6': 4}}]},
            {'id': 'repair', 'kind': 'service', 'parts': {'EYE': 1}, 'hardware': {},
             'hardware_allocations': [{'allocation_id': 'eye-joint', 'role': 'service', 'hardware': {'M2x6': 4}}]},
        ]}

    def run_check(self):
        return c.check_quantities(self.hardware, self.supplies, self.catalog, self.guide, self.parts)

    def test_split_preload_and_service_do_not_duplicate_demand(self):
        self.assertEqual(self.run_check(), {'N2': 4, 'M2x6': 4})
        self.guide['steps'].reverse()  # editorial ordering is not joint identity
        self.run_check()

    def test_duplicate_allocation_is_rejected(self):
        self.guide['steps'][1]['hardware']['N2'] = 4
        self.guide['steps'][1]['hardware_allocations'][0]['hardware']['N2'] = 4
        with self.assertRaisesRegex(ValueError, 'counted twice'):
            self.run_check()

    def test_totals_cannot_hide_changed_joint(self):
        self.hardware['allocations'][0]['hardware']['M2x6'] = 5
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.run_check()

    def test_printed_quantity_drift_is_rejected(self):
        self.parts[-1]['qty'] = 2
        with self.assertRaisesRegex(ValueError, 'installed quantity'):
            self.run_check()

    def test_supply_specification_drift_is_rejected(self):
        self.parts[0]['exact'] = 'Different nut'
        with self.assertRaisesRegex(ValueError, 'canonical supply'):
            self.run_check()


class ToolListTests(unittest.TestCase):
    """Each step lists the tools its work needs; each tool card lists those steps (R3)."""
    def setUp(self):
        self.parts = [dict(id='T01', category='Tool', steps=['cut', 'service']),
                      dict(id='T02', category='Tool', steps=['cut']),
                      dict(id='EYE', category='Printed', steps=['fit'])]
        self.guide = {'steps': [dict(id='cut', parts={'T01': 1, 'T02': 1}),
                                dict(id='fit', parts={'EYE': 1}),
                                dict(id='service', parts={'T01': 1})]}

    def check(self):
        c.check_tools(self.guide, self.parts)

    def test_matching_tool_lists_pass(self):
        self.check()

    def test_tool_card_must_list_every_step_that_uses_it_in_order(self):
        for steps in (['cut'], ['service', 'cut'], ['cut', 'fit', 'service']):
            with self.subTest(steps=steps):
                self.parts[0]['steps'] = steps
                with self.assertRaisesRegex(ValueError, r'^T01: tool card steps differ from the steps that use it'):
                    self.check()

    def test_a_tool_is_listed_once_per_step(self):
        self.guide['steps'][0]['parts']['T02'] = 2
        with self.assertRaisesRegex(ValueError, r'^cut: tool T02 must have quantity 1'):
            self.check()


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.step = dict(id='fixture', actions=['prepare', 'fit', 'check'], panels=[
            dict(title='Prepare', image='assets/prepare.svg', actions=[0]),
            dict(title='Fit and check', image='assets/fit.svg', actions=[1, 2])])

    def check(self):
        c.check_panels({'steps': [self.step]})

    def test_each_action_is_present_in_order(self):
        self.check()
        self.step['panels'].reverse()
        with self.assertRaisesRegex(ValueError, 'exactly once in order'):
            self.check()

    def test_missing_duplicate_and_out_of_range_actions_fail(self):
        for indices in ([1], [0, 1], [1, 3], [True, 2]):
            with self.subTest(indices=indices):
                self.step['panels'][1]['actions'] = indices
                with self.assertRaises(ValueError):
                    self.check()

    def test_command_panel_does_not_need_decorative_image(self):
        self.step['panels'][0].pop('image')
        self.step['panels'][0]['commands'] = ['make pi-status']
        self.check()
        self.step['panels'][0]['commands'] = ['']
        with self.assertRaisesRegex(ValueError, 'commands must be nonempty'):
            self.check()

    def test_optional_detail_requires_title_and_image(self):
        self.step['panels'][0]['detail'] = dict(title='Nut fit', image='detail.svg')
        self.check()
        for value in (None, {}, {'title': 'Nut fit', 'image': ''}):
            self.step['panels'][0]['detail'] = value
            with self.assertRaisesRegex(ValueError, 'detail needs a title and image'):
                self.check()

    def test_typed_code_cards_can_replace_an_image(self):
        panel = self.step['panels'][0]
        del panel['image']
        panel['codeBlocks'] = [
            dict(kind='command', context='computer', label='Repository folder', lines=['make pi-status']),
            dict(kind='command', context='pi', lines=['cat /proc/asound/cards']),
            dict(kind='config', label='.env', lines=['PI_HOST=demo.local', '', 'PI_USER=builder']),
            dict(kind='output', lines=['active (running)'], copy=False),
        ]
        self.check()

    def test_bad_code_card_metadata_is_rejected(self):
        valid = dict(kind='command', context='computer', lines=['make pi-status'])
        bad = [None, {}, dict(valid, kind='shell'), dict(valid, context='server'),
               dict(kind='command', lines=['make pi-status']),
               dict(valid, lines='make pi-status'), dict(valid, lines=[]),
               dict(valid, lines=['', '  ']), dict(valid, lines=[7]),
               dict(valid, label=''), dict(valid, copy=True), dict(valid, copy=0),
               dict(kind='config', context='pi', lines=['A=B'])]
        for block in bad:
            with self.subTest(block=block):
                self.step['panels'][0]['codeBlocks'] = [block]
                with self.assertRaises(ValueError):
                    self.check()
        for blocks in ({}, [], 'make pi-status'):
            self.step['panels'][0]['codeBlocks'] = blocks
            with self.assertRaises(ValueError):
                self.check()

    def test_link_labels_and_destinations_are_required(self):
        panel = self.step['panels'][0]
        panel['links'] = [dict(label='This step', url='#step-fixture'),
                          dict(label='Manufacturer', url='https://example.com/setup'),
                          dict(label='Download', url='downloads/setup.txt')]
        self.check()
        for link in (None, {}, dict(label='', url='#step-fixture'),
                     dict(label='Missing', url='#step-absent'),
                     dict(label='Invalid', url='javascript:alert(1)')):
            panel['links'] = [link]
            with self.subTest(link=link), self.assertRaises(ValueError):
                self.check()

    def test_typed_cards_do_not_bypass_action_coverage(self):
        panel = self.step['panels'][0]
        panel['codeBlocks'] = [dict(kind='command', context='computer', lines=['make pi-status'])]
        panel['actions'] = [0, 1]
        with self.assertRaisesRegex(ValueError, 'exactly once in order'):
            self.check()

    def test_text_only_panel_requires_explicit_intent(self):
        self.step['panels'][0].pop('image')
        self.step['panels'][0]['textOnly'] = True
        self.check()
        self.step['panels'][0]['textOnly'] = 'true'
        with self.assertRaisesRegex(ValueError, 'title and image'):
            self.check()

    def test_image_and_panel_required(self):
        self.step['panels'][0]['image'] = ''
        with self.assertRaisesRegex(ValueError, 'title and image'):
            self.check()
        self.step['panels'] = []
        with self.assertRaisesRegex(ValueError, 'panels are required'):
            self.check()

    def test_safety_entries_on_panels_and_steps_are_accepted(self):
        self.step['safety'] = dict(level='warning', text='A short circuit can cause burns. Unplug first.')
        self.step['panels'][0]['safety'] = dict(level='notice', text='Thin plastic cracks. Do not force the nut.')
        self.step['panels'][1]['safety'] = [dict(level='caution', text='C1 is polarized. Match its stripe.'),
                                            dict(level='notice', text='Forcing the plug bends its pins.')]
        self.check()

    def test_safety_with_unknown_level_fails_with_step_id(self):
        for where in ('step', 'panel'):
            with self.subTest(where=where):
                self.setUp()
                entry = dict(level='danger', text='A short circuit can cause burns.')
                (self.step if where == 'step' else self.step['panels'][1])['safety'] = entry
                with self.assertRaisesRegex(ValueError, r'^fixture.*safety level must be warning, caution or notice'):
                    self.check()
        self.step['panels'][1]['safety'] = dict(text='A short circuit can cause burns.')
        with self.assertRaisesRegex(ValueError, r'^fixture panels\[1\]: safety level'):
            self.check()

    def test_safety_with_empty_text_fails_with_step_id(self):
        for text in ('', '   ', None):
            with self.subTest(text=text):
                self.step['panels'][0]['safety'] = dict(level='caution', text=text)
                with self.assertRaisesRegex(ValueError, r'^fixture panels\[0\]: safety text'):
                    self.check()
        self.step['panels'][0].pop('safety')
        self.step['safety'] = [dict(level='warning', text='Unplug first.'), dict(level='warning', text='')]
        with self.assertRaisesRegex(ValueError, r'^fixture: safety text'):
            self.check()

    def test_safety_shape_is_one_entry_or_a_nonempty_list(self):
        for value in ([], 'Unplug first.', [dict(level='warning', text='Unplug first.'), 'Unplug first.'],
                      dict(level='warning', text='Unplug first.', title='Power')):
            with self.subTest(value=value):
                self.step['safety'] = value
                with self.assertRaisesRegex(ValueError, r'^fixture: safety'):
                    self.check()

    def test_safety_text_does_not_repeat_its_level_label(self):
        # The guide shows the level label; the text must not type it again.
        for text in ('WARNING: unplug first.', 'Caution - C1 is polarized.', '**Notice** thin plastic.'):
            with self.subTest(text=text):
                self.step['panels'][0]['safety'] = dict(level='caution', text=text)
                with self.assertRaisesRegex(ValueError, 'safety text must not repeat the level label or add bold'):
                    self.check()


def words(count, word='bolt'):
    return ' '.join([word] * count)


class WritingTests(unittest.TestCase):
    """Writing-standard rules; check() reports every finding as an error."""

    def setUp(self):
        self.parts = [dict(id='FB41', category='Printed', name='Front microphone grille'),
                      dict(id='C01', category='Consumable', name='Clear eye film'),
                      dict(id='W2', category='Fastener', name='M2 washer'),
                      dict(id='M3x12', category='Fastener', name='M3×12')]
        self.step = dict(id='fixture', title='Fit the grille', actions=['Fit the part.', 'Tighten the screws.'],
                         check='The part sits flat.', note='', panels=[
                             dict(title='Fit', image='fit.svg', caption='Front view.', actions=[0, 1])])

    def warnings(self, rule=None):
        found = c.check_writing({'steps': [self.step]}, self.parts)
        return [w for w in found if rule is None or w.startswith(rule + ':')]

    def test_clean_step_has_no_warnings(self):
        self.assertEqual(self.warnings(), [])

    def test_long_sentence_names_step_and_action(self):
        self.step['actions'][1] = words(25) + '.'
        found = self.warnings()
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith('sentence-length:'))
        self.assertIn('fixture actions[1]', found[0])
        self.assertIn('25 words', found[0])

    def test_action_at_exact_limits_passes_and_one_more_word_warns(self):
        self.step['actions'][0] = words(20) + '. ' + words(15, 'Nut') + '.'
        self.assertEqual(self.warnings(), [])
        self.step['actions'][0] = words(20) + '. ' + words(16, 'Nut') + '.'
        found = self.warnings()
        self.assertEqual(len(found), 1, found)
        self.assertIn('action-length: fixture actions[0]', found[0])

    def test_units_step_links_commands_and_symbols_do_not_inflate_counts(self):
        # 20 words when a command is one word and arrows are not words; 23 otherwise.
        self.step['actions'][0] = ('Run make pi-servo-fit now, then read {step:board-cover-nuts} for four M3×6 '
                                   'screws at W1/3 → F1 → W2/1 with an 11 mm strip here.')
        self.assertEqual(self.warnings('sentence-length'), [])

    def test_caption_repeating_its_action_warns(self):
        self.step['panels'][0]['caption'] = 'Tighten the screws.'
        found = self.warnings()
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith('caption-repeats-action: fixture panels[0].caption'))

    def test_banned_terms_in_actions_notes_and_captions(self):
        self.step['actions'][0] = 'Dress the cable along the rib.'
        self.step['note'] = 'Simply check the fit.'
        self.step['panels'][0]['caption'] = 'Enclosure cut away, not to scale.'
        found = self.warnings('banned-term')
        self.assertEqual(len(found), 4, found)
        self.assertTrue(any('fixture actions[0]' in w and 'dress' in w for w in found))
        self.assertTrue(any('fixture note' in w and 'simply' in w for w in found))
        self.assertTrue(any('panels[0].caption' in w and 'enclosure' in w for w in found))
        self.assertTrue(any('panels[0].caption' in w and 'not to scale' in w for w in found))

    def test_banned_letters_inside_longer_words_pass(self):
        self.step['actions'][0] = 'Address the headland, adjust the enclosed speaker and stand it on the landscape mat.'
        self.step['note'] = 'The BODY LIGHT and HEAD LIGHT labels face up. Label the HEAD servo cable.'
        self.assertEqual(self.warnings('banned-term'), [])

    def test_connector_terms_are_case_sensitive(self):
        self.step['actions'][0] = 'Connect H3 to BODY.'
        self.step['actions'][1] = 'Seat the HEAD plug.'
        found = self.warnings('banned-term')
        self.assertEqual(len(found), 3, found)

    def test_safety_words_only_in_safety_entries_or_quotes(self):
        self.step['actions'][1] = 'Stop at a warning.'
        self.assertEqual(len(self.warnings('banned-term')), 1)
        self.step['actions'][1] = 'Stop if it shows “power warning”.'
        self.assertEqual(self.warnings('banned-term'), [])
        self.step['panels'][0]['safety'] = dict(level='caution', text='A reversed capacitor can vent. Take caution with its stripe.')
        self.assertEqual(self.warnings('banned-term'), [])

    def test_part_id_needs_plain_name_on_first_use_only(self):
        self.step['actions'] = ['Fit FB41 to the base.', 'Tighten FB41.']
        found = self.warnings('first-use')
        self.assertEqual(len(found), 1, found)
        self.assertIn('fixture actions[0]', found[0])
        self.assertIn('FB41', found[0])
        self.step['actions'] = ['Fit the front microphone grille (FB41).', 'Tighten FB41.']
        self.assertEqual(self.warnings('first-use'), [])

    def test_wago_labels_are_not_washer_ids_and_similar_ids_stay_distinct(self):
        self.step['actions'] = ['Cut the clear eye film (C01). Insert the loop into W2/1.',
                                'Fit four M3×12 screws and a T3.15 A fuse at the servo power WAGO (W3).']
        found = self.warnings('first-use')
        self.assertEqual(len(found), 1, found)
        self.assertIn('W2', found[0])

    def test_step_with_more_panels_than_limit_warns(self):
        limit = c.WRITING['step_panels']
        self.step['actions'] = ['Fit the part.'] * (limit + 1)
        self.step['panels'] = [dict(title=f'Panel {i}', image='p.svg', actions=[i]) for i in range(limit)]
        self.step['panels'][-1]['actions'] = [limit - 1, limit]
        self.assertEqual(self.warnings('panel-count'), [])
        self.step['panels'][-1]['actions'] = [limit - 1]
        self.step['panels'].append(dict(title='Extra', image='p.svg', actions=[limit]))
        found = self.warnings('panel-count')
        self.assertEqual(len(found), 1, found)
        self.assertIn(f'{limit + 1} panels', found[0])

    def test_joined_instructions_warn(self):
        for text in ('Start the screws by hand, then tighten them.', 'Start the screws by hand; tighten them.'):
            self.step['actions'][0] = text
            with self.subTest(text=text):
                self.assertEqual(len(self.warnings('one-instruction')), 1)
        self.step['actions'][0] = 'Start the screws by hand. Then tighten them.'
        self.assertEqual(self.warnings('one-instruction'), [])

    def test_quoted_messages_and_code_do_not_count_as_joined_instructions(self):
        for text in ('Wait for “Done; reboot now”.', 'Run `sync; sync` on the Pi.', 'Wait for “Saved, then closed”.'):
            self.step['actions'][0] = text
            with self.subTest(text=text):
                self.assertEqual(self.warnings('one-instruction'), [])
        for text in ('Wait for “Done”; then reboot.', 'Run `sync` on the Pi; reboot it.',
                     'Cut a 1" square; press a 2" square beside it.', 'Wait for "Saved; closed".'):
            self.step['actions'][0] = text
            with self.subTest(text=text):
                self.assertEqual(len(self.warnings('one-instruction')), 1)

    def test_retired_harness_opening_names_are_banned(self):
        self.step['actions'][0] = 'Feed the cable through the central opening.'
        self.step['check'] = 'The central wire hole stays clear.'
        found = self.warnings('banned-term')
        self.assertEqual(len(found), 2, found)
        self.assertIn('central opening', found[0])
        self.assertIn('central wire hole', found[1])

    def test_retired_service_stand_is_banned(self):
        self.step['note'] = 'Rest the robot on the service stand.'
        self.step['check'] = 'The stand blocks hold the head.'
        self.assertEqual(len(self.warnings('banned-term')), 2)
        self.step['note'], self.step['check'] = '', 'Stand the robot on its feet.'
        self.assertEqual(self.warnings('banned-term'), [])

    def test_current_guide_has_no_writing_errors(self):
        root = Path(__file__).resolve().parents[3]
        found = c.check_writing(c.read(root, c.GUIDE + '/guide-data.json'), c.read(root, c.GUIDE + '/parts.json'))
        self.assertEqual(found, [])

    def test_part_card_text_is_checked_for_banned_terms(self):
        self.parts[0]['status'] = 'Print it, then dry-fit it.'
        found = self.warnings('banned-term')
        self.assertEqual(len(found), 1, found)
        self.assertIn('part FB41 status', found[0])

    def test_limits_match_the_approved_standard(self):
        standard = (Path(__file__).resolve().parents[2] / 'build-guide/INSTRUCTION-DESIGN.md').read_text()
        for rule, key in (('Words in one sentence', 'sentence_words'), ('Words in one action (all its sentences)', 'action_words'),
                          ('Panels in one step', 'step_panels')):
            self.assertIn(f"| {rule} | {c.WRITING[key]} or fewer |", standard)


class FactTests(unittest.TestCase):
    def setUp(self):
        self.step = dict(id='fuse', title='Wire the fuse', actions=[
            'Fit the servo fuse (F1) with a T3.15 A fuse.',
            'Insert its loop into W2/1. Strip 11 mm first.',
            'Connect Pi pin 12 to DAT. Fasten four M3×12 screws. Run make pi-servo-fit.'],
            check='The fuse holder closes.', note='',
            panels=[dict(title='Fuse', image='f.svg', caption='', actions=[0, 1, 2],
                         codeBlocks=[dict(kind='output', lines=['throttled=0x0'])])])
        self.parts = [dict(id='E07', category='Purchased', name='Fuse holder', description='Holds a 5 × 20 mm fuse.')]

    def inventory(self):
        return c.fact_inventory({'steps': [self.step]}, self.parts)

    def test_sample_step_lists_technical_tokens(self):
        facts = self.inventory()['fuse']
        for token in ('T3.15 A', 'W2/1', '11 mm', 'pin 12', 'M3×12', 'F1', 'make pi-servo-fit', 'throttled=0x0'):
            self.assertIn(token, [t for _, t in facts])
        self.assertIn(('value', '5 × 20 mm'), self.inventory()['part E07'])

    def test_output_is_stable_and_sorted(self):
        first = c.format_facts(self.inventory())
        self.assertEqual(first, c.format_facts(self.inventory()))
        lines = [line for line in first.splitlines() if line.startswith('fuse\t')]
        self.assertEqual(lines, sorted(lines))

    def test_moving_a_fact_between_actions_keeps_the_inventory(self):
        before = self.inventory()
        self.step['actions'][1] = 'Insert its loop into W2/1.'
        self.step['actions'][0] = 'Strip 11 mm first. Fit the servo fuse (F1) with a T3.15 A fuse.'
        self.assertEqual(self.inventory(), before)

    def test_removed_fact_changes_the_inventory(self):
        before = self.inventory()
        self.step['actions'][1] = 'Insert its loop into W2/2. Strip 11 mm first.'
        self.assertNotEqual(self.inventory(), before)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ref = dict(id='ref', part_ids=['EYE'], publisher='Manufacturer',
                        official_url='https://example.com/product',
                        download_url='https://example.com/drawing.pdf', checked_date='2026-09-26')
        self.row = dict(reference_id='ref', parts=['EYE'], publisher='Manufacturer',
                        url='https://example.com/drawing.pdf', checked='2026-09-26')

    def check(self):
        c.check_references(self.root, dict(references=[self.ref]), dict(references=[self.row]))

    def test_external_document_url_is_used_without_a_download(self):
        self.check()
        self.row['url'] = self.ref['official_url']
        with self.assertRaisesRegex(ValueError, 'url differs'):
            self.check()

    def test_local_copy_and_non_https_links_are_rejected(self):
        self.ref['local_path'] = 'drawing.pdf'
        with self.assertRaisesRegex(ValueError, 'external links'):
            self.check()
        del self.ref['local_path']
        self.ref['download_url'] = self.row['url'] = 'file:///tmp/drawing.pdf'
        with self.assertRaisesRegex(ValueError, 'HTTPS URL'):
            self.check()

    def test_publisher_pdf_cannot_be_reintroduced(self):
        folder = self.root / 'hardware/references'
        folder.mkdir(parents=True)
        (folder / 'drawing.PDF').write_bytes(b'%PDF-example')
        with self.assertRaisesRegex(ValueError, 'Publisher PDFs'):
            self.check()

    def test_reference_page_must_include_catalog_link(self):
        presentation = dict(references=[self.row])
        c.check_reference_page('<a href="https://example.com/drawing.pdf">Drawing</a>', presentation)
        with self.assertRaisesRegex(ValueError, 'omits catalog URL'):
            c.check_reference_page('<a href="https://example.com/old.pdf">Drawing</a>', presentation)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)

    def test_missing_manual_review_stays_pending(self):
        self.assertTrue(all(row['status'] == 'pending'
                            for row in c.review_status(self.root).values()))

    def test_verified_review_requires_revision_reviewer_and_evidence(self):
        row = dict(surface='instructions', status='verified')
        self.write(c.RECEIPT, json.dumps({'surfaces': [row]}))
        with self.assertRaisesRegex(ValueError, 'revision, reviewer and evidence'):
            c.review_status(self.root)
        row.update(reviewed_revision='fixture revision', reviewer='Fixture reviewer',
                   evidence=['fixture inspection'], reason='Instructions inspected')
        self.write(c.RECEIPT, json.dumps({'surfaces': [row]}))
        self.assertEqual(c.review_status(self.root)['instructions']['status'], 'verified')

    def test_unknown_surface_is_rejected(self):
        self.write(c.RECEIPT, json.dumps({'surfaces': [dict(surface='typo', status='verified')]}))
        with self.assertRaisesRegex(ValueError, 'unknown surfaces'):
            c.review_status(self.root)

    def test_command_check_does_not_confuse_prose_or_execute_targets(self):
        self.write('Makefile', 'pi-check:\n\tfalse\n')
        self.write(c.GUIDE + '/app.js', '<code>make pi-check</code><code>make pi-servo-fit</code> make it fit; make the part')
        self.assertEqual(c.missing_commands(self.root), ['pi-servo-fit'])

    def test_commands_in_typed_cards_are_checked_after_json_decoding(self):
        self.write('Makefile', 'pi-check:\n\tfalse\n')
        panel = {'codeBlocks': [dict(kind='command', context='computer',
                                   lines=['make pi-check\nmake absent', 'make pi-not-a-target'])]}
        self.write(c.GUIDE + '/guide-data.json', json.dumps({'steps': [{'panels': [panel]}]}))
        self.assertEqual(c.missing_commands(self.root), ['absent', 'pi-not-a-target'])

    def check_fixture(self, commands=(), writing=()):
        self.write(c.GUIDE + '/references.html', '')
        with ExitStack() as stack:
            for name in ('check_panels', 'check_quantities', 'check_tools', 'check_references', 'check_reference_page'):
                stack.enter_context(patch.object(c, name))
            stack.enter_context(patch.object(c, 'check_writing', return_value=list(writing)))
            stack.enter_context(patch.object(c, 'read', return_value={}))
            stack.enter_context(patch.object(c, 'missing_commands', return_value=list(commands)))
            stack.enter_context(patch.object(c, 'review_status', return_value={
                'instructions': {'status': 'pending', 'reason': 'Assembly inspection needed'}}))
            return c.check(self.root), c.check(self.root, publication=True)

    def test_pending_review_allows_preview_but_blocks_publication(self):
        offline, publication = self.check_fixture()
        self.assertTrue(offline['ok'])
        self.assertEqual(offline['errors'], [])
        self.assertFalse(publication['ok'])

    def test_missing_documented_command_fails_offline_too(self):
        offline, _ = self.check_fixture(['pi-servo-fit'])
        self.assertFalse(offline['ok'])
        self.assertIn('pi-servo-fit', offline['errors'][0])

    def test_writing_violations_are_errors_outside_publication(self):
        offline, publication = self.check_fixture(writing=['sentence-length: fixture actions[0]: 25 words'])
        self.assertFalse(offline['ok'])
        self.assertFalse(publication['ok'])
        self.assertEqual(offline['errors'], ['sentence-length: fixture actions[0]: 25 words'])
        offline, _ = self.check_fixture(['pi-servo-fit'], writing=['banned-term: fixture note: simply'])
        self.assertFalse(offline['ok'])
        self.assertEqual(len(offline['errors']), 2)

    def test_real_sentence_over_the_limit_fails_the_check(self):
        step = dict(id='fixture', title='Fit the grille', actions=[' '.join(['word'] * 21) + '.'], check='', note='',
                    panels=[dict(title='Fit', image='fit.svg', caption='', actions=[0])])
        self.write(c.GUIDE + '/references.html', '')
        with ExitStack() as stack:
            for name in ('check_panels', 'check_quantities', 'check_tools', 'check_references', 'check_reference_page'):
                stack.enter_context(patch.object(c, name))
            stack.enter_context(patch.object(c, 'read', side_effect=lambda root, path: (
                {'steps': [step]} if path.endswith('guide-data.json') else [] if path.endswith('parts.json') else {})))
            stack.enter_context(patch.object(c, 'missing_commands', return_value=[]))
            stack.enter_context(patch.object(c, 'review_status', return_value={}))
            result = c.check(self.root)
        self.assertFalse(result['ok'])
        self.assertEqual(len(result['errors']), 1)
        self.assertTrue(result['errors'][0].startswith('sentence-length: fixture actions[0]'))


class InlinePrintSettingsTests(unittest.TestCase):
    def test_catalog_keeps_notes_and_stl_links_without_duplicate_intro(self):
        html = build.plate_settings_html((build.SRC / 'repeat-build.html').read_text())
        self.assertTrue(html.startswith('<h2>The ten plates</h2>'))
        self.assertIn('Printer and material notes', html)
        self.assertIn('Bambu Lab X1 Carbon', html)
        self.assertIn('Synchronize filament list from AMS', html)
        self.assertIn('downloads/stl/GS11.stl', html)
        self.assertIn('data-zoom="assets/plates/plate-1.png"', html)
        self.assertNotIn('<h1>', html)
        self.assertNotIn('downloads/BlooglyBlob-PLA.3mf', html)


class AtomicBuildTests(unittest.TestCase):
    def test_setup_panel_screenshot_and_link_paths_are_checked(self):
        data = {'steps': [{'panels': [{'image': 'assets/setup/imager-device.png',
                                     'links': [{'label': 'Example', 'url': 'downloads/setup.txt'}]}]}]}
        (self.src / 'guide-data.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(SystemExit, 'assets/setup/imager-device.png'):
            build.build()
        self.assert_preview_preserved()
        (self.src / 'assets/setup').mkdir(parents=True)
        (self.src / 'assets/setup/imager-device.png').write_bytes(b'fixture PNG')
        with self.assertRaisesRegex(SystemExit, 'downloads/setup.txt'):
            build.build()
        (self.src / 'downloads').mkdir()
        (self.src / 'downloads/setup.txt').write_text('fixture download')
        build.build()
        self.assertTrue((self.dist / 'assets/setup/imager-device.png').is_file())

    def test_process_exit_during_swap_keeps_recoverable_preview(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            destination, output, backup = base/'dist', base/'next', base/'.guide-previous'
            destination.mkdir(); output.mkdir()
            (destination/'keep.txt').write_text('previous preview')
            code = '''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import build
output, destination, backup = map(Path, sys.argv[2:])
original = Path.rename
def interrupted(path, target):
    if path == output: os._exit(19)
    return original(path, target)
Path.rename = interrupted
build.publish_staged(output, destination, backup)
'''
            result = subprocess.run([sys.executable, '-c', code, str(Path(build.__file__).parent),
                                     str(output), str(destination), str(backup)])
            self.assertEqual(result.returncode, 19)
            self.assertFalse(destination.exists())
            build.recover_preview(destination, backup)
            self.assertEqual((destination/'keep.txt').read_text(), 'previous preview')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src, self.dist = self.root / 'src', self.root / 'dist'
        self.src.mkdir()
        self.dist.mkdir()
        (self.dist / 'keep.txt').write_text('working preview')
        for name in build.CORE:
            (self.src / name).write_text('')
        (self.src / 'repeat-build.html').write_text(
            '<main id="content"><h1>Plate settings</h1><p>Estimated total: 0 h 0 min, 0 g.</p><footer></footer></main>')
        for name, value in [('guide-data.json', {'steps': []}), ('parts.json', []), ('print-data.json', [])]:
            (self.src / name).write_text(json.dumps(value))
        prices = self.root / 'prices.json'
        prices.write_text(json.dumps({'schema_version': 1, 'currency': 'USD', 'checked_date': '2026-10-01', 'items': []}))
        electrical = self.root / 'electrical.json'
        electrical.write_text(json.dumps({'power': [], 'signal': []}))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in [('ROOT', self.root), ('SRC', self.src), ('DIST', self.dist), ('INPUTS', []),
                            ('ELECTRICAL', electrical), ('PRICES', prices)]:
            self.stack.enter_context(patch.object(build, name, value))
        self.stack.enter_context(patch.object(build.packages, 'sources', return_value={'manifest': {'plates': []}}))
        self.stack.enter_context(patch.object(build.consistency, 'check', return_value={'errors': [], 'blockers': []}))
        self.writer = self.stack.enter_context(patch.object(build.packages, 'write'))

    def assert_preview_preserved(self):
        self.assertEqual((self.dist / 'keep.txt').read_text(), 'working preview')
        self.assertEqual(list(self.root.glob('.guide-stage-*')), [])

    def test_late_missing_link_preserves_previous_preview(self):
        (self.src / 'index.html').write_text('<img src="assets/missing.png">')
        with self.assertRaisesRegex(SystemExit, 'referenced but missing'):
            build.build()
        self.writer.assert_called_once()
        self.assert_preview_preserved()

    def test_package_failure_preserves_previous_preview(self):
        self.writer.side_effect = ValueError('CSV differs')
        with self.assertRaisesRegex(ValueError, 'CSV differs'):
            build.build()
        self.assert_preview_preserved()

    def test_success_replaces_previous_preview(self):
        build.build()
        self.assertFalse((self.dist / 'keep.txt').exists())
        self.assertTrue((self.dist / 'data.js').is_file())

    def test_invalid_plate_settings_preserves_previous_preview(self):
        (self.src / 'repeat-build.html').write_text('<main>Incomplete settings page. Estimated total: 0 h 0 min,</main>')
        with self.assertRaisesRegex(ValueError, 'Plate settings page'):
            build.build()
        self.assert_preview_preserved()

    def test_final_rename_failure_rolls_back_previous_preview(self):
        output = self.root / 'ready'
        output.mkdir()
        backup = self.root / 'backup'
        rename = Path.rename
        def fail_final(path, target):
            if path == output:
                raise OSError('simulated final rename failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_final), self.assertRaisesRegex(OSError, 'final rename failure'):
            build.publish_staged(output, self.dist, backup)
        self.assertEqual((self.dist / 'keep.txt').read_text(), 'working preview')
        self.assertFalse(backup.exists())

class PackageDemandTests(unittest.TestCase):
    def test_csv_rows_must_match_each_selected_part_not_only_total(self):
        import packages
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stls = root / 'stl'
            stls.mkdir()
            (stls / 'A.stl').write_bytes(b'fixture A')
            (stls / 'B.stl').write_bytes(b'fixture B')
            project = root / 'fixture.3mf'
            with zipfile.ZipFile(project, 'w'):
                pass
            csv = root / 'settings.csv'
            csv.write_text('part\nA\nA\n')
            selected = {'manifest': {'plates': [{'parts': {'A': 1, 'B': 1}}]},
                        'pla': project, 'petg': project, 'csv': csv}
            with patch.object(packages, 'stl_sources', return_value=[stls / 'A.stl', stls / 'B.stl']), self.assertRaisesRegex(ValueError, 'CSV quantities differ'):
                packages.write(root / 'out', selected)


if __name__ == '__main__':
    unittest.main()
