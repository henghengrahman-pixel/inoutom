from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from datetime import datetime, timedelta
import pytz
import json
import os

TOKEN = "8470164747:AAEWD_WjuNjqj1-fiG1DJZ1UFie13_Ajtjs"
ADMIN_IDS = [7755401822, 6925289822, 1890985441, 5397964203, 7230912053, 7714276267, 8851258385]
MAKS_IZIN = 5
TIMEZONE = pytz.timezone("Asia/Jakarta")
IZIN_FILE = "izin.json"

# === BLACKLIST SYSTEM ===
BLACKLIST_FILE = "blacklist.json"
DENDA_SPAM = 500000
MAX_SPAM = 4

blacklist = {}
spam_counter = {}
# =======================

DURASI = {
    "makan": 20,
    "merokok": 10,
    "toilet": 5,
    "bab": 15
}

izin_aktif = {}

def simpan_data():
    with open(IZIN_FILE, "w") as f:
        json.dump(izin_aktif, f, indent=2, default=str)

def load_data():
    global izin_aktif
    if os.path.exists(IZIN_FILE):
        with open(IZIN_FILE, "r") as f:
            raw = json.load(f)
            for uid, data in raw.items():
                izin_aktif[uid] = {
                    "nama": data["nama"],
                    "alasan": data["alasan"],
                    "keluar": datetime.fromisoformat(data["keluar"]),
                    "kembali": datetime.fromisoformat(data["kembali"])
                }

def load_blacklist():
    global blacklist
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f:
            blacklist = json.load(f)

def save_blacklist():
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(blacklist, f, indent=2)

async def kirim_ke_admins(context, pesan: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=pesan,
                parse_mode="Markdown"
            )
        except:
            pass

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    keyboard = [
        [InlineKeyboardButton("🍽️ Makan", callback_data="izin_makan"),
         InlineKeyboardButton("🚬 Merokok", callback_data="izin_merokok")],
        [InlineKeyboardButton("🚽 Toilet", callback_data="izin_toilet"),
         InlineKeyboardButton("💩 BAB", callback_data="izin_bab")]
    ]

    await update.message.reply_text(
        "Silakan pilih jenis izin keluar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_izin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.type not in ["group", "supergroup"]:
        return

    user = query.from_user
    alasan = query.data.replace("izin_", "")
    uid = str(user.id)

    if uid in blacklist:
        return await query.message.reply_text(
            "⛔ Kamu masuk *BLACKLIST*.\n"
            "Tidak bisa menggunakan izin.\n"
            "Hubungi admin.",
            parse_mode="Markdown"
        )

    if uid in izin_aktif:
        return await query.message.reply_text("⚠️ Kamu masih dalam status izin.")

    if len(izin_aktif) >= MAKS_IZIN:
        return await query.message.reply_text("❌ Maksimal 5 orang boleh izin bersamaan.")

    now = datetime.now(TIMEZONE)
    kembali = now + timedelta(minutes=DURASI[alasan])

    izin_aktif[uid] = {
        "nama": user.first_name,
        "alasan": alasan,
        "keluar": now,
        "kembali": kembali
    }
    simpan_data()

    tombol = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Saya Sudah Kembali", callback_data=f"in_{uid}")]
    ])

    await query.message.reply_text(
        f"✅ {user.first_name} izin {alasan} pukul {now.strftime('%H:%M')} WIB.\n"
        f"⏳ Estimasi kembali: {kembali.strftime('%H:%M')}",
        reply_markup=tombol
    )

    await kirim_ke_admins(context, f"📤 {user.first_name} izin {alasan}.")

async def handle_kembali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.type not in ["group", "supergroup"]:
        return

    uid = query.data.replace("in_", "")
    user = query.from_user

    # === SPAM DETECTION (ADMIN ONLY REPORT) ===
    if str(user.id) != uid:
        pelaku = str(user.id)
        spam_counter[pelaku] = spam_counter.get(pelaku, 0) + 1
        jumlah = spam_counter[pelaku]

        pemilik = izin_aktif.get(uid, {}).get("nama", "Tidak diketahui")

        laporan = (
            "🚨 *SPAM TOMBOL KEMBALI*\n\n"
            f"👤 Pelaku: {user.first_name}\n"
            f"🆔 ID: `{user.id}`\n"
            f"👥 Pemilik izin: {pemilik}\n"
            f"🔢 Percobaan: {jumlah}x\n"
            f"⏰ Waktu: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}"
        )

        if jumlah > MAX_SPAM:
            blacklist[pelaku] = {
                "nama": user.first_name,
                "id": user.id,
                "alasan": "Spam tombol kembali",
                "denda": DENDA_SPAM,
                "waktu": datetime.now(TIMEZONE).isoformat()
            }
            save_blacklist()

            laporan += (
                "\n\n⛔ *AUTO BLACKLIST*\n"
                f"💸 Denda: Rp{DENDA_SPAM:,}"
            )

            await kirim_ke_admins(context, laporan)

            return await query.message.reply_text(
                "⛔ Kamu resmi masuk *BLACKLIST*.\n"
                f"💸 Denda: Rp{DENDA_SPAM:,}\n"
                "Hubungi admin.",
                parse_mode="Markdown"
            )

        await kirim_ke_admins(context, laporan)

        return await query.message.reply_text(
            f"❌ Tombol ini bukan milik kamu.\n"
            f"⚠️ Percobaan ke-{jumlah}/{MAX_SPAM}"
        )

    now = datetime.now(TIMEZONE)

    if uid not in izin_aktif:
        return await query.message.reply_text("❌ Data izin tidak ditemukan.")

    data = izin_aktif.pop(uid)
    simpan_data()

    durasi = now - data["keluar"]
    terlambat = now > data["kembali"]
    telat = (now - data["kembali"]).seconds // 60 if terlambat else 0

    denda = 0
    if 1 <= telat <= 9:
        denda = telat * 50000
    elif telat >= 10:
        denda = 500000

    teks = (
        f"👋 {user.first_name} kembali dari {data['alasan']}.\n"
        f"⏱️ Durasi: {str(durasi).split('.')[0]}"
    )

    if denda:
        teks += f"\n⚠️ Terlambat {telat} menit.\n💸 Denda: Rp{denda:,}"

    await query.message.reply_text(teks)
    await kirim_ke_admins(context, teks)

async def auto_kembali(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE)
    auto_remove = []

    for uid, data in izin_aktif.items():
        if now > data["kembali"] + timedelta(minutes=10):
            durasi = now - data["keluar"]
            teks = (
                f"⚠️ {data['nama']} tidak kembali.\n"
                f"Alasan: {data['alasan']}\n"
                f"Durasi: {str(durasi).split('.')[0]}\n"
                f"Denda otomatis: Rp500.000"
            )
            await kirim_ke_admins(context, teks)
            auto_remove.append(uid)

    for uid in auto_remove:
        izin_aktif.pop(uid, None)

    if auto_remove:
        simpan_data()

async def get_id(update, context):
    await update.message.reply_text(
        f"ID kamu: `{update.effective_user.id}`",
        parse_mode="Markdown"
    )

async def status(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not izin_aktif:
        return await update.message.reply_text("✔ Semua sudah kembali.")

    teks = "📋 *Status Izin Aktif:*\n\n"
    for d in izin_aktif.values():
        teks += f"👤 {d['nama']} — {d['alasan']}\n⏳ {d['kembali'].strftime('%H:%M')}\n\n"

    await update.message.reply_text(teks, parse_mode="Markdown")

async def unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ Kamu bukan admin.")

    if not context.args:
        return await update.message.reply_text(
            "Format salah.\nGunakan:\n`/unblacklist ID_USER`",
            parse_mode="Markdown"
        )

    uid = context.args[0].strip()

    if uid in blacklist:
        nama = blacklist[uid].get("nama", "User")
        blacklist.pop(uid, None)
        spam_counter.pop(uid, None)
        save_blacklist()

        teks = (
            f"✅ User berhasil di-unblacklist.\n"
            f"👤 Nama: {nama}\n"
            f"🆔 ID: `{uid}`"
        )
        await update.message.reply_text(teks, parse_mode="Markdown")
        await kirim_ke_admins(context, f"✅ Admin menghapus blacklist:\n👤 {nama}\n🆔 ID: `{uid}`")
    else:
        await update.message.reply_text(
            "⚠️ ID tersebut tidak ada di blacklist.",
            parse_mode="Markdown"
        )

def main():
    load_data()
    load_blacklist()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", show_menu))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("unblacklist", unblacklist))

    app.add_handler(MessageHandler(filters.Regex("^(izin|menu)$"), show_menu))
    app.add_handler(CallbackQueryHandler(handle_izin, pattern="^izin_"))
    app.add_handler(CallbackQueryHandler(handle_kembali, pattern="^in_"))

    app.job_queue.run_repeating(auto_kembali, interval=60, first=10)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
