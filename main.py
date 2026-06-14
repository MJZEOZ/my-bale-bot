import os
import requests
import sqlite3
import json
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
REQUIRED_CHANNEL = "@wamsara"

# --- مدیریت دیتابیس (برای ماندگاری داده‌ها) ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    # جدول نظرسنجی‌ها
    cursor.execute('''CREATE TABLE IF NOT EXISTS polls 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id TEXT, question TEXT, 
         options TEXT, votes TEXT, voters TEXT, img_id TEXT)''')
    conn.commit()
    conn.close()

init_db()

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

user_state = {}

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET": return "Bot is Online", 200
    update = request.get_json(silent=True)
    if not update: return "ok", 200

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = str(msg["from"]["id"])
        text = msg.get("text", "")

        if text == "/start":
            user_state[user_id] = None
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": "🌟 به پنل مدیریت خوش آمدید. گزینه مورد نظر را انتخاب کنید:",
                "reply_markup": {
                    "keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}], [{"text": "📊 نظرسنجی‌های من"}]],
                    "resize_keyboard": True
                }
            })

        elif text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q", "opts": []}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "🔴 سوال نظرسنجی را بنویسید:", "reply_markup": {"remove_keyboard": True}})

        elif text == "📊 نظرسنجی‌های من":
            show_my_polls(chat_id, user_id)

        elif user_id in user_state:
            handle_steps(chat_id, user_id, msg)

    elif "callback_query" in update:
        handle_callbacks(update["callback_query"])

    return "ok", 200

def handle_steps(chat_id, user_id, msg):
    state = user_state[user_id]
    text = msg.get("text", "")

    if state["step"] == "get_q":
        state.update({"q": text, "step": "get_opts"})
        bot_api("sendMessage", {"chat_id": chat_id, "text": "🟢 حالا گزینه‌ها را یکی یکی بفرستید. بعد از اتمام 'تایید' را بزنید:", 
            "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام گزینه‌ها", "callback_data": "finish_opts"}]]}})
    
    elif state["step"] == "get_opts":
        state["opts"].append(text)
        bot_api("sendMessage", {"chat_id": chat_id, "text": f"ثبت شد. گزینه بعدی؟", 
            "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام گزینه‌ها", "callback_data": "finish_opts"}]]}})

    elif state["step"] == "edit_q":
        p_id = state["edit_p_id"]
        update_db(p_id, "question", text)
        user_state[user_id] = None
        bot_api("sendMessage", {"chat_id": chat_id, "text": "✅ متن سوال با موفقیت ویرایش شد."})
        show_report(chat_id, user_id, p_id)

def show_my_polls(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, question FROM polls WHERE creator_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot_api("sendMessage", {"chat_id": chat_id, "text": "📭 شما هنوز نظرسنجی نساخته‌اید."})
        return

    btns = [[{"text": f"📋 {r[1][:25]}...", "callback_data": f"rep_{r[0]}"}] for r in rows]
    bot_api("sendMessage", {"chat_id": chat_id, "text": "📂 لیست نظرسنجی‌های شما:", "reply_markup": {"inline_keyboard": btns}})

def handle_callbacks(cq):
    user_id = str(cq["from"]["id"])
    chat_id = cq["message"]["chat"]["id"]
    data = cq["data"]

    if data == "finish_opts":
        # ذخیره در دیتابیس
        state = user_state[user_id]
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO polls (creator_id, question, options, votes, voters) VALUES (?, ?, ?, ?, ?)",
                       (user_id, state["q"], json.dumps(state["opts"]), json.dumps([0]*len(state["opts"])), "[]"))
        conn.commit()
        p_id = cursor.lastrowid
        conn.close()
        user_state[user_id] = None
        bot_api("sendMessage", {"chat_id": chat_id, "text": "✅ نظرسنجی ساخته و ذخیره شد."})
        show_report(chat_id, user_id, p_id)

    elif data.startswith("rep_"):
        show_report(chat_id, user_id, data.split("_")[1])

    elif data.startswith("del_"):
        p_id = data.split("_")[1]
        conn = sqlite3.connect('bot_data.db')
        conn.cursor().execute("DELETE FROM polls WHERE id=?", (p_id,))
        conn.commit()
        conn.close()
        bot_api("sendMessage", {"chat_id": chat_id, "text": "🗑 نظرسنجی حذف شد."})
        show_my_polls(chat_id, user_id)

    elif data.startswith("edq_"):
        p_id = data.split("_")[1]
        user_state[user_id] = {"step": "edit_q", "edit_p_id": p_id}
        bot_api("sendMessage", {"chat_id": chat_id, "text": "📝 متن جدید سوال را بفرستید:"})

def show_report(chat_id, user_id, p_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT question, options, votes FROM polls WHERE id=?", (p_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        q, opts, votes = row[0], json.loads(row[1]), json.loads(row[2])
        total = sum(votes)
        text = f"📊 گزارش: {q}\n\n"
        for i, o in enumerate(opts):
            p = (votes[i]/total*100) if total > 0 else 0
            text += f"▪️ {o}: {int(p)}% ({votes[i]} رای)\n"
        
        btns = [
            [{"text": "🗑 حذف", "callback_data": f"del_{p_id}"}, {"text": "📝 ویرایش سوال", "callback_data": f"edq_{p_id}"}],
            [{"text": "🔙 بازگشت به لیست", "callback_data": "back_list"}]
        ]
        bot_api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": {"inline_keyboard": btns}})

def update_db(p_id, field, value):
    conn = sqlite3.connect('bot_data.db')
    conn.cursor().execute(f"UPDATE polls SET {field}=? WHERE id=?", (value, p_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
