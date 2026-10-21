"""Behavior checks for repeatable planetary habitat cells and terrain guides."""
import importlib.util,types,sys,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'open_planet_lab'
package=types.ModuleType('planet_pure_tests');package.__path__=[str(ROOT)];sys.modules['planet_pure_tests']=package
spec=importlib.util.spec_from_file_location('planet_pure_tests.ecology',ROOT/'ecology.py')
ecology=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ecology;spec.loader.exec_module(ecology)
lod_mesh=sys.modules['planet_pure_tests.lod_mesh']

class EcologyTests(unittest.TestCase):
    def test_stable_tree_identity_after_camera_motion(self):
        height=.0000035;center=lod_mesh.unit((.12,-.77,.63));reach=.000018
        first=list(ecology.tree_cells(center,height,reach,7))
        moved=lod_mesh.unit((center[0]+height*2,center[1],center[2]))
        second=list(ecology.tree_cells(moved,height,reach,7))
        a={v[1]:v for v in first};b={v[1]:v for v in second};common=a.keys()&b.keys()
        self.assertGreater(len(common),100)
        for key in common:self.assertEqual(a[key],b[key])
    def test_age_structure_and_physical_scales(self):
        kinds={};factors=[]
        for a in range(90):
            for b in range(90):
                kind,size=ecology.profile(a,b,1,7);kinds[kind]=kinds.get(kind,0)+1;factors.append(size)
        self.assertEqual(set(kinds),set(ecology.TREE_KINDS))
        self.assertGreater(kinds['SAPLING']+kinds['SAPLING_B'],1500)
        self.assertLess(max(factors),1.25);self.assertGreaterEqual(min(factors),.12)
    def test_integer_hash_shader_precision(self):
        import struct
        f32=lambda x:struct.unpack('f',struct.pack('f',x))[0]
        for a,b in ((0,0),(100000,3900000),(20003900,983722),(918,723)):
            h=((a%4093)*13+(b%4093)*17+3*107+7*31+9*109)%4093
            simulated=f32(f32(h*h)%4093)/4093
            self.assertEqual(ecology.cell_hash(a,b,3,7,9),simulated)
    def test_height_guide_refines_raised_landform(self):
        center=(0,-1,0)
        def guide(direction,span):
            distance=math.sqrt(sum((direction[i]-center[i])**2 for i in range(3)))
            return (1.01 if distance<.02 else 1.,.005 if distance<.03 else 0.)
        a=lod_mesh.build((0,-1.0101,0),budget=12000,max_depth=20)
        b=lod_mesh.build((0,-1.0101,0),budget=12000,max_depth=20,height_guide=guide)
        self.assertGreater(b[2]['deepest'],a[2]['deepest'])
        self.assertLessEqual(len(b[1]),12000)

if __name__=='__main__':unittest.main()
