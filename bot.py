import os
import asyncio
import aiohttp
from playwright.async_api import async_playwright
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "5"))

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
ICON_AVAIL  = "\u2705 Available"
ICON_NAVAIL = "\u274C Not available"

async def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print("[OK] Telegram sent")
                else:
                    print(f"[ERR] Telegram status: {resp.status}")
    except Exception as e:
        print(f"[ERR] Telegram: {e}")


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


last_status = None
check_count = 0

async def run_monitor():
    global last_status, check_count
    check_count += 1
    print(f"\n=== Check #{check_count} ===")

    r = await check_batna()
    status_str = "AVAILABLE" if r["available"] else "NOT available"
    print(f"[STATUS] {status_str} - {r['reason']}")

    if r["available"] != last_status:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if r["available"]:
            msg = (
                f"{ICON_GREEN} <b>batna - متاح!</b>\n\n"
                f"{ICON_CHECK} فتح التسجيل لولاية باتنة!\n\n"
                f"{ICON_LINK} https://adhahi.dz/register\n"
                f"{ICON_CLOCK} {now}"
            )
            await send_telegram(msg)
        elif last_status is not None:
            msg = (
                f"{ICON_RED} <b>باتنة - مغلق</b>\n\n"
                f"{ICON_CROSS} انتهى التسجيل لباتنة\n"
                f"{ICON_CLOCK} {now}"
            )
            await send_telegram(msg)
        last_status = r["available"]
    else:
        print("[=] No status change")

    if check_count % 30 == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_label = ICON_AVAIL if r["available"] else ICON_NAVAIL
        msg = (
            f"{ICON_CHART} <b>Adhahi - Batna Report</b>\n"
            f"Checks: {check_count}\n"
            f"Status: {status_label}\n"
            f"{ICON_CLOCK} {now}"
        )
        await send_telegram(msg)


async def main():
    print(f"Adhahi Monitor - Batna | Every {INTERVAL_MINUTES} min")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"{ICON_ROBOT} <b>Adhahi Monitor - باتنة</b>\n"
        f"{ICON_CHECK} Bot started\n"
        f"{ICON_TIMER} Every {INTERVAL_MINUTES} min\n"
        f"{ICON_GLOBE} https://adhahi.dz/register\n"
        f"{ICON_CLOCK} {now}"
    )
    await send_telegram(msg)

    while True:
        await run_monitor()
        await asyncio.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    asyncio.run(main())
