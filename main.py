        elif data.startswith("v_"):
            p_id = data.split("_")[1]
            opt_idx = int(data.split("_")[2])
            poll = polls.get(p_id)
            if not poll: return "ok"

            # --- مرحله ۱: بررسی عضویت هوشمند ---
            if not check_membership(user_id):
                join_btns = {"inline_keyboard": [
                    [{"text": "📢 ورود به کانال وام‌سرا", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                    [{"text": "🔄 ارزیابی مجدد عضویت", "callback_data": data}]
                ]}
                # نمایش علامت ضربدر قرمز در هنگام عدم عضویت
                warning_text = f"❌ وضعیت: عدم عضویت!\n\nکاربر گرامی، برای ثبت رای در نظرسنجی «{poll['q']}» حتماً باید عضو کانال {CHANNEL_ID} باشید."
                
                if "وضعیت" not in cq["message"].get("text", ""):
                    bot_api("sendMessage", {"chat_id": chat_id, "text": warning_text, "reply_markup": join_btns})
                else:
                    bot_api("editMessageText", {"chat_id": chat_id, "message_id": cq["message"]["message_id"], "text": warning_text, "reply_markup": join_btns})
                return "ok"

            # --- مرحله ۲: تایید عضویت و ارسال مجدد نظرسنجی ---
            # اگر کاربر دکمه ارزیابی را زده و عضو شده بود:
            if "وضعیت" in cq["message"].get("text", ""):
                # تغییر پیام به تیک سبز برای یک لحظه
                bot_api("editMessageText", {
                    "chat_id": chat_id, 
                    "message_id": cq["message"]["message_id"], 
                    "text": "✅ عضویت تایید شد! در حال انتقال به نظرسنجی..."
                })
                # حذف پیام ارزیابی و ارسال مجدد نظرسنجی اصلی
                bot_api("deleteMessage", {"chat_id": chat_id, "message_id": cq["message"]["message_id"]})
                
                # نمایش دکمه‌ها (بدون انتخاب اولیه)
                btns = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                if poll["img"]:
                    bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": f"📊 {poll['q']}", "reply_markup": {"inline_keyboard": btns}})
                else:
                    bot_api("sendMessage", {"chat_id": chat_id, "text": f"📊 {poll['q']}", "reply_markup": {"inline_keyboard": btns}})
                return "ok"

            # --- مرحله ۳: ثبت یا تغییر رای (با تم طلایی/تیک) ---
            previous_vote = None
            for user_vote in poll["users"]:
                if user_vote["id"] == user_id:
                    previous_vote = user_vote["choice"]
                    if previous_vote == opt_idx:
                        bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "این گزینه قبلاً توسط شما انتخاب شده است."})
                        return "ok"
                    poll["votes"][previous_vote] -= 1
                    user_vote["choice"] = opt_idx
                    break
            
            if previous_vote is None:
                poll["votes"][opt_idx] += 1
                poll["users"].append({"id": user_id, "choice": opt_idx})
            else:
                poll["votes"][opt_idx] += 1

            # ایجاد دکمه‌ها با استایل متمایز برای گزینه انتخاب شده
            new_buttons = []
            for i, opt in enumerate(poll["opts"]):
                # استفاده از ایموجی دایره طلایی و تیک برای متمایز کردن (شبیه سازی رنگ طلایی)
                btn_text = f"🟡 ✅ {opt} ✅ 🟡" if i == opt_idx else opt
                new_buttons.append([{"text": btn_text, "callback_data": f"v_{p_id}_{i}"}])

            # به‌روزرسانی متن آمار
            total = sum(poll["votes"])
            res_text = f"📊 {poll['q']}\n\n"
            for i, o in enumerate(poll["opts"]):
                p = (poll["votes"][i]/total*100) if total > 0 else 0
                res_text += f"{o}: {int(p)}% ({poll['votes'][i]} رای)\n"

            method = "editMessageCaption" if poll["img"] else "editMessageText"
            field = "caption" if poll["img"] else "text"
            bot_api(method, {
                "chat_id": chat_id, 
                "message_id": cq["message"]["message_id"], 
                field: res_text, 
                "reply_markup": {"inline_keyboard": new_buttons}
            })
            bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما با موفقیت تغییر کرد."})
