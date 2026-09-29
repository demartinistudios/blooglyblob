"""Optional authoring checks: component detail must preserve mounting identity."""
import copy
import gzip
import json
import unittest

import numpy as np

from guide_component_models import replace_envelopes
from source import checked_source


class ComponentModelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=checked_source()[0]
        with gzip.open(path,'rt') as stream:source=json.load(stream)
        cls.rows=[]
        for r in source:
            pid=r.get('part_id')
            if 'FS90MG' in r['path']:pid='E01'
            if 'Capacitor' in r['path']:pid='E08'
            if pid not in ('E01','E08','E09','E14','E17'):continue
            t=np.array(r['transform']).reshape(4,4)
            vertices=np.array(r['vertices_cm']).reshape(-1,3)
            vertices=(vertices@t[:3,:3].T+t[:3,3])*10
            cls.rows.append(dict(id=pid,root=r['path'],occ=0,source=r,
                                 v=vertices,f=np.array(r['faces']).reshape(-1,3)))

    def test_preserves_source_identity_and_never_mutates_authority(self):
        before=copy.deepcopy(self.rows)
        detailed=replace_envelopes(self.rows)
        for a,b in zip(self.rows,before):
            self.assertTrue(np.array_equal(a['v'],b['v']))
            self.assertTrue(np.array_equal(a['f'],b['f']))
            self.assertEqual(a['source'],b['source'])
        self.assertEqual({r['root'] for r in detailed},{r['root'] for r in before})
        self.assertTrue(all(r.get('component_detail') for r in detailed))
        self.assertEqual(len(replace_envelopes(detailed)),len(detailed))

    def test_button_terminals_are_in_total_height_and_nut_bears_on_plate(self):
        rows=replace_envelopes([r for r in self.rows if r['id']=='E17'])
        all_v=np.concatenate([r['v'] for r in rows])
        self.assertTrue(np.allclose([all_v[:,2].min(),all_v[:,2].max()],[-26.4,3]))
        nut=next(r for r in rows if r['component_detail']=='button retaining nut')
        self.assertAlmostEqual(nut['v'][:,2].max(),-4)
        tabs=[r for r in rows if r['component_detail']=='button terminal']
        self.assertEqual(len(tabs),4)
        self.assertTrue(all(np.isclose(r['v'][:,2].max(),-20.9) for r in tabs))

    def test_button_shaft_flats_clear_the_actual_plate_opening(self):
        rows=replace_envelopes([r for r in self.rows if r['id']=='E17'])
        for row in rows:
            if row['component_detail'] in ('button barrel','button thread'):
                self.assertLessEqual(np.ptp(row['v'][:,1]),14.89+1e-8)
                self.assertLessEqual(np.ptp(row['v'][:,0]),15.6+1e-8)

    def test_header_has_two_rows_of_twenty_pins_at_standard_pitch(self):
        rows=replace_envelopes([r for r in self.rows if r['id']=='E09'])
        pins=[r['v'].mean(0) for r in rows if r['component_detail']=='GPIO pin']
        self.assertEqual(len(pins),40)
        self.assertEqual(len(np.unique(np.round(np.array(pins)[:,0],5))),2)
        self.assertTrue(np.allclose(np.diff(np.unique(np.round(np.array(pins)[:,1],5))),2.54))

    def test_each_servo_keeps_every_source_face_at_its_mounting_position(self):
        for original in [r for r in self.rows if r['id']=='E01']:
            rows=replace_envelopes([original])
            source_rows=[r for r in rows if r['component_detail'] in ('servo case and ears','servo output spline')]
            self.assertEqual(sum(len(r['f']) for r in source_rows),len(original['f']))
            for r in source_rows:
                distances=np.linalg.norm(r['v'][:,None,:]-original['v'][None,:,:],axis=2)
                self.assertLess(distances.min(axis=1).max(),1e-10)

    def test_pi_recognition_features_follow_the_board_translation(self):
        original=next(r for r in self.rows if r['id']=='E09' and 'PCB' in r['source']['path'])
        translated=dict(original,v=original['v']+[0,7,0])
        a=replace_envelopes([original]);b=replace_envelopes([translated])
        self.assertEqual(len(a),len(b))
        for before,after in zip(a,b):self.assertTrue(np.allclose(after['v'],before['v']+[0,7,0]))

    def test_rotated_capacitor_details_follow_accepted_body_axis(self):
        for original in [r for r in self.rows if r['id']=='E08']:
            rows=replace_envelopes([original])
            sleeve=next(r for r in rows if r['component_detail']=='sleeve')
            self.assertTrue(np.allclose(sleeve['v'].mean(0),(original['v'].min(0)+original['v'].max(0))/2))
            self.assertEqual(np.argmax(np.ptp(sleeve['v'],axis=0)),np.argmax(np.ptp(original['v'],axis=0)))

    def test_changed_button_envelope_requires_review(self):
        row=copy.deepcopy(next(r for r in self.rows if r['id']=='E17'))
        row['v'][:,2]+=1
        with self.assertRaises(ValueError):replace_envelopes([row])


if __name__=='__main__':unittest.main()
