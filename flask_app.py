from flask import Flask, request
import telebot
import logging
import json
import os
import re

logging.basicConfig(level=logging.DEBUG)

GROUPS_FILE = 'groups.json'

def load_settings():
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_group_settings(chat_id):
    settings = load_settings()
    chat_id = str(chat_id)
    if chat_id not in settings:
        settings[chat_id] = {
            "locks": {
                "links": False,
                "tags": False,
                "forwards": False,
                "stickers": False,
                "media": False,
                "service": False
            },
            "welcome": {
                "enabled": False,
                "text": "خوش آمدید!"
            }
        }
        save_settings(settings)
    return settings[chat_id]

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False

TOKEN = '8608812191:AAH1FdweBXAMMifn1FawPiua8CKlFPm2XSQ'

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            user_id = int(parts[1])

    if user_id:
        try:
            bot.ban_chat_member(message.chat.id, user_id)
            bot.reply_to(message, f"کاربر {user_id} مسدود شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    user_id = None
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        user_id = int(parts[1])

    if user_id:
        try:
            bot.unban_chat_member(message.chat.id, user_id, only_if_blocked=True)
            bot.reply_to(message, f"کاربر {user_id} آزاد شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(commands=['kick'])
def kick_user(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            user_id = int(parts[1])

    if user_id:
        try:
            bot.ban_chat_member(message.chat.id, user_id)
            bot.unban_chat_member(message.chat.id, user_id)
            bot.reply_to(message, f"کاربر {user_id} اخراج شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            user_id = int(parts[1])

    if user_id:
        try:
            bot.restrict_chat_member(message.chat.id, user_id, can_send_messages=False)
            bot.reply_to(message, f"کاربر {user_id} بی‌صدا شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    user_id = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            user_id = int(parts[1])

    if user_id:
        try:
            bot.restrict_chat_member(message.chat.id, user_id,
                                     can_send_messages=True,
                                     can_send_media_messages=True,
                                     can_send_other_messages=True,
                                     can_add_web_page_previews=True)
            bot.reply_to(message, f"کاربر {user_id} مجدداً مجاز به ارسال پیام شد.")
        except Exception as e:
            bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_group_filters(message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    settings = get_group_settings(chat_id)
    locks = settings['locks']

    if is_admin(chat_id, user_id):
        return

    should_delete = False

    # Check for Links
    if locks.get('links'):
        if re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.text or message.caption or ''):
            should_delete = True

    # Check for Usernames/Tags
    if not should_delete and locks.get('tags'):
        if re.search(r'@\w+', message.text or message.caption or ''):
            should_delete = True

    # Check for Forwards
    if not should_delete and locks.get('forwards'):
        if message.forward_from or message.forward_from_chat:
            should_delete = True

    # Check for Stickers
    if not should_delete and locks.get('stickers'):
        if message.content_type == 'sticker':
            should_delete = True

    # Check for Media
    if not should_delete and locks.get('media'):
        if message.content_type in ['photo', 'video', 'voice', 'animation', 'document']:
            should_delete = True

    if should_delete:
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            logging.error(f"Error deleting message: {e}")

@bot.message_handler(commands=['lock'])
def lock_feature(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    parts = message.text.split()
    if len(parts) > 1:
        feature = parts[1]
        get_group_settings(message.chat.id) # Ensure initialization
        settings = load_settings()
        chat_id = str(message.chat.id)
        if chat_id in settings and feature in settings[chat_id]['locks']:
            settings[chat_id]['locks'][feature] = True
            save_settings(settings)
            bot.reply_to(message, f"قابلیت {feature} قفل شد.")
        else:
            bot.reply_to(message, "قابلیت نامعتبر است.")

@bot.message_handler(commands=['unlock'])
def unlock_feature(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    parts = message.text.split()
    if len(parts) > 1:
        feature = parts[1]
        get_group_settings(message.chat.id) # Ensure initialization
        settings = load_settings()
        chat_id = str(message.chat.id)
        if chat_id in settings and feature in settings[chat_id]['locks']:
            settings[chat_id]['locks'][feature] = False
            save_settings(settings)
            bot.reply_to(message, f"قابلیت {feature} باز شد.")
        else:
            bot.reply_to(message, "قابلیت نامعتبر است.")

@bot.message_handler(commands=['setwelcome'])
def set_welcome(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    welcome_text = message.text.replace('/setwelcome', '').strip()
    if welcome_text:
        settings = load_settings()
        chat_id = str(message.chat.id)
        if chat_id not in settings: get_group_settings(chat_id); settings = load_settings()
        settings[chat_id]['welcome']['text'] = welcome_text
        save_settings(settings)
        bot.reply_to(message, "متن خوش‌آمدگویی تنظیم شد.")

@bot.message_handler(commands=['welcome'])
def toggle_welcome(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    parts = message.text.split()
    if len(parts) > 1:
        state = parts[1].lower()
        settings = load_settings()
        chat_id = str(message.chat.id)
        if chat_id not in settings: get_group_settings(chat_id); settings = load_settings()

        if state == 'on':
            settings[chat_id]['welcome']['enabled'] = True
            bot.reply_to(message, "خوش‌آمدگویی فعال شد.")
        elif state == 'off':
            settings[chat_id]['welcome']['enabled'] = False
            bot.reply_to(message, "خوش‌آمدگویی غیرفعال شد.")
        save_settings(settings)

@bot.message_handler(commands=['settings'])
def show_settings(message):
    if message.chat.type not in ['group', 'supergroup']: return
    if not is_admin(message.chat.id, message.from_user.id): return

    settings = get_group_settings(message.chat.id)
    locks = settings['locks']
    welcome = settings['welcome']

    text = "تنظیمات گروه:\n\n"
    for lock, state in locks.items():
        text += f"{lock}: {'✅ قفل' if state else '❌ باز'}\n"

    text += f"\nخوش‌آمدگویی: {'✅ فعال' if welcome['enabled'] else '❌ غیرفعال'}"
    bot.reply_to(message, text)

@bot.message_handler(content_types=['new_chat_members', 'left_chat_member'])
def handle_service_messages(message):
    settings = get_group_settings(message.chat.id)

    # Handle Service Locks
    if settings['locks'].get('service'):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            logging.error(f"Error deleting service message: {e}")

    # Handle Welcome Message
    if message.content_type == 'new_chat_members' and settings['welcome']['enabled']:
        for new_member in message.new_chat_members:
            welcome_text = settings['welcome']['text']
            # Simple placeholder replacement
            welcome_text = welcome_text.replace('{name}', new_member.first_name)
            bot.send_message(message.chat.id, welcome_text)

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def index():
    return "bot is running!", 200
