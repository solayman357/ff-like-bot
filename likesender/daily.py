# -*- coding: utf-8 -*-
"""Daily FF Like sender for multiple targets (BD)."""
import asyncio, json, sys, time, os
sys.path.insert(0, '/root/fflikes-bot')
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import uid_generator_pb2, visit_count_pb2, like_pb2
import ff_core
from ff_core import MAIN_KEY, MAIN_IV, LIKE_HEADERS, create_jwt

DIR = "/root/fflikes-bot/likesender"
TARGETS = ["9261851398", "8125935406"]   # PRIME SAMI, AD.*ADOY
REGION = "BD"
HOST = "https://clientbp.ggpolarbear.com"
LOG = os.path.join(DIR, "daily.log")
USED = os.path.join(DIR, "used_daily.json")


def aes_enc(data):
    return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(pad(data, 16))


def enc_uid(uid):
    m = uid_generator_pb2.uid_generator(); m.saturn_ = int(uid); m.garena = 1
    return aes_enc(m.SerializeToString())


def enc_like(uid, region):
    raw = b"\x08" + ff_core.pb_varint(int(uid)) + b"\x12" + ff_core.pb_varint(len(region)) + region.upper().encode()
    return aes_enc(raw)


def parse_info(body):
    p = visit_count_pb2.Info(); p.ParseFromString(body)
    return p.AccountInfo


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")


async def get_likes(c, jwt, uid):
    r = await c.post(f"{HOST}/GetPlayerPersonalShow", data=enc_uid(uid),
                     headers={**LIKE_HEADERS, "Authorization": f"Bearer {jwt}"}, timeout=20)
    a = parse_info(r.content)
    return a.Likes, a.PlayerNickname


async def main():
    pool = json.load(open(os.path.join(DIR, "pool.json")))
    day = time.strftime("%Y-%m-%d")
    used = {}
    try:
        used = json.load(open(USED))
    except Exception:
        pass

    async with httpx.AsyncClient() as c:
        for target in TARGETS:
            used_target = used.get(day, {}).get(target, {})
            todo = [a for a in pool if not used_target.get(a["uid"])]
            if not todo:
                log(f"[{target}] AJKE SAB LIKE AGEI PATHANO HOYECHE. skip.")
                continue
            try:
                before, nick = await get_likes(c, pool[0]["jwt"], target)
                log(f"[{target}] TARGET: {nick} | before={before} likes")
            except Exception as e:
                before, nick = None, "?"
                log(f"[{target}] INFO FAIL: {e}")

            ok = fail = 0
            for acc in todo:
                try:
                    jwt, lr, srv = await create_jwt(c, acc["uid"], acc["password"])
                    acc.update(jwt=jwt, region=lr, server=srv, refreshed=int(time.time()))
                    r = await c.post(f"{HOST}/LikeProfile", data=enc_like(target, REGION),
                                     headers={**LIKE_HEADERS, "Authorization": f"Bearer {jwt}"}, timeout=20)
                    if r.status_code == 200:
                        ok += 1
                    else:
                        fail += 1
                        log(f"  ! {acc['uid']} HTTP {r.status_code}")
                    await asyncio.sleep(1.5)
                except Exception as e:
                    fail += 1
                    log(f"  ! {acc['uid']} ERR {str(e)[:40]}")
            used.setdefault(day, {}).setdefault(target, {})
            for acc in todo:
                used[day][target][acc["uid"]] = True
            json.dump(used, open(USED, "w"), indent=1)
            log(f"[{target}] SENT: {ok} ok | {fail} fail | pool={len(pool)}")

            if before is not None:
                await asyncio.sleep(5)
                try:
                    after, _ = await get_likes(c, pool[0]["jwt"], target)
                    log(f"[{target}] AFTER: {after} likes | delta now: +{after - before}")
                except Exception as e:
                    log(f"[{target}] AFTER FAIL: {e}")


asyncio.run(main())
