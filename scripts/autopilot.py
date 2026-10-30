"""Minimap-following autopilot for unattended PGR4 race tests.

Captures the pgr4recomp window (PrintWindow, works while covered), finds the route line in the rotating HUD
minimap (white core, red edges; the car arrow always points up) and writes steering/throttle to the live pad
command file (work/pad_cmd.txt, see src/scripted_input.h). Commands hold for 250 ms, so the car coasts if this
script stops. Window client size must be 960x540 (scripts/dev/run.ps1).

Steering: follow the route line outward from the arrow tip (breadth-first over the line mask) and steer at the
point ~30 px along it. Speed: read the HUD MPH digits (templates in scripts/speed_digits.json, built by
build_speed_templates.py) and hold a target speed that drops in bends. Stuck at <= 3 mph: three-point turn.
Stops when the speed readout is gone for 5 s (race over / paused).

usage: python autopilot.py [seconds=600] [max_throttle=0.6]
       python autopilot.py --debug      (one frame: prints the trace, writes work/map_debug.ppm)
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD = os.path.join(ROOT, 'work', 'pad_cmd.txt')
W, H = 960, 540
ARROW_X, ARROW_Y = 104, 407          # car arrow tip in the minimap (960x540 client)

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.SetProcessDPIAware()


def find_window():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value.startswith('pgr4recomp ['):
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD),
                ('biBitCount', wt.WORD), ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD),
                ('biClrImportant', wt.DWORD)]


def capture(hwnd):
    """Client area as BGRA bytes, top-down."""
    hdc_win = user32.GetDC(hwnd)
    hdc = gdi32.CreateCompatibleDC(hdc_win)
    bmp = gdi32.CreateCompatibleBitmap(hdc_win, W, H)
    gdi32.SelectObject(hdc, bmp)
    user32.PrintWindow(hwnd, hdc, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(W * H * 4)
    gdi32.GetDIBits(hdc, bmp, 0, H, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(hwnd, hdc_win)
    return buf.raw


SPEED_BOX = (790, 476, 832, 500)  # x0, y0, x1, y1 of the MPH digits
DIGIT_X = (818, 807, 796)         # units, tens, hundreds cell left edges (11x16 cells at y 480)
DIGIT_Y, DIGIT_W, DIGIT_H = 480, 11, 16
try:
    with open(os.path.join(ROOT, 'scripts', 'speed_digits.json')) as f:
        TEMPLATES = {int(k): v for k, v in json.load(f).items()}
except OSError:
    TEMPLATES = {}


def read_speed(px):
    """MPH from the HUD readout, or None if a digit does not match any template."""
    value, scale = 0, 1
    for cx in DIGIT_X:
        bits = ''.join('1' if min(px[((DIGIT_Y + y) * W + cx + x) * 4 + c] for c in range(3)) > 150 else '0'
                       for y in range(DIGIT_H) for x in range(DIGIT_W))
        if bits.count('1') < 10:
            break  # no more digits to the left
        digit, dist = min(((d, sum(a != b for a, b in zip(bits, t))) for d, t in TEMPLATES.items()),
                          key=lambda e: e[1], default=(None, 999))
        if digit is None or dist > 45:
            return None
        value += digit * scale
        scale *= 10
    return value


def save_speed_strip(crops, path):
    """Stack speed-readout crops vertically into one binary PPM for template building."""
    x0, y0, x1, y1 = SPEED_BOX
    w, h = x1 - x0, y1 - y0
    with open(path, 'wb') as f:
        f.write(f'P6 {w} {h * len(crops)} 255\n'.encode())
        for px in crops:
            for y in range(y0, y1):
                row = px[(y * W + x0) * 4:(y * W + x1) * 4]
                f.write(bytes(v for i in range(0, len(row), 4) for v in (row[i + 2], row[i + 1], row[i])))


MAP_BOX = (40, 330, 170, 460)   # minimap search area (x0, y0, x1, y1)


def trace_route(px):
    """Follow the route line from the arrow tip along the minimap.

    Returns {path_len: (dx, dy)} = mean offset from the arrow tip of line pixels at that geodesic distance,
    for a few distances, or {} if the line was not found. dy < 0 is ahead (the map rotates; arrow points up).
    """
    x0, y0, x1, y1 = MAP_BOX
    w, h = x1 - x0, y1 - y0
    red = bytearray(w * h)
    bright = bytearray(w * h)
    for y in range(h):
        row = ((y0 + y) * W + x0) * 4
        for x in range(w):
            i = row + x * 4
            b, g, r = px[i], px[i + 1], px[i + 2]
            if r > 120 and g < 90 and b < 90 and r > 2 * g:
                red[y * w + x] = 1
            elif r > 170 and g > 170 and b > 170:
                bright[y * w + x] = 1
    # Line = red edge pixels, plus white core pixels that have red within 3 px on the same row.
    line = bytearray(red)
    for y in range(h):
        for x in range(3, w - 3):
            if bright[y * w + x] and any(red[y * w + x + d] for d in (-3, -2, -1, 1, 2, 3)):
                line[y * w + x] = 1
    # Seeds: line pixels ahead of the arrow tip, up to 30 rows (opponent dots can cover the first part).
    # Seed distance = rows ahead; the arrow itself is orange, not part of the mask.
    ax, ay = ARROW_X - x0, ARROW_Y - y0
    dist = {}
    seeds = sorted(((ay - y, x, y) for y in range(ay - 30, ay - 3) for x in range(ax - 10, ax + 11)
                    if 0 <= x < w and 0 <= y < h and line[y * w + x]))
    if not seeds:
        return {}
    first = seeds[0][0]
    frontier = [(x, y) for d, x, y in seeds if d <= first + 2]   # nearest seed rows only
    for x, y in frontier:
        dist[(x, y)] = ay - y
    # Breadth-first along the mask, bridging gaps up to 2 px; early steps may not head back past the arrow.
    while frontier:
        nxt = []
        for (x, y) in frontier:
            d = dist[(x, y)] + 1
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (x + dx, y + dy)
                    if (0 <= q[0] < w and 0 <= q[1] < h and q not in dist and line[q[1] * w + q[0]]
                            and (d > 25 or q[1] < ay - 2)):
                        dist[q] = d
                        nxt.append(q)
        frontier = nxt
    out = {}
    for L in (15, 30, 45):
        pts = [(x, y) for (x, y), d in dist.items() if L - 3 <= d <= L + 3]
        if pts:
            out[L] = (sum(p[0] for p in pts) / len(pts) - ax, sum(p[1] for p in pts) / len(pts) - ay)
    return out


def send(text):
    # Plain overwrite: an atomic rename fails while the game has the file open for reading.
    for _ in range(5):
        try:
            with open(CMD, 'w') as f:
                f.write(text)
            return
        except PermissionError:
            time.sleep(0.01)


def debug_frame(hwnd):
    """Save work/map_debug.ppm: the minimap box at 3x, mask pixels tinted (red edge=green, core=cyan)."""
    px = capture(hwnd)
    print('route', trace_route(px), 'speed', read_speed(px))
    x0, y0, x1, y1 = MAP_BOX
    s = 3
    with open(os.path.join(ROOT, 'work', 'map_debug.ppm'), 'wb') as f:
        f.write(f'P6 {(x1 - x0) * s} {(y1 - y0) * s} 255\n'.encode())
        for y in range(y0, y1):
            row = bytearray()
            for x in range(x0, x1):
                i = (y * W + x) * 4
                b, g, r = px[i], px[i + 1], px[i + 2]
                if r > 140 and g < 70 and b < 70:
                    c = (0, 255, 0)
                elif r > 190 and g > 190 and b > 190:
                    c = (0, 255, 255)
                elif (x, y) == (ARROW_X, ARROW_Y):
                    c = (255, 0, 255)
                else:
                    c = (r, g, b)
                row += bytes(c) * s
            f.write(bytes(row) * s)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        debug_frame(find_window())
        return
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    max_thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
    hwnd = find_window()
    if not hwnd:
        sys.exit('pgr4recomp window not found')
    t0 = time.time()
    last_log = 0
    still_since, reverse_until, reverse_steer, last_thr = None, 0.0, 0.0, 0.0
    no_hud_since = None
    crops, last_crop = [], 0.0
    while time.time() - t0 < seconds:
        if not user32.IsWindow(hwnd):
            print('window gone')
            break
        px = capture(hwnd)
        now = time.time() - t0
        if now - last_crop >= 0.5 and len(crops) < 200:
            crops.append(px)
            last_crop = now
        route = trace_route(px)
        speed = read_speed(px)
        # The speed readout vanishes when the race ends (or pauses): stop before stick input moves menus.
        if speed is None:
            no_hud_since = no_hud_since or now
            if now - no_hud_since > 5:
                print(f't={now:6.1f} no speed HUD for 5 s -> race over or paused, stopping', flush=True)
                break
        else:
            no_hud_since = None
        # Heading to the route point 30 px along the line (fallback 15 px): 0 = straight ahead.
        tgt = route.get(30) or route.get(15)
        angle = math.atan2(tgt[0], -tgt[1]) if tgt else 0.0
        far = route.get(45)
        far_angle = math.atan2(far[0], -far[1]) if far else angle
        # Stuck: barely moving although we asked for throttle.
        if speed is not None and speed <= 3 and now >= reverse_until and last_thr >= 0.2:
            still_since = still_since or now
        else:
            still_since = None
        if now < reverse_until:
            steer, thr, brake = reverse_steer, 0.0, 1.0   # LT at a standstill = reverse
        elif still_since is not None and now - still_since > 1.2:
            # Three-point turn: reverse with opposite lock so the nose swings toward the route.
            reverse_until = now + 2.2
            reverse_steer = -1.0 if angle > 0 else 1.0
            print(f't={now:6.1f} stuck (angle {math.degrees(angle):+.0f}) -> reversing, steer {reverse_steer:+.0f}',
                  flush=True)
            still_since = None
            steer, thr, brake = reverse_steer, 0.0, 1.0
        elif not tgt:
            steer, thr, brake = 0.0, 0.25, 0.0            # line not found: creep straight
        else:
            steer = max(-1.0, min(1.0, angle / math.radians(35)))
            sharp = min(1.0, max(abs(angle), abs(far_angle)) / math.radians(70))
            target = 75 - 50 * sharp                      # mph: 75 on straights, 25 in hairpins
            if speed is None:
                thr, brake = max(0.15, max_thr * (1 - sharp)), 0.0
            else:
                thr = max(0.0, min(max_thr, 0.08 * (target - speed) + 0.2))
                brake = min(1.0, 0.1 * (speed - target - 5)) if speed > target + 5 else 0.0
        last_thr = thr
        cmd = f'0:LX={steer:.2f}:250,0:RT={thr:.2f}:250'
        if brake:
            cmd += f',0:LT={brake:.2f}:250'
        send(cmd)
        if now - last_log >= 1:
            print(f't={now:6.1f} mph={speed} angle={math.degrees(angle):+4.0f} far={math.degrees(far_angle):+4.0f} '
                  f'steer={steer:+.2f} thr={thr:.2f} brake={brake:.2f}', flush=True)
            last_log = now
        time.sleep(0.08)
    send('0:RT=0:100')
    if crops:
        save_speed_strip(crops, os.path.join(ROOT, 'work', 'speed_strip.ppm'))


if __name__ == '__main__':
    main()
