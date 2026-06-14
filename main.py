import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
REQUIRED_CHANNEL = "@wamsara"  # کانالی که عضویت در آن الزامی است

user_state = {}
polls = {}

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

def check_membership(user_id):
    """بررسی عضویت کاربر در کانال الزامی"""
    try:
        res = bot_api("getChatMember", {"chat_id": REQUIRED_CHANNEL, "user_id": user_id}).json()
        if res.get("ok"):
            status = res["result"]["status"]
            return status in ["member", "administrator", "creator"]
        return False
    except:
        return False

@app.route("/", methods=["GET", "POST"])
def receive_update():
    if request.method == "GET":
        return "Bot is Online", 200

    update = request.get_json(silent=True)
    if not update: return "ok", 200

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # شروع فرآیند
        if text == "/start" or text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": "🔴 مرحله ۱: متن سوال را بنویسید:",
                "reply_markup": {"remove_keyboard": True}
            })

        elif user_id in user_state:
            state = user_state[user_id]

            # دریافت سوال
            if state["step"] == "get_q":
                state.update({"q": text, "opts": [], "step": "get_opts"})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "🟢 مرحله ۲: گزینه‌ها را یکی یکی بفرستید (حداقل ۲ مورد).\nبعد از اتمام، روی دکمه زیر بزنید:", 
                    "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام ثبت گزینه‌ها", "callback_data": "finish_opts"}]]}})

            # دریافت گزینه‌ها
            elif state["step"] == "get_opts":
                state["opts"].append(text)
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه '{text}' ثبت شد. بعدی را بفرستید یا تمام کنید:", 
                    "reply_markup": {"inline_keyboard": [[{"text": "✅ اتمام ثبت گزینه‌ها", "callback_data": "finish_opts"}]]}})

            # دریافت عکس
            elif state["step"] == "get_img" and "photo" in msg:
                state["img"] = msg["photo"][-1]["file_id"]
                show_preview(chat_id, user_id)

            # دریافت آیدی کانال برای انتشار
            elif state["step"] == "get_channel":
                publish_to_channel(chat_id, user_id, text)

    elif "callback_query" in update:
        cq = update["callback_query"]
        data = cq["data"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]

        # بعد از اتمام گزینه‌ها -> درخواست عکس
        if data == "finish_opts":
            if len(user_state[user_id]["opts"]) < 2:
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "حداقل ۲ گزینه لازم است!", "show_alert": True})
            else:
                user_state[user_id]["step"] = "get_img"
                bot_api("sendMessage", {"chat_id": chat_id, "text": "📸 مرحله ۳: اگر مایلید یک عکس بفرستید، در غیر این صورت دکمه زیر را بزنید:", 
                    "reply_markup": {"inline_keyboard": [[{"text": "⏩ بدون عکس (ادامه)", "callback_data": "skip_img"}]]}})

        elif data == "skip_img":
            user_state[user_id]["img"] = None
            show_preview(chat_id, user_id)

        elif data == "start_publish":
            user_state[user_id]["step"] = "get_channel"
            bot_api("sendMessage", {"chat_id": chat_id, "text": "📢 آیدی کانال مقصد را بفرستید (مثلاً @mychannel):"})

        # عملیات رای‌گیری (با بررسی عضویت)
        elif data.startswith("v_"):
            handle_vote(chat_id, user_id, cq)

    return "ok", 200

def show_preview(chat_id, user_id):
    """نمایش پیش‌نمایش به ادمین قبل از انتشار"""
    state = user_state[user_id]
    p_id = str(len(polls) + 1)
    polls[p_id] = {"q": state["q"], "opts": state["opts"], "img": state.get("img"), "votes": [0]*len(state["opts"]), "users": []}
    
    btns = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(state["opts"])]
    text = f"👀 پیش‌نمایش نظرسنجی شما:\n\n📊 {state['q']}"
    
    if state.get("img"):
        bot_api("sendPhoto", {"chat_id": chat_id, "photo": state["img"], "caption": text, "reply_markup": {"inline_keyboard": btns}})
    else:
        bot_api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": {"inline_keyboard": btns}})
    
    bot_api("sendMessage", {"chat_id": chat_id, "text": "آیا از ظاهر نظرسنجی راضی هستید؟", 
        "reply_markup": {"inline_keyboard": [[{"text": "🚀 تایید و انتشار در کانال", "callback_data": "start_publish"}], [{"text": "❌ انصراف و شروع مجدد", "callback_data": "restart"}]]}})
    user_state[user_id]["poll_id"] = p_id

def publish_to_channel(chat_id, user_id, channel_text):
    """ارسال نهایی به کانال مقصد"""
    channel_id = channel_text if channel_text.startswith("@") else f"@{channel_text}"
    p_id = user_state[user_id]["poll_id"]
    poll = polls[p_id]
    
    btns = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
    cap = f"📊 {poll['q']}"

    if poll["img"]:
        res = bot_api("sendPhoto", {"chat_id": channel_id, "photo": poll["img"], "caption": cap, "reply_markup": {"inline_keyboard": btns}})
    else:
        res = bot_api("sendMessage", {"chat_id": channel_id, "text": cap, "reply_markup": {"inline_keyboard": btns}})

    if res.status_code == 200:
        bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ با موفقیت در کانال {channel_id} منتشر شد."})
        user_state[user_id] = None
    else:
        bot_api("sendMessage", {"chat_id": chat_id, "text": "❌ خطا! ادمین بودن ربات یا آیدی کانال را چک کنید."})

def handle_vote(chat_id, user_id, cq):
    """مدیریت رای‌گیری و چک کردن عضویت"""
    data = cq["data"]
    p_id, opt_idx = data.split("_")[1], int(data.split("_")[2])
    poll = polls.get(p_id)
    
    if not poll: return

    # ۱. بررسی عضویت اجباری
    if not check_membership(user_id):
        bot_api("answerCallbackQuery", {
            "callback_query_id": cq["id"], 
            "text": f"⚠️ برای ثبت رای باید عضو کانال {REQUIRED_CHANNEL} باشید!", 
            "show_alert": True
        })
        return

    # ۲. بررسی تکراری نبودن رای
    if user_id in poll["users"]:
        bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً رای داده‌اید.", "show_alert": True})
        return

    # ۳. ثبت رای و آپدیت پیام
    poll["votes"][opt_idx] += 1
    poll["users"].append(user_id)
    total = sum(poll["votes"])
    
    new_text = f"📊 {poll['q']}\n\n"
    for i, o in enumerate(poll["opts"]):
        p = (poll["votes"][i]/total*100) if total > 0 else 0
        new_text += f"{o}: {int(p)}% ({poll['votes'][i]} رای)\n"
    
    method = "editMessageCaption" if poll["img"] else "editMessageText"
    field = "caption" if poll["img"] else "text"
    
    bot_api(method, {
        "chat_id": chat_id,
        "message_id": cq["message"]["message_id"],
        field: new_text,
        "reply_markup": cq["message"]["reply_markup"]
    })
    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "✅ رای شما با موفقیت ثبت شد."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
