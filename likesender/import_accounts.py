#!/usr/bin/env python3
"""Import raw guest account JSON lines into likesender/pool.json format.

Input: accounts_input.txt with one JSON object per line (keys: uid, password,
jwt_token, region, server_url, nickname).
Output: likesender/pool.json  (normalized)
"""
import json
import os
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DIR)
sys.path.insert(0, ROOT)

POOL = os.path.join(DIR, "pool.json")
INPUT = os.path.join(DIR, "accounts_input.txt")


def load_existing():
    if os.path.exists(POOL):
        try:
            with open(POOL) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_pool(pool):
    tmp = POOL + ".tmp"
    with open(tmp, "w") as f:
        json.dump(pool, f, indent=2)
    os.replace(tmp, POOL)


def normalize(raw):
    uid = str(raw.get("uid") or raw.get("account_id") or "").strip()
    pwd = str(raw.get("password") or "").strip()
    jwt = str(raw.get("jwt_token") or raw.get("jwt") or "").strip()
    region = str(raw.get("region") or "BD").strip().upper()
    server = str(raw.get("server_url") or "").strip()
    nickname = str(raw.get("nickname") or "").strip()
    if not uid or not pwd:
        return None
    return {
        "uid": uid,
        "password": pwd,
        "jwt": jwt,
        "region": region,
        "server": server,
        "nickname": nickname,
        "alive": True,
        "likes": 0,
        "level": 0,
        "refreshed": int(time.time()),
    }


def main():
    if not os.path.exists(INPUT):
        print(f"ERROR: {INPUT} not found")
        print("Create it with one JSON account per line, then re-run.")
        sys.exit(1)

    existing = load_existing()
    seen = {g["uid"] for g in existing}

    added = 0
    skipped = 0
    with open(INPUT) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("["):
                continue
            if line.endswith("]"):
                line = line[:-1].strip()
                if not line:
                    continue
            try:
                raw = json.loads(line)
            except Exception:
                # try wrapping trailing commas etc.
                try:
                    raw = json.loads(line + "}")
                except Exception:
                    skipped += 1
                    continue
            norm = normalize(raw)
            if norm is None:
                skipped += 1
                continue
            if norm["uid"] in seen:
                skipped += 1
                continue
            existing.append(norm)
            seen.add(norm["uid"])
            added += 1

    save_pool(existing)
    print(f"Added: {added} | Skipped/dupes: {skipped} | Total in pool: {len(existing)}")
    print(f"Pool saved to: {POOL}")


if __name__ == "__main__":
    main()
