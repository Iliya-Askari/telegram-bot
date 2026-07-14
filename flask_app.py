from flask import Flask, request

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from apscheduler.schedulers.background import BackgroundScheduler

import sqlite3
import requests
from bs4 import BeautifulSoup

import logging
import os
import datetime

logging.basicConfig(level=logging.INFO)


# =========================================================
# Config
# =========================================================

BOT_TOKEN = "8931839877:AAFauFX1kv2zlLXEhWhm_alWt04ncYdL5z0"
CHANNEL_ID = "@NerkhBann"

# آدرس عمومی سروری که ربات روش دیپلوی میشه، مثلا:
# https://your-app-name.onrender.com
WEBHOOK_URL = "https://telegram-bot-7nhc.onrender.com"

PORT = int(os.getenv("PORT", 5000))

BOT_NAME = "نرخ‌بان"
BOT_VERSION = "1.0.0"
DEFAULT_INTERVAL = 30

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN تنظیم نشده. آن را در Environment Variables سرور قرار دهید."
    )

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)


def safe_reply(message, text, **kwargs):
    try:
        return bot.reply_to(message, text, allow_sending_without_reply=True, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        error_str = str(e).lower()
        if "message to be replied not found" in error_str or "reply" in error_str:
            return bot.send_message(message.chat.id, text, **kwargs)
        raise e


# =========================================================
# Database
# =========================================================

DB_FILE = "nerkhban.db"

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
)
""")
conn.commit()


def initialize_settings():
    defaults = {
        "interval": str(DEFAULT_INTERVAL),
        "btc": "1",
        "eth": "1",
        "usdt": "1",
        "gold": "1",
        "silver": "1",
        "last_update": "-",
    }

    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value)
        )

    conn.commit()


initialize_settings()


def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cursor.fetchone()
    return result[0] if result else None


def set_setting(key, value):
    cursor.execute(
        "UPDATE settings SET value=? WHERE key=?",
        (str(value), key)
    )
    conn.commit()


def get_interval():
    return int(get_setting("interval"))


def get_enabled_assets():
    return {
        "btc": bool(int(get_setting("btc"))),
        "eth": bool(int(get_setting("eth"))),
        "usdt": bool(int(get_setting("usdt"))),
        "gold": bool(int(get_setting("gold"))),
        "silver": bool(int(get_setting("silver"))),
    }


def set_asset(asset, status):
    set_setting(asset, int(status))


# =========================================================
# Market Data (TGJU + CoinGecko)
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)

COINGECKO_API = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum&vs_currencies=usd"
)


def get_tgju_price(url):
    response = session.get(url, timeout=(5, 30))
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    price = soup.find(
        "span",
        attrs={"data-col": "info.last_trade.PDrCotVal"}
    )

    if price is None:
        raise Exception(f"Price not found : {url}")

    # ریال → تومان
    return int(price.text.replace(",", "").strip()) // 10


def get_iran_market():
    return {
        "usd": get_tgju_price("https://www.tgju.org/profile/price_dollar_rl"),
        "gold18": get_tgju_price("https://www.tgju.org/profile/geram18"),
        "gold24": get_tgju_price("https://www.tgju.org/profile/geram24"),
        "silver999": get_tgju_price("https://www.tgju.org/profile/silver_999"),
    }


def get_crypto():
    response = requests.get(COINGECKO_API, timeout=15)
    response.raise_for_status()
    data = response.json()

    return {
        "btc": data["bitcoin"]["usd"],
        "eth": data["ethereum"]["usd"],
    }


def get_market_data():
    iran = get_iran_market()
    crypto = get_crypto()
    usd = iran["usd"]

    return {
        "usd": usd,
        "btc_usd": crypto["btc"],
        "btc_toman": round(crypto["btc"] * usd),
        "eth_usd": crypto["eth"],
        "eth_toman": round(crypto["eth"] * usd),
        "gold18": iran["gold18"],
        "gold24": iran["gold24"],
        "silver999": iran["silver999"],
    }


# =========================================================
# Formatter
# =========================================================

def format_message(data):
    assets = get_enabled_assets()

    text = "📊 <b>نرخ‌بان</b>\n\n"

    if assets["btc"]:
        text += (
            "🪙 <b>بیت‌کوین</b>\n"
            f"💵 {data['btc_usd']:,.2f} $\n"
            f"💰 {data['btc_toman']:,.0f} تومان\n\n"
        )

    if assets["eth"]:
        text += (
            "🔷 <b>اتریوم</b>\n"
            f"💵 {data['eth_usd']:,.2f} $\n"
            f"💰 {data['eth_toman']:,.0f} تومان\n\n"
        )

    if assets["usdt"]:
        text += (
            "💲 <b>تتر</b>\n"
            f"💰 {data['usd']:,.0f} تومان\n\n"
        )

    if assets["gold"]:
        text += (
            "🥇 <b>طلای 18 عیار</b>\n"
            f"💰 {data['gold18']:,} تومان\n\n"
            "🏆 <b>طلای 24 عیار</b>\n"
            f"💰 {data['gold24']:,} تومان\n\n"
        )

    if assets["silver"]:
        text += (
            "🥈 <b>گرم نقره 999</b>\n"
            f"💰 {data['silver999']:,} تومان\n\n"
        )

    text += "@NerkhBann"
    return text


# =========================================================
# Telegram Sender (send to channel)
# =========================================================

def send_price_to_channel(text):
    bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")


# =========================================================
# Keyboards
# =========================================================

ASSET_NAMES = {
    "btc": "بیت‌کوین",
    "eth": "اتریوم",
    "usdt": "تتر",
    "gold": "طلا",
    "silver": "نقره",
}


def main_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings"))
    keyboard.add(InlineKeyboardButton("📊 وضعیت", callback_data="status"))
    keyboard.add(InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about"))
    return keyboard


def settings_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            f"⏰ فاصله ارسال ({get_interval()} دقیقه)",
            callback_data="interval_menu"
        )
    )
    keyboard.add(InlineKeyboardButton("💰 دارایی‌های فعال", callback_data="assets_menu"))
    keyboard.add(InlineKeyboardButton("⬅️ بازگشت", callback_data="back_home"))
    return keyboard


def interval_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("1", callback_data="interval_1"),
        InlineKeyboardButton("5", callback_data="interval_5"),
        InlineKeyboardButton("10", callback_data="interval_10"),
    )
    keyboard.row(
        InlineKeyboardButton("15", callback_data="interval_15"),
        InlineKeyboardButton("30", callback_data="interval_30"),
        InlineKeyboardButton("60", callback_data="interval_60"),
    )
    keyboard.add(InlineKeyboardButton("⬅️ بازگشت", callback_data="settings"))
    return keyboard


def assets_menu():
    assets = get_enabled_assets()
    keyboard = InlineKeyboardMarkup()

    for key, value in assets.items():
        icon = "✅" if value else "❌"
        keyboard.add(
            InlineKeyboardButton(
                f"{icon} {ASSET_NAMES[key]}",
                callback_data=f"asset_{key}"
            )
        )

    keyboard.add(InlineKeyboardButton("⬅️ بازگشت", callback_data="settings"))
    return keyboard


# =========================================================
# Scheduler (ارسال خودکار قیمت به کانال)
# =========================================================

scheduler = BackgroundScheduler()


def send_price_job():
    print("⏰ شروع دریافت قیمت...")

    try:
        data = get_market_data()
        print("📊 قیمت دریافت شد")

        text = format_message(data)
        print(text)

        send_price_to_channel(text)

        set_setting(
            "last_update",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        print("✅ پیام ارسال شد")

    except Exception as e:
        print("❌ Scheduler Error:")
        print(e)


def start_scheduler():
    scheduler.add_job(
        send_price_job,
        trigger="interval",
        minutes=get_interval(),
        id="price_sender",
        replace_existing=True,
    )
    scheduler.start()
    print("✅ Scheduler Started")


def update_scheduler_interval(minutes):
    try:
        scheduler.reschedule_job(
            "price_sender",
            trigger="interval",
            minutes=minutes,
        )
    except Exception as e:
        print(f"❌ Reschedule Error: {e}")


# =========================================================
# Handlers
# =========================================================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    text = (
        "👋 سلام\n\n"
        "به ربات نرخ‌بان خوش آمدید.\n\n"
        "🤖 این ربات قیمت بازار را به صورت خودکار در کانال شما منتشر می‌کند.\n\n"
        "🔒 این ربات فقط تنظیمات مربوط به خودش را ذخیره می‌کند "
        "و به اطلاعات شخصی شما دسترسی ندارد.\n\n"
        "از منوی زیر استفاده کنید."
    )
    safe_reply(message, text, reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    bot.answer_callback_query(call.id)

    # ---------------- Home ----------------
    if data == "back_home":
        bot.edit_message_text(
            "🏠 منوی اصلی", chat_id, message_id, reply_markup=main_menu()
        )
        return

    # ---------------- Settings ----------------
    if data == "settings":
        bot.edit_message_text(
            "⚙️ تنظیمات", chat_id, message_id, reply_markup=settings_menu()
        )
        return

    # ---------------- Interval Menu ----------------
    if data == "interval_menu":
        bot.edit_message_text(
            "⏰ فاصله ارسال را انتخاب کنید.",
            chat_id, message_id, reply_markup=interval_menu()
        )
        return

    # ---------------- Assets Menu ----------------
    if data == "assets_menu":
        bot.edit_message_text(
            "💰 دارایی‌های فعال", chat_id, message_id, reply_markup=assets_menu()
        )
        return

    # ---------------- Interval ----------------
    if data.startswith("interval_"):
        minute = int(data.split("_")[1])
        set_setting("interval", minute)
        update_scheduler_interval(minute)

        bot.edit_message_text(
            f"✅ فاصله ارسال روی {minute} دقیقه تنظیم شد.",
            chat_id, message_id, reply_markup=settings_menu()
        )
        return

    # ---------------- Asset toggle ----------------
    if data.startswith("asset_"):
        asset = data.split("_")[1]
        assets = get_enabled_assets()
        status = not assets[asset]
        set_asset(asset, status)

        bot.edit_message_reply_markup(
            chat_id, message_id, reply_markup=assets_menu()
        )
        return

    # ---------------- Status ----------------
    if data == "status":
        text = (
            "📊 وضعیت ربات\n\n"
            "✅ فعال\n\n"
            f"⏰ فاصله ارسال:\n{get_interval()} دقیقه\n\n"
            f"📌 نسخه:\n{BOT_VERSION}"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=main_menu())
        return

    # ---------------- About ----------------
    if data == "about":
        text = (
            f"🤖 {BOT_NAME}\n\n"
            f"نسخه {BOT_VERSION}\n\n"
            "ربات انتشار خودکار قیمت بازار\n\n"
            "Developed with ❤️ by Eleya"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=main_menu())
        return


# =========================================================
# Flask / Webhook
# =========================================================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        logging.error(f"Webhook error: {e}")
    return "OK", 200


@app.route("/")
def index():
    return "NerkhBan bot is running!", 200


# =========================================================
# Startup
# =========================================================

start_scheduler()

if WEBHOOK_URL:
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    print(f"✅ Webhook set to {WEBHOOK_URL}/{BOT_TOKEN}")
else:
    print("⚠️ WEBHOOK_URL تنظیم نشده — بعد از دیپلوی حتما ست کن.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
