import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU" 
CHANNEL_ID = "@wamsara" 
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

# ذخیره وضعیت کاربران و نظرسنجی‌ها
user_state = {}
polls = {}

def send_msg(chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup: data["reply_markup"] = markup
    return requests.post(BASE_URL + "/sendMessage", json=data)

def check_membership(user_id):
    url = f"{BASE_URL}/getChatMember"
    params = {"chat_id": CHANNEL_ID, "user_id": user_id}
    try:
        r = requests.get(url, params=params).json()
        return r.get("ok") and r["result"]["status"] in ["creator", "administrator", "member"]
    except: return False

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
            send_msg(chat_id, "❌ برای استفاده از ربات باید عضو کانال ما شوید:", markup)
            return "ok"

        if text == "/start":
            user_state[user_id] = None
            send_msg(chat_id, "سلام! به ربات نظرسنجی خوش آمدید.\nبرای ساخت نظرسنجی جدید دستور /new را بفرستید.")
        
        elif text == "/new":
            user_state[user_id] = {"step": "get_q"}
            send_msg(chat_id, "لطفاً صورت سوال نظرسنجی را بفرستید:")
        
        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            if state["step"] == "get_q":
                user_state[user_id].update({"step": "get_opts", "q": text, "opts": []})
                send_msg(chat_id, "حالا گزینه‌ها را یکی یکی بفرستید. در پایان دستور /done را بزنید.")
            
            elif state["step"] == "get_opts":
                if text == "/done":
                    if len(state["opts"]) < 2:
                        send_msg(chat_id, "حداقل باید ۲ گزینه بفرستید!")
                    else:
                        # ساخت نظرسنجی نهایی
                        p_id = str(len(polls) + 1)
                        polls[p_id] = {"q": state["q"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                        
                        buttons = [[{"text": f"{opt}", "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(state["opts"])]
                        markup = {"inline_keyboard": buttons}
                        
                        send_msg(chat_id, f"✅ نظرسنجی ساخته شد:\n\n📊 {state['q']}", markup)
                        user_state[user_id] = None
                else:
                    user_state[user_id]["opts"].append(text)
                    send_msg(chat_id, f"گزینه {len(user_state[user_id]['opts'])} ثبت شد. گزینه بعدی؟ (یا /done)")

    elif "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        data = cq["data"]

        if data.startswith("v_"):
            _, p_id, opt_idx = data.split("_")
            opt_idx = int(opt_idx)
            if p_id in polls:
                if user_id in polls[p_id]["users"]:
                    requests.post(BASE_URL+"/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "قبلاً رأی داده‌اید!"})
                else:
                    polls[p_id]["votes"][opt_idx] += 1
                    polls[p_id]["users"].append(user_id)
                    
                    res = f"📊 {polls[p_id]['q']}\n\n"
                    for i, o in enumerate(polls[p_id]["opts"]):
                        res += f"{o}: {polls[p_id]['votes'][i]} رأی\n"
                    
                    requests.post(BASE_URL+"/editMessageText", json={
                        "chat_id": cq["message"]["chat"]["id"],
                        "message_id": cq["message"]["message_id"],
                        "text": res,
                        "reply_markup": cq["message"]["reply_markup"]
                    })
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
