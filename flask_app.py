from flask import Flask, request
import telebot
from telebot.types import ChatPermissions
import logging
import json
import os
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
            "locks": {"links": False, "tags": False, "forwards": False, "stickers": False, "media": False, "service": False},
            "welcome": {"enabled": False, "text": "خوش آمدید {name}!"},
            "bot_admins": [],
            "vip_members": [],
            "nicknames": {},
            "stats": {},
            "flirty_mode": False
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

def get_name(message):
    user = message.from_user
    group = get_group(message.chat.id)
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

TOKEN = '8608812191:AAH1FdweBXAMMifn1FawPiua8CKlFPm2XSQ'
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ─── پیام‌های احوال‌پرسی ───
GREETINGS = ['سلام', 'درود', 'هی', 'خوبی', 'چطوری']
GOODNIGHTS = ['شب بخیر', 'شب خوش', 'بخیر']
GOODMORNINGS = ['صبح بخیر', 'صبح خوش', 'بامداد بخیر']
GOODBYES = ['خداحافظ', 'بای', 'فعلا', 'خدافظ', 'داری میری']

FLIRTY_RESPONSES = [
    "اوه عزیزم، چقدر دلم برات تنگ شده بود 😍",
    "وای تو که اومدی همه چیز قشنگ‌تر شد 💕",
    "هی خوشگله، امروز چطوری؟ 🌸",
    "تو که میای ربات من ضربان قلبش بالا میره 💓"
]

def get_flirty():
    import random
    return random.choice(FLIRTY_RESPONSES)

# ─── راهنما ───
HELP_TEXT = """
📖 راهنمای ربات:

👑 دستورات مالک گپ:
- ادمین ربات @یوزرنیم — ادمین کردن در ربات
- حذف ادمین @یوزرنیم — حذف ادمین ربات
- عضو ویژه @یوزرنیم — اضافه کردن عضو ویژه
- حذف ویژه @یوزرنیم — حذف عضو ویژه

🛡️ دستورات ادمین:
- بن — بن کردن (روی پیام ریپلای کن)
- آنبن [آیدی] — آزاد کردن
- کیک — اخراج موقت
- سکوت [دقیقه] — بی‌صدا کردن (مثال: سکوت 20)
- آنسکوت — برداشتن سکوت
- قفل [نوع] — قفل کردن (لینک/تگ/فوروارد/استیکر/مدیا/سرویس)
- آنقفل [نوع] — باز کردن قفل
- خوشامد روشن — فعال کردن خوشامد
- خوشامد خاموش — غیرفعال کردن خوشامد
- متن خوشامد [متن] — تنظیم متن خوشامد
- لقب @یوزر [لقب] — تنظیم لقب
- تنظیمات — نمایش تنظیمات گروه
- عشوه روشن/خاموش — حالت عشوه‌وار

📊 دستورات عمومی:
- آمار — آمار پیام‌های امروز و کل
- راهنما — نمایش این پیام
"""

# ─── هندلرهای متنی ───
def parse_text(message):
    return (message.text or '').strip()

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'راهنما', content_types=['text'])
def cmd_help(message):
    bot.reply_to(message, HELP_TEXT)

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'تنظیمات', content_types=['text'])
def cmd_settings(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند تنظیمات را ببینند.")
        return
    group = get_group(message.chat.id)
    locks = group['locks']
    welcome = group['welcome']
    flirty = group.get('flirty_mode', False)
    text = "⚙️ تنظیمات گروه:\n\n🔒 قفل‌ها:\n"
    names = {'links':'لینک','tags':'تگ','forwards':'فوروارد','stickers':'استیکر','media':'مدیا','service':'سرویس'}
    for k,v in locks.items():
        text += f"• {names.get(k,k)}: {'✅ قفل' if v else '❌ باز'}\n"
    text += f"\n👋 خوشامد: {'✅ فعال' if welcome['enabled'] else '❌ غیرفعال'}"
    text += f"\n💕 حالت عشوه: {'✅ فعال' if flirty else '❌ غیرفعال'}"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'آمار', content_types=['text'])
def cmd_stats(message):
    data = load_data()
    cid = str(message.chat.id)
    today = datetime.date.today().isoformat()
    if cid not in data or 'stats' not in data[cid] or not data[cid]['stats']:
        bot.reply_to(message, "هنوز آماری ثبت نشده.")
        return
    stats = data[cid]['stats']
    today_stats = sorted([(uid, s['name'], s['daily'].get(today,0)) for uid,s in stats.items()], key=lambda x: x[2], reverse=True)
    total_stats = sorted([(uid, s['name'], s['total']) for uid,s in stats.items()], key=lambda x: x[2], reverse=True)
    text = "📊 آمار پیام‌ها:\n\n🌅 امروز:\n"
    for i, (uid, name, count) in enumerate(today_stats[:5], 1):
        if count > 0:
            text += f"{i}. {name}: {count} پیام\n"
    text += "\n🏆 کل تاریخچه:\n"
    for i, (uid, name, count) in enumerate(total_stats[:5], 1):
        text += f"{i}. {name}: {count} پیام\n"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'بن', content_types=['text'])
def cmd_ban(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند بن کنند.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    target = message.reply_to_message.from_user.id
    if is_vip(message.chat.id, target):
        bot.reply_to(message, "⭐ این کاربر عضو ویژه است و نمی‌توان بنش کرد.")
        return
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"✅ کاربر {message.reply_to_message.from_user.first_name} بن شد.")
    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('آنبن'), content_types=['text'])
def cmd_unban(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند آنبن کنند.")
        return
    parts = parse_text(message).split()
    if len(parts) < 2:
        bot.reply_to(message, "مثال: آنبن 123456789")
        return
    try:
        uid = int(parts[1])
        bot.unban_chat_member(message.chat.id, uid, only_if_blocked=True)
        bot.reply_to(message, f"✅ کاربر {uid} آزاد شد.")
    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'کیک', content_types=['text'])
def cmd_kick(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند کیک کنند.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    target = message.reply_to_message.from_user.id
    if is_vip(message.chat.id, target):
        bot.reply_to(message, "⭐ این کاربر عضو ویژه است.")
        return
    try:
        bot.ban_chat_member(message.chat.id, target)
        bot.unban_chat_member(message.chat.id, target)
        bot.reply_to(message, f"✅ کاربر {message.reply_to_message.from_user.first_name} اخراج شد.")
    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('سکوت'), content_types=['text'])
def cmd_mute(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند سکوت بدهند.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    target = message.reply_to_message.from_user.id
    if is_vip(message.chat.id, target):
        bot.reply_to(message, "⭐ این کاربر عضو ویژه است.")
        return
    parts = parse_text(message).split()
    minutes = 0
    if len(parts) > 1 and parts[1].isdigit():
        minutes = int(parts[1])
    until = 0
    if minutes > 0:
        until = int((datetime.datetime.now() + datetime.timedelta(minutes=minutes)).timestamp())
    try:
        bot.restrict_chat_member(message.chat.id, target, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        msg = f"✅ کاربر {message.reply_to_message.from_user.first_name} سکوت شد"
        if minutes > 0:
            msg += f" برای {minutes} دقیقه."
        bot.reply_to(message, msg)
    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'آنسکوت', content_types=['text'])
def cmd_unmute(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند آنسکوت کنند.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    target = message.reply_to_message.from_user.id
    try:
        bot.restrict_chat_member(message.chat.id, target, permissions=ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True))
        bot.reply_to(message, f"✅ سکوت {message.reply_to_message.from_user.first_name} برداشته شد.")
    except Exception as e:
        bot.reply_to(message, f"خطا: {e}")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('قفل '), content_types=['text'])
def cmd_lock(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند قفل کنند.")
        return
    fa_map = {'لینک':'links','تگ':'tags','فوروارد':'forwards','استیکر':'stickers','مدیا':'media','سرویس':'service'}
    parts = parse_text(message).split()
    if len(parts) < 2:
        return
    feature = fa_map.get(parts[1])
    if not feature:
        bot.reply_to(message, "نوع قفل نامعتبر است.\nانواع: لینک، تگ، فوروارد، استیکر، مدیا، سرویس")
        return
    data = load_data()
    cid = str(message.chat.id)
    data[cid]['locks'][feature] = True
    save_data(data)
    bot.reply_to(message, f"🔒 {parts[1]} قفل شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('آنقفل '), content_types=['text'])
def cmd_unlock(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند قفل را باز کنند.")
        return
    fa_map = {'لینک':'links','تگ':'tags','فوروارد':'forwards','استیکر':'stickers','مدیا':'media','سرویس':'service'}
    parts = parse_text(message).split()
    if len(parts) < 2:
        return
    feature = fa_map.get(parts[1])
    if not feature:
        bot.reply_to(message, "نوع قفل نامعتبر است.")
        return
    data = load_data()
    cid = str(message.chat.id)
    data[cid]['locks'][feature] = False
    save_data(data)
    bot.reply_to(message, f"🔓 {parts[1]} باز شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'خوشامد روشن', content_types=['text'])
def cmd_welcome_on(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ دسترسی ندارید.")
        return
    data = load_data()
    data[str(message.chat.id)]['welcome']['enabled'] = True
    save_data(data)
    bot.reply_to(message, "✅ خوشامدگویی فعال شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) == 'خوشامد خاموش', content_types=['text'])
def cmd_welcome_off(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ دسترسی ندارید.")
        return
    data = load_data()
    data[str(message.chat.id)]['welcome']['enabled'] = False
    save_data(data)
    bot.reply_to(message, "✅ خوشامدگویی غیرفعال شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('متن خوشامد '), content_types=['text'])
def cmd_set_welcome(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ دسترسی ندارید.")
        return
    text = parse_text(message).replace('متن خوشامد ', '', 1).strip()
    data = load_data()
    data[str(message.chat.id)]['welcome']['text'] = text
    save_data(data)
    bot.reply_to(message, "✅ متن خوشامد تنظیم شد.\n({name} برای نام کاربر)")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('ادمین ربات'), content_types=['text'])
def cmd_add_bot_admin(message):
    if not is_owner(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط مالک گپ می‌تواند ادمین ربات تعریف کند.")
        return
    if message.reply_to_message:
        uid = str(message.reply_to_message.from_user.id)
        name = message.reply_to_message.from_user.first_name
    else:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    data = load_data()
    cid = str(message.chat.id)
    if uid not in data[cid]['bot_admins']:
        data[cid]['bot_admins'].append(uid)
        save_data(data)
    bot.reply_to(message, f"✅ {name} به عنوان ادمین ربات اضافه شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('حذف ادمین'), content_types=['text'])
def cmd_remove_bot_admin(message):
    if not is_owner(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط مالک گپ می‌تواند ادمین را حذف کند.")
        return
    if message.reply_to_message:
        uid = str(message.reply_to_message.from_user.id)
        name = message.reply_to_message.from_user.first_name
    else:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    data = load_data()
    cid = str(message.chat.id)
    if uid in data[cid]['bot_admins']:
        data[cid]['bot_admins'].remove(uid)
        save_data(data)
    bot.reply_to(message, f"✅ {name} از ادمین‌های ربات حذف شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('عضو ویژه'), content_types=['text'])
def cmd_add_vip(message):
    if not is_owner(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط مالک گپ می‌تواند عضو ویژه تعریف کند.")
        return
    if message.reply_to_message:
        uid = str(message.reply_to_message.from_user.id)
        name = message.reply_to_message.from_user.first_name
    else:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    data = load_data()
    cid = str(message.chat.id)
    if uid not in data[cid]['vip_members']:
        data[cid]['vip_members'].append(uid)
        save_data(data)
    bot.reply_to(message, f"⭐ {name} به عنوان عضو ویژه اضافه شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('حذف ویژه'), content_types=['text'])
def cmd_remove_vip(message):
    if not is_owner(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط مالک گپ می‌تواند عضو ویژه را حذف کند.")
        return
    if message.reply_to_message:
        uid = str(message.reply_to_message.from_user.id)
        name = message.reply_to_message.from_user.first_name
    else:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    data = load_data()
    cid = str(message.chat.id)
    if uid in data[cid]['vip_members']:
        data[cid]['vip_members'].remove(uid)
        save_data(data)
    bot.reply_to(message, f"✅ {name} از اعضای ویژه حذف شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m).startswith('لقب '), content_types=['text'])
def cmd_set_nickname(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند لقب تعیین کنند.")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "روی پیام کاربر ریپلای کن.")
        return
    nickname = parse_text(message).replace('لقب ', '', 1).strip()
    uid = str(message.reply_to_message.from_user.id)
    data = load_data()
    cid = str(message.chat.id)
    data[cid]['nicknames'][uid] = nickname
    save_data(data)
    bot.reply_to(message, f"✅ لقب '{nickname}' برای {message.reply_to_message.from_user.first_name} تنظیم شد.")

@bot.message_handler(func=lambda m: m.chat.type in ['group','supergroup'] and parse_text(m) in ['عشوه روشن', 'عشوه خاموش'], content_types=['text'])
def cmd_flirty(message):
    if not is_bot_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⛔ دسترسی ندارید.")
        return
    state = parse_text(message) == 'عشوه روشن'
    data = load_data()
    data[str(message.chat.id)]['flirty_mode'] = state
    save_data(data)
    bot.reply_to(message, "💕 حالت عشوه فعال شد!" if state else "✅ حالت عشوه غیرفعال شد.")

# ─── هندلر اصلی پیام‌ها ───
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def handle_all(message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    text = parse_text(message)
    name = get_name(message)
    group = get_group(chat_id)

    # آمار
    add_stat(chat_id, user_id, message.from_user.first_name)

    # فیلترها (برای غیر ادمین)
    if not is_bot_admin(chat_id, user_id):
        locks = group['locks']
        should_delete = False
        if locks.get('links') and re.search(r'http[s]?://', text or message.caption or ''):
            should_delete = True
        if not should_delete and locks.get('tags') and re.search(r'@\w+', text or message.caption or ''):
            should_delete = True
        if not should_delete and locks.get('forwards') and (message.forward_from or message.forward_from_chat):
            should_delete = True
        if not should_delete and locks.get('stickers') and message.content_type == 'sticker':
            should_delete = True
        if not should_delete and locks.get('media') and message.content_type in ['photo','video','voice','animation','document']:
            should_delete = True
        if should_delete:
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return

    if not text:
        return

    # واکنش به احوال‌پرسی
    flirty = group.get('flirty_mode', False)

    if any(g in text for g in GREETINGS):
        if flirty:
            bot.reply_to(message, get_flirty())
        else:
            bot.reply_to(message, f"سلام {name}! 👋")

    elif any(g in text for g in GOODMORNINGS):
        if flirty:
            bot.reply_to(message, f"صبح تو هم بخیر عزیزم {name} 🌸☀️")
        else:
            bot.reply_to(message, f"صبح بخیر {name}! ☀️")

    elif any(g in text for g in GOODNIGHTS):
        if flirty:
            bot.reply_to(message, f"شب بخیر {name} عزیزم، خواب خوب ببینی 🌙💕")
        else:
            bot.reply_to(message, f"شب بخیر {name}! 🌙")

    elif any(g in text for g in GOODBYES):
        if flirty:
            bot.reply_to(message, f"نرو {name}، دلم برات تنگ میشه 🥺💔")
        else:
            bot.reply_to(message, f"خداحافظ {name}! 👋")

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_members(message):
    group = get_group(message.chat.id)
    if group['locks'].get('service'):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
    if group['welcome']['enabled']:
        for member in message.new_chat_members:
            text = group['welcome']['text'].replace('{name}', member.first_name)
            bot.send_message(message.chat.id, text)

@bot.message_handler(content_types=['left_chat_member'])
def handle_left_member(message):
    group = get_group(message.chat.id)
    if group['locks'].get('service'):
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
