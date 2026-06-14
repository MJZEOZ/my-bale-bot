        elif data.startswith("v_"):
            # مرحله اول: بررسی واقعی عضویت در کانال
            if not check_membership(user_id):
                join_btns = {"inline_keyboard": [
                    [{"text": "📢 ورود به کانال و عضویت", "url": f"https://ble.ir/{CHANNEL_ID.replace('@','')}"}],
                    [{"text": "✅ عضو شدم (ارزیابی مجدد)", "callback_data": data}]
                ]}
                
                # متن هشدار در صورتی که کاربر هنوز عضو نشده باشد
                warning_text = f"❌ ارزیابی ناموفق بود!\n\nکاربر گرامی، شما هنوز در کانال {CHANNEL_ID} عضو نشده‌اید. برای شرکت در نظرسنجی، حتماً باید ابتدا عضو کانال شوید و سپس دکمه ارزیابی را بزنید."
                
                # ویرایش پیام قبلی برای جلوگیری از تکرار پیام‌ها در چت
                bot_api("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": cq["message"]["message_id"],
                    "text": warning_text,
                    "reply_markup": join_btns
                })
                bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "عضویت تایید نشد!"})
                return "ok"
            
            # مرحله دوم: اگر کاربر عضو بود، نظرسنجی را مجدد برایش میفرستیم تا رای بدهد
            p_id = data.split("_")[1]
            opt_idx = int(data.split("_")[2])
            poll = polls.get(p_id)
            
            if poll:
                # اگر کاربر از طریق دکمه "عضو شدم" آمده، پیام ارزیابی را پاک میکنیم و نظرسنجی را میفرستیم
                if "ارزیابی" in cq["message"].get("text", ""):
                    bot_api("deleteMessage", {"chat_id": chat_id, "message_id": cq["message"]["message_id"]})
                    
                    buttons = [[{"text": opt, "callback_data": f"v_{p_id}_{i}"}] for i, opt in enumerate(poll["opts"])]
                    cap = f"📊 {poll['q']}"
                    if poll["img"]:
                        bot_api("sendPhoto", {"chat_id": chat_id, "photo": poll["img"], "caption": cap, "reply_markup": {"inline_keyboard": buttons}})
                    else:
                        bot_api("sendMessage", {"chat_id": chat_id, "text": cap, "reply_markup": {"inline_keyboard": buttons}})
                    return "ok"

                # فرآیند ثبت رای اصلی (اگر قبلا رای نداده باشد)
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
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "رای شما با موفقیت ثبت شد."})
                else:
                    bot_api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "شما قبلاً در این نظرسنجی شرکت کرده‌اید.", "show_alert": True})
