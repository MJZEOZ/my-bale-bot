import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات اصلی ---
TOKEN = "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU" 

CHANNEL_ID = "@wamsara" 
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

def check_membership(user_id):
    url = f"{BASE_URL}/getChatMember"
    params = {"chat_id": CHANNEL_ID, "user_id": user_id}
    try:
        response = requests.get(url, params=params).json()
        if response.get("ok"):
            status = response["result"]["status"]
            return status in ["creator", "administrator", "member"]
    except:
        return False
    return False

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{BASE_URL}/sendMessage", json=data)

@app.route("/", methods=["POST"])
def receive_update():
    update = request.json
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # بررسی عضویت اجباری
        if not check_membership(user_id):
            markup = {"inline_keyboard": [[{"text": "عضویت در کانال", "url": f"https://ble.ir/{CHANNEL_ID[1:]}"}]]}
            send_message(chat_id, "❌ برای استفاده از ربات باید ابتدا عضو کانال شوید.", markup)
            return "ok"

        if text == "/start":
            send_message(chat_id, "سلام! به ربات نظرسنجی خوش آمدید.\nبرای ساخت نظرسنجی دستور /new_poll را بزنید.")
        
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
