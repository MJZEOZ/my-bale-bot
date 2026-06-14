import os
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"

user_state = {}
polls = {}

def bot_api(method, data=None):
    return requests.post(f"{BASE_URL}/{method}", json=data)

def get_bot_username():
    try:
        res = requests.get(f"{BASE_URL}/getMe").json()
        return res.get("result", {}).get("username", "bot")
    except:
        return "bot"

def check_admin(channel_id, user_id):
    try:
        res = bot_api("getChatMember", {
            "chat_id": channel_id,
            "user_id": user_id
        }).json()

        if not res.get("ok"):
            return False

        return res["result"]["status"] in ["administrator","creator"]
    except:
        return False

@app.route("/", methods=["GET","POST"])
def receive_update():

    if request.method == "GET":
        return "Bot is Online",200

    update = request.get_json(silent=True)
    if not update:
        return "ok"

    if "message" in update:

        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text","")

        if text.startswith("/start"):

            if " " in text:
                p_id = text.split(" ")[1]
                poll = polls.get(p_id)

                if poll:
                    buttons = [
                        [{"text":opt,"callback_data":f"v_{p_id}_{i}"}]
                        for i,opt in enumerate(poll["opts"])
                    ]

                    cap = f"📊 {poll['q']}"

                    if poll["img"]:
                        bot_api("sendPhoto",{
                            "chat_id":chat_id,
                            "photo":poll["img"],
                            "caption":cap,
                            "repl_markup":{"inline_keyboard":buttons}
                        })
                    else:
                        bot_api("sendMessage",{
                            "chat_id":chat_id,
                            "text":cap,
                            "reply_markup":{"inline_keyboard":buttons}
                        })
                    return "ok"

            markup = {
                "keyboard":[[{"text":"🚀 ساخت نظرسنجی جدید"}]],
                "resize_keyboard":True
            }

            bot_api("sendMessage",
