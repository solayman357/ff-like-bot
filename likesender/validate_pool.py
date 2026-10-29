#!/usr/bin/env python3
"""FF Likes Pool Validator & JWT Refresher.
Tests every account in likesender/pool.json:
  1. Tries the stored JWT on GetPlayerPersonalShow
  2. If JWT dead/expired, creates a fresh JWT via create_jwt()
  3. If account is blocked/invalid, removes it from the pool
  4. Writes back a cleaned pool.json with alive status + fresh JWTs
Usage:
  python3 likesender/validate_pool.py
"""
import asyncio
import json
import os
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
sys.path.insert(0, ROOT)

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import uid_generator_pb2, visit_count_pb2
import ff_core
from ff_core import MAIN_KEY, MAIN_IV, LIKE_HEADERS, create_jwt, base_url_for

POOL = os.path.join(DIR, "pool.json")
BACKUP = os.path.join(DIR, "pool.json.bak")

REGION_HOSTS = {
    "BD": "https://clientbp.ggpolarbear.com",
    "IND": "https://client.ind.freefiremobile.com",
    "SG": "https://clientbp.ggblueshark.com",
    "PK": "https://clientbp.ggblueshark.com",
    "VN": "https://clientbp.ggblueshark.com",
    "TH": "https://clientbp.ggblueshark.com",
    "ID": "https://clientbp.ggblueshark.com",
    "EU": "https://clientbp.ggblueshark.com",
    "ME": "https://clientbp.ggblueshark.com",
    "RU": "https://clientbp.ggblueshark.com",
}


def aes_enc(data):
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(pad(data, 16))


def enc_uid(uid):
    m = uid_generator_pb2.uid_generator()
    m.saturn_ = int(uid)
    m.garena = 1
    return aes_enc(m.SerializeToString())


def parse_info(body):
    p = visit_count_pb2.Info()
    p.ParseFromString(body)
    return p.AccountInfo


def load_pool():
    with open(POOL) as f:
        return json.load(f)


def save_pool(pool):
    tmp = POOL + ".tmp"
    with open(tmp, "w") as f:
        json.dump(pool, f, indent=2)
    os.replace(tmp, POOL)


async def test_account(client, acc):
    """Return (ok, info_or_none, fresh_jwt_or_none, region, server)."""
    uid = acc["uid"]
    pwd = acc["password"]
    host = REGION_HOSTS.get(acc.get("region", "BD"),
                            REGION_HOSTS.get("BD"))

    # 1. Try stored JWT first
    jwt = acc.get("jwt")
    if jwt:
        try:
            r = await client.post(
                f"{host}/GetPlayerPersonalShow",
                data=enc_uid(uid),
                headers={**LIKE_HEADERS, "Authorization": f"Bearer {jwt}"},
                timeout=15,
            )
            if r.status_code == 200:
                info = parse_info(r.content)
                return True, info, jwt, acc.get("region", "BD"), host
        except Exception:
            pass

    # 2. JWT dead -> create fresh JWT
    try:
        fresh_jwt, lock_region, server = await create_jwt(client, uid, pwd)
        region = lock_region or acc.get("region", "BD")
        host = REGION_HOSTS.get(region, host)
        r = await client.post(
            f"{host}/GetPlayerPersonalShow",
            data=enc_uid(uid),
            headers={**LIKE_HEADERS, "Authorization": f"Bearer {fresh_jwt}"},
            timeout=15,
        )
        if r.status_code == 200:
            info = parse_info(r.content)
            return True, info, fresh_jwt, region, host
        return False, None, None, region, host
    except Exception as e:
        return False, None, None, acc.get("region", "BD"), host


async def main():
    if not os.path.exists(POOL):
        print(f"ERROR: {POOL} not found")
        sys.exit(1)

    # Backup before modifying
    if not os.path.exists(BACKUP):
        import shutil
        shutil.copy2(POOL, BACKUP)
        print(f"[*] Backup created: {BACKUP}")

    pool = load_pool()
    print(f"[*] Loaded {len(pool)} accounts from pool.json\n")

    alive = []
    dead = []
    refreshed = 0

    async with httpx.AsyncClient(http2=False) as client:
        for i, acc in enumerate(pool, 1):
            uid = acc.get("uid", "?")
            ok, info, fresh_jwt, region, host = await test_account(client, acc)

            if ok:
                acc["jwt"] = fresh_jwt or acc.get("jwt")
                acc["region"] = region
                acc["server"] = host
                acc["alive"] = True
                acc["refreshed"] = int(time.time())
                acc["nickname"] = getattr(info, "PlayerNickname", "?")
                acc["likes"] = getattr(info, "Likes", 0)
                acc["level"] = getattr(info, "Levels", 0)
                alive.append(acc)
                if fresh_jwt:
                    refreshed += 1
                print(f"  [{i:2d}/{len(pool)}] [OK] {uid} | {region} | nick={acc['nickname']} | likes={acc['likes']} | lvl={acc['level']}{' (JWT refreshed)' if fresh_jwt else ''}")
            else:
                dead.append(acc)
                print(f"  [{i:2d}/{len(pool)}] [DEAD] {uid} | removed from pool")

            # small delay to be polite to Garena
            await asyncio.sleep(0.4)

    save_pool(alive)

    print("\n" + "=" * 52)
    print(f" RESULTS")
    print("=" * 52)
    print(f"  Total accounts : {len(pool)}")
    print(f"  Alive/working  : {len(alive)}")
    print(f"  Dead/removed   : {len(dead)}")
    print(f"  JWTs refreshed : {refreshed}")
    print(f"  Likes/day capacity: {len(alive)} (1 per account per target per 24h)")
    print(f"  Cleaned pool saved to: {POOL}")
    print(f"  Backup at: {BACKUP}")


if __name__ == "__main__":
    asyncio.run(main())
