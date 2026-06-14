import os
import requests
from flask import Flask, request

app = Flask(__name__)

# --- تنظیمات توکن ---
TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

# حافظه موقت (بعد از ریست شدن رندر پاک می‌شود)
user_state = {}
polls = {}

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

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

        # شروع ساخت نظرسنجی
        if text == "/start" or text == "🚀 ساخت نظرسنجی جدید":
            user_state[user_id] = {"step": "get_q"}
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": "🔴 مرحله ۱: سوال نظرسنجی را بنویسید:",
                "reply_markup": {"remove_keyboard": True}
            })

        # دریافت سوال
        elif user_id in user_state and user_state[user_id]["step"] == "get_q":
            user_state[user_id].update({"q": text, "opts": [], "step": "get_opts"})
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": "🟢 مرحله ۲: حالا گزینه‌ها را یکی یکی بفرستید. حداقل ۲ گزینه لازم است.\n\nبعد از اتمام، روی دکمه 'تایید نهایی' بزنید.",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "✅ تایید نهایی و انتشار", "callback_data": "finish"}]]
                }
            })

        # دریافت گزینه‌ها
        elif user_id in user_state and user_state[user_id]["step"] == "get_opts":
            user_state[user_id]["opts"].append(text)
            bot_api("sendMessage", {
                "chat_id": chat_id, 
                "text": f"گزینه '{text}' ثبت شد. گزینه بعدی را بفرستید یا تایید کنید.",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "✅ تایید نهایی و انتشار", "callback_data": "finish"}]]
                }
            })

        # دریافت آیدی کانال برای انتشار مستقیم
        elif user_id in user_state and user_state[user_id]["step"] == "get_channel":
            channel_id = text if text.startswith("@") else f"@{text}"
            p_id = user_state[user_id]["poll_id"]
            poll = polls[p_id]

            # ساخت دکمه‌های رای‌گیری
            btns = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
            
            # ارسال مستقیم به کانال
            res = bot_api("sendMessage", {
                "chat_id": channel_id,
                "text": f"📊 {poll['q']}\n\n(برای رای دادن روی گزینه‌ها کلیک کنید)",
                "reply_markup": {"inline_keyboard": btns}
            })

            if res.status_code == 200:
                bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ نظرسنجی با موفقیت در کانال {channel_id} منتشر شد!"})
                user_state[user_id] = None
            else:
                bot_api("sendMessage", {"chat_id": chat_id, "text": "❌ خطا! مطمئن شوید ربات در کانال ادمین است و آیدی را درست وارد کردید."})

    elif "callback_query" in update:
        cq = update["callback_query"]
        data = cq["data"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]

        # پایان ساخت و درخواست آیدی کانال
        if data == "finish":
            state = user_state.get(user_id)
            if state and len(state["opts"]) >= 2:
                p_id = str(len(polls) + 1)
                polls[p_id] = {"q": state["q"], "opts": state["opts"], "votes": [0]*len(state["opts"]), "users": []}
                user_state[user_id] = {"step": "get_channel", "poll_id": p_id}
                bot_api("sendMessage", {
                    "chat_id": chat_id, 
                    "text": "📢 آیدی کانال را بفرستید تا نظرسنجی فوراً آنجا منتشر شود:\nمثلاً: @my_channel"
                })
        
        # پردازش رای‌ها در کانال
        elif data.startswith("v_"):
            p_id, opt_idx = data.split("_")[1], int(data.split("_")[2])
            poll = polls.get(p_id)
            if poll:
                if user_id not in poll["users"]:
                    poll["votes"][opt_idx] += 1
                    poll["users"].append(user_id)
                    total = sum(poll["votes"])
                    
                    # آپدیت متن نظرسنجی با نتایج جدید
                    new_text = f"📊 {poll['q']}\n\n"
                    for i, o in enumerate(poll["opts"]):
                        p = (poll["votes"][i]/total*100) if total > 0 else 0
                        new_text += f"{o}: {int(p)}% ({poll['votes'][i]} رای)\n"
                    
                    bot_api("editMessageText", {
                        "chat_id": chat_id,
                        "message_id": cq["message"]["message_id"],
                        "text": new_text,
                        "reply_markup": cq["message"]["reply_markup"]
                    })
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما ثبت شد"})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "قبلاً رای داده‌اید", "show_alert": True})

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
