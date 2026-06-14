import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = os.environ.get("BOT_TOKEN", "1634412047:jRQE064aVdzbIOfF9qWZ-u9tkyzwhrN68QU")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

user_state = {}
polls = {}

def bot_api(method, data=None):
    try:
        return requests.post(f"{BASE_URL}/{method}", json=data)
    except Exception as e:
        print(f"Error calling API: {e}")
        return None

def get_bot_username():
    try:
        res = requests.get(f"{BASE_URL}/getMe").json()
        return res.get("result", {}).get("username", "bot")
    except:
        return "bot"

def check_admin(channel_id, user_id):
    try:
        res = bot_api("getChatMember", {"chat_id": channel_id, "user_id": user_id}).json()
        if not res.get("ok"):
            return False
        return res["result"]["status"] in ["administrator", "creator"]
    except:
        return False

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET":
        return "Bot is Online", 200

    update = request.get_json(silent=True)
    if not update:
        return "ok", 200

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            if " " in text:
                p_id = text.split(" ")[1]
                poll = polls.get(p_id)
                if poll:
                    buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                    cap = f"📊 {poll['q']}"
                    if poll["img"]:
                        bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": cap, "reply_markup": {"inline_keyboard": buttons}})
                    else:
                        bot_api("sendMessage", {"chat_id": chat_id, "text": cap, "reply_markup": {"inline_keyboard": buttons}})
                    return "ok"

            user_state[user_id] = None
            markup = {"keyboard": [[{"text": "🚀 ساخت نظرسنجی جدید"}]], "resize_keyboard": True}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "به ربات نظرسنجی خوش آمدید", "reply_markup": markup})

        elif text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "۱- متن سوال نظرسنجی را بفرستید", "reply_markup": {"remove_keyboard": True}})

        elif user_id in user_state and user_state[user_id]:
            state = user_state[user_id]
            if state.get("step") == "get_q":
                state.update({"q": text, "step": "get_img"})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۲- عکس بفرستید یا بدون عکس ادامه دهید", "reply_markup": {"inline_keyboard": [[{"text": "❌ بدون عکس", "callback_data": "skip_img"}]]}})
            elif state.get("step") == "get_img" and "photo" in msg:
                state.update({"img": msg["photo"][-1]["file_id"], "opts": [], "step": "get_opts"})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۳- اولین گزینه را بفرستید"})
            elif state.get("step") == "get_opts":
                state["opts"].append(text)
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه '{text}' ثبت شد. بعدی را بفرستید یا تمام کنید:", "reply_markup": {"inline_keyboard": [[{"text": "✅ تکمیل نظرسنجی", "callback_data": "finish_poll"}]]}})
            elif state.get("step") == "get_channel":
                p_id = state.get("poll_id")
                channel = text if text.startswith("@") else f"@{text}"
                poll = polls.get(p_id)
                if poll:
                    if check_admin(channel, user_id):
                        buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                        cap = f"📊 {poll['q']}"
                        if poll["img"]:
                            bot_api("sendPhoto", {"chat_id": channel, "photo": poll["img"], "caption": cap, "reply_markup": {"inline_keyboard": buttons}})
                        else:
                            bot_api("sendMessage", {"chat_id": channel, "text": cap, "reply_markup": {"inline_keyboard": buttons}})
                        bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ نظرسنجی با موفقیت در {channel} منتشر شد."})
                        user_state[user_id] = None
                    else:
                        bot_api("sendMessage", {"chat_id": chat_id, "text": "❌ خطا: یا نام کانال اشتباه است، یا ربات در آن ادمین نیست و یا شما ادمین آن نیستید."})

    elif "callback_query" in update:
        cq = update["callback_query"]
        data = cq["data"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]

        if data == "skip_img":
            if user_id in user_state and user_state[user_id]:
                user_state[user_id].update({"img": None, "opts": [], "step": "get_opts"})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "۳- گزینه‌های نظرسنجی را بفرستید"})

        elif data == "finish_poll":
            state = user_state.get(user_id)
            if state and len(state.get("opts", [])) >= 2:
                p_id = str(len(polls) + 1)
                polls[p_id] = {"q": state["q"], "img": state.get("img"), "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                share_link = f"https://ble.ir/{get_bot_username()}?start={p_id}"
                markup = {"inline_keyboard": [[{"text": "🔗 لینک اشتراک", "url": share_link}], [{"text": "📢 انتشار در کانال", "callback_data": f"pub_{p_id}"}]]}
                bot_api("sendMessage", {"chat_id": chat_id, "text": "✅ نظرسنجی ساخته شد. می‌توانید لینک را کپی کنید یا مستقیم در کانال منتشر کنید:", "reply_markup": markup})
                user_state[user_id] = None

        elif data.startswith("pub_"):
            p_id = data.split("_")[1]
            user_state[user_id] = {"step": "get_channel", "poll_id": p_id}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "نام کاربری کانال را بفرستید (مثلاً @wamsara):\n\n*(دقت کنید ربات باید در کانال ادمین باشد)*"})

        elif data.startswith("v_"):
            p_id, opt_idx = data.split("_")[1], int(data.split("_")[2])
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
                    
                    method = "editMessageCaption" if poll["img"] else "editMessageText"
                    field = "caption" if poll["img"] else "text"
                    bot_api(method, {"chat_id": chat_id, "message_id": cq["message"]["message_id"], field: res_text, "reply_markup": cq["message"]["reply_markup"]})
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "✅ رای شما ثبت شد."})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "⚠️ شما قبلاً رای داده‌اید.", "show_alert": True})

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
