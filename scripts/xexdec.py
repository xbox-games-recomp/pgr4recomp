"""Decrypt + basic-decompress a retail XEX2 to its PE image using openssl.
xexdec.py <in.xex> <out.pe> <openssl.exe>"""
import struct, subprocess, sys

RETAIL_KEY = bytes.fromhex('20B185A59D28FDC340583FBB0896BF91')

src, dst, openssl = sys.argv[1:4]
d = open(src, 'rb').read()
be32 = lambda o: struct.unpack_from('>I', d, o)[0]
pe_off, sec_off, nopt = be32(8), be32(0x10), be32(0x14)
opt = dict(struct.unpack_from('>II', d, 0x18 + i * 8) for i in range(nopt))
ff = opt[0x3FF]
enc, comp = struct.unpack_from('>HH', d, ff + 4)
assert comp == 1, 'only basic compression handled here'

def aes(mode, key, data):
    return subprocess.run([openssl, 'enc', '-d', mode, '-nopad', '-K', key.hex(), '-iv', '00' * 16],
                          input=data, capture_output=True, check=True).stdout

payload = d[pe_off:]
if enc == 1:
    session = aes('-aes-128-cbc', RETAIL_KEY, d[sec_off + 0x150:sec_off + 0x160])  # 1 block, IV 0 == ECB
    payload = aes('-aes-128-cbc', session, payload)

out, pos = bytearray(), 0
for o in range(ff + 8, ff + be32(ff), 8):
    dsz, zsz = struct.unpack_from('>II', d, o)
    out += payload[pos:pos + dsz] + bytes(zsz)
    pos += dsz
img_size = be32(sec_off + 4)
print(f'image {len(out):#x} (expected {img_size:#x}) magic={bytes(out[:2])}')
open(dst, 'wb').write(out)
