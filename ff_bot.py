"""FF Daily Like Bot — sends likes to a target UID daily using guest accounts.

Each guest account can send 1 like per target per 24h.
Usage tracking resets automatically at midnight, so every day you get
~N likes where N = number of guest accounts in guest_accounts.json.

Usage:
  python3 ff_bot.py <target_uid> [region] [target_likes] [concurrency]
  python3 ff_bot.py 1234567890 IND 220 20
"""

import asyncio
import json
import os
import sys
import time
import httpx
import ff_core

GUESTS_FILE = os.path.join(os.path.dirname(__file__), "guest_accounts.json")
USAGE_FILE = os.path.join(os.path.dirname(__file__), "usage_daily.json")

RATE_PER_DAY_PER_TARGET = 220  # target likes per day


def load_guests():
    with open(GUESTS_FILE) as f:
        guests = json.load(f)
    seen, uniq = set(), []
    for g in guests:
        uid = str(g.get("uid", "")).strip()
        pwd = str(g.get("password", "")).strip()
        if uid and pwd and uid not in seen:
            seen.add(uid)
            uniq.append({"uid": uid, "password": pwd})
    return uniq


def load_usage():
    if os.path.exists(USAGE_FILE):
        try:
            return json.load(open(USAGE_FILE))
        except Exception:
            pass
    return {}


def save_usage(usage):
    tmp = USAGE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(usage, f, indent=1)
    os.replace(tmp, USAGE_FILE)


def day_key():
    return time.strftime("%Y-%m-%d")


def used_for(usage, day, target, guest_uid):
    return guest_uid in usage.get(day, {}).get(target, {})


def mark_used(usage, day, target, guest_uid, info):
    usage.setdefault(day, {}).setdefault(target, {})[guest_uid] = info
    save_usage(usage)


async def like_one(client, sem, guest, target, region, usage, day):
    guest_uid = guest["uid"]
    if used_for(usage, day, target, guest_uid):
        return None
    async with sem:
        try:
            jwt, lock_region, _ = await ff_core.create_jwt(client, guest_uid, guest["password"])
            region_for = lock_region or region
            r = await ff_core.send_like(client, target, region_for, jwt)
            ok = r.status_code == 200
            mark_used(usage, day, target, guest_uid,
                      {"ok": ok, "status": r.status_code, "t": int(time.time()), "region": region_for})
            return {"guest": guest_uid, "ok": ok, "status": r.status_code}
        except Exception as e:
            return {"guest": guest_uid, "ok": False, "err": str(e)[:120]}


async def run(target, region, want, concurrency):
    guests = load_guests()
    print(f"Loaded {len(guests)} guest accounts")
    if not guests:
        print("ERROR: no accounts in guest_accounts.json")
        sys.exit(1)

    usage = load_usage()
    day = day_key()
    print(f"Today: {day} | Target: {target} | Region: {region}")

    sem = asyncio.Semaphore(concurrency)
    results = []
    done = 0
    async with httpx.AsyncClient(http2=False) as client:
        for i in range(0, len(guests), concurrency):
            batch = guests[i:i + concurrency]
            batch_results = await asyncio.gather(*[like_one(client, sem, g, target, region, usage, day) for g in batch])
            for res in batch_results:
                if res is None:
                    continue
                results.append(res)
                if res["ok"]:
                    done += 1
                    print(f"  [+] {res['guest']} like sent (HTTP {res['status']})")
                else:
                    print(f"  [-] {res['guest']} failed: {res.get('err', res.get('status'))}")
            print(f"  ... {done} likes so far")
            if done >= want:
                print("Target reached, stopping.")
                break

    failed = sum(1 for r in results if not r["ok"])
    print(f"\nDone: {done} likes sent, {failed} failed (today {day})")
    print(f"Usage file: {USAGE_FILE}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    target = sys.argv[1].strip()
    region = (sys.argv[2] if len(sys.argv) > 2 else "IND").upper()
    want = int(sys.argv[3]) if len(sys.argv) > 3 else RATE_PER_DAY_PER_TARGET
    concurrency = int(sys.argv[4]) if len(sys.argv) > 4 else 15
    asyncio.run(run(target, region, want, concurrency))


if __name__ == "__main__":
    main()
