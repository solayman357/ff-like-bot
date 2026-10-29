"""FF Likes core: manual protobuf + AES + JWT + like sending. No external token service needed."""

import base64
import json
import time
import httpx
from Crypto.Cipher import AES

MAIN_KEY = base64.b64decode("WWcmdGMlREV1aDYlWmNeOA==")  # Yg&tc%DEuh6%Zc^8
MAIN_IV = base64.b64decode("Nm95WkRyMjJFM3ljaGpNJQ==")   # 6oyZDr22E3ychjM%

USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
RELEASE_VERSION = "OB54"  # OB51/OB52 return 503 on LB; OB50 is accepted

OAUTH_URL = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
MAJOR_LOGIN_URLS = [
    "https://loginbp.ggpolarbear.com/MajorLogin",
    "https://loginbp.ggwhitehawk.com/MajorLogin",
    "https://loginbp.ggblueshark.com/MajorLogin",
]
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
CLIENT_ID = "100067"

SERVERS = {
    "IND": "https://client.ind.freefiremobile.com",
    "BR": "https://client.us.freefiremobile.com",
    "US": "https://client.us.freefiremobile.com",
    "SAC": "https://client.us.freefiremobile.com",
    "NA": "https://client.us.freefiremobile.com",
    "EU": "https://clientbp.ggblueshark.com",
    "SG": "https://clientbp.ggblueshark.com",
    "BD": "https://clientbp.ggpolarbear.com",
    "PK": "https://clientbp.ggblueshark.com",
    "VN": "https://clientbp.ggblueshark.com",
    "TH": "https://clientbp.ggblueshark.com",
    "ID": "https://clientbp.ggblueshark.com",
    "TW": "https://clientbp.ggblueshark.com",
    "ME": "https://clientbp.ggblueshark.com",
    "RU": "https://clientbp.ggblueshark.com",
}


# ---------------- protobuf manual encoding ----------------

def _varint(n):
    out = b""
    n = int(n)
    while n > 0x7F:
        out += bytes([(n & 0x7F) | 0x80])
        n >>= 7
    return out + bytes([n])


def _tag(field, wire):
    return _varint((field << 3) | wire)


def pb_string(field, s):
    b = s.encode() if isinstance(s, str) else s
    return _tag(field, 2) + _varint(len(b)) + b


def pb_int(field, n):
    return _tag(field, 0) + _varint(n)


def pb_build(*chunks):
    return b"".join(chunks)


def pb_decode_strings(data):
    """Decode (field_num, value_str) pairs from protobuf bytes (string fields only)."""
    out = {}
    i = 0
    n = len(data)
    while i < n:
        tag = 0
        shift = 0
        while i < n:
            b = data[i]; i += 1
            tag |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
        field, wire = tag >> 3, tag & 7
        if wire == 2:
            ln = 0; shift = 0
            while i < n:
                b = data[i]; i += 1
                ln |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            out[field] = data[i:i + ln]
            i += ln
        elif wire == 0:
            v = 0; shift = 0
            while i < n:
                b = data[i]; i += 1
                v |= (b & 0x7F) << shift
                shift += 7
                if not (b & 0x80):
                    break
            out[field] = v
        else:
            break
    return out


def build_login_req(open_id, login_token):
    return pb_build(
        pb_string(22, open_id),
        pb_string(23, "4"),
        pb_string(29, login_token),
        pb_string(99, "4"),
    )


REGION_CODES = {
    "IND": 1, "BR": 2, "SG": 3, "TH": 4, "PH": 5, "VN": 6,
    "ME": 7, "RU": 8, "US": 9, "PK": 10, "BD": 11, "TW": 12,
}

def pb_varint(n):
    out = b""
    while n > 0:
        b = n & 0x7F
        n >>= 7
        if n > 0:
            b |= 0x80
        out += bytes([b])
    return out


def build_like_payload(target_uid, region):
    """LikeProfile payload: field1 uid varint, field2 region STRING (confirmed live format)."""
    region = region.upper()
    return pb_build(
        pb_int(1, int(target_uid)),
        pb_string(2, region),
    )


# ---------------- AES ----------------

def pkcs7_pad(b, block=16):
    padlen = block - (len(b) % block)
    return b + bytes([padlen]) * padlen


def aes_cbc_encrypt(plaintext, key=MAIN_KEY, iv=MAIN_IV):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pkcs7_pad(plaintext))


# ---------------- JWT flow ----------------

async def get_access_token(client, uid, password):
    payload = (
        f"uid={uid}&password={password}&response_type=token&client_type=2"
        f"&client_secret={CLIENT_SECRET}&client_id={CLIENT_ID}"
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = await client.post(OAUTH_URL, data=payload, headers=headers, timeout=15)
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"OAuth error: {data.get('error_description', data['error'])}")
    return data.get("access_token", "0"), data.get("open_id", "0")


async def major_login(client, encrypted_payload):
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
    }
    last_err = None
    for url in MAJOR_LOGIN_URLS:
        try:
            r = await client.post(url, content=encrypted_payload, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.content
            last_err = f"{url} -> HTTP {r.status_code}"
        except Exception as e:
            last_err = f"{url} -> {e}"
    raise RuntimeError(f"MajorLogin failed: {last_err}")


async def create_jwt(client, uid, password):
    access_token, open_id = await get_access_token(client, uid, password)
    if access_token == "0":
        raise RuntimeError("Failed to obtain access token")
    req = build_login_req(open_id, access_token)
    encrypted = aes_cbc_encrypt(req)
    resp = await major_login(client, encrypted)
    fields = pb_decode_strings(resp)
    if 13 in fields:
        raise RuntimeError("Account blocked/temp-banned (login queue info returned)")
    token = fields.get(8, b"0").decode(errors="replace")
    lock_region = fields.get(2, b"").decode(errors="replace")
    server_url = fields.get(10, b"").decode(errors="replace")
    if token in ("0", ""):
        raise RuntimeError(f"No JWT in response: {fields}")
    return token, lock_region, server_url


# ---------------- like sending ----------------

LIKE_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 8 Build/UP1A.231005.007)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": RELEASE_VERSION,
}


def base_url_for(region):
    return SERVERS.get(region, "https://clientbp.ggpolarbear.com")


async def send_like(client, target_uid, region, jwt):
    payload = aes_cbc_encrypt(build_like_payload(target_uid, region))
    headers = dict(LIKE_HEADERS, Authorization=f"Bearer {jwt}")
    r = await client.post(
        f"{base_url_for(region)}/LikeProfile", data=payload, headers=headers, timeout=30
    )
    return r


async def get_player_info(client, target_uid, region, jwt=None):
    """Fetch account info via GetPlayerPersonalShow. jwt=None uses unauthenticated raw UID body."""
    url = f"{base_url_for(region)}/GetPlayerPersonalShow"
    headers = dict(LIKE_HEADERS)
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    r = await client.post(url, data=str(target_uid).encode(), headers=headers, timeout=30)
    return r
