"""Live draw-skip probe for a running pgr4recomp started with REX_DRAW_DEBUG_FILE=work\\drawdbg.txt.

Usage: python scripts/skip_probe.py <tag> <shots> [skip_vs hashes comma-separated | raw:<lines;...>] [skip_ps ...]
Writes the debug file, waits for the reload, snapshots <shots> frames with snap.ps1 and runs the same
sky-artifact count as sky_probe.py. Prints "<tag>: k/n".
"""
import glob
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
tag, shots = sys.argv[1], int(sys.argv[2])
skip_vs = sys.argv[3] if len(sys.argv) > 3 else ''
skip_ps = sys.argv[4] if len(sys.argv) > 4 else ''
with open(os.path.join(WORK, 'drawdbg.txt'), 'w') as f:
    if skip_vs.startswith('raw:'):  # raw:<debug file lines separated by ;>
        f.write(skip_vs[4:].replace(';', '\n') + '\n')
    else:
        f.write(f'skip_vs = {skip_vs}\nskip_ps = {skip_ps}\n')
time.sleep(1.5)
for old in glob.glob(os.path.join(WORK, f'{tag}_k_*.png')):
    os.remove(old)
ps = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
times = []
for n in range(shots):
    times.append(time.strftime('%H:%M:%S') + f'.{int(time.time() * 1000) % 1000:03d}')
    subprocess.run([ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    os.path.join(ROOT, 'scripts', 'snap.ps1'), os.path.join(WORK, f'{tag}_k_{n}.png')],
                   capture_output=True)
    time.sleep(0.3)
files = [os.path.join(WORK, f'{tag}_k_{n}.png') for n in range(shots)]
# Skip failed captures (1x1 while minimized); compare at a fixed size whatever the window size.
frames = [Image.open(f) for f in files if os.path.exists(f)]
frames = [im for im in frames if im.size[0] > 100]
imgs = np.stack([np.asarray(im.convert('L').resize((960, 540)), dtype=np.int16) for im in frames])
shots = len(frames)
h, w = imgs.shape[1:]
sky = imgs[:, : h // 3, w // 6: w * 5 // 6]
med = np.median(sky, axis=0)
hits = [i for i, s in enumerate(sky) if float((np.abs(s - med) > 40).mean()) > 0.003]
print(f'{tag}: {len(hits)}/{shots} {hits}')
with open(os.path.join(WORK, f'{tag}_times.txt'), 'w') as f:  # capture start time per shot, for log correlation
    f.write('\n'.join(f'{i} {t}{" HIT" if i in hits else ""}' for i, t in enumerate(times)))
