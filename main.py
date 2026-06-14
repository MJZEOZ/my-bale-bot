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

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS polls 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id TEXT, question TEXT, 
         options TEXT, votes TEXT, voters TEXT, img_id TEXT)''')
    conn.commit()
    conn.close()

init_db()

user_state = {}

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

def check_membership(user_id):
    """بررسی عضویت در کانال وامسرا"""
    try:
        res = bot_api("getChatMember", {"chat_id": REQUIRED_CHANNEL, "user_id": user_id}).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["member", "administrator", "creator"]
    except: pass
    return False

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET": return "Bot is Online", 200
    update = request.get_json(silent=True)
    if not update or "callback_query" not in update and "message" not in update: return "ok", 200

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = str(msg["from"]["id"])
        text = msg.get("text", "")

        if text == "/start":
            user_state[user_id] = None
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": "🌟 به مدیریت نظرسنجی خوش آمدید. گزینه مورد نظر را انتخاب کنید:",
                "reply_markup": {
                    "keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}], [{"text": "📊 نظرسنجی‌های من"}]],
                    "resize_keyboard": True
                }
            })

        elif text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q", "opts": []}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "🔴 متن سوال را بنویسید:", "reply_markup": {"remove_keyboard": True}})

        elif text == "📊 نظرسنجی‌های من":
            show_my_polls(chat_id, user_id)

        elif user_id in user_state and user_state[user_id] is not None:
            handle_steps(chat_id, user_id, msg)

    elif "callback_query" in update:
        handle_callbacks(update["callback_query"])

    return "ok", 200

def handle_steps(chat_id, user_id, msg):
    state = user_state[user_id]
    text = msg.get("text", "")

    if state["step"] == "get_q":
        state.update({"q": text, "step": "get_opts"})
        bot_api("sendMessage", {"chat_id": chat_id, "text": "🟢 حالا گزینه‌ها را یکی یکی بفرستید. بعد از اتمام دکمه زیر را بزنید:", 
            "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام گزینه‌ها", "callback_data": "finish_opts"}]]}})
    
    elif state["step"] == "get_opts":
        if text:
            state["opts"].append(text)
            bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه '{text}' ثبت شد. بعدی؟", 
                "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام گزینه‌ها", "callback_data": "finish_opts"}]]}})

    elif state["step"] == "get_img" and "photo" in msg:
        img_id = msg["photo"][-1]["file_id"]
        save_poll(user_id, state["q"], state["opts"], img_id)
        user_state[user_id] = None
        bot_api("sendMessage", {"chat_id": chat_id, "text": "✅ نظرسنجی با موفقیت ذخیره شد."})
        show_my_polls(chat_id, user_id)

    elif state["step"] == "get_pub_channel":
        publish_now(chat_id, user_id, text, state["p_id"])

def save_poll(creator_id, q, opts, img_id=None):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO polls (creator_id, question, options, votes, voters, img_id) VALUES (?, ?, ?, ?, ?, ?)",
                   (creator_id, q, json.dumps(opts), json.dumps([0]*len(opts)), "[]", img_id))
    conn.commit()
    conn.close()

def show_my_polls(chat_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, question FROM polls WHERE creator_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot_api("sendMessage", {"chat_id": chat_id, "text": "📭 لیست نظرسنجی‌های شما خالی است."})
        return
    btns = [[{"text": f"📋 {r[1][:25]}...", "callback_data": f"rep_{r[0]}"}] for r in rows]
    bot_api("sendMessage", {"chat_id": chat_id, "text": "📂 لیست نظرسنجی‌های شما:", "reply_markup": {"inline_keyboard": btns}})

def handle_callbacks(cq):
    user_id = str(cq["from"]["id"])
    chat_id = cq["message"]["chat"]["id"]
    data = cq["data"]

    if data == "finish_opts":
        if len(user_state[user_id]["opts"]) < 2:
            bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "حداقل ۲ گزینه لازم است!", "show_alert": True})
        else:
            user_state[user_id]["step"] = "get_img"
            bot_api("sendMessage", {"chat_id": chat_id, "text": "📸 (اختیاری) یک تصویر بفرستید یا دکمه زیر را بزنید:", 
                "reply_markup": {"inline_keyboard": [[{"text": "⏩ بدون تصویر (ادامه)", "callback_data": "skip_img"}]]}})

    elif data == "skip_img":
        state = user_state[user_id]
        save_poll(user_id, state["q"], state["opts"])
        user_state[user_id] = None
        bot_api("sendMessage", {"chat_id": chat_id, "text": "✅ نظرسنجی بدون تصویر ذخیره شد."})
        show_my_polls(chat_id, user_id)

    elif data.startswith("rep_"):
        show_report(chat_id, user_id, data.split("_")[1])

    elif data.startswith("del_"):
        conn = sqlite3.connect('bot_data.db')
        conn.cursor().execute("DELETE FROM polls WHERE id=?", (data.split("_")[1],))
        conn.commit()
        conn.close()
        bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "نظرسنجی حذف شد."})
        show_my_polls(chat_id, user_id)

    elif data == "back_list":
        show_my_polls(chat_id, user_id)

    elif data.startswith("pub_"):
        if not check_membership(user_id):
            bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": f"❌ ابتدا باید در کانال {REQUIRED_CHANNEL} عضو شوید!", "show_alert": True})
        else:
            user_state[user_id] = {"step": "get_pub_channel", "p_id": data.split("_")[1]}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "📢 آیدی کانال مقصد را بفرستید (مثلاً @mychannel):"})

    elif data.startswith("v_"):
        process_vote(chat_id, user_id, cq)

def show_report(chat_id, user_id, p_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT question, options, votes, img_id FROM polls WHERE id=?", (p_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        q, opts, votes, img = row[0], json.loads(row[1]), json.loads(row[2]), row[3]
        total = sum(votes)
        report = f"📊 گزارش نظرسنجی:\n\n❓ سوال: {q}\n\n"
        for i, o in enumerate(opts):
            p = (votes[i]/total*100) if total > 0 else 0
            report += f"🔹 {o}: {int(p)}% ({votes[i]} رای)\n"
        report += f"\n👥 کل آرا: {total}"
        
        btns = [
            [{"text": "🚀 انتشار در کانال", "callback_data": f"pub_{p_id}"}],
            [{"text": "🔄 بروزرسانی", "callback_data": f"rep_{p_id}"}, {"text": "🗑 حذف", "callback_data": f"del_{p_id}"}],
            [{"text": "🔙 بازگشت به لیست", "callback_data": "back_list"}]
        ]
        if img:
            bot_api("sendPhoto", {"chat_id": chat_id, "photo": img, "caption": report, "reply_markup": {"inline_keyboard": btns}})
        else:
            bot_api("sendMessage", {"chat_id": chat_id, "text": report, "reply_markup": {"inline_keyboard": btns}})

def publish_now(chat_id, user_id, channel_id, p_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT question, options, img_id FROM polls WHERE id=?", (p_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        q, opts, img = row[0], json.loads(row[1]), row[2]
        kb = [[{"text": o, "callback_data": f"v_{p_id}_{i}"}] for i, o in enumerate(opts)]
        
        if img:
            res = bot_api("sendPhoto", {"chat_id": channel_id, "photo": img, "caption": q, "reply_markup": {"inline_keyboard": kb}})
        else:
            res = bot_api("sendMessage", {"chat_id": channel_id, "text": q, "reply_markup": {"inline_keyboard": kb}})
        
        if res.status_code == 200:
            bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ با موفقیت در کانال {channel_id} منتشر شد."})
            user_state[user_id] = None
        else:
            bot_api("sendMessage", {"chat_id": chat_id, "text": "❌ خطا در انتشار! آیا بازو در کانال ادمین است؟"})

def process_vote(chat_id, user_id, cq):
    p_id, opt_idx = cq["data"].split("_")[1], int(cq["data"].split("_")[2])
    if not check_membership(user_id):
        bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "⚠️ برای ثبت رای باید عضو کانال وامسرا شوید!", "show_alert": True})
        return

    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT question, options, votes, voters, img_id FROM polls WHERE id=?", (p_id,))
    row = cursor.fetchone()
    if row:
        voters = json.loads(row[3])
        if user_id in voters:
            bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً رای داده‌اید."})
            conn.close()
            return
        
        votes = json.loads(row[2])
        votes[opt_idx] += 1
        voters.append(user_id)
        
        cursor.execute("UPDATE polls SET votes=?, voters=? WHERE id=?", (json.dumps(votes), json.dumps(voters), p_id))
        conn.commit()
        
        total = sum(votes)
        new_txt = f"{row[0]}\n\n"
        for i, o in enumerate(json.loads(row[1])):
            p = (votes[i]/total*100) if total > 0 else 0
            new_txt += f"{o}: {int(p)}% ({votes[i]} رای)\n"
        
        method = "editMessageCaption" if row[4] else "editMessageText"
        bot_api(method, {
            "chat_id": chat_id, 
            "message_id": cq["message"]["message_id"], 
            ("caption" if row[4] else "text"): new_txt, 
            "reply_markup": cq["message"]["reply_markup"]
        })
    conn.close()
    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما ثبت شد."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
