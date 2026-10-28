"""Build MPH digit templates from work/speed_strip.ppm (autopilot crops) using hand-read labels.

usage: build_speed_templates.py frame=digit ...   e.g. 0=0 4=1 13=2   -> scripts/speed_digits.json
Cell = 11x16 px at crop x 28, y 4 (units digit; crop origin = autopilot SPEED_BOX).
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(ROOT, 'work', 'speed_strip.ppm'), 'rb').read()
px = d[d.index(b'255\n') + 4:]
W, H, CX, CY, CW, CH = 42, 24, 28, 4, 11, 16
out_path = os.path.join(ROOT, 'scripts', 'speed_digits.json')
tpl = json.load(open(out_path)) if os.path.exists(out_path) else {}
for arg in sys.argv[1:]:
    k, digit = map(int, arg.split('='))
    bits = ''.join('1' if min(px[3 * ((k * H + CY + y) * W + CX + x) + c] for c in range(3)) > 150 else '0'
                   for y in range(CH) for x in range(CW))
    tpl[str(digit)] = bits
json.dump(tpl, open(out_path, 'w'), indent=0, sort_keys=True)
print('templates:', sorted(tpl))
