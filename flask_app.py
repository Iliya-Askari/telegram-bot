from flask import Flask, request
import telebot
import logging

logging.basicConfig(level=logging.DEBUG)

TOKEN = '8976118793:AAFYGenztS5eeq6PVMEJcBq1Uiq8wSxCqUo'
WEBHOOK_URL = 'https://telegram-bot-7nhc.onrender.com/' + TOKEN

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
users = []

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    logging.debug(f"Start from {chat_id}")
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
    global users
    if message.chat.id in users:
        for u in users:
            bot.send_message(u, "چت پایان یافت.")
        users = []

@bot.message_handler(commands=['clear_all'])
def handle_admin_clear(message):
    global users
    users = []
    bot.send_message(message.chat.id, "ظرفیت صفر شد.")

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_messages(message):
    chat_id = message.chat.id
    if chat_id in users and len(users) == 2:
        other_user = users[0] if users[1] == chat_id else users[1]
        bot.copy_message(
            chat_id=other_user,
            from_chat_id=chat_id,
            message_id=message.message_id,
            protect_content=True
        )
    elif chat_id in users and len(users) < 2:
        bot.send_message(chat_id, "هنوز نفر دوم وارد ربات نشده است...")

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    logging.debug(f"Received update: {json_string}")
    update = telebot.types.Update.de_json(json_string)
    logging.debug(f"Update object: {update}")
    logging.debug(f"Message: {update.message}")
    bot.process_new_updates([update])
    logging.debug("process_new_updates called")
    return 'OK', 200

@app.route('/')
def index():
    return "bot is running!", 200
