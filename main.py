

import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات توکن بله ---
TOKEN = "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
CHANNEL_ID = "@wamsara"  # آیدی کانال برای قفل عضویت

# حافظه موقت (بعد از ریست شدن سرور پاک می‌شود)
user_state = {}
polls = {}

def bot_api(method, data=None, files=None):
    return requests.post(f"{BASE_URL}/{method}", json=data, files=files)

def get_bot_username():
    try:
        res = requests.get(f"{BASE_URL}/getMe").json()
        return res.get("result", {}).get("username", "bot")
    except:
        return "bot"

def check_membership(user_id):
    try:
        res = bot_api("getChatMember", {"chat_id": CHANNEL_ID, "user_id": user_id}).json()
        # وضعیت‌های مجاز برای عبور از قفل کانال
        return res.get("ok") and res["result"]["status"] in ["member", "creator", "administrator"]
    except:
        return False

def create_progress_bar(percent):
    full = int(percent / 10)
    return "🔵" * full + "⚪" * (10 - full)

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET":
        return "GapGPT Bot is Online!", 200
    
    update = request.json
    
    # مدیریت پیام‌های متنی و استارت
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # شروع و هندل کردن لینک‌های Start
        if text.startswith("/start"):
            if " " in text: # اگر کاربر با لینک وارد شده باشد (مثلا برای رای دادن)
                p_id = text.split(" ")[1]
                poll = polls.get(p_id)
                if poll:
                    buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                    text_final = f"📊 {poll['q']}\n\n⚠️ برای ثبت رای باید عضو کانال {CHANNEL_ID} باشید."
                    if poll["img"]:
                        bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": text_final, "reply_markup": {"inline_keyboard": buttons}})
                    else:
                        bot_api("sendMessage", {"chat_id": chat_id, "text": text_final, "reply_markup": {"inline_keyboard": buttons}})
                    return "ok"

            user_state[user_id] = None
            markup = {"keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}]], "resize_keyboard": True}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "سلام! به ربات نظرسنجی پیشرفته خوش آمدید.\nبرای شروع روی دکمه زیر کلیک کنید:", "reply_markup": markup})
        
        elif text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۱. لطفاً متن سوال نظرسنجی را بفرستید:", "reply_markup": {"remove_keyboard": True}})
        
        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            
            if state["step"] == "get_q":
                user_state[user_id].update({"step": "get_img", "q": text})
                markup = {"inline_keyboard": [[{"text": "❌ بدون عکس (ادامه مرحله بعد)", "callback_data": "skip_img"}]]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۲. اگر مایلید برای نظرسنجی عکسی ارسال کنید، آن را همینجا بفرستید.\nدر غیر این صورت روی دکمه زیر بزنید:", "reply_markup": markup})
            
            elif state["step"] == "get_img" and "photo" in msg:
                file_id = msg["photo"][-1]["file_id"]
                user_state[user_id].update({"step": "get_opts", "img": file_id, "opts": []})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. حالا اولین گزینه نظرسنجی را بنویسید:"})

            elif state["step"] == "get_opts":
                user_state[user_id]["opts"].append(text)
                markup = {"inline_keyboard": [[{"text": "✅ تکمیل و دریافت لینک انتشار", "callback_data": "finish_poll"}]]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه «{text}» ثبت شد.\nگزینه بعدی را بفرستید یا روی دکمه تکمیل کلیک کنید:", "reply_markup": markup})

    # مدیریت دکمه‌های شیشه‌ای (Callback Queries)
    elif "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq["data"]

        if data == "skip_img":
            user_state[user_id].update({"step": "get_opts", "img": None, "opts": []})
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. عکسی ثبت نشد. حالا اولین گزینه نظرسنجی را بفرستید:"})

        elif data == "finish_poll":
            state = user_state.get(user_id)
            if state and len(state.get("opts", [])) >= 2:
                p_id = str(len(polls) + 1)
                polls[p_id] = {"q": state["q"], "img": state["img"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                
                bot_username = get_bot_username()
                share_link = f"https://ble.ir/{bot_username}?start={p_id}"
                
                bot_api("sendMessage", {
                    "chat_id": chat_id, 
                    "text": f"✅ نظرسنجی با موفقیت ساخته شد!\n\n🔗 **لینک انتشار در کانال و گروه‌ها:**\n`{share_link}`\n\n(می‌توانید پیام نظرسنجی بالا را هم برای دیگران فوروارد کنید.)", 
                    "parse_mode": "Markdown"
                })
                user_state[user_id] = None
            else:
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "حداقل باید ۲ گزینه وارد کنید!", "show_alert": True})

        elif data.startswith("v_"):
            # چک کردن عضویت در کانال پیش از ثبت رای
            if not check_membership(user_id):
                bot_api("answerCallbackQuery", {
                    "callback_query_id": cq["id"], 
                    "text": f"❌ برای شرکت در نظرسنجی باید عضو کانال {CHANNEL_ID} باشید!", 
                    "show_alert": True
                })
                return "ok"

            parts = data.split("_")
            p_id, opt_idx = parts[1], int(parts[2])
            poll = polls.get(p_id)
            
            if poll:
                if user_id in poll["users"]:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً در این نظرسنجی شرکت کرده‌اید.", "show_alert": False})
                else:
                    poll["votes"][opt_idx] += 1
                    poll["users"].append(user_id)
                    total = sum(poll["votes"])
                    
                    res_text = f"📊 {poll['q']}\n\n"
                    for i, o in enumerate(poll["opts"]):
                        percent = (poll["votes"][i] / total * 100) if total > 0 else 0
                        res_text += f"{o}\n{create_progress_bar(percent)} {int(percent)}% ({poll['votes'][i]} رای)\n\n"
                    
                    method = "editMessageCaption" if poll["img"] else "editMessageText"
                    field = "caption" if poll["img"] else "text"
                    payload = {
                        "chat_id": chat_id, 
                        "message_id": cq["message"]["message_id"], 
                        field: res_text, 
                        "reply_markup": cq["message"]["reply_markup"]
                    }
                    bot_api(method, payload)
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما با موفقیت ثبت شد."})

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
