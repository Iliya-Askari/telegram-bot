from flask import Flask, request

import telebot

from telebot.types import ChatPermissions

import logging

import json

import os

import html

import re

import datetime



logging.basicConfig(level=logging.DEBUG)



DATA_FILE = 'data.json'



def load_data():

    if os.path.exists(DATA_FILE):

        with open(DATA_FILE, 'r', encoding='utf-8') as f:

            return json.load(f)

    return {}



def save_data(data):

    with open(DATA_FILE, 'w', encoding='utf-8') as f:

        json.dump(data, f, ensure_ascii=False, indent=4)



def get_group(chat_id):

    data = load_data()

    cid = str(chat_id)

    if cid not in data:

        data[cid] = {

            "locks": {"لینک": False, "تگ": False, "فوروارد": False, "استیکر": False, "مدیا": False, "سرویس": False},

            "welcome": {"enabled": False, "text": "خوش آمدید {name}!"},

            "bot_admins": [],

            "vip_members": [],

            "nicknames": {},

            "stats": {},

            "flirty_mode": False,

            "banned_users": {},

            "muted_users": {}

        }

        save_data(data)

    return data[cid]



def save_group(chat_id, group_data):

    data = load_data()

    data[str(chat_id)] = group_data

    save_data(data)



def is_owner(chat_id, user_id):

    try:

        member = bot.get_chat_member(chat_id, user_id)

        return member.status == 'creator'

    except:

        return False



def is_telegram_admin(chat_id, user_id):

    try:

        member = bot.get_chat_member(chat_id, user_id)

        return member.status in ['administrator', 'creator']

    except:

        return False



def is_bot_admin(chat_id, user_id):

    group = get_group(chat_id)

    return str(user_id) in group.get('bot_admins', []) or is_telegram_admin(chat_id, user_id)



def is_vip(chat_id, user_id):

    group = get_group(chat_id)

    return str(user_id) in group.get('vip_members', [])



def get_name(chat_id, user):

    group = get_group(chat_id)

    nicknames = group.get('nicknames', {})

    if str(user.id) in nicknames:

        return nicknames[str(user.id)]

    return user.first_name



def add_stat(chat_id, user_id, first_name):

    data = load_data()

    cid = str(chat_id)

    uid = str(user_id)

    today = datetime.date.today().isoformat()

    if cid not in data:

        get_group(chat_id)

        data = load_data()

    if 'stats' not in data[cid]:

        data[cid]['stats'] = {}

    if uid not in data[cid]['stats']:

        data[cid]['stats'][uid] = {'name': first_name, 'total': 0, 'daily': {}}

    data[cid]['stats'][uid]['total'] += 1

    data[cid]['stats'][uid]['name'] = first_name

    if today not in data[cid]['stats'][uid]['daily']:

        data[cid]['stats'][uid]['daily'][today] = 0

    data[cid]['stats'][uid]['daily'][today] += 1

    save_data(data)



def check_action_permission(chat_id, actor_id, target_id):

    """

    بررسی اینکه آیا actor مجاز به انجام عملیات روی target هست

    خروجی: (مجاز؟, پیام خطا)

    """

    if is_owner(chat_id, target_id):

        return False, "👑 این کاربر مالک گپ است و نمی‌توان روی او عملیات انجام داد."

    if not is_owner(chat_id, actor_id):

        if is_telegram_admin(chat_id, target_id) or is_bot_admin(chat_id, target_id):

            return False, "🛡️ این کاربر ادمین است. فقط مالک گپ می‌تواند روی ادمین‌ها عملیات انجام دهد."

        if is_vip(chat_id, target_id):

            return False, "⭐ این کاربر عضو ویژه است. فقط مالک گپ می‌تواند روی اعضای ویژه عملیات انجام دهد."

    return True, ""


def is_user_removed(chat_id, user_id):
    group = get_group(chat_id)
    return str(user_id) in group.get('banned_users', {})


def store_removed_user(chat_id, user_id, user_name):
    data = load_data()
    cid = str(chat_id)
    if cid not in data:
        get_group(chat_id)
        data = load_data()
    data[cid].setdefault('banned_users', {})[str(user_id)] = user_name
    save_data(data)


def remove_user_from_ban_list(chat_id, user_id):
    data = load_data()
    cid = str(chat_id)
    if cid not in data:
        return None
    removed = data[cid].get('banned_users', {}).pop(str(user_id), None)
    save_data(data)
    return removed


def get_group_link(chat_id):
    try:
        chat = bot.get_chat(chat_id)
        username = getattr(chat, 'username', None)
        if username:
            return f"https://t.me/{username}"
    except Exception:
        pass
    return None



TOKEN = '8608812191:AAH1FdweBXAMMifn1FawPiua8CKlFPm2XSQ'

bot = telebot.TeleBot(TOKEN, threaded=False)

app = Flask(__name__)

def safe_reply(message, text, **kwargs):
    try:
        # تلاش برای ریپلای کردن با اجازه ارسال بدون ریپلای
        return bot.reply_to(message, text, allow_sending_without_reply=True, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        # اگر به هر دلیلی باز هم خطا داد، پیام را بدون ریپلای ارسال کن
        error_str = str(e).lower()
        if "message to be replied not found" in error_str or "reply" in error_str:
            return bot.send_message(message.chat.id, text, **kwargs)
        raise e

GREETINGS = ['سلام', 'درود', 'هی ', 'خوبی', 'چطوری']

GOODNIGHTS = ['شب بخیر', 'شب خوش']

GOODMORNINGS = ['صبح بخیر', 'صبح خوش']

GOODBYES = ['خداحافظ', 'بای', 'فعلا', 'خدافظ']



FLIRTY_RESPONSES = [

    "اوه عزیزم، چقدر دلم برات تنگ شده بود 😍",

    "وای تو که اومدی همه چیز قشنگ‌تر شد 💕",

    "هی خوشگله، امروز چطوری؟ 🌸",

    "تو که میای ربات من ضربان قلبش بالا میره 💓"

]



def get_flirty():

    import random

    return random.choice(FLIRTY_RESPONSES)



HELP_TEXT = """
📖 راهنمای ربات

دستورات مالک گپ:
- ادمین ربات ← اضافه کردن ادمین ربات با ریپلای
- حذف ادمین ← حذف ادمین ربات با ریپلای
- عضو ویژه ← اضافه کردن عضو ویژه با ریپلای
- حذف ویژه ← حذف عضو ویژه با ریپلای

دستورات ادمین:
- بن ← بن کردن کاربر با ریپلای
- سیک ← همان بن
- حذف بن [آیدی] ← حذف از لیست بن
- حذف بن ← روی پیام کاربر ریپلای کن تا از لیست بن خارج شود
- سکوت [دقیقه] ← مثال: سکوت 20
- حذف سکوت ← حذف سکوت کاربر با ریپلای
- حذف پیام ← حذف پیام ریپلای شده
- حذف [تعداد] ← حذف چند پیام آخر، مثلا: حذف 10
- تگ ← همه کرابران را صدا میزند
قفل محتوا:
- قفل لینک
- قفل تگ
- قفل فوروارد
- قفل استیکر
- قفل مدیا
- حذف قفل [نوع]

خوشامدگویی:
- خوشامد روشن
- خوشامد خاموش
- متن خوشامد [متن] ← از {name} برای نام کاربر استفاده کن

لقب:
- تنظیم لقب [لقب] ← روی پیام کاربر ریپلای کن
- نمایش لقب ← روی پیام کاربر ریپلای کن

حالت عشوه:
- عشوه روشن
- عشوه خاموش

همه اعضا:
- آمار
- پنل
- راهنما
- تنظیمات
"""

def parse_text(message):

    return (message.text or '').strip()



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'راهنما', content_types=['text'])

def cmd_help(message):

    safe_reply(message, HELP_TEXT)



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'تنظیمات', content_types=['text'])

def cmd_settings(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند تنظیمات را ببینند.")

        return

    group = get_group(message.chat.id)

    locks = group['locks']

    welcome = group['welcome']

    flirty = group.get('flirty_mode', False)

    text = "⚙️ تنظیمات گروه:\n\n🔒 قفل‌ها:\n"

    for k, v in locks.items():

        text += f"• {k}: {'✅ قفل' if v else '❌ باز'}\n"

    text += f"\n👋 خوشامد: {'✅ فعال' if welcome['enabled'] else '❌ غیرفعال'}"

    text += f"\n💕 حالت عشوه: {'✅ فعال' if flirty else '❌ غیرفعال'}"

    safe_reply(message, text)



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'پنل', content_types=['text'])

def cmd_panel(message):

    group = get_group(message.chat.id)

    banned = group.get('banned_users', {})

    muted = group.get('muted_users', {})

    nicknames = group.get('nicknames', {})

    vips = group.get('vip_members', [])

    bot_admins = group.get('bot_admins', [])



    text = "📋 پنل مدیریت گروه\n\n"



    text += "🚫 بن‌شده‌ها:\n"

    if banned:

        for uid, name in banned.items():

            text += f"• {name} (آیدی: {uid})\n"

    else:

        text += "• کسی بن نشده\n"



    text += "\n🔇 سکوت‌شده‌ها:\n"

    if muted:

        for uid, info in muted.items():

            text += f"• {info['name']} تا {info.get('until', 'نامشخص')}\n"

    else:

        text += "• کسی سکوت نشده\n"



    text += "\n🏷️ لقب‌ها:\n"

    if nicknames:

        for uid, nick in nicknames.items():

            text += f"• آیدی {uid}: {nick}\n"

    else:

        text += "• لقبی تنظیم نشده\n"



    text += "\n⭐ اعضای ویژه:\n"

    if vips:

        for uid in vips:

            text += f"• آیدی {uid}\n"

    else:

        text += "• عضو ویژه‌ای نیست\n"



    text += "\n🛡️ ادمین‌های ربات:\n"

    if bot_admins:

        for uid in bot_admins:

            text += f"• آیدی {uid}\n"

    else:

        text += "• ادمین ربات تعریف نشده\n"



    safe_reply(message, text)



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'آمار', content_types=['text'])

def cmd_stats(message):

    data = load_data()

    cid = str(message.chat.id)

    today = datetime.date.today().isoformat()

    if cid not in data or 'stats' not in data[cid] or not data[cid]['stats']:

        safe_reply(message, "هنوز آماری ثبت نشده.")

        return

    stats = data[cid]['stats']

    today_stats = sorted([(uid, s['name'], s['daily'].get(today, 0)) for uid, s in stats.items()], key=lambda x: x[2], reverse=True)

    total_stats = sorted([(uid, s['name'], s['total']) for uid, s in stats.items()], key=lambda x: x[2], reverse=True)

    text = "📊 آمار پیام‌ها:\n\n🌅 امروز:\n"

    for i, (uid, name, count) in enumerate(today_stats[:5], 1):

        if count > 0:

            text += f"{i}. {name}: {count} پیام\n"

    text += "\n🏆 کل تاریخچه:\n"

    for i, (uid, name, count) in enumerate(total_stats[:5], 1):

        text += f"{i}. {name}: {count} پیام\n"

    safe_reply(message, text)



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'بن', content_types=['text'])

def cmd_ban(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند بن کنند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    target_id = message.reply_to_message.from_user.id

    target_name = message.reply_to_message.from_user.first_name

    if is_user_removed(message.chat.id, target_id):

        safe_reply(message, "کاربر حذف شده است.")

        return

    ok, err = check_action_permission(message.chat.id, message.from_user.id, target_id)

    if not ok:

        safe_reply(message, err)

        return

    try:

        bot.ban_chat_member(message.chat.id, target_id)

        store_removed_user(message.chat.id, target_id, target_name)

        safe_reply(message, f"✅ {target_name} حذف شد.")

    except Exception as e:

        safe_reply(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('حذف بن'), content_types=['text'])

def cmd_unban(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند بن را حذف کنند.")

        return

    text = parse_text(message)

    parts = text.split()

    uid = None

    if message.reply_to_message and len(parts) == 2:

        uid = message.reply_to_message.from_user.id

    elif len(parts) >= 3 and parts[2].isdigit():

        uid = int(parts[2])

    if uid is None:

        safe_reply(message, "مثال: حذف بن 123456789 یا روی پیام کاربر ریپلای کن.")

        return

    try:

        group = get_group(message.chat.id)

        if str(uid) not in group.get('banned_users', {}):

            safe_reply(message, "کاربر حذف شده یا در لیست بن نیست.")

            return

        bot.unban_chat_member(message.chat.id, uid, only_if_blocked=True)

        removed_name = remove_user_from_ban_list(message.chat.id, uid)

        group_link = get_group_link(message.chat.id)

        reply_text = f"✅ بن کاربر {removed_name or uid} حذف شد."

        if group_link:

            reply_text += f"\n🔗 لینک گروه: {group_link}"

        else:

            reply_text += "\n🔗 لینک گروه: برای این گروه لینک عمومی در دسترس نیست."

        safe_reply(message, reply_text)

    except Exception as e:

        safe_reply(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'سیک', content_types=['text'])

def cmd_kick(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند سیک کنند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    target_id = message.reply_to_message.from_user.id

    target_name = message.reply_to_message.from_user.first_name

    if is_user_removed(message.chat.id, target_id):

        safe_reply(message, "کاربر حذف شده است.")

        return

    ok, err = check_action_permission(message.chat.id, message.from_user.id, target_id)

    if not ok:

        safe_reply(message, err)

        return

    try:

        bot.ban_chat_member(message.chat.id, target_id)

        store_removed_user(message.chat.id, target_id, target_name)

        safe_reply(message, f"✅ {target_name} حذف شد.")

    except Exception as e:

        safe_reply(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('سکوت'), content_types=['text'])

def cmd_mute(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند سکوت بدهند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    target_id = message.reply_to_message.from_user.id

    target_name = message.reply_to_message.from_user.first_name

    ok, err = check_action_permission(message.chat.id, message.from_user.id, target_id)

    if not ok:

        safe_reply(message, err)

        return

    parts = parse_text(message).split()

    minutes = 0

    if len(parts) > 1 and parts[1].isdigit():

        minutes = int(parts[1])

    until_dt = None

    until_ts = 0

    if minutes > 0:

        until_dt = datetime.datetime.now() + datetime.timedelta(minutes=minutes)

        until_ts = int(until_dt.timestamp())

    try:

        bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_ts)

        data = load_data()

        data[str(message.chat.id)]['muted_users'][str(target_id)] = {

            'name': target_name,

            'until': until_dt.strftime('%Y-%m-%d %H:%M') if until_dt else 'نامحدود'

        }

        save_data(data)

        msg = f"✅ {target_name} سکوت شد"

        if minutes > 0:

            msg += f" برای {minutes} دقیقه."

        safe_reply(message, msg)

    except Exception as e:

        safe_reply(message, f"خطا: {e}")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'حذف سکوت', content_types=['text'])

def cmd_unmute(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند سکوت را حذف کنند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    target_id = message.reply_to_message.from_user.id

    target_name = message.reply_to_message.from_user.first_name

    try:

        bot.restrict_chat_member(message.chat.id, target_id, permissions=ChatPermissions(

            can_send_messages=True, can_send_media_messages=True,

            can_send_other_messages=True, can_add_web_page_previews=True))

        data = load_data()

        data[str(message.chat.id)]['muted_users'].pop(str(target_id), None)

        save_data(data)

        safe_reply(message, f"✅ سکوت {target_name} حذف شد.")

    except Exception as e:

        safe_reply(message, f"خطا: {e}")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('قفل '), content_types=['text'])

def cmd_lock(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند قفل کنند.")

        return

    valid = ['لینک', 'تگ', 'فوروارد', 'استیکر', 'مدیا', 'سرویس']

    parts = parse_text(message).split()

    if len(parts) < 2 or parts[1] not in valid:

        safe_reply(message, f"انواع قفل: {' | '.join(valid)}")

        return

    feature = parts[1]

    data = load_data()

    data[str(message.chat.id)]['locks'][feature] = True

    save_data(data)

    safe_reply(message, f"🔒 {feature} قفل شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('حذف قفل '), content_types=['text'])

def cmd_unlock(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند قفل را حذف کنند.")

        return

    valid = ['لینک', 'تگ', 'فوروارد', 'استیکر', 'مدیا', 'سرویس']

    parts = parse_text(message).split()

    if len(parts) < 3 or parts[2] not in valid:

        safe_reply(message, f"انواع قفل: {' | '.join(valid)}")

        return

    feature = parts[2]

    data = load_data()

    data[str(message.chat.id)]['locks'][feature] = False

    save_data(data)

    safe_reply(message, f"🔓 قفل {feature} حذف شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'خوشامد روشن', content_types=['text'])

def cmd_welcome_on(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ دسترسی ندارید.")

        return

    data = load_data()

    data[str(message.chat.id)]['welcome']['enabled'] = True

    save_data(data)

    safe_reply(message, "✅ خوشامدگویی فعال شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'خوشامد خاموش', content_types=['text'])

def cmd_welcome_off(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ دسترسی ندارید.")

        return

    data = load_data()

    data[str(message.chat.id)]['welcome']['enabled'] = False

    save_data(data)

    safe_reply(message, "✅ خوشامدگویی غیرفعال شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('متن خوشامد '), content_types=['text'])

def cmd_set_welcome(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ دسترسی ندارید.")

        return

    text = parse_text(message).replace('متن خوشامد ', '', 1).strip()

    data = load_data()

    data[str(message.chat.id)]['welcome']['text'] = text

    save_data(data)

    safe_reply(message, "✅ متن خوشامد تنظیم شد.\n({name} برای نام کاربر)")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'ادمین ربات', content_types=['text'])

def cmd_add_bot_admin(message):

    if not is_owner(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط مالک گپ می‌تواند ادمین ربات تعریف کند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    data = load_data()

    cid = str(message.chat.id)

    if uid not in data[cid]['bot_admins']:

        data[cid]['bot_admins'].append(uid)

        save_data(data)

    safe_reply(message, f"✅ {name} به عنوان ادمین ربات اضافه شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'حذف ادمین', content_types=['text'])

def cmd_remove_bot_admin(message):

    if not is_owner(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط مالک گپ می‌تواند ادمین را حذف کند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    data = load_data()

    cid = str(message.chat.id)

    if uid in data[cid]['bot_admins']:

        data[cid]['bot_admins'].remove(uid)

        save_data(data)

    safe_reply(message, f"✅ {name} از ادمین‌های ربات حذف شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'عضو ویژه', content_types=['text'])

def cmd_add_vip(message):

    if not is_owner(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط مالک گپ می‌تواند عضو ویژه تعریف کند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    data = load_data()

    cid = str(message.chat.id)

    if uid not in data[cid]['vip_members']:

        data[cid]['vip_members'].append(uid)

        save_data(data)

    safe_reply(message, f"⭐ {name} به عنوان عضو ویژه اضافه شد.")

    

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and (parse_text(m) == 'حذف' or parse_text(m) == 'حذف پیام' or (parse_text(m).startswith('حذف ') and parse_text(m).split()[-1].isdigit())), content_types=['text'])

def cmd_delete(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند پیام حذف کنند.")

        return

    text = parse_text(message)

    parts = text.split()

    if message.reply_to_message and text in ('حذف', 'حذف پیام'):

        try:

            bot.delete_message(message.chat.id, message.reply_to_message.message_id)

            bot.delete_message(message.chat.id, message.message_id)

        except Exception as e:

            safe_reply(message, f"خطا: {e}")

        return

    if len(parts) >= 2 and parts[-1].isdigit():

        count = min(int(parts[-1]), 50)

        try:

            bot.delete_message(message.chat.id, message.message_id)

            deleted = 0

            msg_id = message.message_id - 1

            while deleted < count and msg_id > 0:

                try:

                    bot.delete_message(message.chat.id, msg_id)

                    deleted += 1

                except:

                    pass

                msg_id -= 1

            bot.send_message(message.chat.id, f"✅ {deleted} پیام حذف شد.")

        except Exception as e:

            safe_reply(message, f"خطا: {e}")

        return

    safe_reply(message, "روی پیام ریپلای کن و بنویس حذف پیام\nیا بنویس: حذف 10")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'حذف ویژه', content_types=['text'])

def cmd_remove_vip(message):

    if not is_owner(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط مالک گپ می‌تواند عضو ویژه را حذف کند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    data = load_data()

    cid = str(message.chat.id)

    if uid in data[cid]['vip_members']:

        data[cid]['vip_members'].remove(uid)

        save_data(data)

    safe_reply(message, f"✅ {name} از اعضای ویژه حذف شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('تنظیم لقب '), content_types=['text'])

def cmd_set_nickname(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ فقط ادمین‌ها می‌توانند لقب تعیین کنند.")

        return

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    nickname = parse_text(message).replace('تنظیم لقب ', '', 1).strip()

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    data = load_data()

    cid = str(message.chat.id)

    data[cid]['nicknames'][uid] = nickname

    save_data(data)

    safe_reply(message, f"✅ لقب '{nickname}' برای {name} تنظیم شد.")



@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'نمایش لقب', content_types=['text'])

def cmd_show_nickname(message):

    if not message.reply_to_message:

        safe_reply(message, "روی پیام کاربر ریپلای کن.")

        return

    uid = str(message.reply_to_message.from_user.id)

    name = message.reply_to_message.from_user.first_name

    group = get_group(message.chat.id)

    nickname = group.get('nicknames', {}).get(uid)

    if nickname:

        safe_reply(message, f"🏷️ لقب {name}: {nickname}")

    else:

        safe_reply(message, f"{name} لقبی ندارد.")


@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'تگ', content_types=['text'])
def cmd_tag(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        safe_reply(message, "⛔ فقط ادمین‌ها و مالک می‌توانند از دستور تگ استفاده کنند.")
        return
    try:
        members_text = ""
        chat_members = bot.get_chat_administrators(message.chat.id)
        all_member_ids = set()
        for admin in chat_members:
            all_member_ids.add(admin.user.id)

        data = load_data()
        cid = str(message.chat.id)
        stats = data.get(cid, {}).get('stats', {})
        
        tagged = []
        for uid, info in stats.items():
            user_id = int(uid)
            if user_id == message.from_user.id:
                continue
            name = info.get('name', 'کاربر')
            tagged.append(f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>')

        if not tagged:
            safe_reply(message, "کاربری برای تگ کردن پیدا نشد.")
            return

        chunks = [tagged[i:i+10] for i in range(0, len(tagged), 10)]
        for chunk in chunks:
            bot.send_message(message.chat.id, ' '.join(chunk), parse_mode='HTML', disable_web_page_preview=True)

    except Exception as e:
        safe_reply(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) in ['عشوه روشن', 'عشوه خاموش'], content_types=['text'])

def cmd_flirty(message):

    if not is_bot_admin(message.chat.id, message.from_user.id):

        safe_reply(message, "⛔ دسترسی ندارید.")

        return

    state = parse_text(message) == 'عشوه روشن'

    data = load_data()

    data[str(message.chat.id)]['flirty_mode'] = state

    save_data(data)

    safe_reply(message, "💕 حالت عشوه فعال شد!" if state else "✅ حالت عشوه غیرفعال شد.")



@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])

def handle_all(message):

    if message.chat.type not in ['group', 'supergroup']:

        return



    chat_id = message.chat.id

    user_id = message.from_user.id

    text = parse_text(message)

    group = get_group(chat_id)



    # آمار

    add_stat(chat_id, user_id, message.from_user.first_name)



    # فیلترها برای غیر ادمین

    if not is_bot_admin(chat_id, user_id):

        locks = group['locks']

        should_delete = False

        delete_reason = ""



        if locks.get('لینک') and re.search(r'http[s]?://', text or message.caption or ''):

            should_delete = True

            delete_reason = "🔒 ارسال لینک در این گروه قفل است."

        elif locks.get('تگ') and re.search(r'@\w+', text or message.caption or ''):

            should_delete = True

            delete_reason = "🔒 تگ کردن در این گروه قفل است."

        elif locks.get('فوروارد') and (message.forward_from or message.forward_from_chat):

            should_delete = True

            delete_reason = "🔒 فوروارد در این گروه قفل است."

        elif locks.get('استیکر') and message.content_type == 'sticker':

            should_delete = True

            delete_reason = "🔒 ارسال استیکر در این گروه قفل است."

        elif locks.get('مدیا') and message.content_type in ['photo', 'video', 'voice', 'animation', 'document']:

            should_delete = True

            delete_reason = "🔒 ارسال مدیا در این گروه قفل است."



        if should_delete:

            try:

                bot.delete_message(chat_id, message.message_id)

                sent = bot.send_message(chat_id, f"{message.from_user.first_name}، {delete_reason}")

                import time

                time.sleep(5)

                bot.delete_message(chat_id, sent.message_id)

            except:

                pass

            return



    if not text:

        return



    name = get_name(chat_id, message.from_user)

    flirty = group.get('flirty_mode', False)



    # واکنش به احوال‌پرسی

    if any(g in text for g in GREETINGS):

        if flirty:

            bot.send_message(message.chat.id, get_flirty())

        else:

            bot.send_message(message.chat.id, f"سلام {name}! 👋")

    elif any(g in text for g in GOODMORNINGS):

        if flirty:

            bot.send_message(message.chat.id, f"صبح تو هم بخیر عزیزم {name} 🌸☀️")

        else:

            bot.send_message(message.chat.id, f"صبح بخیر {name}! ☀️")

    elif any(g in text for g in GOODNIGHTS):

        if flirty:

            bot.send_message(message.chat.id, f"شب بخیر {name} عزیزم 🌙💕")

        else:

            bot.send_message(message.chat.id, f"شب بخیر {name}! 🌙")

    elif any(g in text for g in GOODBYES):

        if flirty:

            bot.send_message(message.chat.id, f"نرو {name}، دلم برات تنگ میشه 🥺💔")

        else:

            bot.send_message(message.chat.id, f"خداحافظ {name}! 👋")



@bot.message_handler(content_types=['new_chat_members'])

def handle_new_members(message):

    group = get_group(message.chat.id)

    if group['locks'].get('سرویس'):

        try:

            bot.delete_message(message.chat.id, message.message_id)

        except:

            pass

    if group['welcome']['enabled']:

        for member in message.new_chat_members:

            if member.is_bot:

                continue

            text = group['welcome']['text'].replace('{name}', member.first_name)

            bot.send_message(message.chat.id, text)



@bot.message_handler(content_types=['left_chat_member'])

def handle_left_member(message):

    group = get_group(message.chat.id)

    if group['locks'].get('سرویس'):

        try:

            bot.delete_message(message.chat.id, message.message_id)

        except:

            pass



@app.route(f'/{TOKEN}', methods=['POST'])

def webhook():

    json_string = request.get_data().decode('utf-8')

    update = telebot.types.Update.de_json(json_string)

    bot.process_new_updates([update])

    return 'OK', 200



@app.route('/')

def index():

    return "bot is running!", 200

