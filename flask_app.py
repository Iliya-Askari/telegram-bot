from flask import Flask, request

from apscheduler.schedulers.background import BackgroundScheduler

import sqlite3
import requests
from bs4 import BeautifulSoup

import logging
import datetime
import time

logging.basicConfig(level=logging.INFO)


# =========================================================
# Config  (بدون استفاده از Environment Variables)
# =========================================================

# ⚠️ توجه: چون این توکن قبلاً در یک گفتگو/چت به اشتراک گذاشته شده،
# پیشنهاد می‌شود از BotFather یک توکن جدید بگیرید (/revoke) و این مقدار را جایگزین کنید.
BOT_TOKEN = "8931839877:AAFauFX1kv2zlLXEhWhm_alWt04ncYdL5z0"
CHANNEL_ID = "@NerkhBann"

# آدرس عمومی سرویس روی Render
WEBHOOK_URL = "https://telegram-bot-7nhc.onrender.com"

BOT_NAME = "نرخ‌بان"
BOT_VERSION = "1.0.0"
DEFAULT_INTERVAL = 30

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# حداقل فاصله بین دو استفاده‌ی متوالی از /send-now (ثانیه)
SEND_NOW_COOLDOWN = 60
last_send_now_ts = 0


def tg_call(method, payload=None):
    """
    یک تماس ساده و sync با API تلگرام.
    به‌جای کتابخونه‌ی async از درخواست HTTP مستقیم استفاده می‌کنیم
    تا هیچ وابستگی‌ای به asyncio/event loop نداشته باشیم
    (که با gunicorn - که sync هست - همیشه مشکل‌ساز می‌شد).
    """
    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            json=payload or {},
            timeout=15
        )
        result = response.json()
        if not result.get("ok"):
            print(f"❌ Telegram API error ({method}): {result}", flush=True)
        return result
    except Exception as e:
        print(f"❌ tg_call error ({method}): {e}", flush=True)
        return None


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
        # کش آخرین قیمت موفق کریپتو - برای وقتی همه‌ی منابع آنلاین fail کنن
        "btc_usd_cache": "",
        "eth_usd_cache": "",
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


def _get_crypto_from_coingecko():
    response = requests.get(COINGECKO_API, timeout=15, headers=HEADERS)

    if response.status_code == 429:
        raise Exception("CoinGecko rate limit (429)")

    response.raise_for_status()
    data = response.json()

    return {
        "btc": data["bitcoin"]["usd"],
        "eth": data["ethereum"]["usd"],
    }


def _get_crypto_from_kraken():
    # Kraken: هر جفت‌ارز باید جدا خونده بشه
    r_btc = requests.get(
        "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
        timeout=15, headers=HEADERS
    )
    r_btc.raise_for_status()
    d_btc = r_btc.json()
    if d_btc.get("error"):
        raise Exception(f"Kraken error: {d_btc['error']}")
    btc_price = float(list(d_btc["result"].values())[0]["c"][0])

    r_eth = requests.get(
        "https://api.kraken.com/0/public/Ticker?pair=ETHUSD",
        timeout=15, headers=HEADERS
    )
    r_eth.raise_for_status()
    d_eth = r_eth.json()
    if d_eth.get("error"):
        raise Exception(f"Kraken error: {d_eth['error']}")
    eth_price = float(list(d_eth["result"].values())[0]["c"][0])

    return {"btc": btc_price, "eth": eth_price}


def _get_crypto_from_coinbase():
    r_btc = requests.get(
        "https://api.coinbase.com/v2/prices/BTC-USD/spot",
        timeout=15, headers=HEADERS
    )
    r_btc.raise_for_status()
    btc_price = float(r_btc.json()["data"]["amount"])

    r_eth = requests.get(
        "https://api.coinbase.com/v2/prices/ETH-USD/spot",
        timeout=15, headers=HEADERS
    )
    r_eth.raise_for_status()
    eth_price = float(r_eth.json()["data"]["amount"])

    return {"btc": btc_price, "eth": eth_price}


# ترتیب اولویت منابع قیمت کریپتو.
# توجه: Binance عمداً اینجا نیست چون از روی سرورهای آمریکایی (مثل Render)
# با خطای 451 (Unavailable For Legal Reasons) مسدود می‌شه.
CRYPTO_SOURCES = [
    ("CoinGecko", _get_crypto_from_coingecko),
    ("Kraken", _get_crypto_from_kraken),
    ("Coinbase", _get_crypto_from_coinbase),
]


def get_crypto():
    """
    قیمت کریپتو رو به‌ترتیب از چند منبع مختلف می‌گیره تا وابسته به
    محدودیت/قطعی یک سرویس خاص نباشیم. اگه همه‌ی منابع fail کردن،
    از آخرین قیمت موفق کش‌شده در دیتابیس استفاده می‌کنه.
    """
    last_error = None

    for source_name, source_func in CRYPTO_SOURCES:
        for attempt in range(2):
            try:
                result = source_func()

                # کش کردن آخرین قیمت موفق برای استفاده در صورت بروز خطا در آینده
                set_setting("btc_usd_cache", result["btc"])
                set_setting("eth_usd_cache", result["eth"])

                if source_name != "CoinGecko":
                    print(f"ℹ️ قیمت کریپتو از {source_name} دریافت شد", flush=True)

                return result

            except Exception as e:
                last_error = e
                print(
                    f"❌ {source_name} تلاش {attempt + 1}/2 ناموفق: {e}",
                    flush=True
                )
                time.sleep(2)

    # همه‌ی منابع ناموفق بودن -> بازگشت به کش
    cached_btc = get_setting("btc_usd_cache")
    cached_eth = get_setting("eth_usd_cache")

    if cached_btc and cached_eth:
        print(
            "⚠️ استفاده از قیمت کش‌شده‌ی کریپتو به‌خاطر خطای همه‌ی منابع",
            flush=True
        )
        return {"btc": float(cached_btc), "eth": float(cached_eth)}

    raise Exception(
        f"دریافت قیمت کریپتو از هیچ منبعی ممکن نشد و کش هم موجود نیست: {last_error}"
    )


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
# Keyboards (همون keyboards.py، به فرمت خام JSON تلگرام)
# =========================================================

def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "⚙️ تنظیمات", "callback_data": "settings"}],
            [{"text": "📊 وضعیت", "callback_data": "status"}],
            [{"text": "ℹ️ درباره ربات", "callback_data": "about"}],
        ]
    }


def settings_menu():
    return {
        "inline_keyboard": [
            [{
                "text": f"⏰ فاصله ارسال ({get_interval()} دقیقه)",
                "callback_data": "interval_menu"
            }],
            [{"text": "💰 دارایی‌های فعال", "callback_data": "assets_menu"}],
            [{"text": "⬅️ بازگشت", "callback_data": "back_home"}],
        ]
    }


def interval_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "1", "callback_data": "interval_1"},
                {"text": "5", "callback_data": "interval_5"},
                {"text": "10", "callback_data": "interval_10"},
            ],
            [
                {"text": "15", "callback_data": "interval_15"},
                {"text": "30", "callback_data": "interval_30"},
                {"text": "60", "callback_data": "interval_60"},
            ],
            [{"text": "⬅️ بازگشت", "callback_data": "settings"}],
        ]
    }


def assets_menu():

    assets = get_enabled_assets()

    names = {
        "btc": "بیت‌کوین",
        "eth": "اتریوم",
        "usdt": "تتر",
        "gold": "طلا",
        "silver": "نقره",
    }

    rows = []

    for key, value in assets.items():
        icon = "✅" if value else "❌"
        rows.append([{
            "text": f"{icon} {names[key]}",
            "callback_data": f"asset_{key}"
        }])

    rows.append([{"text": "⬅️ بازگشت", "callback_data": "settings"}])

    return {"inline_keyboard": rows}


# =========================================================
# Handlers (همون handlers.py، ولی با فراخوانی مستقیم API تلگرام)
# =========================================================

def handle_start(message):
    chat_id = message["chat"]["id"]

    text = (
        "👋 سلام\n\n"
        "به ربات نرخ‌بان خوش آمدید.\n\n"
        "🤖 این ربات قیمت بازار را به صورت خودکار در کانال شما منتشر می‌کند.\n\n"
        "🔒 این ربات فقط تنظیمات مربوط به خودش را ذخیره می‌کند "
        "و به اطلاعات شخصی شما دسترسی ندارد.\n\n"
        "از منوی زیر استفاده کنید."
    )

    tg_call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": main_menu(),
    })


def handle_callback(callback_query):

    data = callback_query["data"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]

    tg_call("answerCallbackQuery", {"callback_query_id": callback_query["id"]})

    # ---------------- Home ----------------
    if data == "back_home":
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": "🏠 منوی اصلی", "reply_markup": main_menu(),
        })
        return

    # ---------------- Settings ----------------
    if data == "settings":
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": "⚙️ تنظیمات", "reply_markup": settings_menu(),
        })
        return

    # ---------------- Interval Menu ----------------
    if data == "interval_menu":
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": "⏰ فاصله ارسال را انتخاب کنید.",
            "reply_markup": interval_menu(),
        })
        return

    # ---------------- Assets Menu ----------------
    if data == "assets_menu":
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": "💰 دارایی‌های فعال", "reply_markup": assets_menu(),
        })
        return

    # ---------------- Interval ----------------
    if data.startswith("interval_"):
        minute = data.split("_")[1]
        set_setting("interval", minute)
        update_scheduler_interval(int(minute))

        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": f"✅ فاصله ارسال روی {minute} دقیقه تنظیم شد.",
            "reply_markup": settings_menu(),
        })
        return

    # ---------------- Asset ----------------
    if data.startswith("asset_"):
        asset = data.split("_")[1]
        assets = get_enabled_assets()
        status = not assets[asset]
        set_asset(asset, status)

        tg_call("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message_id,
            "reply_markup": assets_menu(),
        })
        return

    # ---------------- Status ----------------
    if data == "status":
        text = (
            "📊 وضعیت ربات\n\n"
            "✅ فعال\n\n"
            f"⏰ فاصله ارسال:\n{get_interval()} دقیقه\n\n"
            "📌 نسخه:\n1.0"
        )
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": text, "reply_markup": main_menu(),
        })
        return

    # ---------------- About ----------------
    if data == "about":
        text = (
            "🤖 نرخ‌بان\n\n"
            "نسخه 1.0\n\n"
            "ربات انتشار خودکار قیمت بازار\n\n"
            "Developed with ❤️ by Eleya"
        )
        tg_call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id,
            "text": text, "reply_markup": main_menu(),
        })
        return


def dispatch_update(update):
    """آپدیت دریافتی از وبهوک رو به هندلر درست می‌فرسته."""

    message = update.get("message")
    if message and message.get("text", "").strip() == "/start":
        handle_start(message)
        return

    callback_query = update.get("callback_query")
    if callback_query:
        handle_callback(callback_query)
        return


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

        tg_call("sendMessage", {
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
        })

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
# Flask App + Webhook
# =========================================================

app = Flask(__name__)


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        print(f"📩 Update دریافت شد: {str(update)[:200]}", flush=True)

        dispatch_update(update)

    except Exception as e:
        print(f"❌ Webhook error: {e}", flush=True)
        logging.exception("Webhook error")

    return "OK", 200


@app.route("/")
def index():
    return "NerkhBan bot is running!", 200


@app.route(f"/{BOT_TOKEN}/send-now")
def send_now():
    """
    برای تست دستی: قیمت رو همین الان به کانال بفرست.
    برای جلوگیری از rate limit شدن API‌های قیمت به‌خاطر کلیک‌های پشت‌سرهم،
    یک فاصله‌ی حداقلی (SEND_NOW_COOLDOWN ثانیه) بین دو استفاده اعمال شده.
    """
    global last_send_now_ts

    now = time.time()
    remaining = SEND_NOW_COOLDOWN - (now - last_send_now_ts)

    if remaining > 0:
        return (
            f"⏳ لطفاً {int(remaining)} ثانیه دیگر صبر کنید "
            f"(برای جلوگیری از rate limit).",
            429,
        )

    last_send_now_ts = now

    try:
        send_price_job()
        return "✅ send_price_job اجرا شد، لاگ‌ها رو در Render چک کن.", 200
    except Exception as e:
        return f"❌ خطا: {e}", 500


# ست کردن وبهوک هنگام بالا آمدن اپ
tg_call("deleteWebhook")
tg_call("setWebhook", {"url": f"{WEBHOOK_URL}/{BOT_TOKEN}"})
print(f"✅ Webhook set to {WEBHOOK_URL}/{BOT_TOKEN}", flush=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
