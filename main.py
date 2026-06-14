        elif data.startswith("v_"):
            p_id = data.split("_")[1]
            opt_idx = int(data.split("_")[2])
            poll = polls.get(p_id)
            
            if not poll: return "ok"

            # ۱. بررسی عضویت (همان منطق قبلی شما)
            if not check_membership(user_id):
                join_btns = {"inline_keyboard": [
                    [{"text": "📢 ورود به کانال و عضویت", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                    [{"text": "✅ عضو شدم (ارزیابی مجدد)", "callback_data": data}]
                ]}
                warning_text = f"❌ ارزیابی ناموفق!\n\nکاربر گرامی، برای ثبت یا تغییر رای حتماً باید عضو کانال {CHANNEL_ID} باشید."
                
                # اگر پیام فعلی پیام هشدار نیست، آن را به هشدار تغییر بده، وگرنه فقط هشدار بده
                if "ارزیابی" not in cq["message"].get("text", "") and "ارزیابی" not in cq["message"].get("caption", ""):
                    bot_api("sendMessage", {"chat_id": chat_id, "text": warning_text, "reply_markup": join_btns})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "هنوز عضو نشده‌اید!", "show_alert": True})
                return "ok"

            # ۲. مدیریت تغییر رای
            previous_vote = None
            # چک میکنیم آیا کاربر قبلا رای داده؟
            for user_vote in poll["users"]:
                if user_vote["id"] == user_id:
                    previous_vote = user_vote["choice"]
                    if previous_vote == opt_idx:
                        bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً این گزینه را انتخاب کرده‌اید."})
                        return "ok"
                    # حذف رای قبلی
                    poll["votes"][previous_vote] -= 1
                    user_vote["choice"] = opt_idx # به‌روزرسانی انتخاب جدید
                    break
            
            # اگر رای اولش است:
            if previous_vote is None:
                poll["votes"][opt_idx] += 1
                poll["users"].append({"id": user_id, "choice": opt_idx})
            else:
                # اگر تغییر رای داده است:
                poll["votes"][opt_idx] += 1

            # ۳. به‌روزرسانی ظاهر دکمه‌ها (افزودن تیک به گزینه انتخاب شده)
            new_buttons = []
            for i, opt in enumerate(poll["opts"]):
                btn_text = f"✅ {opt}" if i == opt_idx else opt
                new_buttons.append([{"text": btn_text, "callback_data": f"v_{p_id}_{i}"}])

            # ۴. محاسبه آمار و ویرایش پیام
            total = sum(poll["votes"])
            res_text = f"📊 {poll['q']}\n\n"
            for i, o in enumerate(poll["opts"]):
                p = (poll["votes"][i]/total*100) if total > 0 else 0
                res_text += f"{o}: {int(p)}% ({poll['votes'][i]} رای)\n"

            method = "editMessageCaption" if poll["img"] else "editMessageText"
            field = "caption" if poll["img"] else "text"
            
            # اگر کاربر از مرحله ارزیابی آمده بود، پیام ارزیابی را پاک کن و نظرسنجی جدید بفرست
            if "ارزیابی" in cq["message"].get("text", ""):
                bot_api("deleteMessage", {"chat_id": chat_id, "message_id": cq["message"]["message_id"]})
                if poll["img"]:
                    bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": res_text, "reply_markup": {"inline_keyboard": new_buttons}})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": res_text, "reply_markup": {"inline_keyboard": new_buttons}})
            else:
                # در غیر این صورت همان پیام را ویرایش کن
                bot_api(method, {
                    "chat_id": chat_id, 
                    "message_id": cq["message"]["message_id"], 
                    field: res_text, 
                    "reply_markup": {"inline_keyboard": new_buttons}
                })
            
            bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما ثبت/تغییر یافت."})


