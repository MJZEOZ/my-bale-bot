import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU"
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
CHANNEL_ID = "@wamsara"  # آیدی کانال شما برای قفل

user_state = {}
polls = {}

def bot_api(method, data=None, files=None):
    return requests.post(f"{BASE_URL}/{method}", json=data, files=files)

def check_membership(user_id):
    try:
        res = bot_api("getChatMember", {"chat_id": CHANNEL_ID, "user_id": user_id}).json()
        return res.get("ok") and res["result"]["status"] in ["member", "creator", "administrator"]
    except: return False

def create_progress_bar(percent):
    full = int(percent / 10)
    return "🔵" * full + "⚪" * (10 - full)

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET": return "Bot is Online!", 200
    
    update = request.json
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # شروع مجدد
        if text == "/start":
            user_state[user_id] = None
            markup = {"keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}]], "resize_keyboard": True}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "خوش آمدید! برای شروع از دکمه زیر استفاده کنید:", "reply_markup": markup})
        
        elif text == "🚀 ساخت نظرسنجی جدید" or text == "/new":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۱. سوال نظرسنجی را بنویسید:", "reply_markup": {"remove_keyboard": True}})
        
        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            
            # دریافت سوال
            if state["step"] == "get_q":
                user_state[user_id].update({"step": "get_img", "q": text})
                markup = {"inline_keyboard": [[{"text": "❌ بدون عکس (ادامه)", "callback_data": "skip_img"}]]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۲. اگر مایلید عکسی بفرستید (از کامپیوتر یا گالری)، در غیر این صورت دکمه زیر را بزنید:", "reply_markup": markup})
            
            # دریافت عکس
            elif state["step"] == "get_img":
                if "photo" in msg:
                    file_id = msg["photo"][-1]["file_id"]
                    user_state[user_id].update({"step": "get_opts", "img": file_id, "opts": []})
                    bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. حالا اولین گزینه را بفرستید:"})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": "لطفاً یک عکس بفرستید یا دکمه «بدون عکس» را بزنید."})

            # دریافت گزینه‌ها
            elif state["step"] == "get_opts":
                user_state[user_id]["opts"].append(text)
                markup = {"inline_keyboard": [[{"text": "✅ تکمیل و انتشار نظرسنجی", "callback_data": "finish_poll"}]]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه {len(user_state[user_id]['opts'])} ثبت شد. گزینه بعدی را بفرستید یا روی تکمیل کلیک کنید:", "reply_markup": markup})

    elif "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq["data"]

        # رد کردن عکس
        if data == "skip_img":
            user_state[user_id].update({"step": "get_opts", "img": None, "opts": []})
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. حالا اولین گزینه را بفرستید:"})

        # نهایی کردن نظرسنجی
        elif data == "finish_poll":
            state = user_state[user_id]
            if len(state["opts"]) < 2:
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "حداقل ۲ گزینه لازم است!"})
            else:
                p_id = str(len(polls) + 1)
                polls[p_id] = {"q": state["q"], "img": state["img"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                
                # نمایش پیش‌نمایش
                buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(state["opts"])]
                text_final = f"📊 {state['q']}\n\nبرای رأی دادن باید عضو کانال {CHANNEL_ID} باشید."
                
                if state["img"]:
                    bot_api("sendPhoto", {"chat_id": chat_id, "photo": state["img"], "caption": text_final, "reply_markup": {"inline_keyboard": buttons}})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": text_final, "reply_markup": {"inline_keyboard": buttons}})
                
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ نظرسنجی ساخته شد!\n\n🔗 لینک انتشار:\n`https://ble.ir/vambot?start={p_id}`\n\n(می‌توانید پیام بالا را مستقیماً به کانال خود فوروارد کنید.)", "parse_mode": "Markdown"})
                user_state[user_id] = None

        # عملیات رأی دادن
        elif data.startswith("v_"):
            if not check_membership(user_id):
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": f"❌ ابتدا باید عضو کانال {CHANNEL_ID} شوید!", "show_alert": True})
                return "ok"

            _, p_id, opt_idx = data.split("_")
            opt_idx = int(opt_idx)
            poll = polls.get(p_id)
            
            if poll:
                if user_id in poll["users"]:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً رأی داده‌اید!"})
                else:
                    poll["votes"][opt_idx] += 1
                    poll["users"].append(user_id)
                    total = sum(poll["votes"])
                    
                    res_text = f"📊 {poll['q']}\n\n"
                    for i, o in enumerate(poll["opts"]):
                        percent = (poll["votes"][i] / total * 100) if total > 0 else 0
                        res_text += f"{o}\n{create_progress_bar(percent)} {int(percent)}% ({poll['votes'][i]} رأی)\n\n"
                    
                    method = "editMessageCaption" if poll["img"] else "editMessageText"
                    payload = {"chat_id": chat_id, "message_id": cq["message"]["message_id"], "text" if not poll["img"] else "caption": res_text, "reply_markup": cq["message"]["reply_markup"]}
                    bot_api(method, payload)
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رأی شما ثبت شد."})

    return "ok"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


