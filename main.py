# -*- coding: utf-8 -*-
import os
import requests
from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")
API = f"https://tapi.bale.ai/bot{TOKEN}/"

CHANNEL_ID = "@wamsara"

app = Flask(__name__)

polls = {}
user_state = {}

# ---------------- API ----------------

def bot_api(method, data=None):
    try:
        return requests.post(API + method, json=data).json()
    except:
        return None


def get_bot_username():
    r = bot_api("getMe")
    if r and r.get("ok"):
        return r["result"]["username"]
    return "yourbot"


# ---------------- Membership ----------------

def check_membership(user_id):
    r = bot_api("getChatMember", {
        "chat_id": CHANNEL_ID,
        "user_id": user_id
    })
    if not r or not r.get("ok"):
        return False

    status = r["result"]["status"]
    return status in ["creator", "administrator", "member"]


# ---------------- Poll Rendering ----------------

def render_poll(poll_id, poll, selected=None):
    buttons = []

    total_votes = sum(poll["votes"])

    for i, opt in enumerate(poll["opts"]):

        vote_count = poll["votes"][i]
        percent = 0
        if total_votes > 0:
            percent = round((vote_count / total_votes) * 100)

        text = f"{opt} ({percent}% - {vote_count})"

        if selected == i:
            text = f"🟡 ✅ {opt} ✅ 🟡 ({percent}% - {vote_count})"

        buttons.append([{
            "text": text,
            "callback_data": f"v_{poll_id}_{i}"
        }])

    return {"inline_keyboard": buttons}


# ---------------- Routes ----------------

@app.route("/", methods=["POST"])
def webhook():

    data = request.json

    if "message" in data:

        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]

        text = msg.get("text", "")

        if text.startswith("/start"):

            parts = text.split()

            # start poll
            if len(parts) > 1:

                p_id = parts[1]

                poll = polls.get(p_id)

                if not poll:
                    bot_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": "❌ این نظرسنجی وجود ندارد."
                    })
                    return "ok"

                # membership check
                if not check_membership(user_id):

                    buttons = {
                        "inline_keyboard": [
                            [{"text": "📢 عضویت در کانال", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                            [{"text": "❓ عضو شدم", "callback_data": f"checkjoin_{p_id}"}]
                        ]
                    }

                    bot_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"برای شرکت در نظرسنجی ابتدا عضو کانال {CHANNEL_ID} شوید.",
                        "reply_markup": buttons
                    })

                    return "ok"

                # show poll
                keyboard = render_poll(p_id, poll)

                if poll["img"]:
                    bot_api("sendPhoto", {
                        "chat_id": chat_id,
                        "photo": poll["img"],
                        "caption": f"📊 {poll['q']}",
                        "reply_markup": keyboard
                    })
                else:
                    bot_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"📊 {poll['q']}",
                        "reply_markup": keyboard
                    })

                return "ok"

            # create poll
            user_state[user_id] = {"step": "q"}
            bot_api("sendMessage", {
                "chat_id": chat_id,
                "text": "سوال نظرسنجی را ارسال کنید:"
            })

        elif user_id in user_state:

            state = user_state[user_id]

            if state["step"] == "q":
                state["q"] = text
                state["opts"] = []
                state["img"] = None
                state["step"] = "opt"

                bot_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": "گزینه اول را بفرستید:"
                })

            elif state["step"] == "opt":

                if text == "/done":

                    if len(state["opts"]) < 2:
                        bot_api("sendMessage", {
                            "chat_id": chat_id,
                            "text": "حداقل دو گزینه لازم است."
                        })
                        return "ok"

                    p_id = str(len(polls) + 1)

                    polls[p_id] = {
                        "q": state["q"],
                        "img": state["img"],
                        "opts": state["opts"],
                        "votes": [0]*len(state["opts"]),
                        "users": {},
                        "creator": user_id
                    }

                    bot_username = get_bot_username()
                    link = f"https://ble.ir/{bot_username}?start={p_id}"

                    btn = {
                        "inline_keyboard":[
                            [{"text":"🔗 کپی لینک نظرسنجی","url":link}],
                            [{"text":"📈 مشاهده گزارش دقیق آرا","callback_data":f"report_{p_id}"}]
                        ]
                    }

                    bot_api("sendMessage",{
                        "chat_id":chat_id,
                        "text":f"✅ نظرسنجی ساخته شد\n\n{link}",
                        "reply_markup":btn
                    })

                    user_state.pop(user_id)

                else:

                    state["opts"].append(text)

                    bot_api("sendMessage", {
                        "chat_id": chat_id,
                        "text": "گزینه بعدی را بفرستید یا /done"
                    })

    # ---------------- CALLBACK ----------------

    if "callback_query" in data:

        cq = data["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]
        data_cb = cq["data"]

        # membership check button
        if data_cb.startswith("checkjoin_"):

            p_id = data_cb.split("_")[1]

            if not check_membership(user_id):

                bot_api("answerCallbackQuery", {
                    "callback_query_id": cq["id"],
                    "text": "❌ هنوز عضو کانال نشده‌اید",
                    "show_alert": True
                })

                return "ok"

            # change button to ✅
            buttons = {
                "inline_keyboard":[
                    [{"text":"✅ عضویت تایید شد","callback_data":"ok"}]
                ]
            }

            bot_api("editMessageReplyMarkup",{
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":buttons
            })

            poll = polls.get(p_id)

            keyboard = render_poll(p_id,poll)

            bot_api("sendMessage",{
                "chat_id":chat_id,
                "text":f"📊 {poll['q']}",
                "reply_markup":keyboard
            })

            return "ok"

        # voting
        if data_cb.startswith("v_"):

            _,p_id,opt = data_cb.split("_")
            opt = int(opt)

            poll = polls.get(p_id)

            if not poll:
                return "ok"

            prev = poll["users"].get(user_id)

            if prev is not None:
                poll["votes"][prev] -= 1

            poll["votes"][opt] += 1
            poll["users"][user_id] = opt

            keyboard = render_poll(p_id,poll,opt)

            bot_api("editMessageReplyMarkup",{
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            })

        # report
        if data_cb.startswith("report_"):

            p_id = data_cb.split("_")[1]
            poll = polls.get(p_id)

            if not poll:
                return "ok"

            total = sum(poll["votes"])

            ranking = []

            for i,opt in enumerate(poll["opts"]):

                v = poll["votes"][i]

                percent = 0
                if total > 0:
                    percent = round((v/total)*100)

                ranking.append((opt,v,percent))

            ranking.sort(key=lambda x: x[1],reverse=True)

            nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣"]

            text = "📈 گزارش دقیق آرا\n\n"

            for i,(opt,v,p) in enumerate(ranking):
                text += f"{nums[i]} {opt}\n{v} رای — {p}%\n\n"

            bot_api("answerCallbackQuery",{
                "callback_query_id":cq["id"],
                "text":"گزارش ارسال شد"
            })

            bot_api("sendMessage",{
                "chat_id":chat_id,
                "text":text
            })

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


