"""Summarise frame pacing from a pgr4recomp log (frame_stats.cpp's 'PGR4 frames' / 'PGR4 hitch' lines).

usage: python hitch_stats.py <log> [skip_seconds=0] [seconds=0 (all)]
Counts from the first 'PGR4 frames' line with >= 2000 draws/frame (the race), skipping skip_seconds.
"""
import re
import sys
from datetime import datetime

log, skip, span = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0, \
    float(sys.argv[3]) if len(sys.argv) > 3 else 0
ts = lambda line: datetime.strptime(line[1:24], '%Y-%m-%d %H:%M:%S.%f')
lines = open(log, encoding='utf-8', errors='replace').read().splitlines()
start = None
for l in lines:
    m = re.search(r'PGR4 frames: .*per frame: (\d+) draws', l)
    if m and int(m.group(1)) >= 2000:
        start = ts(l)
        break
if start is None:
    sys.exit('no race found')
secs, fps, over, maxes, hitches = 0, [], 0, [], []
for l in lines:
    if 'PGR4 frames' not in l and 'PGR4 hitch' not in l:
        continue
    t = (ts(l) - start).total_seconds()
    if t < skip or (span and t > skip + span):
        continue
    m = re.search(r'PGR4 frames: ([\d.]+) fps, max ([\d.]+) ms, (\d+) over', l)
    if m:
        fps.append(float(m.group(1)))
        maxes.append(float(m.group(2)))
        over += int(m.group(3))
    m = re.search(r'PGR4 hitch swap #\d+: ([\d.]+) ms', l)
    if m:
        hitches.append(float(m.group(1)))
n = len(fps)
print(f'{n} s: mean {sum(fps) / n:.1f} fps, min second {min(fps):.1f} fps, '
      f'{over} frames over threshold ({over / n:.2f}/s), seconds with a hitch {sum(1 for x in maxes if x > 25)}, '
      f'worst {max(maxes):.1f} ms, >50 ms: {sum(1 for h in hitches if h > 50)}')
