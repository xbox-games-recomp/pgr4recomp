"""Count sky-artifact frames in a series of start-line snapshots (static camera).

Usage: python -I scripts/sky_probe.py <glob>   e.g. "work/sky_def_*.png"
For each image, the top third (minus the HUD corners) is compared with the per-pixel median of the
series; a frame counts as an artifact when more than 0.3% of the region differs by > 40 levels.
"""
import glob
import sys

import numpy as np
from PIL import Image

files = sorted(glob.glob(sys.argv[1]), key=lambda f: int(f.rsplit('_', 1)[1].split('.')[0]))
imgs = np.stack([np.asarray(Image.open(f).convert('L'), dtype=np.int16) for f in files])
h, w = imgs.shape[1:]
sky = imgs[:, : h // 3, w // 6: w * 5 // 6]
med = np.median(sky, axis=0)
bad = 0
for f, s in zip(files, sky):
    frac = float((np.abs(s - med) > 40).mean())
    flag = frac > 0.003
    bad += flag
    print(f'{f}: {100 * frac:.2f}%{"  <-- artifact" if flag else ""}')
print(f'{bad}/{len(files)} frames with sky artifacts')
