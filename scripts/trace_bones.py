"""Decode DRAWDBG trace lines (PGR4 skinned crowd draw) and flag implausible bone matrices.

Usage: python scripts/trace_bones.py work/<log> [max_rows]
Each palette entry is 3 rows x half4 in 8in32 byte order. A bone row's first three components are a
scaled rotation (|v| <= ~2) and the fourth a translation; flags NaN/Inf, huge values and all-zero entries.
"""
import re
import struct
import sys

import numpy as np

pat = re.compile(r'\[(\d+)\]([0-9A-F]{48})')
bad = 0
total = 0
examples = []
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    if 'DRAWDBG trace' not in line:
        continue
    t = line[12:24]
    draw = re.search(r'trace #(\d+)', line).group(1)
    c55 = re.search(r'c55=\(([^)]*)\)', line).group(1)
    for idx, hx in pat.findall(line):
        raw = bytes.fromhex(hx)
        # 8in32: swap bytes within each dword, then read big-endian... -> little-endian halves pairwise.
        sw = b''.join(raw[i:i + 4][::-1] for i in range(0, 24, 4))
        h = np.frombuffer(sw, dtype='<f2').astype(np.float32)
        # Within a dword the two halves are (y, x) after the swap; order does not matter for range checks.
        total += 1
        reason = None
        if not np.all(np.isfinite(h)):
            reason = 'nan/inf'
        elif np.max(np.abs(h)) > 50:
            reason = f'max {np.max(np.abs(h)):.3g}'
        elif not np.any(h):
            reason = 'zero'
        if reason:
            bad += 1
            if len(examples) < int(sys.argv[2] if len(sys.argv) > 2 else 30):
                examples.append(f'{t} #{draw} c55=({c55}) [{idx}] {reason}: {np.round(h, 3).tolist()}')
print(f'{bad}/{total} suspicious palette entries')
print('\n'.join(examples))
