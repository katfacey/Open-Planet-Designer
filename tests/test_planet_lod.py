import importlib.util
from pathlib import Path
import unittest
from collections import Counter

spec=importlib.util.spec_from_file_location('lod_mesh',Path(__file__).resolve().parents[1]/'open_planet_lab'/'lod_mesh.py')
lod_mesh=importlib.util.module_from_spec(spec);spec.loader.exec_module(lod_mesh)

class LODMeshTests(unittest.TestCase):
    def check_mesh(self,camera,budget=12000,**kw):
        vs,fs,stats=lod_mesh.build(camera,budget=budget,**kw)
        self.assertLessEqual(len(fs),budget);self.assertGreater(len(fs),24)
        edges=Counter(tuple(sorted(e)) for f in fs for e in zip(f,f[1:]+f[:1]))
        self.assertTrue(all(n==2 for n in edges.values()),'Every edge must have exactly two incident triangles')
        for a,b,c in fs:
            v0=vs[a];v1=vs[b];v2=vs[c]
            u=[v1[i]-v0[i] for i in range(3)];v=[v2[i]-v0[i] for i in range(3)]
            cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            self.assertGreater(sum(cross[i]*v0[i] for i in range(3)),0.)
        return stats
    def test_orbit(self):self.check_mesh((0,-4,1))
    def test_near_surface(self):self.check_mesh((.01,-1.0001,.01),max_depth=18)
    def test_cube_face_seam(self):self.check_mesh((.708,-.708,.0001),max_depth=18)
    def test_cube_corner(self):self.check_mesh((.578,.578,.578),max_depth=18)
    def test_deterministic_and_near_refinement(self):
        far=lod_mesh.build((0,-8,0),budget=12000);near=lod_mesh.build((0,-1.0001,0),budget=12000)
        self.assertGreater(near[2]['deepest'],far[2]['deepest'])
        self.assertEqual(near,lod_mesh.build((0,-1.0001,0),budget=12000))
    def test_orthographic(self):self.check_mesh((0,-4,0),ortho_size=3.,focal=720.)
    def test_budget_is_used_without_breaking_closed_surface(self):
        for budget in (2048,12000,12003):
            vs,fs,stats=lod_mesh.build((.01,-1.0001,.01),budget=budget,max_depth=20)
            self.assertLessEqual(len(fs),budget)
            self.assertLess(budget-len(fs),16)
            self.assertEqual(len(fs),2*len(vs)-4)
if __name__=='__main__':unittest.main()
