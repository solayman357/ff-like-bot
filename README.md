# FF Daily Like Bot — 220 Likes/Day System

Sends likes to your Free Fire UID **daily** using guest accounts.
No external token service needed — JWTs are generated locally
(only Garena's official OAuth + MajorLogin endpoints are used).

## How it works

- Each guest account can send **1 like per target per 24h**
- The bot generates a JWT for every guest account (locally, AES-CBC + protobuf)
- Sends likes concurrently (default 15/sec)
- Tracks which guest already liked today in `usage_daily.json`
- Usage **auto-resets at midnight** → every day you get ~N likes,
  where N = number of guest accounts in `guest_accounts.json`

**To get 220 likes/day → put 220+ guest accounts in the list.**

## Requirements

```bash
pip3 install --break-system-packages httpx pycryptodome
```

## Step 1 — Add guest accounts

Edit `guest_accounts.json`:

```json
[
  {"uid": "1000000001", "password": "AAAA...31"},
  {"uid": "1000000002", "password": "BBBB...42"}
]
```

Or interactively:

```bash
python3 add_guests.py
```

### Where to get guest accounts
1. Install Free Fire on Android/emulator, login as **Guest** → new account is created
2. After playing a few seconds, use `guest to bind` flow or an extractor app
   (e.g. FF tools/EXplorer) to export UID + password hash
3. Repeat for each account (100–220 accounts for 100–220 likes/day)
4. Telegram groups that sell FF guest account lists also work

## Step 2 — Run the daily bot

```bash
python3 ff_bot.py <your_uid> <region> <likes_per_day> <concurrency>
```

Example (220 likes/day, IND region):

```bash
python3 ff_bot.py 1234567890 IND 220 15
```

- `<your_uid>` — the UID you want to receive likes on
- `<region>` — IND, BR, SG, EU, BD, PK, VN, TH, ID, TW, ME, RU...
- `<likes_per_day>` — default 220
- `<concurrency>` — likes sent per second (10–30 recommended)

## Step 3 — Run daily automatically

Add to crontab (runs every day at 2 AM):

```bash
crontab -e
```

```
0 2 * * * cd /root/fflikes-bot && python3 ff_bot.py 1234567890 IND 220 15 >> likes.log 2>&1
```

## Verify likes

```bash
python3 check_likes.py 1234567890 IND
```

## Notes

- Each guest can like the same target only once per 24h (Garena rule)
- Free Fire caps ~100 guest likes per profile per 24h from one server pool;
  use guest accounts from multiple regions (IND + SG + BR...) to push higher
- Public sample account in `guest_accounts.json` is blocked — replace it
- If an account returns "blocked/temp-banned", remove it from the list

## Files

| File | Purpose |
|------|---------|
| `ff_core.py` | Core: protobuf, AES, JWT generation, like sending |
| `ff_bot.py` | Main daily bot |
| `add_guests.py` | Add guest accounts interactively |
| `check_likes.py` | Check current like count of a UID |
| `guest_accounts.json` | Your guest account pool |
| `usage_daily.json` | Auto-tracking of daily usage (resets at midnight) |
