import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# تنظیمات اصلی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = "@wamsara" # آیدی کانال شما
DB_FILE = "/tmp/polls_db.json"

# بارگذاری دیتابیس نظرسنجی
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({}, f)

def load_polls():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_polls(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f)

def bot_api(method, data):
    url = f"https://messenger.bale.ai/bot{BOT_TOKEN}/{method}"
    return requests.post(url, json=data)

def check_membership(user_id):
    # این تابع را بسته به نیاز دقیق‌تان می‌توانید تکمیل کنید
    return True 

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "ok", 200

    update = request.get_json(silent=True)
    if not update:
        return "ok", 200

    polls = load_polls()
    
    # پردازش دکمه‌ها (Callback Query)
    if "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq["data"]

        if data.startswith("v_"):
            # مرحله اول: بررسی عضویت
            if not check_membership(user_id):
                # ... (کدی که فرستادید اینجا قرار می‌گیرد)
                join_btns = {"inline_keyboard": [
                    [{"text": "📢 ورود به کانال", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                    [{"text": "✅ عضو شدم (ارزیابی مجدد)", "callback_data": data}]
                ]}
                bot_api("editMessageText", {
                    "chat_id": chat_id, "message_id": cq["message"]["message_id"],
                    "text": "❌ ابتدا باید در کانال عضو شوید.", "reply_markup": join_btns
                })
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "عضویت تایید نشد!"})
                return "ok"
            
            # مرحله دوم: ثبت رای (بقیه کد شما)
            p_id = data.split("_")[1]
            opt_idx = int(data.split("_")[2])
            poll = polls.get(p_id)
            
            if poll:
                # ثبت رای و ذخیره در فایل
                if user_id not in poll.get("users", []):
                    poll["votes"][opt_idx] += 1
                    poll.setdefault("users", []).append(user_id)
                    save_polls(polls)
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما ثبت شد."})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "قبلا رای داده‌اید.", "show_alert": True})
            return "ok"

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
