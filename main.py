import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU" 
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

# حافظه موقت برای ذخیره وضعیت کاربران و نظرسنجی‌ها
user_state = {}
polls = {}

def send_msg(chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup: data["reply_markup"] = markup
    return requests.post(BASE_URL + "/sendMessage", json=data)

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET": return "Bot is Active!", 200
    
    update = request.json
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            user_state[user_id] = None
            send_msg(chat_id, "سلام! به ربات نظرسنجی خوش آمدید.\nبرای ساخت یک نظرسنجی جدید، دستور /new را بفرستید.")
        
        elif text == "/new":
            user_state[user_id] = {"step": "get_q"}
            send_msg(chat_id, "۱. لطفاً **سوال** نظرسنجی را بفرستید:")
        
        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            
            if state["step"] == "get_q":
                user_state[user_id].update({"step": "get_opts", "q": text, "opts": []})
                send_msg(chat_id, f"سوال ثبت شد: {text}\n\n۲. حالا گزینه‌ها را یکی‌یکی بفرستید. در انتها دستور /done را بفرستید.")
            
            elif state["step"] == "get_opts":
                if text == "/done":
                    if len(state["opts"]) < 2:
                        send_msg(chat_id, "باید حداقل ۲ گزینه بفرستید!")
                    else:
                        p_id = str(len(polls) + 1)
                        polls[p_id] = {"q": state["q"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                        
                        # ساخت دکمه‌های شیشه‌ای
                        buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(state["opts"])]
                        markup = {"inline_keyboard": buttons}
                        
                        send_msg(chat_id, f"📊 {state['q']}\n\n(برای رأی دادن روی گزینه‌ها کلیک کنید)", markup)
                        user_state[user_id] = None # ریست کردن وضعیت کاربر
                else:
                    user_state[user_id]["opts"].append(text)
                    send_msg(chat_id, f"گزینه «{text}» ثبت شد. بعدی؟ (یا /done)")

    elif "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        data = cq["data"] # فرمت: v_pollid_index

        if data.startswith("v_"):
            _, p_id, opt_idx = data.split("_")
            opt_idx = int(opt_idx)
            
            if p_id in polls:
                if user_id in polls[p_id]["users"]:
                    # پاسخ به کلیک برای بستن حالت لودینگ دکمه
                    requests.post(BASE_URL + "/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "شما قبلاً رأی داده‌اید!"})
                else:
                    polls[p_id]["votes"][opt_idx] += 1
                    polls[p_id]["users"].append(user_id)
                    
                    # آپدیت متن پیام با نتایج جدید
                    res_text = f"📊 {polls[p_id]['q']}\n\n"
                    for i, o in enumerate(polls[p_id]["opts"]):
                        res_text += f"🔹 {o}: {polls[p_id]['votes'][i]} رأی\n"
                    
                    requests.post(BASE_URL + "/editMessageText", json={
                        "chat_id": cq["message"]["chat"]["id"],
                        "message_id": cq["message"]["message_id"],
                        "text": res_text,
                        "reply_markup": cq["message"]["reply_markup"]
                    })
    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
