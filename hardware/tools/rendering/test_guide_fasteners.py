"""Optional authoring tests; run with the NumPy/trimesh rendering environment."""
import unittest

import numpy as np
import trimesh

from guide_fasteners import axis_basis, hex_nut, screw, washer


class ScrewGeometryTests(unittest.TestCase):
    def test_nominal_shaft_length_and_head_envelopes_in_any_axis(self):
        for d,diameter,height in ((2,3.8,2),(3,5.5,3)):
            for axis in ([0,0,1],[0,1,0],[0,-1,0],[1,0,0]):
                origin=np.array([7.,-4.,12.]);basis=axis_basis(axis)
                rows=screw(d,8,origin,axis)
                shaft=(rows[0]['v']-origin)@basis
                head=(rows[1]['v']-origin)@basis
                self.assertAlmostEqual(shaft[:,2].min(),0)
                self.assertAlmostEqual(shaft[:,2].max(),8)
                self.assertLessEqual(np.linalg.norm(shaft[:,:2],axis=1).max(),d/2+1e-10)
                self.assertAlmostEqual(head[:,2].min(),-height)
                self.assertAlmostEqual(head[:,2].max(),0)
                self.assertLessEqual(np.linalg.norm(head[:,:2],axis=1).max(),diameter/2+1e-10)

    def test_thread_is_helical_and_has_the_nominal_pitch(self):
        for d,pitch in ((2,.4),(3,.5)):
            shaft=screw(d,8,[0,0,0],[0,0,1])[0]['v'][:-2].reshape(-1,72,3)
            middle=shaft[40]
            radii=np.linalg.norm(middle[:,:2],axis=1)
            self.assertGreater(np.ptp(radii),.2*pitch)
            # One revolution of axial travel returns the same radial profile.
            self.assertTrue(np.allclose(np.linalg.norm(shaft[48,:,:2],axis=1),radii))
            self.assertAlmostEqual(shaft[48,0,2]-shaft[40,0,2],pitch)
            # Half a pitch rotates the crest/root profile by half a turn.
            self.assertTrue(np.allclose(np.linalg.norm(shaft[44,:,:2],axis=1),np.roll(radii,36)))

    def test_head_and_shaft_are_closed_and_socket_has_real_depth(self):
        for row in screw(3,12,[0,0,0],[0,0,1])[:2]:
            mesh=trimesh.Trimesh(row['v'],row['f'],process=False)
            self.assertTrue(mesh.is_watertight)
            self.assertTrue(mesh.is_winding_consistent)
            self.assertGreater(mesh.volume,0)
        rows=screw(3,12,[0,0,0],[0,0,1])
        floor=rows[2]['v'][:,2]
        self.assertGreater(floor.min(),-3)
        self.assertLess(floor.max(),0)

    def test_button_head_uses_low_rounded_envelope(self):
        row=screw(2,8,[0,0,0],[0,0,1],head='button')[1]
        self.assertAlmostEqual(row['v'][:,2].min(),-1.1)
        self.assertLessEqual(np.linalg.norm(row['v'][:,:2],axis=1).max(),1.9+1e-10)
        self.assertTrue(trimesh.Trimesh(row['v'],row['f'],process=False).is_watertight)


class CountersunkTests(unittest.TestCase):
    def test_countersunk_head_is_flush_closed_and_inside_overall_length(self):
        rows=screw(3,10,[0,0,0],[0,0,1],head='countersunk')
        head=rows[1]['v']
        self.assertAlmostEqual(head[:,2].min(),0)
        self.assertAlmostEqual(head[:,2].max(),1.5)
        self.assertLessEqual(np.linalg.norm(head[:,:2],axis=1).max(),3+1e-10)
        self.assertAlmostEqual(rows[0]['v'][:,2].max(),10)
        mesh=trimesh.Trimesh(rows[1]['v'],rows[1]['f'],process=False)
        self.assertTrue(mesh.is_watertight)
        self.assertTrue(mesh.is_winding_consistent)
        self.assertGreater(mesh.volume,0)
        with self.assertRaises(ValueError):
            screw(2,8,[0,0,0],[0,0,1],head='countersunk')


class NutAndWasherTests(unittest.TestCase):
    def test_nut_flats_phase_size_and_thickness_are_preserved(self):
        for d,af,thickness in ((2,4,1.6),(3,5.5,2.4)):
            for axis in ([0,0,1],[0,0,-1],[0,1,0],[0,-1,0]):
                row=hex_nut(d,[0,0,0],axis)
                vertices=row['v']@axis_basis(axis)
                self.assertAlmostEqual(vertices[:,0].max(),af/2)
                self.assertAlmostEqual(vertices[:,0].min(),-af/2)
                self.assertAlmostEqual(vertices[:,2].max()-vertices[:,2].min(),thickness)
                self.assertGreaterEqual(np.linalg.norm(vertices[:,:2],axis=1).min(),d/2-1e-10)
                self.assertTrue(trimesh.Trimesh(row['v'],row['f'],process=False).is_watertight)
                # World X is never rotated away from the required pocket flat.
                self.assertAlmostEqual(row['v'][:,0].max(),af/2)

    def test_supplied_retaining_nut_overrides(self):
        row=hex_nut(8,[0,0,0],[0,1,0],af=11,thickness=1.8,bore=7.94)
        self.assertAlmostEqual(row['v'][:,0].max(),5.5)
        self.assertAlmostEqual(np.ptp(row['v'][:,1]),1.8)

    def test_washer_is_annular_with_insulator_color_override(self):
        row=washer([0,0,0],[0,0,1],2.5,1.1,.5,color=(230,224,200))
        self.assertEqual(row['guide_color'],(230,224,200))
        self.assertGreaterEqual(np.linalg.norm(row['v'][:,:2],axis=1).min(),1.1-1e-10)
        self.assertTrue(trimesh.Trimesh(row['v'],row['f'],process=False).is_watertight)

    def test_invalid_dimensions_and_axes_fail(self):
        with self.assertRaises(ValueError):screw(4,10,[0,0,0],[0,0,1])
        with self.assertRaises(ValueError):screw(3,0,[0,0,0],[0,0,1])
        with self.assertRaises(ValueError):hex_nut(3,[0,0,0],[0,0,1],bore=6)
        with self.assertRaises(ValueError):washer([0,0,0],[0,0,1],1,2,.5)
        with self.assertRaises(ValueError):axis_basis([0,0,0])


if __name__=='__main__':
    unittest.main()
