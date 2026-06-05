from flask import Flask, request
import telebot
import logging

logging.basicConfig(level=logging.DEBUG)

TOKEN = '8976118793:AAFYGenztS5eeq6PVMEJcBq1Uiq8wSxCqUo'

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
users = []
message_map = {}  # نگه داشتن نقشه پیام‌ها برای reply و edit

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if chat_id not in users:
        if len(users) < 2:
            users.append(chat_id)
            bot.send_message(chat_id, "شما به چت متصل شدید.")
            if len(users) == 2:
                for u in users:
                    bot.send_message(u, "ارتباط برقرار شد!")
        else:
            bot.send_message(chat_id, "ظرفیت چت پر است.")
    else:
        bot.send_message(chat_id, "شما از قبل داخل چت هستید.")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global users, message_map
    if message.chat.id in users:
        for u in users:
            bot.send_message(u, "چت پایان یافت.")
        users = []
        message_map = {}

@bot.message_handler(commands=['clear_all'])
def handle_admin_clear(message):
    global users, message_map
    users = []
    message_map = {}
    bot.send_message(message.chat.id, "ظرفیت صفر شد.")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_messages(message):
    chat_id = message.chat.id
    if chat_id in users and len(users) == 2:
        other_user = users[0] if users[1] == chat_id else users[1]

        reply_to = None
        if message.reply_to_message:
            original_id = message.reply_to_message.message_id
            key = f"{chat_id}:{original_id}"
            if key in message_map:
                reply_to = message_map[key]

        sent = bot.copy_message(
            chat_id=other_user,
            from_chat_id=chat_id,
            message_id=message.message_id,
            protect_content=True,
            reply_to_message_id=reply_to
        )

        # ذخیره نقشه پیام‌ها
        message_map[f"{other_user}:{sent.message_id}"] = message.message_id
        message_map[f"{chat_id}:{message.message_id}"] = sent.message_id

    elif chat_id in users and len(users) < 2:
        bot.send_message(chat_id, "هنوز نفر دوم وارد ربات نشده است...")

@bot.edited_message_handler(func=lambda message: True)
def handle_edited_message(message):
    chat_id = message.chat.id
    if chat_id in users and len(users) == 2:
        other_user = users[0] if users[1] == chat_id else users[1]
        key = f"{chat_id}:{message.message_id}"
        if key in message_map:
            other_message_id = message_map[key]
            try:
                if message.text:
                    bot.edit_message_text(
                        chat_id=other_user,
                        message_id=other_message_id,
                        text=message.text
                    )
                elif message.caption:
                    bot.edit_message_caption(
                        chat_id=other_user,
                        message_id=other_message_id,
                        caption=message.caption
                    )
            except Exception as e:
                logging.debug(f"Edit error: {e}")

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    return "bot is running!", 200
