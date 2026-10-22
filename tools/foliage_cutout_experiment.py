# SPDX-License-Identifier: GPL-3.0-or-later
"""Benchmark adapter for the production alpha-support mesh builder."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from open_planet_lab.foliage import capture_mesh


def cutout(ob,resolution=64):
    mesh=capture_mesh(ob,resolution);ob.data=mesh
    return mesh
