"""Behavioral gates for substrate conservation, rebasing and clear-air paths."""
import importlib.util,math,random,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('look_math',Path(__file__).resolve().parents[1]/'open_planet_lab/look_math.py')
look=importlib.util.module_from_spec(spec);spec.loader.exec_module(look)

class LookMathTests(unittest.TestCase):
    def test_substrate_weights_conserve_coverage(self):
        rng=random.Random(47)
        for _ in range(500):
            slope=rng.uniform(-1,1)
            forest,mountain,desert,moisture,patch=[rng.random() for _ in range(5)]
            weights=look.ground_weights(slope,forest,mountain,desert,moisture,patch)
            self.assertAlmostEqual(sum(weights),1.,places=12)
            self.assertTrue(all(0<=x<=1 for x in weights))
    def test_steep_surfaces_expose_rock(self):
        self.assertEqual(look.ground_weights(.4,1,0,0,1,.8),(0,0,0,1))
        self.assertEqual(look.ground_weights(1,1,0,0,0,.8),(0,1,0,0))
    def test_ground_scan_phase_survives_rebase(self):
        radius=6371000.
        absolute=(.123456789,-.923456789,.345678901)
        for tile in (1.3,1.8,2.,20.):
            expected=look.texture_phase(absolute,radius,tile)
            for anchor in ((.123,-.923,.346),(.124,-.924,.345)):
                phase=look.texture_phase(anchor,radius,tile)
                observed=tuple((phase[i]+(absolute[i]-anchor[i])*radius/tile)%1 for i in range(3))
                for a,b in zip(expected,observed):self.assertLess(min(abs(a-b),1-abs(a-b)),2e-9)
    def test_vertical_atmosphere_matches_analytic_column(self):
        radius=6371000.
        tau=look.optical_depth((0,0,1),(0,0,1),100000/radius)
        expected=1.75e-5*8000*(1-math.exp(-100000/8000))+.35*2e-5*1200*(1-math.exp(-100000/1200))
        self.assertLess(abs(tau/expected-1),.01)
    def test_grazing_path_tracks_dense_reference(self):
        radius=6371000.
        origin=(-.3,0,1.0002)
        fast=look.optical_depth(origin,(1,0,0),.6)
        reference=look.optical_depth(origin,(1,0,0),.6,samples=4096)
        self.assertLess(abs(fast/reference-1),.02)
    def test_clipping_empty_and_vacuum(self):
        self.assertEqual(look.optical_depth((0,0,1.1),(0,0,1),1),0)
        self.assertEqual(look.optical_depth((0,0,1),(1,0,0),0),0)
        self.assertEqual(look.optical_depth((0,0,1),(0,0,1),1,air=0,aerosol=0),0)
    def test_optical_depth_reversible_on_same_clear_air_segment(self):
        a=(-.1,0,1.001);b=(.1,0,1.001)
        forward=look.optical_depth(a,(1,0,0),.2)
        backward=look.optical_depth(b,(-1,0,0),.2)
        self.assertAlmostEqual(forward,backward,places=10)

if __name__=='__main__':unittest.main()
