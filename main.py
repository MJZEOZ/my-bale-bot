import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = os.environ.get("BOT_TOKEN", "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
CHANNEL_ID = "@wamsara"

# دیتابیس ساده برای جلوگیری از پاک شدن در ریست‌های کوتاه (اختیاری)
user_state = {}
polls = {}

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

def get_bot_username():
    try:
        res = requests.get(f"{BASE_URL}/getMe").json()
        return res.get("result", {}).get("username", "vamclcbot")
    except: return "vamclcbot"

def check_membership(user_id):
    try:
        res = bot_api("getChatMember", {"chat_id": CHANNEL_ID, "user_id": user_id}).json()
        # بله ممکن است وضعیت‌های مختلفی برگرداند، این حالت استاندارد است
        return res.get("ok") and res["result"]["status"] in ["member", "creator", "administrator"]
    except: return False

@app.route("/", methods=["GET", "POST"])
def receive_update():
    # برای جلوگیری از خطای 405 در Render
    if request.method == "GET": 
        return "Bot is Online!", 200
    
    update = request.get_json(silent=True)
    if not update:
        return "ok", 200

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # مدیریت استارت و لینک‌های اشتراک‌گذاری
        if text.startswith("/start"):
            if " " in text:
                parts = text.split(" ")
                if len(parts) > 1:
                    p_id = parts[1]
                    poll = polls.get(p_id)
                    if poll:
                        buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                        cap = f"📊 {poll['q']}\n\n⚠️ برای ثبت رای باید عضو کانال {CHANNEL_ID} باشید."
                        if poll["img"]:
                            bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": cap, "reply_markup": {"inline_keyboard": buttons}})
                        else:
                            bot_api("sendMessage", {"chat_id": chat_id, "text": cap, "reply_markup": {"inline_keyboard": buttons}})
                        return "ok"

            user_state[user_id] = None
            markup = {"keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}]], "resize_keyboard": True}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "به ربات نظرسنجی خوش آمدید:", "reply_markup": markup})
        
        elif text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۱. متن سوال نظرسنجی را بفرستید:", "reply_markup": {"remove_keyboard": True}})
        
        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            if state["step"] == "get_q":
                user_state[user_id].update({"step": "get_img", "q": text})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۲. عکس بفرستید یا از دکمه زیر استفاده کنید:", "reply_markup": {"inline_keyboard": [[{"text": "❌ بدون عکس", "callback_data": "skip_img"}]]}})
            elif state["step"] == "get_img" and "photo" in msg:
                user_state[user_id].update({"step": "get_opts", "img": msg["photo"][-1]["file_id"], "opts": []})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. اولین گزینه پاسخ را بفرستید:"})
            elif state["step"] == "get_opts":
                user_state[user_id]["opts"].append(text)
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه '{text}' ثبت شد. گزینه بعدی را بفرستید یا دکمه پایان را بزنید:", "reply_markup": {"inline_keyboard": [[{"text": "✅ تکمیل و دریافت لینک", "callback_data": "finish_poll"}]]}})

    elif "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        data = cq["data"]

        if data == "skip_img":
            if user_id in user_state and user_state[user_id]:
                user_state[user_id].update({"step": "get_opts", "img": None, "opts": []})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۳. اولین گزینه پاسخ را بفرستید:"})

        elif data == "finish_poll":
            state = user_state.get(user_id)
            if state and len(state.get("opts", [])) >= 2:
                p_id = str(len(polls) + 1)
                polls[p_id] = {"q": state["q"], "img": state["img"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": [], "creator": user_id}
                
                buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(state["opts"])]
                cap = f"📊 {state['q']}"
                if state["img"]:
                    bot_api("sendPhoto", {"chat_id": chat_id, "photo": state["img"], "caption": cap, "reply_markup": {"inline_keyboard": buttons}})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": cap, "reply_markup": {"inline_keyboard": buttons}})
                
                share_link = f"https://ble.ir/{get_bot_username()}?start={p_id}"
                m_btns = {"inline_keyboard": [
                    [{"text": "🔗 اشتراک‌گذاری مستقیم در بله", "url": f"https://ble.ir/share/url?url={share_link}"}],
                    [{"text": "📈 مشاهده گزارش دقیق آرا", "callback_data": f"report_{p_id}"}]
                ]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ نظرسنجی ساخته شد.\nبرای انتشار، از دکمه اشتراک‌گذاری استفاده کنید:\n\n{share_link}", "reply_markup": m_btns})
                user_state[user_id] = None

        elif data.startswith("report_"):
            p_id = data.split("_")[1]
            poll = polls.get(p_id)
            if poll:
                total = sum(poll["votes"])
                report = f"📈 گزارش آرا: \n❓ {poll['q']}\n\n"
                for i, o in enumerate(poll["opts"]):
                    p = (poll["votes"][i]/total*100) if total > 0 else 0
                    report += f"🔹 {o}: {poll['votes'][i]} رای ({int(p)}%)\n"
                bot_api("sendMessage", {"chat_id": chat_id, "text": report})

        elif data.startswith("v_"):
            if not check_membership(user_id):
                join_btns = {"inline_keyboard": [
                    [{"text": "📢 ورود به کانال و عضویت", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                    [{"text": "✅ عضو شدم (ثبت رای)", "callback_data": data}]
                ]}
                bot_api("sendMessage", {
                    "chat_id": chat_id, 
                    "text": f"⚠️ برای ثبت رای باید عضو کانال زیر باشید:\n{CHANNEL_ID}", 
                    "reply_markup": join_btns
                })
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "ابتدا عضو کانال شوید"})
                return "ok"
            
            p_id = data.split("_")[1]
            opt_idx = int(data.split("_")[2])
            poll = polls.get(p_id)
            
            if poll:
                if user_id not in poll["users"]:
                    poll["votes"][opt_idx] += 1
                    poll["users"].append(user_id)
                    total = sum(poll["votes"])
                    res_text = f"📊 {poll['q']}\n\n"
                    for i, o in enumerate(poll["opts"]):
                        p = (poll["votes"][i]/total*100) if total > 0 else 0
                        res_text += f"{o}: {int(p)}% ({poll['votes'][i]} رای)\n"
                    
                    if poll["img"]:
                        bot_api("editMessageCaption", {"chat_id": chat_id, "message_id": cq["message"]["message_id"], "caption": res_text, "reply_markup": cq["message"]["reply_markup"]})
                    else:
                        bot_api("editMessageText", {"chat_id": chat_id, "message_id": cq["message"]["message_id"], "text": res_text, "reply_markup": cq["message"]["reply_markup"]})
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما ثبت شد."})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "قبلاً رای داده‌اید!", "show_alert": True})

    return "ok"

if __name__ == "__main__":
    # تنظیم پورت برای Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
