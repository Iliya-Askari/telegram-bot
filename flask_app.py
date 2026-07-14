from flask import Flask, request

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from apscheduler.schedulers.background import BackgroundScheduler

import sqlite3
import requests
from bs4 import BeautifulSoup

import asyncio
import threading
import logging
import datetime

logging.basicConfig(level=logging.INFO)


# =========================================================
# Config  (بدون استفاده از Environment Variables)
# =========================================================

BOT_TOKEN = "8931839877:AAFauFX1kv2zlLXEhWhm_alWt04ncYdL5z0"
CHANNEL_ID = "@NerkhBann"

# آدرس عمومی سرویس روی Render
WEBHOOK_URL = "https://telegram-bot-7nhc.onrender.com"

BOT_NAME = "نرخ‌بان"
BOT_VERSION = "1.0.0"
DEFAULT_INTERVAL = 30


# =========================================================
# Database  (همون database.py)
# =========================================================

conn = sqlite3.connect("nerkhban.db", check_same_thread=False)
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
# Market Data (همون market.py)
# =========================================================

COINGECKO_API = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum"
    "&vs_currencies=usd"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/138.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


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
# Formatter (همون formatter.py)
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
# Keyboards (همون keyboards.py)
# =========================================================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("📊 وضعیت", callback_data="status")],
        [InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about")]
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_menu():
    keyboard = [
        [InlineKeyboardButton(
            f"⏰ فاصله ارسال ({get_interval()} دقیقه)",
            callback_data="interval_menu"
        )],
        [InlineKeyboardButton(
            "💰 دارایی‌های فعال",
            callback_data="assets_menu"
        )],
        [InlineKeyboardButton(
            "⬅️ بازگشت",
            callback_data="back_home"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)


def interval_menu():
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="interval_1"),
            InlineKeyboardButton("5", callback_data="interval_5"),
            InlineKeyboardButton("10", callback_data="interval_10")
        ],
        [
            InlineKeyboardButton("15", callback_data="interval_15"),
            InlineKeyboardButton("30", callback_data="interval_30"),
            InlineKeyboardButton("60", callback_data="interval_60")
        ],
        [
            InlineKeyboardButton("⬅️ بازگشت", callback_data="settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def assets_menu():

    assets = get_enabled_assets()

    keyboard = []

    names = {
        "btc": "بیت‌کوین",
        "eth": "اتریوم",
        "usdt": "تتر",
        "gold": "طلا",
        "silver": "نقره"
    }

    for key, value in assets.items():
        icon = "✅" if value else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{icon} {names[key]}",
                callback_data=f"asset_{key}"
            )
        ])

    keyboard.append(
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="settings")]
    )

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# ساخت Application و مدیریت event loop پس‌زمینه
# (چون python-telegram-bot جدید async هست ولی Flask/gunicorn sync هست)
# =========================================================

application = Application.builder().token(BOT_TOKEN).build()

bot_loop = asyncio.new_event_loop()


def _start_loop():
    asyncio.set_event_loop(bot_loop)
    bot_loop.run_forever()


threading.Thread(target=_start_loop, daemon=True).start()


def run_async(coro, timeout=30):
    """اجرای یک تابع async روی event loop ربات، از داخل کد sync"""
    future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
    return future.result(timeout=timeout)


# =========================================================
# Handlers (همون handlers.py)
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
👋 سلام

به ربات نرخ‌بان خوش آمدید.

🤖 این ربات قیمت بازار را به صورت خودکار در کانال شما منتشر می‌کند.

🔒 این ربات فقط تنظیمات مربوط به خودش را ذخیره می‌کند و به اطلاعات شخصی شما دسترسی ندارد.

از منوی زیر استفاده کنید.
"""

    await update.message.reply_text(text, reply_markup=main_menu())


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    data = query.data

    # ---------------- Home ----------------
    if data == "back_home":
        await query.edit_message_text(text="🏠 منوی اصلی", reply_markup=main_menu())
        return

    # ---------------- Settings ----------------
    if data == "settings":
        await query.edit_message_text(text="⚙️ تنظیمات", reply_markup=settings_menu())
        return

    # ---------------- Interval Menu ----------------
    if data == "interval_menu":
        await query.edit_message_text(
            text="⏰ فاصله ارسال را انتخاب کنید.",
            reply_markup=interval_menu()
        )
        return

    # ---------------- Assets Menu ----------------
    if data == "assets_menu":
        await query.edit_message_text(text="💰 دارایی‌های فعال", reply_markup=assets_menu())
        return

    # ---------------- Interval ----------------
    if data.startswith("interval_"):
        minute = data.split("_")[1]
        set_setting("interval", minute)
        update_scheduler_interval(int(minute))

        await query.edit_message_text(
            text=f"✅ فاصله ارسال روی {minute} دقیقه تنظیم شد.",
            reply_markup=settings_menu()
        )
        return

    # ---------------- Asset ----------------
    if data.startswith("asset_"):
        asset = data.split("_")[1]
        assets = get_enabled_assets()
        status = not assets[asset]
        set_asset(asset, status)

        await query.edit_message_reply_markup(reply_markup=assets_menu())
        return

    # ---------------- Status ----------------
    if data == "status":
        text = f"""
📊 وضعیت ربات

✅ فعال

⏰ فاصله ارسال:
{get_interval()} دقیقه

📌 نسخه:
1.0
"""
        await query.edit_message_text(text=text, reply_markup=main_menu())
        return

    # ---------------- About ----------------
    if data == "about":
        await query.edit_message_text(
            text="""
🤖 نرخ‌بان

نسخه 1.0

ربات انتشار خودکار قیمت بازار

Developed with ❤️ by Eleya
""",
            reply_markup=main_menu()
        )
        return


application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback))

# مقداردهی اولیه‌ی Application روی event loop خودش
run_async(application.initialize())
run_async(application.start())


# =========================================================
# ارسال پیام به کانال (async)
# =========================================================

async def send_price_to_channel_async(text):
    await application.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")


# =========================================================
# Scheduler (همون scheduler.py)
# =========================================================

scheduler = BackgroundScheduler()


def send_price_job():

    print("⏰ شروع دریافت قیمت...", flush=True)

    try:
        data = get_market_data()
        print("📊 قیمت دریافت شد", flush=True)

        text = format_message(data)
        print(text, flush=True)

        run_async(send_price_to_channel_async(text))

        set_setting(
            "last_update",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        print("✅ پیام ارسال شد", flush=True)

    except Exception as e:
        print("❌ Scheduler Error:", flush=True)
        print(e, flush=True)


def start_scheduler():
    scheduler.add_job(
        send_price_job,
        trigger="interval",
        minutes=get_interval(),
        id="price_sender",
        replace_existing=True,
    )
    scheduler.start()
    print("✅ Scheduler Started", flush=True)


def update_scheduler_interval(minutes):
    try:
        scheduler.reschedule_job("price_sender", trigger="interval", minutes=minutes)
    except Exception as e:
        print(f"❌ Reschedule Error: {e}", flush=True)


start_scheduler()


# =========================================================
# Flask App + Webhook (همون main.py ولی به‌جای polling، webhook)
# =========================================================

app = Flask(__name__)


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print(f"📩 Update دریافت شد: {str(data)[:200]}", flush=True)

        update = Update.de_json(data, application.bot)
        run_async(application.process_update(update))

    except Exception as e:
        print(f"❌ Webhook error: {e}", flush=True)
        logging.exception("Webhook error")

    return "OK", 200


@app.route("/")
def index():
    return "NerkhBan bot is running!", 200


# ست کردن وبهوک هنگام بالا آمدن اپ
run_async(application.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}"))
print(f"✅ Webhook set to {WEBHOOK_URL}/{BOT_TOKEN}", flush=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
