"""Prepare bounded alpha-cutout and color-padding experiments from CC0 atlases."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/foliage-parity/dilated';OUT.mkdir(exist_ok=True,parents=True)
for path in (ROOT/'open_planet_lab/assets/canopy').glob('*_color.png'):
    image=np.asarray(Image.open(path).convert('RGBA')).copy()
    alpha=image[:,:,3].copy();valid=alpha>0
    rgb=image[:,:,:3].copy()
    for _ in range(32):
        accum=np.zeros_like(rgb,dtype=np.float32);count=np.zeros(valid.shape,dtype=np.float32)
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
            shifted=np.roll(valid,(dy,dx),(0,1));values=np.roll(rgb,(dy,dx),(0,1))
            if dy==-1:shifted[-1]=False
            if dy==1:shifted[0]=False
            if dx==-1:shifted[:,-1]=False
            if dx==1:shifted[:,0]=False
            accum+=values*shifted[:,:,None];count+=shifted
        fill=(~valid)&(count>0)
        rgb[fill]=(accum[fill]/count[fill,None]).astype(np.uint8);valid|=fill
    image[:,:,:3]=rgb
    assert np.array_equal(image[:,:,3],alpha)
    Image.fromarray(image).save(OUT/path.name)
print('Prepared atlas RGB gutters; original alpha unchanged')
