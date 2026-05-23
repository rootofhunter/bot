import os
import sys
import subprocess
import json
import datetime
import time
import sqlite3

# --- Auto Installer ---
def setup_environment():
    packages = ["pyTelegramBotAPI", "phonenumbers"]
    for pkg in packages:
        try:
            __import__(pkg.replace("pyTelegramBotAPI", "telebot"))
        except ImportError:
            print(f"⏳ Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", pkg])

setup_environment()

import telebot
from telebot import types
import phonenumbers

# ==================== CONFIG ====================
BOT_TOKEN = "7975206888:AAGQd0sLHTV4bUB0_nWqZfbGb58aEb29RlQ"
ADMIN_ID = 5360189030
DB_FILE = "bot_database.db"

bot = telebot.TeleBot(BOT_TOKEN)

admin_states = {}
user_search_state = {}

# ====================== SQLite ======================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nid TEXT UNIQUE,
        name TEXT,
        phone TEXT,
        dob TEXT,
        operator TEXT DEFAULT "Unknown",
        status TEXT DEFAULT "Verified",
        account_type TEXT DEFAULT "Premium",
        date INTEGER
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        coins INTEGER DEFAULT 10,
        rank TEXT DEFAULT "FREE USER",
        last_bonus INTEGER DEFAULT 0,
        history TEXT DEFAULT "[]"
    )''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def add_record(nid, name, phone, dob="N/A", operator="Unknown"):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''INSERT OR IGNORE INTO records 
            (nid, name, phone, dob, operator, date) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (str(nid).strip(), str(name).strip(), str(phone).strip(), 
             str(dob).strip(), str(operator).strip(), int(time.time())))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def search_record(query):
    conn = get_db_connection()
    cur = conn.cursor()
    q = f"%{query}%"
    cur.execute('''SELECT nid, name, phone, dob, operator, status, account_type, date 
                   FROM records 
                   WHERE nid LIKE ? OR phone LIKE ? OR name LIKE ? 
                   LIMIT 1''', (q, q, q))
    result = cur.fetchone()
    conn.close()
    return result

def get_total_records():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM records")
    return cur.fetchone()[0]

def get_user_profile(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT coins, rank, last_bonus, history FROM users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (str(user_id),))
        conn.commit()
        return {"coins": 10, "rank": "FREE USER", "last_bonus": 0, "history": []}
    return {"coins": row[0], "rank": row[1], "last_bonus": row[2], "history": json.loads(row[3])}

def update_user_profile(user_id, profile):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''UPDATE users SET coins=?, rank=?, last_bonus=?, history=? WHERE user_id=?''',
                (profile["coins"], profile["rank"], profile["last_bonus"], json.dumps(profile["history"]), str(user_id)))
    conn.commit()
    conn.close()

def is_valid_phone_number(raw):
    if not raw: return False, None, None
    try:
        parsed = phonenumbers.parse(raw, "BD") if not raw.startswith('+') else phonenumbers.parse(raw)
        if phonenumbers.is_valid_number(parsed):
            return True, phonenumbers.region_code_for_number(parsed), phonenumbers.geocoder.description_for_number(parsed, "en")
    except:
        pass
    cleaned = ''.join(filter(str.isdigit, raw))
    if cleaned.isdigit() and 3 <= len(cleaned) <= 17:
        return True, "ID", "Bangladesh"
    return False, None, None

# ====================== Keyboards ======================
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("🔎 Number Info Search"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("👑 ADMIN DATABASE PANEL"))
    else:
        markup.add(types.KeyboardButton("📂 SECURITY DATABASE INFO"))
    markup.row(types.KeyboardButton("💳 MY WALLET"), types.KeyboardButton("🎁 DAILY REWARD"))
    markup.row(types.KeyboardButton("🕘 SEARCH HISTORY"), types.KeyboardButton("👤 USER PROFILE"))
    markup.row(types.KeyboardButton("📊 LIVE SERVER STATS"), types.KeyboardButton("🛠️ CORE SUPPORT"))
    markup.add(types.KeyboardButton("🔙 TERMINAL RESET (HOME)"))
    return markup

def get_admin_menu():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📤 Upload JSON Bulk DB"),
        types.KeyboardButton("➕ Add Single Entry"),
        types.KeyboardButton("📊 Database Live Stats"),
        types.KeyboardButton("🗑️ WIPE / DELETE DATABASE"),
        types.KeyboardButton("🔙 Back to Main Terminal")
    )
    return markup

# ====================== MAIN HANDLER (FIXED) ======================
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    user_id = message.from_user.id
    text = message.text.strip()

    # === SEARCH BUTTON ===
    if text == "🔎 Number Info Search":
        user_search_state[user_id] = "waiting_for_number"
        bot.send_message(message.chat.id, "🔎 Send Phone Number, NID or Name:", parse_mode="Markdown")
        return

    # === ADMIN BUTTONS ===
    if text == "👑 ADMIN DATABASE PANEL" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "👑 **ADMIN PANEL**", reply_markup=get_admin_menu())
        return

    if text == "📤 Upload JSON Bulk DB" and user_id == ADMIN_ID:
        admin_states[user_id] = "waiting_for_json"
        bot.send_message(message.chat.id, "📤 Send database.json file:")
        return

    if text == "📊 Database Live Stats" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Total Records: `{get_total_records()}`", parse_mode="Markdown")
        return

    if text == "🗑️ WIPE / DELETE DATABASE" and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(types.KeyboardButton("🔴 Yes, Delete Everything"), types.KeyboardButton("🟢 No, Cancel"))
        bot.send_message(message.chat.id, "⚠️ Delete everything?", reply_markup=markup)
        return

    if text == "🔴 Yes, Delete Everything" and user_id == ADMIN_ID:
        conn = get_db_connection()
        conn.execute("DELETE FROM records")
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🗑️ Database wiped!", reply_markup=get_main_menu(user_id))
        return

    if text in ["🟢 No, Cancel", "🔙 Back to Main Terminal", "🔙 TERMINAL RESET (HOME)"]:
        admin_states.pop(user_id, None)
        user_search_state.pop(user_id, None)
        bot.send_message(message.chat.id, "✅ Main Menu", reply_markup=get_main_menu(user_id))
        return

    # ====================== SEARCH LOGIC (STRONG) ======================
    if user_search_state.get(user_id) == "waiting_for_number" or text.replace("+", "").replace(" ", "").isdigit() or len(text) > 8:
        profile = get_user_profile(user_id)
        is_valid, _, location = is_valid_phone_number(text)

        if user_id != ADMIN_ID and profile.get("rank") != "VIP USER":
            if profile["coins"] < 1:
                bot.send_message(message.chat.id, "❌ Insufficient coins!", reply_markup=get_main_menu(user_id))
                user_search_state.pop(user_id, None)
                return

        result = search_record(text)

        if result:
            nid, name, phone, dob, operator, status, acc_type, date_ts = result

            if user_id != ADMIN_ID and profile.get("rank") != "VIP USER":
                profile["coins"] -= 1
                history = profile["history"]
                if len(history) >= 15: history.pop(0)
                history.append(f"{text} - Found")
                update_user_profile(user_id, profile)

            response = f"""📡 **MATCH FOUND** 📡

📛 **Name**: {name}
💳 **NID**: `{nid}`
📞 **Phone**: `{phone}`
📅 **DOB**: {dob}
🛰️ **Operator**: {operator}
🌍 **Location**: {location}
🔐 **Status**: {status}
💎 **Type**: {acc_type}
🕘 **Date**: {datetime.datetime.fromtimestamp(date_ts).strftime('%Y-%m-%d %H:%M')}
"""
            bot.send_message(message.chat.id, response, parse_mode="Markdown", reply_markup=get_main_menu(user_id))
        else:
            if user_id != ADMIN_ID and profile.get("rank") != "VIP USER":
                history = profile["history"]
                if len(history) >= 15: history.pop(0)
                history.append(f"{text} - Not Found")
                update_user_profile(user_id, profile)
            bot.send_message(message.chat.id, "❌ No record found in database.", parse_mode="Markdown", reply_markup=get_main_menu(user_id))

        user_search_state.pop(user_id, None)
        return

    # Fallback
    bot.send_message(message.chat.id, "🤖 Use keyboard buttons below.", reply_markup=get_main_menu(user_id))

# Document Handler (JSON Upload)
@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.from_user.id != ADMIN_ID or admin_states.get(message.from_user.id) != "waiting_for_json":
        return
    # ... (keep your previous validation logic here) ...

if __name__ == "__main__":
    print("🚀 BOT STARTED - Search Fixed")
    bot.infinity_polling()