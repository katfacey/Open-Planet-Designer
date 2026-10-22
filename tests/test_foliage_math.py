import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('foliage_math',Path(__file__).resolve().parents[1]/'open_planet_lab/foliage_math.py')
fm=importlib.util.module_from_spec(spec);spec.loader.exec_module(fm)


class AlphaSupportTests(unittest.TestCase):
    def check_mask(self,mask):
        loops=fm.support_loops(mask)
        self.assertEqual(sum(fm.area(loop) for loop in loops),sum(sum(row) for row in mask))
        for loop in loops:self.assertEqual(fm.area(loop),fm.area(fm.simplify_loop(loop)))
        return loops

    def test_empty(self):
        self.assertEqual(self.check_mask([]),[])
        self.assertEqual(self.check_mask([[False]*3 for _ in range(3)]),[])

    def test_holes_remain_open(self):
        loops=self.check_mask([[1,1,1],[1,0,1],[1,1,1]])
        self.assertEqual(sorted(fm.area(loop) for loop in loops),[-1.,9.])

    def test_diagonal_islands_remain_separate(self):
        loops=self.check_mask([[1,0],[0,1]])
        self.assertEqual(len(loops),2)

    def test_thin_branch_and_disconnected_leaves(self):
        self.check_mask([[1,0,1,0,1],[1,1,1,0,0],[0,0,1,1,1],[1,0,1,0,0]])

    def test_all_small_masks_preserve_area(self):
        for bits in range(512):
            self.check_mask([[bool(bits & (1<<(y*3+x))) for x in range(3)] for y in range(3)])


if __name__=='__main__':unittest.main()
