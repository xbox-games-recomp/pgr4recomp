"""Dump XEX2 header facts: xexinfo.py <file.xex>"""
import struct, sys

d = open(sys.argv[1], 'rb').read()
be32 = lambda o: struct.unpack_from('>I', d, o)[0]
be16 = lambda o: struct.unpack_from('>H', d, o)[0]

assert d[:4] == b'XEX2', d[:4]
flags, pe_off, _, sec_off, nopt = struct.unpack_from('>5I', d, 4)
print(f'module_flags={flags:#x} pe_data_offset={pe_off:#x} security_info={sec_off:#x} opt_headers={nopt}')
opt = {}
for i in range(nopt):
    k, v = struct.unpack_from('>II', d, 0x18 + i * 8)
    opt[k] = v
    print(f'  key {k:08x} = {v:#x}')

def blob(k):
    v = opt[k]
    if k & 0xFF == 0xFF:
        return d[v + 4:v + be32(v)]
    return d[v:v + (k & 0xFF) * 4]

if 0x10100 in opt: print(f'entry_point={opt[0x10100]:#x}')
if 0x10201 in opt: print(f'image_base={opt[0x10201]:#x}')
if 0x20200 in opt: print(f'default_stack={opt[0x20200]:#x}')
if 0x30000 in opt: print(f'system_flags={opt[0x30000]:#x}')
if 0x183FF in opt: print('original_pe_name=', blob(0x183FF).split(b'\0')[0].decode())
if 0x40006 in opt:
    b = blob(0x40006)
    media, ver, basever, tid = struct.unpack_from('>4I', b, 0)
    print(f'exec_info media_id={media:#x} version={ver:#x} base_version={basever:#x} title_id={tid:08x} '
          f'platform={b[16]} exe_type={b[17]} disc={b[18]}/{b[19]}')
if 0x3FF in opt:
    b = blob(0x3FF)
    enc, comp = struct.unpack_from('>HH', b, 0)
    print(f'file_format encryption={enc} compression={comp} (comp 1=basic 2=LZX; enc 1=AES)')
    if comp == 2:
        print(f'  lzx window_size={struct.unpack_from(">I", b, 4)[0]:#x}')
if 0x20104 in opt:
    print('tls_info slots/raw/data/rawsize =', [hex(x) for x in struct.unpack_from('>4I', blob(0x20104))])
if 0x200FF in opt:
    b = blob(0x200FF)
    print('static libraries:')
    for o in range(0, len(b), 16):
        name = b[o:o + 8].split(b'\0')[0].decode()
        maj, mnr, bld, qfe = struct.unpack_from('>4H', b, o + 8)
        print(f'  {name:10s} {maj}.{mnr}.{bld}.{qfe & 0xFF}')
if 0x103FF in opt:
    b = blob(0x103FF)
    strsz, nstr = struct.unpack_from('>II', b, 0)
    names = b[8:8 + strsz].split(b'\0')
    names = [n.decode() for n in names if n]
    o = 8 + strsz
    print('import libraries:')
    while o < len(b):
        size = struct.unpack_from('>I', b, o)[0]
        ver, minv = struct.unpack_from('>II', b, o + 28)
        nidx, cnt = struct.unpack_from('>HH', b, o + 36)
        v = lambda x: f'{x >> 28}.{(x >> 24) & 0xF}.{(x >> 8) & 0xFFFF}.{x & 0xFF}'
        print(f'  {names[nidx]:16s} v{v(ver)} (min {v(minv)}) records={cnt}')
        o += size
s = sec_off
hdr_size, img_size = be32(s), be32(s + 4)
print(f'security: image_size={img_size:#x} image_flags={be32(s + 0x10C):#x} load_address={be32(s + 0x110):#x} '
      f'region={be32(s + 0x178):#x} allowed_media={be32(s + 0x17C):#x} pages={be32(s + 0x180)}')
print('file size', hex(len(d)), 'pe data bytes', hex(len(d) - pe_off))
