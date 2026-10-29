# -*- coding: utf-8 -*-
"""IP test - phone theke like pathay (Termux). usage: python3 iptest.py <target_uid> <uid1> <pw1> [uid2 pw2 ...]"""
import asyncio, sys, time, json, base64
try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)
from Crypto.Cipher import AES

MAIN_KEY = b'Yg&tc%DEuh6%Zc^8'
MAIN_IV = b'6oyZDr22E3ychjM%'
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
CLIENT_ID = "100067"
UA = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"


def pb_int(n):
    out = b""
    while n > 127:
        out += bytes([(n & 127) | 128]); n >>= 7
    return out + bytes([n])


def pb_str(s):
    b = s.encode()
    return pb_int(len(b)) + b


def build_login_req(open_id, token):
    body = b""
    body += b"\x0a" + pb_int(len(open_id.encode())) + open_id.encode()   # 1: open_id
    body += b"\x10\x04"                                                  # 2: open_id_type=4
    body += b"\x1a" + pb_int(len(token.encode())) + token.encode()       # 3: login_token
    body += b"\x20\x04"                                                  # 4: orign_platform_type=4
    return body


def build_like(target, region):
    return b"\x08" + pb_int(int(target)) + b"\x12" + pb_str(region)


def aes_enc(data):
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len]) * pad_len
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(data)


def pb_decode(data):
    out, i, n = {}, 0, len(data)
    while i < n:
        tag = data[i]; i += 1
        fnum, wt = tag >> 3, tag & 7
        if wt == 0:
            v = 0; sh = 0
            while True:
                b = data[i]; i += 1
                v |= (b & 127) << sh; sh += 7
                if not b & 128: break
            out[fnum] = v
        elif wt == 2:
            ln = 0; sh = 0
            while True:
                b = data[i]; i += 1
                ln |= (b & 127) << sh; sh += 7
                if not b & 128: break
            out[fnum] = data[i:i + ln]; i += ln
        else:
            return out
    return out


async def create_jwt(client, uid, password):
    r = await client.post("https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant",
                          data=f"uid={uid}&password={password}&response_type=token&client_type=2&client_secret={CLIENT_SECRET}&client_id={CLIENT_ID}",
                          headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
    d = r.json()
    if "error" in d:
        raise RuntimeError(f"oauth: {d.get('error_description', d['error'])}")
    token, open_id = d["access_token"], d["open_id"]
    r = await client.post("https://loginbp.ggblueshark.com/MajorLogin",
                          content=aes_enc(build_login_req(open_id, token)),
                          headers={"User-Agent": UA, "Content-Type": "application/octet-stream", "Expect": "100-continue",
                                   "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1", "ReleaseVersion": "OB54"}, timeout=20)
    f = pb_decode(r.content)
    if 13 in f:
        raise RuntimeError("BLOCKED")
    return f.get(8, b"0").decode(errors="replace"), f.get(2, b"").decode(errors="replace")


async def main():
    if len(sys.argv) < 5 or (len(sys.argv) - 2) % 2 != 0:
        print("usage: python3 iptest.py <TARGET_UID> <uid1> <pw1> [uid2 pw2 ...]")
        return
    target, region = sys.argv[1], "BD"
    pairs = [(sys.argv[i], sys.argv[i + 1]) for i in range(2, len(sys.argv), 2)]
    async with httpx.AsyncClient() as c:
        for uid, pw in pairs:
            try:
                jwt, lock = await create_jwt(c, uid, pw)
                r = await c.post("https://clientbp.ggpolarbear.com/LikeProfile",
                                 data=aes_enc(build_like(target, region)),
                                 headers={"User-Agent": UA, "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
                                          "Authorization": f"Bearer {jwt}", "Content-Type": "application/x-www-form-urlencoded",
                                          "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1",
                                          "ReleaseVersion": "OB54"}, timeout=30)
                print(f"[{uid}] like -> {target}: HTTP {r.status_code}")
            except Exception as e:
                print(f"[{uid}] FAIL: {str(e)[:60]}")
            await asyncio.sleep(5)


asyncio.run(main())
