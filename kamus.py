import asyncio
import logging
import math
import traceback
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ErrorEvent
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- KONFIGURASI ---
TOKEN = "8758513218:AAFpUkoz6haX6qbAa4Fju5w4eg9befqufm8"
DICTIONARY_FILE = "list_10.0.0.txt"
OWNER_ID = 8298238837
LOG_GROUP_ID = -1003031295203
PER_PAGE = 50
DAILY_LIMIT = 3  # Batas pencarian harian untuk user gratis

# --- SILENT LOGGING (Agar VPS/Termux Tetap Diam) ---
logging.basicConfig(level=logging.CRITICAL)

# --- DATABASE SETUP ---
conn = sqlite3.connect("kamus_premium.db")
cursor = conn.cursor()
# Membuat tabel dan memastikan kolom search_count tersedia
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   last_search TEXT, 
                   premium_expiry TEXT,
                   search_count INTEGER DEFAULT 0)''')
conn.commit()

# --- LOADING DATA KAMUS ---
kamus_data = []
try:
    with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
        # Memuat semua kata ke memori dalam huruf besar agar pencarian sangat cepat
        kamus_data = [line.strip().upper() for line in f if line.strip()]
except Exception:
    pass

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FUNGSI DATABASE ---
def get_user_data(user_id):
    cursor.execute("SELECT last_search, premium_expiry, search_count FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    if not data:
        # Jika user baru, masukkan ke database
        cursor.execute("INSERT INTO users (user_id, last_search, premium_expiry, search_count) VALUES (?, ?, ?, ?)", 
                       (user_id, None, "none", 0))
        conn.commit()
        return (None, "none", 0)
    return data

def update_user_search(user_id, count, date_str):
    cursor.execute("UPDATE users SET search_count = ?, last_search = ? WHERE user_id = ?", (count, date_str, user_id))
    conn.commit()

def set_premium_db(user_id, expiry_str):
    cursor.execute("UPDATE users SET premium_expiry = ? WHERE user_id = ?", (expiry_str, user_id))
    conn.commit()

# --- UTILS / PEMBANTU ---
async def delayed_delete(chat_id, message_id):
    """Menghapus pesan otomatis setelah 24 jam"""
    await asyncio.sleep(86400) 
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

def is_user_premium(user_data):
    """Mengecek apakah user memiliki paket premium yang masih aktif"""
    if user_data[1] and user_data[1] != "none":
        try:
            if datetime.fromisoformat(user_data[1]) > datetime.now():
                return True
        except:
            pass
    return False

# --- ERROR HANDLER (Kirim ke Grup Log) ---
@dp.error()
async def error_handler(event: ErrorEvent):
    tb = traceback.format_exc()
    error_text = f"⚠️ **DETEKSI ERROR BOT**\n\n❌ `{event.exception}`\n\n📜 **Traceback:**\n`{tb[:3000]}`"
    try:
        await bot.send_message(chat_id=LOG_GROUP_ID, text=error_text, parse_mode="Markdown")
    except:
        pass

# --- CALLBACK HANDLERS ---
@dp.callback_query(F.data == "tutup_pesan")
async def tutup_pesan(callback: types.CallbackQuery):
    await callback.message.delete()

@dp.callback_query(F.data == "show_premium_info")
async def prem_info(callback: types.CallbackQuery):
    text = (
        "🔐 **DETAIL LAYANAN PREMIUM**\n\n"
        "Buka batasan pencarian harian Anda dengan paket premium:\n"
        "• 7 Hari  : Rp 10.000\n"
        "• 1 Bulan : Rp 30.000\n"
        "• 1 Tahun : Rp 50.000\n\n"
        "Silahkan hubungi Admin untuk aktivasi paket."
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Chat Admin (Aktivasi)", url=f"tg://user?id={OWNER_ID}", style="success"))
    builder.row(InlineKeyboardButton(text="❌ Tutup", callback_data="tutup_pesan", style="danger"))
    
    # Mengedit pesan menjadi info premium
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("page:"))
async def process_page(callback: types.CallbackQuery):
    _, query, page = callback.data.split(":")
    page = int(page)
    results = [word for word in kamus_data if word.startswith(query)]
    total_pages = math.ceil(len(results) / PER_PAGE)
    start_idx = (page - 1) * PER_PAGE
    display_results = results[start_idx : start_idx + PER_PAGE]
    
    response = f"🔍 Hasil Pencarian Kamus Resmi KBBI\n(**{len(results)}** kata ditemukan) - Hal {page}/{total_pages}:\n\n"
    response += "\n".join([f"- {word}" for word in display_results])
    
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.add(InlineKeyboardButton(text="⬅️ Sebelumnya", callback_data=f"page:{query}:{page-1}", style="primary"))
    if page < total_pages:
        builder.add(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"page:{query}:{page+1}", style="success"))
    builder.row(InlineKeyboardButton(text="❌ Tutup", callback_data="tutup_pesan", style="danger"))
    
    await callback.message.edit_text(response, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- ADMIN COMMANDS ---
@dp.message(Command("stats"), F.from_user.id == OWNER_ID)
async def cmd_stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_user = cursor.fetchone()[0]
    
    now_str = datetime.now().isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE premium_expiry != 'none' AND premium_expiry > ?", (now_str,))
    total_prem = cursor.fetchone()[0]
    
    text = f"📈 **Statistik**\n\nUser: {total_user}\nPrem: {total_prem}"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("prem"), F.from_user.id == OWNER_ID)
async def cmd_premium(message: types.Message):
    try:
        args = message.text.split()
        target_id, dur = int(args[1]), args[2]
        now = datetime.now()
        if dur == "+7d": expiry = now + timedelta(days=7)
        elif dur == "+15d": expiry = now + timedelta(days=15)
        elif dur == "+1m": expiry = now + timedelta(days=30)
        elif dur == "+1y": expiry = now + timedelta(days=365)
        set_premium_db(target_id, expiry.isoformat())
        await message.answer(f"✅ User `{target_id}` Berhasil Premium s/d {expiry.date()}")
    except:
        await message.answer("Gunakan: `/prem ID +1m` (+7d, +15d, +1m, +1y)")

@dp.message(Command("e"), F.from_user.id == OWNER_ID)
async def cmd_cancel_prem(message: types.Message):
    try:
        target_id = int(message.text.split()[1])
        set_premium_db(target_id, "none")
        await message.answer(f"❌ Premium user `{target_id}` dicabut.")
    except:
        pass

# --- USER COMMANDS ---
@dp.message(Command("limit"), F.chat.type == "private")
async def limit_handler(message: types.Message):
    uid = message.from_user.id
    user_data = get_user_data(uid)
    
    if is_user_premium(user_data):
        return await message.answer("🌟 Akun Anda adalah **Premium**. Nikmati akses tanpa batas pencarian!")

    today = datetime.now().date().isoformat()
    last_date = user_data[0].split('T')[0] if user_data[0] else ""
    
    # Reset hitungan jika sudah beda hari
    current_count = user_data[2] if last_date == today else 0
    sisa = DAILY_LIMIT - current_count
    
    if sisa > 0:
        text = f"🍋Kabar Baik Akunmu Memiliki Limit {sisa} Pencarian Limit Akan Berkurang Jika Di Gunakan, Dan Akan Bertambah Secara Otomatis Setelah 1×24 Jam"
    else:
        text = "🫩Kamu Sudah Memakai Limit Pemakaian Silahkan Tambahkan Limit Jika Membutuhkan"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📈 Prem", callback_data="show_premium_info", style="primary"))
    await message.answer(text, reply_markup=builder.as_markup())

@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    welcome_text = (
        "👋 **Selamat Datang di Kamus Resmi KBBI!**\n\n"
        "Ini adalah bot database **Kamus Besar Bahasa Indonesia (KBBI) Resmi** yang digunakan sebagai acuan validitas kata.\n\n"
        "📖 **Instruksi Penggunaan:**\n"
        "Cukup ketikkan **Huruf Depan** kata kunci yang ingin Anda cari.\n"
        "└─ Contoh: ketik `NG` untuk melihat semua kata berawalan NG.\n\n"
        "📑 **Navigasi Menu:**\n"
        "Setiap hasil pencarian dapat Anda navigasi melalui tombol di bawah pesan tanpa menumpuk chat.\n\n"
        "⚠️ **Ketentuan:**\n"
        "• Bot melayani pencarian di **Chat Pribadi**.\n"
        "• Database mencakup 112.000+ kosa kata baku.\n\n"
        "📌 **Didukung oleh:** [Drakweb Support](https://t.me/drakwebot)"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👨‍💻 Developer", url=f"tg://user?id={OWNER_ID}", style="danger"))
    builder.row(InlineKeyboardButton(text="➕ Main Sambung Kata", url="https://t.me/bungkatabot?startgroup=start", style="success"))
    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown", disable_web_page_preview=True)

# --- PENCARIAN UTAMA ---
@dp.message(F.chat.type == "private")
async def search_handler(message: types.Message):
    if not message.text or message.text.startswith("/"): return
    uid = message.from_user.id
    user_data = get_user_data(uid)
    
    is_premium = is_user_premium(user_data)
    today = datetime.now().date().isoformat()
    last_date = user_data[0].split('T')[0] if user_data[0] else ""
    
    # Hitung limit hari ini
    current_count = user_data[2] if last_date == today else 0
    
    if not is_premium and current_count >= DAILY_LIMIT:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔐 PREMIUM", callback_data="show_premium_info", style="primary"))
        builder.row(InlineKeyboardButton(text="❌ Tutup", callback_data="tutup_pesan", style="danger"))
        return await message.answer(
            "⚠️ **Limit Harian Terlampaui**\nJadikan akunmu sebagai akun premium di kamus KBBI agar membuka limit harian.", 
            reply_markup=builder.as_markup(), 
            parse_mode="Markdown", 
            protect_content=True
        )

    query = message.text.strip().upper()
    results = [word for word in kamus_data if word.startswith(query)]
    
    if not results:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="❌ Tutup", callback_data="tutup_pesan", style="danger"))
        return await message.answer(f"❌ Kata berawalan **{query}** tidak ditemukan di KBBI Resmi.", reply_markup=builder.as_markup(), parse_mode="Markdown")

    # Update limit jika bukan premium
    if not is_premium:
        update_user_search(uid, current_count + 1, datetime.now().isoformat())

    total_pages = math.ceil(len(results) / PER_PAGE)
    response = f"🔍 Hasil Pencarian Kamus Resmi KBBI\n(**{len(results)}** kata ditemukan) - Hal 1/{total_pages}:\n\n"
    response += "\n".join([f"- {word}" for word in results[:PER_PAGE]])
    
    builder = InlineKeyboardBuilder()
    if total_pages > 1:
        builder.add(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"page:{query}:2", style="success"))
    builder.row(InlineKeyboardButton(text="❌ Tutup", callback_data="tutup_pesan", style="danger"))
    
    msg = await message.answer(response, reply_markup=builder.as_markup(), parse_mode="Markdown")
    # Jalankan tugas hapus otomatis 24 jam di latar belakang
    asyncio.create_task(delayed_delete(message.chat.id, msg.message_id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
