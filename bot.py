import os
import asyncio
import aiohttp
from playwright.async_api import async_playwright
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "5"))

# ======================================
# State
# ======================================
state = {
    "running": True,
    "interval": INTERVAL_MINUTES,
    "last_status": None,
    "last_check_time": None,
    "last_reason": "لم يتم الفحص بعد",
    "check_count": 0,
    "last_update_id": 0,
}

ICON_GREEN  = "\U0001F7E2"
ICON_RED    = "\U0001F534"
ICON_CHECK  = "\u2705"
ICON_CROSS  = "\u274C"
ICON_CLOCK  = "\u23F0"
ICON_TIMER  = "\u23F1"
ICON_LINK   = "\U0001F517"
ICON_CHART  = "\U0001F4CA"
ICON_ROBOT  = "\U0001F916"
ICON_GLOBE  = "\U0001F310"
ICON_PAUSE  = "\u23F8"
ICON_PLAY   = "\u25B6"
ICON_SEARCH = "\U0001F50D"

# ======================================
# Telegram - Send
# ======================================
async def send_telegram(message, chat_id=None):
    cid = chat_id or CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": cid, "text": message, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print("[OK] Telegram sent")
                else:
                    print(f"[ERR] Telegram status: {resp.status}")
    except Exception as e:
        print(f"[ERR] Telegram: {e}")

# ======================================
# Telegram - Get updates (polling)
# ======================================
async def get_updates():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": state["last_update_id"] + 1, "timeout": 2}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", [])
    except Exception:
        pass
    return []

# ======================================
# Handle incoming commands
# ======================================
async def handle_commands():
    updates = await get_updates()
    for update in updates:
        state["last_update_id"] = update["update_id"]
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            continue

        text = msg.get("text", "").strip().lower()
        chat_id = str(msg["chat"]["id"])

        # Only respond to authorized chat
        if chat_id != str(CHAT_ID):
            continue

        print(f"[CMD] {text}")

        if text == "/status":
            now = state["last_check_time"] or "لم يتم بعد"
            status_icon = ICON_CHECK if state["last_status"] else ICON_CROSS
            running_icon = ICON_PLAY if state["running"] else ICON_PAUSE
            await send_telegram(
                f"{ICON_CHART} <b>الحالة الحالية</b>\n\n"
                f"{status_icon} التوفر: {'متاح' if state['last_status'] else 'غير متاح'}\n"
                f"{running_icon} المراقبة: {'شغالة' if state['running'] else 'موقوفة'}\n"
                f"{ICON_TIMER} الفحص كل: {state['interval']} دقيقة\n"
                f"{ICON_SEARCH} عدد الفحوصات: {state['check_count']}\n"
                f"{ICON_CLOCK} آخر فحص: {now}\n"
                f"السبب: {state['last_reason']}"
            )

        elif text == "/check":
            await send_telegram(f"{ICON_SEARCH} جاري الفحص الآن...")
            result = await check_batna()
            state["last_status"] = result["available"]
            state["last_reason"] = result["reason"]
            state["last_check_time"] = datetime.now().strftime("%H:%M:%S")
            state["check_count"] += 1
            status_icon = ICON_CHECK if result["available"] else ICON_CROSS
            await send_telegram(
                f"{status_icon} <b>نتيجة الفحص</b>\n\n"
                f"باتنة: {'متاح' if result['available'] else 'غير متاح'}\n"
                f"السبب: {result['reason']}\n"
                f"{ICON_CLOCK} {datetime.now().strftime('%H:%M:%S')}"
            )

        elif text == "/stop":
            state["running"] = False
            await send_telegram(f"{ICON_PAUSE} <b>تم إيقاف المراقبة</b>\n\nاستخدم /start لاستئنافها")

        elif text == "/start":
            state["running"] = True
            await send_telegram(f"{ICON_PLAY} <b>تم استئناف المراقبة</b>\n\nالفحص كل {state['interval']} دقيقة")

        elif text.startswith("/interval"):
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                mins = int(parts[1])
                if 1 <= mins <= 60:
                    state["interval"] = mins
                    await send_telegram(
                        f"{ICON_TIMER} <b>تم تغيير فترة الفحص</b>\n\nالفحص الآن كل {mins} دقيقة"
                    )
                else:
                    await send_telegram("القيمة يجب تكون بين 1 و 60 دقيقة")
            else:
                await send_telegram("الاستخدام: /interval 3\nمثال: /interval 10")

        elif text == "/help":
            await send_telegram(
                f"{ICON_ROBOT} <b>الأوامر المتاحة</b>\n\n"
                f"/status — الحالة الحالية\n"
                f"/check — فحص يدوي فوري\n"
                f"/stop — إيقاف المراقبة\n"
                f"/start — استئناف المراقبة\n"
                f"/interval 5 — تغيير فترة الفحص (بالدقائق)\n"
                f"/help — هذه القائمة"
            )

# ======================================
# Check Batna availability
# ======================================
async def check_batna():
    result = {"available": False, "reason": "unknown"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="ar-DZ",
        )
        page = await context.new_page()
        api_data = {}

        async def handle_response(response):
            url = response.url
            ct = response.headers.get("content-type", "")
            if any(k in url for k in ["wilaya", "commune", "availability", "stock", "quota"]) or \
               ("api" in url and "json" in ct):
                try:
                    data = await response.json()
                    print(f"[API] {url}")
                    api_data["last"] = {"url": url, "data": data}
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking adhahi.dz...")
            await page.goto("https://adhahi.dz/register", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            if api_data.get("last"):
                import json
                s = json.dumps(api_data["last"]["data"]).lower()
                has_batna = "batna" in s or '"05"' in s
                if has_batna:
                    available = (
                        '"available":true' in s or
                        '"status":"open"' in s or
                        '"disponible":true' in s
                    )
                    result = {
                        "available": available,
                        "reason": "Available in API" if available else "Batna found but not available",
                    }
                    await browser.close()
                    return result

            content = await page.content()
            closed_words = ["complet", "ferme", "epuise", "sold out", "quota atteint"]
            open_words   = ["disponible", "ouvert", "احجز", "حجز"]

            is_closed = any(w in content.lower() for w in closed_words)
            is_open   = any(w in content.lower() for w in open_words)

            try:
                sel = page.locator(
                    'select[name*="wilaya"], select[id*="wilaya"], select[name*="province"]'
                ).first
                if await sel.is_visible(timeout=3000):
                    print("[OK] Found wilaya select")
                    try:
                        await sel.select_option(label="Batna")
                    except Exception:
                        try:
                            await sel.select_option(value="05")
                        except Exception:
                            pass
                    await page.wait_for_timeout(2000)

                    after = await page.content()
                    closed_after = any(w in after.lower() for w in closed_words)
                    open_after   = any(w in after.lower() for w in open_words)

                    if open_after and not closed_after:
                        result = {"available": True,  "reason": "Batna open after select"}
                    elif closed_after:
                        result = {"available": False, "reason": "Batna full/closed"}
                    else:
                        result = {"available": False, "reason": "Status unclear after Batna select"}
                else:
                    avail = is_open and not is_closed
                    result = {
                        "available": avail,
                        "reason": "Page open" if avail else ("Page closed" if is_closed else "No clear signal"),
                    }
            except Exception as e:
                result = {"available": False, "reason": f"Select error: {e}"}

        except Exception as e:
            print(f"[ERR] {e}")
            result = {"available": False, "reason": f"Error: {e}"}
        finally:
            await browser.close()

    return result

# ======================================
# Monitor loop
# ======================================
async def monitor_loop():
    while True:
        if state["running"]:
            state["check_count"] += 1
            print(f"\n=== Check #{state['check_count']} ===")

            r = await check_batna()
            state["last_check_time"] = datetime.now().strftime("%H:%M:%S")
            state["last_reason"] = r["reason"]
            print(f"[STATUS] {'AVAILABLE' if r['available'] else 'NOT available'} - {r['reason']}")

            if r["available"] != state["last_status"]:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if r["available"]:
                    await send_telegram(
                        f"{ICON_GREEN} <b>باتنة - متاح!</b>\n\n"
                        f"{ICON_CHECK} فتح التسجيل لولاية باتنة!\n\n"
                        f"{ICON_LINK} https://adhahi.dz/register\n"
                        f"{ICON_CLOCK} {now}"
                    )
                elif state["last_status"] is not None:
                    await send_telegram(
                        f"{ICON_RED} <b>باتنة - مغلق</b>\n\n"
                        f"{ICON_CROSS} انتهى التسجيل لباتنة\n"
                        f"{ICON_CLOCK} {now}"
                    )
                state["last_status"] = r["available"]
            else:
                print("[=] No status change")

            if state["check_count"] % 30 == 0:
                status_label = "متاح" if r["available"] else "غير متاح"
                await send_telegram(
                    f"{ICON_CHART} <b>تقرير دوري - باتنة</b>\n"
                    f"الفحوصات: {state['check_count']}\n"
                    f"الحالة: {status_label}\n"
                    f"{ICON_CLOCK} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        else:
            print("[PAUSED] Monitoring is stopped")

        # Wait interval while checking commands every 3 seconds
        elapsed = 0
        interval_secs = state["interval"] * 60
        while elapsed < interval_secs:
            await handle_commands()
            await asyncio.sleep(3)
            elapsed += 3

# ======================================
# Main
# ======================================
async def main():
    print(f"Adhahi Monitor - Batna | Every {state['interval']} min")

    await send_telegram(
        f"{ICON_ROBOT} <b>Adhahi Monitor - باتنة</b>\n"
        f"{ICON_CHECK} Bot started\n"
        f"{ICON_TIMER} Every {state['interval']} min\n"
        f"{ICON_GLOBE} https://adhahi.dz/register\n\n"
        f"الأوامر:\n"
        f"/status — الحالة\n"
        f"/check — فحص فوري\n"
        f"/stop — إيقاف\n"
        f"/start — تشغيل\n"
        f"/interval 5 — تغيير الفترة"
    )

    await monitor_loop()


if __name__ == "__main__":
    asyncio.run(main())
