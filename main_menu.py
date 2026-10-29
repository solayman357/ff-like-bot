# -*- coding: utf-8 -*-
"""FF Daily Like Bot - Simple Bangla menu (no technical knowledge needed)."""

import asyncio
import json
import os
import subprocess
import sys
import time
import httpx

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import ff_core

GUESTS_FILE = os.path.join(BASE, "guest_accounts.json")
USAGE_FILE = os.path.join(BASE, "usage_daily.json")
SETTINGS_FILE = os.path.join(BASE, "settings.json")

try:
    input = raw_input
except NameError:
    pass


def banner():
    print("=" * 52)
    print("   FREE FIRE DAILY LIKE BOT - 220 LIKE/DAY")
    print("=" * 52)


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


def load_settings():
    return load_json(SETTINGS_FILE, {"target_uid": "", "region": "IND", "likes": 220})


def load_guests():
    return load_json(GUESTS_FILE, [])


def clean_guests():
    seen, out = set(), []
    for g in load_guests():
        uid = str(g.get("uid", "")).strip()
        pwd = str(g.get("password", "")).strip()
        if uid and pwd and uid not in seen:
            seen.add(uid)
            out.append({"uid": uid, "password": pwd})
    return out


def day_key():
    return time.strftime("%Y-%m-%d")


def load_usage():
    return load_json(USAGE_FILE, {})


def menu():
    banner()
    settings = load_settings()
    guests = clean_guests()
    print()
    print(" Apnar target UID :", settings["target_uid"] or "(set kora hoyni)")
    print(" Region           :", settings["region"])
    print(" Guest accounts   :", len(guests), "ta")
    print()
    print(" [1] Target UID + Region set korun")
    print(" [2] Guest account add korun")
    print(" [3] Ajke like pathan (ek bar chalan)")
    print(" [6] 24 GHONTA AUTO MODE (computer ON thakle proti din nijei korbe)")
    print(" [4] Like count check korun")
    print(" [5] Band kora guest account dekhte/delete korun")
    print(" [0] Band (Exit)")
    print("-" * 52)
    return input(" Number ta likhun (0-6) : ").strip()


def set_target():
    settings = load_settings()
    print()
    uid = input(" Apnar Free Fire UID likhun (je UID te like ashbe): ").strip()
    if uid:
        settings["target_uid"] = uid
    print(" Region gulor code: IND, SG, BD, PK, ID, VN, TH, EU, ME, RU, TW, BR")
    region = input(" Region code likhun [IND]: ").strip().upper() or "IND"
    settings["region"] = region
    try:
        likes = int(input(" Proti din koto like chai? [220]: ").strip() or "220")
        settings["likes"] = likes
    except ValueError:
        pass
    save_json(SETTINGS_FILE, settings)
    print(" [OK] Save hoyeche!")
    print("      Target UID:", settings["target_uid"], "| Region:", region)
    print()


def add_guests():
    guests = load_guests()
    print()
    print(" Guest account add korun.")
    print(" (Free Fire app e Guest login korle protita notun account hoy)")
    print(" Add korte korte enter chapun, shesh hole UID faka rekhe enter din)")
    print("-" * 52)
    while True:
        uid = input(" Guest UID : ").strip()
        if not uid:
            break
        pwd = input(" Password  : ").strip()
        if not pwd:
            print("  (!) Password faka - skip kora holo")
            continue
        guests.append({"uid": uid, "password": pwd})
        print(f"  [+] Added: {uid}  (total: {len(guests)})")
    save_json(GUESTS_FILE, guests)
    print(f" [OK] {len(guests)} ta guest account save hoyeche!")
    print()


async def send_all(client, sem, guest, target, region, usage, day):
    uid = guest["uid"]
    if uid in usage.get(day, {}).get(target, {}):
        return "used"
    async with sem:
        try:
            jwt, lock_region, _ = await ff_core.create_jwt(client, uid, guest["password"])
            region_for = lock_region or region
            r = await ff_core.send_like(client, target, region_for, jwt)
            ok = r.status_code == 200
            usage.setdefault(day, {}).setdefault(target, {})[uid] = {
                "ok": ok, "status": r.status_code, "region": region_for
            }
            save_json(USAGE_FILE, usage)
            return "ok" if ok else "fail"
        except Exception as e:
            msg = str(e)[:60]
            if "blocked" in msg.lower() or "queue" in msg.lower():
                return "blocked"
            return "err"


def run_daily(loop=False):
    settings = load_settings()
    if not settings.get("target_uid"):
        print(" (!) Age target UID set korun (menu 1)")
        return
    guests = clean_guests()
    if not guests:
        print(" (!) Age guest account add korun (menu 2)")
        return
    target = settings["target_uid"]
    region = settings["region"]
    want = int(settings.get("likes", 220))
    print()
    print(f" Target: {target} | Region: {region} | Chai: {want} like")
    print(f" Guest accounts: {len(guests)} ta")
    print(" Like pathano shuru holo... (ekta ekta account diye)")
    print("-" * 52)

    sem = asyncio.Semaphore(15)

    async def runner():
        nonlocal_usage = load_usage()
        day = day_key()
        done = fail = blocked = err = used = 0
        async with httpx.AsyncClient() as client:
            for i, g in enumerate(guests, 1):
                res = await send_all(client, sem, g, target, region, nonlocal_usage, day)
                if res == "ok":
                    done += 1
                    print(f"  [{i}/{len(guests)}] [+] {g['uid']} - like pathano hocche! (total: {done})")
                elif res == "blocked":
                    blocked += 1
                    print(f"  [{i}/{len(guests)}] [!] {g['uid']} - band (menu 5 diye remove korun)")
                elif res == "used":
                    used += 1
                    print(f"  [{i}/{len(guests)}] [>] {g['uid']} - agei like diyeche (skip)")
                elif res == "fail":
                    fail += 1
                    print(f"  [{i}/{len(guests)}] [-] {g['uid']} - fail (HTTP error)")
                else:
                    err += 1
                    print(f"  [{i}/{len(guests)}] [-] {g['uid']} - onno error: {res[:40]}")
                if done >= want:
                    print(" [OK] Je koto like chai ta hoye geche! Bondho kora holo.")
                    break
            return done, fail, blocked, err, used

    done, fail, blocked, err, used = asyncio.run(runner())
    print("-" * 52)
    print(f" Result: {done} like pathano hoyeche | fail: {fail} | band: {blocked} | skip: {used}")
    if loop:
        print()
        print(" [LOOP] Kal abar automatic like pathabe.")
        print("        Computer ta ON rekhe din - sob automatic hobe.")
        print()
        print(" Kal porjonto wait hocche (24 ghonta)...")
        print(" (Ctrl+C chaple bondho hobe)")
        print()
        try:
            while True:
                time.sleep(3600)
                today = day_key()
                if today != day:
                    print(f" [LOOP] Notun din ({today})! Abar like pathano hocche...")
                    day = today
                    d, f, b, e, u = asyncio.run(runner())
                    print(f" Result: {d} like | fail: {f} | band: {b} | skip: {u}")
        except KeyboardInterrupt:
            print("\n Loop bondho holo.")
    print()


def check_likes():
    settings = load_settings()
    uid = settings.get("target_uid") or input(" UID likhun: ").strip()
    region = settings.get("region", "IND")

    async def run():
        async with httpx.AsyncClient() as c:
            r = await ff_core.get_player_info(c, uid, region)
            print(f" HTTP: {r.status_code}")
            fields = ff_core.pb_decode_strings(r.content)
            likes = None
            for _, v in fields.items():
                if isinstance(v, bytes):
                    try:
                        s = v.decode()
                        if s.isdigit() and 1 < len(s) < 12:
                            likes = s
                    except Exception:
                        pass
            print(f" Likes: {likes if likes else 'count na paowa gelo (auth dorkar)'}")

    asyncio.run(run())
    print()


def remove_blocked():
    guests = clean_guests()
    if not guests:
        print(" Kono guest account nai.")
        return
    print()
    print(" List:")
    for i, g in enumerate(guests, 1):
        print(f"  [{i}] {g['uid']}")
    print()
    choice = input(" Delete korar number likhun (faka rekhe return korun): ").strip()
    if choice.isdigit() and 0 < int(choice) <= len(guests):
        removed = guests.pop(int(choice) - 1)
        save_json(GUESTS_FILE, guests)
        print(f" [-] Removed: {removed['uid']}")
    print()


def main():
    while True:
        ch = menu()
        if ch == "1":
            set_target()
        elif ch == "2":
            add_guests()
        elif ch == "3":
            run_daily(loop=False)
        elif ch == "6":
            print()
            ans = input(" Computer ON thaka lagbe. Sure? (y/n): ").strip().lower()
            if ans in ("y", "yes"):
                run_daily(loop=True)
        elif ch == "4":
            check_likes()
        elif ch == "5":
            remove_blocked()
        elif ch == "0":
            print(" Bye!")
            break
        else:
            print(" (!) Vul number. 0-5 er moddhe likhun.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n Bye!")
