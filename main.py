# -*- coding: utf-8 -*-
import os
import json
import requests
from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")
API = f"https://tapi.bale.ai/bot{TOKEN}/"
CHANNEL_ID = "@wamsara"
DB_FILE = "polls_db.json"

app = Flask(__name__)

# بارگذاری داده‌ها از فایل برای جلوگیری از پاک شدن
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

polls = load_db()
user_state = {}

def bot_api(method, data=None):
    try:
        return requests.post(API + method, json=data).json()
    except: return None

def get_bot_username():
    r = bot_api("getMe")
    return r["result"]["username"] if r and r.get("ok") else "bot"

def check_membership(user_id):
    r = bot_api("getChatMember", {"chat_id": CHANNEL_ID, "user_id": user_id})
    if r and r.get("ok"):
        return r["result"]["status"] in ["creator", "administrator", "member"]
    return False

def render_poll(p_id, poll, selected=None):
    buttons = []
    total = sum(poll["votes"])
    for i, opt in enumerate(poll["opts"]):
        v = poll["votes"][i]
        p = round((v/total)*100) if total > 0 else 0
        txt = f"{opt} ({p}% - {v})"
        if selected == i: txt = f"🟡 ✅ {opt} ✅ 🟡 ({p}% - {v})"
        buttons.append([{"text": txt, "callback_data": f"v_{p_id}_{i}"}])
    return {"inline_keyboard": buttons}

@app.route("/", methods=["POST"])
def webhook():
    global polls
    data = request.json
    
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                p_id = parts[1]
                poll = polls.get(p_id)
                if not poll:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": "❌ نظرسنجی یافت نشد."})
                    return "ok"
                
                if not check_membership(user_id):
                    btns = {"inline_keyboard": [
                        [{"text": "📢 عضویت در کانال", "url": f"https://ble.ir/{CHANNEL_ID[1:]}"}],
                        [{"text": "❓ عضو شدم", "callback_data": f"check_{p_id}"}]
                    ]}
                    bot_api("sendMessage", {"chat_id": chat_id, "text": f"لطفاً برای شرکت در نظرسنجی ابتدا در کانال {CHANNEL_ID} عضو شوید.", "reply_markup": btns})
                    return "ok"

                kb = render_poll(p_id, poll)
                if poll.get("img"):
                    bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": f"📊 {poll['q']}", "reply_markup": kb})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": f"📊 {poll['q']}", "reply_markup": kb})
                return "ok"

            user_state[user_id] = {"step": "q"}
            bot_api("sendMessage", {"chat_id": chat_id, "text": "لطفاً سوال نظرسنجی را بفرستید:"})

        elif user_id in user_state:
            st = user_state[user_id]
            if st["step"] == "q":
                st.update({"q": text, "opts": [], "img": None, "step": "opt"})
                bot_api("sendMessage", {"chat_id": chat_id, "text": "حالا گزینه اول را بفرستید:"})
            elif st["step"] == "opt":
                if text == "/done":
                    if len(st["opts"]) < 2:
                        bot_api("sendMessage", {"chat_id": chat_id, "text": "حداقل ۲ گزینه بفرستید."})
                    else:
                        p_id = str(len(polls) + 1)
                        polls[p_id] = {"q": st["q"], "img": st.get("img"), "opts": st["opts"], "votes": [0]*len(st["opts"]), "users": {}}
                        save_db(polls)
                        link = f"https://ble.ir/{get_bot_username()}?start={p_id}"
                        btns = {"inline_keyboard": [[{"text": "🔗 لینک انتشار", "url": link}], [{"text": "📈 گزارش آرا", "callback_data": f"rep_{p_id}"}]]}
                        bot_api("sendMessage", {"chat_id": chat_id, "text": f"✅ ساخته شد!\n\nلینک کپی:\n`{link}`", "reply_markup": btns, "parse_mode": "Markdown"})
                        del user_state[user_id]
                else:
                    st["opts"].append(text)
                    bot_api("sendMessage", {"chat_id": chat_id, "text": f"گزینه {len(st['opts'])+1} را بفرستید یا پایان با /done"})

    if "callback_query" in data:
        cq = data["callback_query"]
        u_id, c_id, m_id, cb_data = cq["from"]["id"], cq["message"]["chat"]["id"], cq["message"]["message_id"], cq["data"]

        if cb_data.startswith("check_"):
            p_id = cb_data.split("_")[1]
            if check_membership(u_id):
                bot_api("editMessageReplyMarkup", {"chat_id": c_id, "message_id": m_id, "reply_markup": {"inline_keyboard": [[{"text": "✅ عضویت تایید شد", "callback_data": "none"}]]}})
                poll = polls.get(p_id)
                kb = render_poll(p_id, poll)
                bot_api("sendMessage", {"chat_id": c_id, "text": f"📊 {poll['q']}", "reply_markup": kb})
            else:
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "❌ هنوز عضو نیستید!", "show_alert": True})

        elif cb_data.startswith("v_"):
            _, p_id, opt_idx = cb_data.split("_")
            opt_idx = int(opt_idx)
            poll = polls.get(p_id)
            if poll:
                old_v = poll["users"].get(str(u_id))
                if old_v is not None: poll["votes"][old_v] -= 1
                poll["votes"][opt_idx] += 1
                poll["users"][str(u_id)] = opt_idx
                save_db(polls)
                bot_api("editMessageReplyMarkup", {"chat_id": c_id, "message_id": m_id, "reply_markup": render_poll(p_id, poll, opt_idx)})

        elif cb_data.startswith("rep_"):
            p_id = cb_data.split("_")[1]
            poll = polls.get(p_id)
            if poll:
                res = sorted(zip(poll["opts"], poll["votes"]), key=lambda x: x[1], reverse=True)
                total = sum(poll["votes"])
                txt = "📈 گزارش آرا:\n\n"
                icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
                for i, (o, v) in enumerate(res):
                    p = round((v/total)*100) if total > 0 else 0
                    txt += f"{icons[i] if i<5 else '🔹'} {o}\n{v} رای ({p}%)\n\n"
                bot_api("sendMessage", {"chat_id": c_id, "text": txt})

    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

