# -*- coding: utf-8 -*-
"""FF Daily Like Bot - SINGLE FILE (mobile/Termux ready)"""

import asyncio
import base64
import json
import os
import sys
import time

try:
    import httpx
    from Crypto.Cipher import AES
except ImportError:
    print("(!) Age install korun:  pip install httpx pycryptodome")
    sys.exit(1)

BASE = os.path.dirname(os.path.abspath(__file__))
GUESTS_FILE = os.path.join(BASE, "guest_accounts.json")
USAGE_FILE = os.path.join(BASE, "usage_daily.json")
SETTINGS_FILE = os.path.join(BASE, "settings.json")

MAIN_KEY = base64.b64decode("WWcmdGMlREV1aDYlWmNeOA==")
MAIN_IV = base64.b64decode("Nm95WkRyMjJFM3ljaGpNJQ==")
USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
RELEASE_VERSION = "OB50"
OAUTH_URL = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
MAJOR_LOGIN_URLS = ["https://loginbp.ggwhitehawk.com/MajorLogin",
                    "https://loginbp.ggblueshark.com/MajorLogin"]
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
CLIENT_ID = "100067"
SERVERS = {
    "IND": "https://client.ind.freefiremobile.com",
    "BR": "https://client.us.freefiremobile.com",
    "US": "https://client.us.freefiremobile.com",
    "SAC": "https://client.us.freefiremobile.com",
    "NA": "https://client.us.freefiremobile.com",
}


# ---------------- protobuf (manual) ----------------
def _varint(n):
    out = b""
    n = int(n)
    while n > 0x7F:
        out += bytes([(n & 0x7F) | 0x80])
        n >>= 7
    return out + bytes([n])


def pb_string(field, s):
    b = s.encode() if isinstance(s, str) else s
    return _varint((field << 3) | 2) + _varint(len(b)) + b


def pb_int(field, n):
    return _varint((field << 3) | 0) + _varint(n)


def pb_decode(data):
    out, i, n = {}, 0, len(data)
    while i < n:
        tag = 0
        sh = 0
        while i < n:
            b = data[i]; i += 1
            tag |= (b & 0x7F) << sh
            sh += 7
            if not (b & 0x80):
                break
        field, wire = tag >> 3, tag & 7
        if wire == 2:
            ln = 0; sh = 0
            while i < n:
                b = data[i]; i += 1
                ln |= (b & 0x7F) << sh
                sh += 7
                if not (b & 0x80):
                    break
            out[field] = data[i:i + ln]
            i += ln
        elif wire == 0:
            v = 0; sh = 0
            while i < n:
                b = data[i]; i += 1
                v |= (b & 0x7F) << sh
                sh += 7
                if not (b & 0x80):
                    break
            out[field] = v
        else:
            break
    return out


def build_login_req(open_id, token):
    return (pb_string(22, open_id) + pb_string(23, "4") +
            pb_string(29, token) + pb_string(99, "4"))


def build_like(target_uid, region):
    return pb_int(1, int(target_uid)) + pb_string(2, region)


def aes_enc(data):
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len]) * pad_len
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(data)


# ---------------- JWT ----------------
async def get_access(client, uid, password):
    payload = (f"uid={uid}&password={password}&response_type=token&client_type=2"
               f"&client_secret={CLIENT_SECRET}&client_id={CLIENT_ID}")
    headers = {"User-Agent": USER_AGENT, "Connection": "Keep-Alive",
               "Accept-Encoding": "gzip",
               "Content-Type": "application/x-www-form-urlencoded"}
    r = await client.post(OAUTH_URL, data=payload, headers=headers, timeout=15)
    data = r.json()
    if "error" in data:
        raise RuntimeError("OAuth error")
    return data.get("access_token", "0"), data.get("open_id", "0")


async def major_login(client, encrypted):
    headers = {"User-Agent": USER_AGENT, "Connection": "Keep-Alive",
               "Accept-Encoding": "gzip", "Content-Type": "application/octet-stream",
               "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1",
               "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION}
    for url in MAJOR_LOGIN_URLS:
        try:
            r = await client.post(url, content=encrypted, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.content
        except Exception:
            continue
    raise RuntimeError("MajorLogin failed")


async def create_jwt(client, uid, password):
    at, oid = await get_access(client, uid, password)
    if at == "0":
        raise RuntimeError("No access token")
    resp = await major_login(client, aes_enc(build_login_req(oid, at)))
    fields = pb_decode(resp)
    if 13 in fields:
        raise RuntimeError("BLOCKED (queue)")
    token = fields.get(8, b"0").decode(errors="replace")
    region = fields.get(2, b"").decode(errors="replace")
    if token in ("0", ""):
        raise RuntimeError("No JWT")
    return token, region


async def send_like(client, target, region, jwt):
    payload = aes_enc(build_like(target, region))
    headers = {"User-Agent": USER_AGENT, "Connection": "Keep-Alive",
               "Accept-Encoding": "gzip", "Content-Type": "application/octet-stream",
               "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1",
               "X-GA": "v1 1", "ReleaseVersion": RELEASE_VERSION,
               "Authorization": f"Bearer {jwt}"}
    base = SERVERS.get(region, "https://clientbp.ggblueshark.com")
    r = await client.post(f"{base}/LikeProfile", data=payload, headers=headers, timeout=30)
    return r.status_code


# ---------------- storage ----------------
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def day_key():
    return time.strftime("%Y-%m-%d")


# ---------------- menu ----------------
def banner():
    print("=" * 46)
    print("  FF DAILY LIKE BOT - 220 LIKE/DAY")
    print("=" * 46)


def menu():
    s = load_json(SETTINGS_FILE, {})
    guests = load_json(GUESTS_FILE, [])
    banner()
    print(" Target UID:", s.get("target_uid") or "-")
    print(" Region    :", s.get("region", "IND"))
    print(" Guests    :", len(guests), "ta")
    print(" [1] Target UID + Region set")
    print(" [2] Guest account add")
    print(" [3] Ajke like pathan")
    print(" [4] 24ghonta AUTO (computer/mobile ON thaka lagbe)")
    print(" [0] Exit")
    return input(" Number: ").strip()


async def send_all(client, sem, g, target, region, usage, day):
    uid = g["uid"]
    if uid in usage.get(day, {}).get(target, {}):
        return "used"
    async with sem:
        try:
            jwt, lock = await create_jwt(client, uid, g["password"])
            reg = lock or region
            status = await send_like(client, target, reg, jwt)
            ok = status == 200
            usage.setdefault(day, {}).setdefault(target, {})[uid] = {
                "ok": ok, "status": status, "region": reg}
            save_json(USAGE_FILE, usage)
            return "ok" if ok else f"fail({status})"
        except Exception as e:
            msg = str(e)
            if "BLOCKED" in msg:
                return "blocked"
            return "err"


def run_likes(loop=False):
    s = load_json(SETTINGS_FILE, {})
    if not s.get("target_uid"):
        print(" (!) Age menu [1] diye UID set korun"); return
    guests = load_json(GUESTS_FILE, [])
    if not guests:
        print(" (!) Age menu [2] diye guest account add korun"); return
    target = s["target_uid"]; region = s.get("region", "IND")
    want = int(s.get("likes", 220))
    print(f" Target: {target} | Region: {region} | Chai: {want} like | Guests: {len(guests)}")

    sem = asyncio.Semaphore(10)

    async def runner():
        usage = load_json(USAGE_FILE, {})
        day = day_key()
        done = fail = blocked = used = err = 0
        async with httpx.AsyncClient() as client:
            for i, g in enumerate(guests, 1):
                res = await send_all(client, sem, g, target, region, usage, day)
                if res == "ok":
                    done += 1
                    print(f"  [{i}/{len(guests)}] [+] {g['uid']} -> like pathano hocche! (total {done})")
                elif res == "used":
                    used += 1
                elif res == "blocked":
                    blocked += 1
                    print(f"  [{i}/{len(guests)}] [!] {g['uid']} band - menu 6 diye remove korun")
                elif res.startswith("fail"):
                    fail += 1
                    print(f"  [{i}/{len(guests)}] [-] {g['uid']} {res}")
                else:
                    err += 1
                if done >= want:
                    print(" [OK] Je koto like chai hoye geche!")
                    break
            return done, fail, blocked, used, err

    done, fail, blocked, used, err = asyncio.run(runner())
    print("-" * 46)
    print(f" Result: {done} like | fail: {fail} | band: {blocked} | skip: {used} | err: {err}")
    if loop:
        print(" [AUTO] Kal abar automatic. Mobile ta ON rakhen, Termux khula rakhen.")
        try:
            while True:
                time.sleep(1800)
                if day_key() != load_json(SETTINGS_FILE, {}).get("_day", ""):
                    print(" [AUTO] Notun din! Abar like pathano hocche...")
                    d, f, b, u, e = asyncio.run(runner())
                    print(f" Result: {d} like | fail: {f} | band: {b} | skip: {u}")
                    s2 = load_json(SETTINGS_FILE, {}); s2["_day"] = day_key(); save_json(SETTINGS_FILE, s2)
        except KeyboardInterrupt:
            print(" AUTO bondho.")


def main():
    while True:
        ch = menu()
        if ch == "1":
            s = load_json(SETTINGS_FILE, {})
            uid = input(" Apnar Free Fire UID: ").strip()
            if uid: s["target_uid"] = uid
            region = input(" Region [IND]: ").strip().upper() or "IND"
            s["region"] = region
            try:
                likes = int(input(" Koto like/chai din? [220]: ").strip() or "220")
                s["likes"] = likes
            except ValueError:
                pass
            save_json(SETTINGS_FILE, s)
            print(" [OK] Save hoyeche!\n")
        elif ch == "2":
            guests = load_json(GUESTS_FILE, [])
            print(" Guest UID+password add korun (UID faka rekhe enter = shesh)")
            while True:
                uid = input(" Guest UID: ").strip()
                if not uid: break
                pwd = input(" Password : ").strip()
                if not pwd: continue
                guests.append({"uid": uid, "password": pwd})
                print(f" [+] {uid} (total {len(guests)})")
            save_json(GUESTS_FILE, guests)
            print(f" [OK] {len(guests)} ta guest save!\n")
        elif ch == "3":
            run_likes(False)
        elif ch == "4":
            run_likes(True)
        elif ch == "0":
            print(" Bye!"); break
        else:
            print(" (!) Vul number\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n Bye!")
