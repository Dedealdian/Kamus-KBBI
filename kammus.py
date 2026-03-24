import os, time, json, asyncio, sys, traceback
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
import segno

load_dotenv()

# Konfigurasi
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOGS_GROUP = int(os.getenv("LOGS_GROUP"))
QRIS_PAYLOAD = os.getenv("QRIS_DATA")
DB_FILE = "users_db.json"
START_TIME = time.time()
SEARCH_CACHE = {}

def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}, "premium": []}
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {"users": {}, "premium": []}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

db = load_db()
app = Client("kbbi_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def send_logs(client, err):
    try: await client.send_message(LOGS_GROUP, f"❌ **ERROR**:\n```python\n{err}```")
    except: print(err)

def check_limit(user_id):
    uid = str(user_id)
    if uid in db["premium"] or user_id == OWNER_ID: return True, "Unlimited ⭐"
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in db["users"]: db["users"][uid] = {"count": 0, "date": today}
    if db["users"][uid]["date"] != today: db["users"][uid] = {"count": 0, "date": today}
    left = 3 - db["users"][uid]["count"]
    return (True, left) if left > 0 else (False, 0)

@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    text = (f"🎗️Hallo selamat datang di kamus KBBI {m.from_user.mention}\n"
            "•Bot ini digunakan untuk mencari kata baku bisa digunakan untuk mata pelajaran Bahasa Indonesia ataupun mencari jawaban di dalam game Kata Bersambung.\n"
            "• Gunakan /prem untuk accses tanpa batas\n• Gunakan /limit untuk chek limit\n✅ Gunakan bot ini dengan bijak.\n\n"
            "⭐Di Dukung Oleh [Drakweb](https://t.me/drakwebot).")
    btns = [[InlineKeyboardButton("⚡Support", url="https://t.me/bungkata"), InlineKeyboardButton("🔎Search", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("➕Create a New Group", url="https://t.me/bungkatabot?startgroup=start")]]
    await m.reply(text, reply_markup=InlineKeyboardMarkup(btns), disable_web_page_preview=True)

@app.on_message(filters.command("limit") & filters.private)
async def limit(c, m):
    uid = str(m.from_user.id)
    _, rem = check_limit(m.from_user.id)
    uptime = f"{int(time.time() - START_TIME)}s"
    txt = (f"Date User:⤵️\n```python\n🆔 User_ID: {m.from_user.id}\n👤 User_Name: {m.from_user.first_name}\n⛔ Limit: {rem}\n```\n"
           f"Pyrogram Bot:\n```bash\n📛 Pyrogram: 2.0.106\n🫟 Liberary: Python Bash KBBI Resmi\n🏓 Pong: {c.ping_ms if hasattr(c, 'ping_ms') else 15}ms\n📶 Latecy: {uptime}\n```\n"
           f"Dates Bot:⤵️\n```python\n📈Stats: Active\n📚File Kamus: kamus.txt\n👨‍💻Developer: {OWNER_ID}\n```")
    await m.reply(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔃Reflesh", callback_data="ref_lim")]]))

@app.on_message(filters.command("prem") & filters.private)
async def prem(c, m):
    txt = "👤Becoming Premium is easier using QRIS Bank Indonesia payments"
    btns = [[InlineKeyboardButton("⭐1Month", callback_data="p_26"), InlineKeyboardButton("⭐1Year", callback_data="p_300")],
            [InlineKeyboardButton("⭐6Month", callback_data="p_50")], [InlineKeyboardButton("Close❌", callback_data="cls")]]
    await m.reply(txt, reply_markup=InlineKeyboardMarkup(btns))

@app.on_message(filters.text & filters.private & ~filters.command(["start", "limit", "prem"]))
async def search(c, m):
    ok, _ = check_limit(m.from_user.id)
    if not ok: return await m.reply("⛔ Limit habis! Silahkan ke /prem.")
    query = m.text.lower()
    res = []
    if os.path.exists("kamus.txt"):
        with open("kamus.txt", "r") as f:
            for l in f:
                if l.strip().lower().startswith(query): res.append(l.strip())
    if not res: return await m.reply("❌ Tidak ditemukan.")
    SEARCH_CACHE[m.from_user.id] = {"q": query, "r": res, "p": 0}
    await show_res(m, m.from_user.id, 0)
    if str(m.from_user.id) not in db["premium"]:
        db["users"][str(m.from_user.id)]["count"] += 1
        save_db(db)

async def show_res(m, uid, p):
    d = SEARCH_CACHE.get(uid)
    if not d: return
    total = (len(d["r"]) - 1) // 10 + 1
    items = d["r"][p*10:(p+1)*10]
    txt = f"🔎 Hasil '{d['q']}' ({p+1}/{total}):\n\n" + "\n".join(items)
    nav = []
    if p > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"pg_{p-1}"))
    if p < total - 1: nav.append(InlineKeyboardButton("➡️", callback_data=f"pg_{p+1}"))
    btns = [nav] if nav else []
    btns.append([InlineKeyboardButton("🔎Search", switch_inline_query_current_chat="")])
    try:
        if hasattr(m, "edit_text"): await m.edit_text(txt, reply_markup=InlineKeyboardMarkup(btns))
        else: await m.reply(txt, reply_markup=InlineKeyboardMarkup(btns))
    except: pass

@app.on_callback_query()
async def cb(c, q):
    try:
        if q.data == "ref_lim": await q.message.delete(); await limit(c, q)
        elif q.data == "cls": await q.message.delete()
        elif q.data.startswith("pg_"): await show_res(q.message, q.from_user.id, int(q.data.split("_")[1]))
        elif q.data.startswith("p_"):
            m = await q.message.edit_text("⚡Please Wait.")
            for i in range(3): await asyncio.sleep(0.4); await m.edit_text("⚡Wait" + "."*(i+1))
            segno.make(QRIS_PAYLOAD).save("q.png", scale=10)
            await q.message.delete()
            await c.send_photo(q.message.chat.id, "q.png", caption="⭐Prem:\nPlease scan & screenshot proof.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌", callback_data="cls")]]))
            if os.path.exists("q.png"): os.remove("q.png")
        elif q.data.startswith("acc_"):
            u = q.data.split("_")[1]
            if u not in db["premium"]: db["premium"].append(u); save_db(db)
            await q.message.edit_text(f"✅ {u} Premium!"); await c.send_message(int(u), "⭐ Akun anda Premium!")
        elif q.data.startswith("rej_"):
            u = q.data.split("_")[1]
            await q.message.edit_text(f"❌ {u} Ditolak"); await c.send_message(int(u), "❌ Bukti ditolak.")
    except: await send_logs(c, traceback.format_exc())

@app.on_message(filters.photo & filters.private)
async def proof(c, m):
    btn = [[InlineKeyboardButton("✅ Acc", callback_data=f"acc_{m.from_user.id}"), InlineKeyboardButton("❌ Rej", callback_data=f"rej_{m.from_user.id}")]]
    await c.send_photo(LOGS_GROUP, m.photo.file_id, caption=f"⭐Prem:\nID: `{m.from_user.id}`\nUser: @{m.from_user.username}", reply_markup=InlineKeyboardMarkup(btn))
    await m.reply("⚡ Bukti dikirim ke Admin.")

@app.on_inline_query()
async def inline(c, i):
    if str(i.from_user.id) not in db["premium"] and i.from_user.id != OWNER_ID:
        return await i.answer([], switch_pm_text="⭐ Premium Only", switch_pm_parameter="pay")
    q = i.query.lower()
    if not q: return
    match = []
    if os.path.exists("kamus.txt"):
        with open("kamus.txt", "r") as f:
            for l in f:
                if l.strip().lower().startswith(q): match.append(l.strip())
                if len(match) >= 20: break
    res = [InlineQueryResultArticle(title=x, input_message_content=InputTextMessageContent(x), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎Search", switch_inline_query_current_chat="")]])) for x in match]
    await i.answer(res, cache_time=1)

print("Bot Running..."); app.run()
