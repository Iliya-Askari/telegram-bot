from flask import Flask, request
import telebot
import logging
import json
import os
import re
import datetime
import time
import threading

logging.basicConfig(level=logging.DEBUG)

GROUPS_FILE = 'groups.json'
file_lock = threading.Lock()
admin_cache = {}
CACHE_TIME = 300 # 5 minutes
_settings_cache = None
_last_load_time = 0

def load_settings():
    global _settings_cache, _last_load_time
    with file_lock:
        now = time.time()
        if _settings_cache is not None and now - _last_load_time < 2: # 2 seconds cache for reads
            return _settings_cache
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                try:
                    _settings_cache = json.load(f)
                    _last_load_time = now
                    return _settings_cache
                except: pass
        return _settings_cache or {}

def save_settings(data):
    global _settings_cache, _last_load_time
    with file_lock:
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        _settings_cache = data
        _last_load_time = time.time()

def get_group_settings(chat_id):
    settings = load_settings()
    chat_id = str(chat_id)
    today = str(datetime.date.today())
    if chat_id not in settings:
        settings[chat_id] = {
            "locks": {"links": False, "tags": False, "forwards": False, "stickers": False, "media": False, "service": False},
            "welcome": {"enabled": False, "text": "خوش آمدید {name}!"},
            "stats": {"daily": {}, "total": {}, "last_reset": today},
            "vips": [], "bot_admins": [], "nicknames": {}
        }
        save_settings(settings)
    elif settings[chat_id].get("stats", {}).get("last_reset") != today:
        settings[chat_id]["stats"]["daily"] = {}
        settings[chat_id]["stats"]["last_reset"] = today
        save_settings(settings)
    return settings[chat_id]

def is_admin(chat_id, user_id):
    settings = load_settings()
    c_id = str(chat_id)
    if c_id in settings and user_id in settings[c_id].get("bot_admins", []): return True

    now = time.time()
    if chat_id in admin_cache and now - admin_cache[chat_id]['time'] < CACHE_TIME:
        return user_id in admin_cache[chat_id]['admins']

    try:
        admins = [m.user.id for m in bot.get_chat_administrators(chat_id)]
        admin_cache[chat_id] = {'admins': admins, 'time': now}
        return user_id in admins
    except: return False

def is_owner(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status == 'creator'
    except: return False

def is_vip(chat_id, user_id):
    settings = load_settings()
    c_id = str(chat_id)
    if c_id in settings: return user_id in settings[c_id].get("vips", [])
    return False

TOKEN = '8608812191:AAH1FdweBXAMMifn1FawPiua8CKlFPm2XSQ'
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

def get_user_id(message):
    if message.reply_to_message: return message.reply_to_message.from_user.id
    parts = (message.text or message.caption or "").split()
    if len(parts) > 1 and parts[1].isdigit(): return int(parts[1])
    return None

stats_buffer = {}
buffer_lock = threading.Lock()

def update_stats(chat_id, user_id):
    c_id, u_id = str(chat_id), str(user_id)
    with buffer_lock:
        group_buf = stats_buffer.setdefault(c_id, {})
        group_buf[u_id] = group_buf.get(u_id, 0) + 1

        # Periodic flush (every 10 messages total)
        total_buf = sum(sum(u.values()) for u in stats_buffer.values())
        if total_buf >= 10:
            flush_stats()

def flush_stats():
    global stats_buffer
    settings = load_settings()
    flushed = False
    with buffer_lock:
        for c_id, users in stats_buffer.items():
            if c_id not in settings: continue
            stats = settings[c_id].setdefault("stats", {"daily": {}, "total": {}, "last_reset": str(datetime.date.today())})
            for u_id, count in users.items():
                stats["daily"][u_id] = stats["daily"].get(u_id, 0) + count
                stats["total"][u_id] = stats["total"].get(u_id, 0) + count
            flushed = True
        stats_buffer = {}
    if flushed: save_settings(settings)

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'voice', 'document', 'sticker', 'animation'])
def main_handler(message):
    if message.chat.type not in ['group', 'supergroup']: return
    chat_id, user_id = message.chat.id, message.from_user.id
    text = (message.text or message.caption or "").strip()

    update_stats(chat_id, user_id)

    # Auto responses
    settings = get_group_settings(chat_id)
    nickname = settings.get("nicknames", {}).get(str(user_id))
    user_label = nickname if nickname else message.from_user.first_name

    if text.lower() == "ربات":
        bot.reply_to(message, f"جونم {user_label}؟ کاری داشتی؟ 😉")
        return

    greetings = ["سلام", "درود", "hi", "hello"]
    if any(text.lower().startswith(g) for g in greetings):
        bot.reply_to(message, f"سلام {user_label} عزیز! خوش اومدی ❤️")
        return

    farewells = ["خداحافظ", "فعلا", "بای", "bye"]
    if any(text.lower().startswith(f) for f in farewells):
        bot.reply_to(message, f"خداحافظ {user_label} جان! به امید دیدار 👋")
        return

    if "شب بخیر" in text:
        bot.reply_to(message, f"شب قشنگت بخیر {user_label} خوابای خوب ببینی ✨")
        return

    if "صبح بخیر" in text:
        bot.reply_to(message, f"صبح زیبای تو هم بخیر {user_label}! روز خوبی داشته باشی ☀️")
        return

    # Dispatcher
    admin = is_admin(chat_id, user_id)
    owner = is_owner(chat_id, user_id)

    commands_map = {
        "مسدود": ban_user_logic,
        "آزاد": unban_user_logic,
        "اخراج": kick_user_logic,
        "سکوت": mute_user_logic,
        "لغو سکوت": unmute_user_logic,
        "قفل": lock_feature_logic,
        "باز کردن": unlock_feature_logic,
        "تنظیم خوش آمد": set_welcome_logic,
        "خوش آمد": toggle_welcome_logic,
        "تنظیمات": show_settings_logic,
        "عضو ویژه": set_vip_logic,
        "حذف ویژه": del_vip_logic,
    }

    for cmd, logic in commands_map.items():
        if text.startswith(cmd):
            if admin:
                logic(message)
            else:
                bot.reply_to(message, "❌ شما دسترسی کافی برای اجرای این دستور را ندارید. این دستور مخصوص مدیران است.")
            return

    if text.startswith("تنظیم ادمین") or text.startswith("حذف ادمین"):
        if owner:
            if text.startswith("تنظیم ادمین"): set_bot_admin_logic(message)
            else: del_bot_admin_logic(message)
        else:
            bot.reply_to(message, "❌ این دستور فقط توسط مالک اصلی گروه قابل اجراست.")
        return
    elif text.startswith("آمار"):
        show_stats_logic(message)
        return
    elif text.startswith("لقب"):
        set_nickname_logic(message)
        return
    elif text.startswith("راهنما"):
        show_help_logic(message)
        return
    else:
        if not admin: handle_filters_logic(message)

# --- Logic Functions ---

def ban_user_logic(message):
    uid = get_user_id(message)
    if uid and not is_admin(message.chat.id, uid) and not is_vip(message.chat.id, uid):
        try:
            bot.ban_chat_member(message.chat.id, uid)
            bot.reply_to(message, f"🚫 کاربر {uid} با موفقیت مسدود شد.")
        except Exception as e: bot.reply_to(message, f"❌ خطا: {e}")
    elif uid: bot.reply_to(message, "⚠️ این کاربر مصونیت دارد!")

def unban_user_logic(message):
    uid = get_user_id(message)
    if uid:
        try:
            bot.unban_chat_member(message.chat.id, uid, only_if_blocked=True)
            bot.reply_to(message, f"✅ کاربر {uid} آزاد شد.")
        except Exception as e: bot.reply_to(message, f"❌ خطا: {e}")

def kick_user_logic(message):
    uid = get_user_id(message)
    if uid and not is_admin(message.chat.id, uid) and not is_vip(message.chat.id, uid):
        try:
            bot.ban_chat_member(message.chat.id, uid)
            bot.unban_chat_member(message.chat.id, uid)
            bot.reply_to(message, f"👢 کاربر {uid} اخراج شد.")
        except Exception as e: bot.reply_to(message, f"❌ خطا: {e}")
    elif uid: bot.reply_to(message, "⚠️ این کاربر مصونیت دارد!")

def mute_user_logic(message):
    uid = None
    duration = 0
    parts = (message.text or message.caption or "").split()

    if message.reply_to_message:
        uid = message.reply_to_message.from_user.id
        if len(parts) > 1 and parts[1].isdigit():
            duration = int(parts[1])
    else:
        if len(parts) > 1 and parts[1].isdigit():
            uid = int(parts[1])
            if len(parts) > 2 and parts[2].isdigit():
                duration = int(parts[2])

    if uid and not is_admin(message.chat.id, uid) and not is_vip(message.chat.id, uid):
        try:
            until = int(time.time() + duration * 60) if duration > 0 else 0
            bot.restrict_chat_member(message.chat.id, uid, can_send_messages=False, until_date=until)
            msg = f"🔇 کاربر {uid} برای {duration} دقیقه بی‌صدا شد." if duration > 0 else f"🔇 کاربر {uid} بی‌صدا شد."
            bot.reply_to(message, msg)
        except Exception as e: bot.reply_to(message, f"❌ خطا: {e}")
    elif uid: bot.reply_to(message, "⚠️ این کاربر مصونیت دارد!")

def unmute_user_logic(message):
    uid = get_user_id(message)
    if uid:
        try:
            bot.restrict_chat_member(message.chat.id, uid, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
            bot.reply_to(message, f"🔊 کاربر {uid} مجدداً مجاز به ارسال پیام شد.")
        except Exception as e: bot.reply_to(message, f"❌ خطا: {e}")

def lock_feature_logic(message):
    parts = (message.text or message.caption or "").split()
    if len(parts) > 1:
        feature = parts[1]
        get_group_settings(message.chat.id)
        settings = load_settings()
        cid = str(message.chat.id)
        if cid in settings and feature in settings[cid]['locks']:
            settings[cid]['locks'][feature] = True
            save_settings(settings)
            bot.reply_to(message, f"🔒 قابلیت **{feature}** قفل شد.")
        else: bot.reply_to(message, "❌ قابلیت نامعتبر است.")

def unlock_feature_logic(message):
    parts = (message.text or message.caption or "").split()
    if len(parts) > 1:
        feature = parts[1]
        get_group_settings(message.chat.id)
        settings = load_settings()
        cid = str(message.chat.id)
        if cid in settings and feature in settings[cid]['locks']:
            settings[cid]['locks'][feature] = False
            save_settings(settings)
            bot.reply_to(message, f"🔓 قابلیت **{feature}** باز شد.")
        else: bot.reply_to(message, "❌ قابلیت نامعتبر است.")

def set_welcome_logic(message):
    text = (message.text or message.caption or "").replace("تنظیم خوش آمد", "").strip()
    if text:
        settings = load_settings()
        cid = str(message.chat.id)
        settings[cid]['welcome']['text'] = text
        save_settings(settings)
        bot.reply_to(message, "✅ متن خوش‌آمدگویی تنظیم شد.")

def toggle_welcome_logic(message):
    parts = (message.text or message.caption or "").split()
    if len(parts) > 1:
        state = parts[-1].lower()
        settings = load_settings()
        cid = str(message.chat.id)
        if state in ['روشن', 'on']: settings[cid]['welcome']['enabled'] = True; bot.reply_to(message, "✅ خوش‌آمدگویی فعال شد.")
        elif state in ['خاموش', 'off']: settings[cid]['welcome']['enabled'] = False; bot.reply_to(message, "❌ خوش‌آمدگویی غیرفعال شد.")
        save_settings(settings)

def show_settings_logic(message):
    s = get_group_settings(message.chat.id)
    text = "⚙️ **تنظیمات گروه:**\n\n"
    for l, v in s['locks'].items(): text += f"🔹 {l}: {'✅ قفل' if v else '❌ باز'}\n"
    text += f"\n👋 خوش‌آمدگویی: {'✅ فعال' if s['welcome']['enabled'] else '❌ غیرفعال'}"
    bot.reply_to(message, text, parse_mode="Markdown")

def show_stats_logic(message):
    s = get_group_settings(message.chat.id)
    stats = s.get("stats", {})
    def get_top(d):
        sd = sorted(d.items(), key=lambda x: x[1], reverse=True)[:5]
        return "\n".join([f"{i+1}. کاربر {u}: {c} پیام" for i, (u, c) in enumerate(sd)]) or "آماری موجود نیست."
    text = f"📊 **آمار پیام‌ها:**\n\n📅 **امروز:**\n{get_top(stats.get('daily', {}))}\n\n🏆 **کل:**\n{get_top(stats.get('total', {}))}"
    bot.reply_to(message, text, parse_mode="Markdown")

def set_vip_logic(message):
    uid = get_user_id(message)
    if uid:
        settings = load_settings()
        settings[str(message.chat.id)].setdefault("vips", []).append(uid)
        save_settings(settings)
        bot.reply_to(message, f"🌟 کاربر {uid} عضو ویژه شد.")

def del_vip_logic(message):
    uid = get_user_id(message)
    if uid:
        settings = load_settings()
        vips = settings[str(message.chat.id)].get("vips", [])
        if uid in vips: vips.remove(uid); save_settings(settings)
        bot.reply_to(message, f"✨ کاربر {uid} از لیست ویژه حذف شد.")

def set_bot_admin_logic(message):
    uid = get_user_id(message)
    if uid:
        settings = load_settings()
        settings[str(message.chat.id)].setdefault("bot_admins", []).append(uid)
        save_settings(settings)
        bot.reply_to(message, f"👮 کاربر {uid} ادمین ربات شد.")

def del_bot_admin_logic(message):
    uid = get_user_id(message)
    if uid:
        settings = load_settings()
        admins = settings[str(message.chat.id)].get("bot_admins", [])
        if uid in admins: admins.remove(uid); save_settings(settings)
        bot.reply_to(message, f"👤 کاربر {uid} از لیست ادمین‌ها حذف شد.")

def set_nickname_logic(message):
    uid = get_user_id(message)
    parts = (message.text or message.caption or "").split()
    if uid and len(parts) > 1:
        nick = parts[-1]
        if nick == "حذف":
            settings = load_settings()
            nicks = settings[str(message.chat.id)].get("nicknames", {})
            if str(uid) in nicks:
                del nicks[str(uid)]
                save_settings(settings)
                bot.reply_to(message, f"🗑 لقب کاربر {uid} حذف شد.")
            return

        settings = load_settings()
        settings[str(message.chat.id)].setdefault("nicknames", {})[str(uid)] = nick
        save_settings(settings)
        bot.reply_to(message, f"🏷 لقب کاربر {uid} به **{nick}** تغییر یافت.")

def show_help_logic(message):
    text = """
📚 **راهنمای ربات مدیریت گروه**

🛡 **دستورات مدیریتی:**
🔹 `مسدود` (ریپلای) - مسدود کردن کاربر
🔹 `آزاد` (آیدی عددی) - باز کردن مسدودیت
🔹 `اخراج` (ریپلای) - بیرون انداختن از گروه
🔹 `سکوت [دقیقه]` (ریپلای) - ساکت کردن کاربر (دائم یا موقت)
🔹 `لغو سکوت` (ریپلای) - اجازه ارسال پیام

🔐 **قفل‌ها:**
🔹 `قفل [قابلیت]` - فعال کردن محدودیت
🔹 `باز کردن [قابلیت]` - غیرفعال کردن محدودیت
(قابلیت‌ها: `links`, `tags`, `forwards`, `stickers`, `media`, `service`)

👤 **نقش‌ها:**
🔹 `عضو ویژه` / `حذف ویژه` - مدیریت کاربران مصون
🔹 `تنظیم ادمین` / `حذف ادمین` - مدیریت مدیران ربات (فقط مالک)

📊 **سایر:**
🔹 `آمار` - مشاهده برترین‌های پیام‌دهنده
🔹 `تنظیمات` - مشاهده وضعیت فعلی گروه
🔹 `لقب [متن]` - تنظیم لقب برای خود یا دیگران
🔹 `تنظیم خوش آمد [متن]` - تنظیم متن خوش‌آمدگویی
🔹 `خوش آمد [روشن/خاموش]` - فعال‌سازی خوش‌آمدگویی
    """
    bot.reply_to(message, text, parse_mode="Markdown")

def handle_filters_logic(message):
    chat_id = message.chat.id
    settings = get_group_settings(chat_id)
    locks = settings['locks']
    text = message.text or message.caption or ""
    should_delete = False
    if locks.get('links') and re.search(r'http[s]?://\S+', text): should_delete = True
    elif locks.get('tags') and re.search(r'@\w+', text): should_delete = True
    elif locks.get('forwards') and (message.forward_from or message.forward_from_chat): should_delete = True
    elif locks.get('stickers') and message.content_type == 'sticker': should_delete = True
    elif locks.get('media') and message.content_type in ['photo', 'video', 'voice', 'animation', 'document']: should_delete = True
    if should_delete:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass

@bot.message_handler(content_types=['new_chat_members', 'left_chat_member'])
def handle_service_messages(message):
    settings = get_group_settings(message.chat.id)
    if settings['locks'].get('service'):
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
    if message.content_type == 'new_chat_members' and settings['welcome']['enabled']:
        for m in message.new_chat_members:
            bot.send_message(message.chat.id, settings['welcome']['text'].replace('{name}', m.first_name))

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return 'OK', 200

@app.route('/')
def index(): return "bot is running!", 200
