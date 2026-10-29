# -*- coding: utf-8 -*-
"""FF Like Telegram Bot - zip er LIKE~BOT~SRC er style e, kintu amader working pool engine diye."""
import asyncio, json, sys, os, time, logging
from datetime import date
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import uid_generator_pb2, visit_count_pb2, like_pb2
import ff_core
from ff_core import MAIN_KEY, MAIN_IV, create_jwt

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:
    print("pip install python-telegram-bot httpx pycryptodome protobuf")
    sys.exit(1)

TOKEN = os.environ.get("FFLIKE_BOT_TOKEN") or (lambda: json.load(open(os.path.join(BASE_DIR, "tg_bot_config.json")))["BOT_TOKEN"])()
ADMIN_IDS = [7176002628]

DIR = BASE_DIR
POOL = os.path.join(DIR, "likesender", "pool.json")
USED = os.path.join(DIR, "likesender", "used_daily.json")
LIMITS = os.path.join(DIR, "user_limits.json")
CONFIG = os.path.join(DIR, "bot_config.json")
HOST = "https://clientbp.ggpolarbear.com"

logging.basicConfig(level=logging.INFO)


def aes_enc(d): return AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV).encrypt(pad(d, 16))
def enc_uid(u):
    m = uid_generator_pb2.uid_generator(); m.saturn_ = int(u); m.garena = 1
    return aes_enc(m.SerializeToString())
def enc_like(u, r):
    raw = b"\x08" + ff_core.pb_varint(int(u)) + b"\x12" + ff_core.pb_varint(len(r)) + r.upper().encode()
    return aes_enc(raw)
def H(jwt):
    return {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)", "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {jwt}", "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1", "ReleaseVersion": "OB54"}


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def today_str():
    return str(date.today())


def is_admin(uid):
    return int(uid) in ADMIN_IDS


def get_config():
    c = load_json(CONFIG, {})
    c.setdefault("status", "on")
    c.setdefault("limit", 2)
    return c


def can_user_like(uid):
    if is_admin(uid):
        return True
    c = get_config()
    t = today_str()
    u = load_json(LIMITS, {})
    if uid not in u or u[uid].get("date") != t:
        u[uid] = {"date": t, "count": 0}
        save_json(LIMITS, u)
        return True
    return u[uid]["count"] < c["limit"]


def update_user_like(uid):
    if is_admin(uid):
        return
    t = today_str()
    u = load_json(LIMITS, {})
    if uid not in u or u[uid].get("date") != t:
        u[uid] = {"date": t, "count": 0}
    u[uid]["count"] += 1
    save_json(LIMITS, u)


def user_usage(uid):
    if is_admin(uid):
        return None
    t = today_str()
    u = load_json(LIMITS, {})
    if uid in u and u[uid].get("date") == t:
        return u[uid]["count"]
    return 0


# ============ HANDLERS ============

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) and update.effective_chat.type == "private":
        await update.message.reply_text("🚫 *Bot works only in groups!*\n(Admins can use in private)", parse_mode="Markdown")
        return
    c = get_config()
    if c["status"] == "off":
        await update.message.reply_text("🔴 *Bot is currently OFF*", parse_mode="Markdown")
        return
    msg = (
        "✨ *𝑭𝑹𝑬𝑬 𝑭𝑰𝑹𝑬 𝑳𝑰𝑲𝑬 𝑩𝑶𝑻* ✨\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "💬 `/like REGION UID` – Send a like\n"
        "💬 `/help` – Show all commands\n"
        "💬 `/info` – Your remaining likes\n\n"
        "📌 *Example:* `/like BD 9261851398`\n"
        f"🔥 Your daily limit: `{c['limit']}` likes\n"
        "⚠️ *Shudhu BD region target e kaj kore*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) and update.effective_chat.type == "private":
        await update.message.reply_text("🚫 *Bot works only in groups!*", parse_mode="Markdown")
        return
    msg = (
        "📖 *𝑪𝑶𝑴𝑴𝑨𝑵𝑫 𝑳𝑰𝑺𝑻*\n\n"
        "🔹 `/like REGION UID` – Send 1 like\n"
        "🔹 `/info` – Check your remaining likes\n"
        "🔹 `/start` – Welcome message\n\n"
        "*Example:* `/like BD 9261851398`\n\n"
        "👑 *Admin commands:*\n"
        "`/off` / `/on` – Bot off/on\n"
        "`/stats` – Today's usage\n"
        "`/setlimit <num>` – Set daily limit per user"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def info_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) and update.effective_chat.type == "private":
        await update.message.reply_text("🚫 *Bot works only in groups!*", parse_mode="Markdown")
        return
    c = get_config()
    uid = update.effective_user.id
    if is_admin(uid):
        await update.message.reply_text("👑 *Admin Account*\n🔥 *Unlimited likes* – No daily limit.", parse_mode="Markdown")
        return
    used = user_usage(uid)
    msg = (
        "🤖 *𝑩𝑶𝑻 𝑰𝑵𝑭𝑶*\n\n"
        f"🟢 Status: `{c['status'].upper()}`\n"
        f"📅 Daily limit: `{c['limit']}` likes\n"
        f"✅ Used today: `{used}`\n"
        f"🟢 Remaining: `{c['limit'] - used}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def like_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id) and update.effective_chat.type == "private":
        await update.message.reply_text("🚫 *Bot works only in groups!*", parse_mode="Markdown")
        return
    c = get_config()
    if c["status"] == "off":
        await update.message.reply_text("🔴 *Bot is currently OFF*", parse_mode="Markdown")
        return

    args = ctx.args
    if len(args) != 2:
        await update.message.reply_text("❌ *Usage:* `/like REGION UID`\nExample: `/like BD 9261851398`", parse_mode="Markdown")
        return
    region = args[0].upper()
    uid = args[1]
    if not uid.isdigit():
        await update.message.reply_text("❌ *UID must contain only numbers!*", parse_mode="Markdown")
        return
    if region != "BD":
        await update.message.reply_text("⚠️ *Shudhu BD region e kaj kore!*\nExample: `/like BD 9261851398`", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    if not can_user_like(user_id):
        used = user_usage(user_id)
        await update.message.reply_text(
            f"⚠️ *Daily limit reached!*\nYou have used `{used}/{c['limit']}` likes today.\n💡 Try again tomorrow.",
            parse_mode="Markdown")
        return

    proc = await update.message.reply_text(f"🔄 *Step 1/4:* Authenticating guest account…\nUID: `{uid}`\nRegion: `{region}`", parse_mode="Markdown")
    pool = load_json(POOL, [])
    if not pool:
        await proc.edit_text("❌ *Pool khali!* Owner-ke janan.", parse_mode="Markdown")
        return

    used_by_target = load_json(USED, {})
    day = today_str()
    used_set = used_by_target.setdefault(day, {}).setdefault(uid, {})
    acc = next((a for a in pool if not used_set.get(a["uid"])), None)
    if not acc:
        await proc.edit_text("⚠️ *Ajke sob account use hoye geche!*\nKal abar chasun.", parse_mode="Markdown")
        return

    jwt = None
    lr = None
    srv = None
    async with httpx.AsyncClient() as c_http:
        try:
            await proc.edit_text(f"🔄 *Step 2/4:* Generating JWT…\nUID: `{uid}`\nRegion: `{region}`", parse_mode="Markdown")
            jwt, lr, srv = await create_jwt(c_http, acc["uid"], acc["password"])
            acc["refreshed"] = int(time.time())
            acc["region"], acc["server"] = lr, srv
            acc["jwt"] = jwt
            save_json(POOL, pool)
        except Exception as e:
            await proc.edit_text(f"❌ *Auth failed:* {str(e)[:80]}", parse_mode="Markdown")
            return

        before = None
        info = None
        try:
            await proc.edit_text(f"🔄 *Step 3/4:* Fetching player info…\nUID: `{uid}`\nRegion: `{region}`", parse_mode="Markdown")
            r = await c_http.post(f"{HOST}/GetPlayerPersonalShow", data=enc_uid(uid), headers=H(jwt), timeout=20)
            if r.status_code == 200:
                p = visit_count_pb2.Info(); p.ParseFromString(r.content)
                info = p.AccountInfo
                before = info.Likes
        except Exception as e:
            await proc.edit_text(f"❌ *Info error:* {str(e)[:80]}", parse_mode="Markdown")
            return

        status = "fail"
        try:
            await proc.edit_text(f"🔄 *Step 4/4:* Sending like…\nUID: `{uid}`\nRegion: `{region}`", parse_mode="Markdown")
            r = await c_http.post(f"{HOST}/LikeProfile", data=enc_like(uid, region), headers=H(jwt), timeout=25)
            status = "ok" if r.status_code == 200 else f"HTTP {r.status_code}"
        except Exception as e:
            status = str(e)[:40]
        used_set[acc["uid"]] = True
        save_json(USED, used_by_target)

        after = None
        try:
            r = await c_http.post(f"{HOST}/GetPlayerPersonalShow", data=enc_uid(uid), headers=H(jwt), timeout=20)
            if r.status_code == 200:
                p = visit_count_pb2.Info(); p.ParseFromString(r.content)
                after = p.AccountInfo.Likes
        except Exception:
            pass
    if status == "ok":
        update_user_like(user_id)
        used_now = user_usage(user_id)
        given = (after - before) if (before is not None and after is not None) else "?"
        nick = info.PlayerNickname if info else "Unknown"
        level = info.Levels if info else "N/A"
        result = (
            f"✅ *𝑳𝑰𝑲𝑬 𝑺𝑬𝑵𝑻* ✅\n\n"
            f"👤 *Player:* {nick}\n"
            f"🏷️ *UID:* `{uid}`\n"
            f"🌍 *Region:* {region}\n"
            f"⭐ *Level:* {level}\n\n"
            f"❤️ *Likes given:* +{given}\n"
            f"📊 *Total:* {before} → {after}\n\n"
            f"📅 *Your usage:* {used_now}/{c['limit'] if not is_admin(user_id) else '∞'}\n"
            f"🎉 *Success!*"
        )
    else:
        result = f"❌ *FAILED:* {status}"
    try:
        await proc.edit_text(result, parse_mode="Markdown")
    except Exception:
        await proc.edit_text(result)


# ============ ADMIN COMMANDS ============

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    pool = load_json(POOL, [])
    used = load_json(USED, {})
    day = today_str()
    sent = sum(len(used.get(day, {}).get(t, {})) for t in used.get(day, {}))
    await update.message.reply_text(
        f"📊 *STATS*\n\n"
        f"🗄️ Pool: `{len(pool)}` accounts\n"
        f"📅 Ajke like pathano: `{sent}`\n"
        f"🟢 Status: `{get_config()['status'].upper()}`",
        parse_mode="Markdown")


async def setlimit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Usage: `/setlimit 5`", parse_mode="Markdown")
        return
    c = get_config()
    c["limit"] = int(ctx.args[0])
    save_json(CONFIG, c)
    await update.message.reply_text(f"✅ Daily limit set to `{c['limit']}`", parse_mode="Markdown")


async def onoff(update: Update, ctx: ContextTypes.DEFAULT_TYPE, status):
    if not is_admin(update.effective_user.id):
        return
    c = get_config()
    c["status"] = status
    save_json(CONFIG, c)
    await update.message.reply_text(f"{'🟢' if status == 'on' else '🔴'} Bot is now `{status.upper()}`", parse_mode="Markdown")


def main():
    app = Application.builder().token(TOKEN).read_timeout(90).connect_timeout(20).write_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("like", like_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("setlimit", setlimit))
    app.add_handler(CommandHandler("on", lambda u, c: onoff(u, c, "on")))
    app.add_handler(CommandHandler("off", lambda u, c: onoff(u, c, "off")))

    async def err_handler(update, context):
        try:
            err = context.error
            print(f"ERROR: {type(err).__name__}: {str(err)[:120]}", flush=True)
            if update and update.effective_message:
                try:
                    # Try editing the existing message first (in case a "Processing..." is pending)
                    msg = update.effective_message
                    if msg.text and "Processing" in msg.text:
                        try:
                            await msg.edit_text(f"⚠️ Error: {str(err)[:80]}", parse_mode="Markdown")
                        except Exception:
                            await msg.edit_text(f"⚠️ Error: {str(err)[:80]}")
                    else:
                        await update.effective_message.reply_text(f"⚠️ Error: {str(err)[:80]}")
                except Exception:
                    pass
        except Exception:
            pass
    app.add_error_handler(err_handler)

    try:
        httpx.post(f"https://api.telegram.org/bot{TOKEN}/setMyCommands",
                   json={"commands": [
                       {"command": "like", "description": "Like pathay: /like REGION UID"},
                       {"command": "info", "description": "Remaining likes"},
                       {"command": "help", "description": "Command list"},
                       {"command": "start", "description": "Start"},
                   ]}, timeout=15)
    except Exception:
        pass
    print("FF Like Bot polling...", flush=True)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
