import os
import asyncio
import aiohttp
from playwright.async_api import async_playwright
from datetime import datetime

# ======================================
# إعدادات البوت (غيرها حسب بياناتك)
# ======================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "5"))

# ======================================
# قائمة الولايات الجزائرية (58 ولاية)
# ======================================
WILAYAS = {
    "01": "أدرار", "02": "الشلف", "03": "الأغواط", "04": "أم البواقي",
    "05": "باتنة", "06": "بجاية", "07": "بسكرة", "08": "بشار",
    "09": "البليدة", "10": "البويرة", "11": "تمنراست", "12": "تبسة",
    "13": "تلمسان", "14": "تيارت", "15": "تيزي وزو", "16": "الجزائر",
    "17": "الجلفة", "18": "جيجل", "19": "سطيف", "20": "سعيدة",
    "21": "سكيكدة", "22": "سيدي بلعباس", "23": "عنابة", "24": "قالمة",
    "25": "قسنطينة", "26": "المدية", "27": "مستغانم", "28": "المسيلة",
    "29": "معسكر", "30": "ورقلة", "31": "وهران", "32": "البيض",
    "33": "إليزي", "34": "برج بوعريريج", "35": "بومرداس", "36": "الطارف",
    "37": "تندوف", "38": "تيسمسيلت", "39": "الوادي", "40": "خنشلة",
    "41": "سوق أهراس", "42": "تيبازة", "43": "ميلة", "44": "عين الدفلى",
    "45": "النعامة", "46": "عين تموشنت", "47": "غرداية", "48": "غليزان",
    "49": "تيميمون", "50": "برج باجي مختار", "51": "أولاد جلال",
    "52": "بني عباس", "53": "عين صالح", "54": "عين قزام", "55": "توقرت",
    "56": "جانت", "57": "المغير", "58": "المنيعة",
}

# ======================================
# الولاية المستهدفة (قابلة للتغيير عبر التيليجرام)
# ======================================
TARGET_CODE = os.getenv("WILAYA_CODE", "16")
TARGET_NAME = WILAYAS.get(TARGET_CODE, TARGET_CODE)

# ======================================
# الحالة العامة للبوت
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

# ======================================
# أيقونات للرسائل
# ======================================
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
# دوال إرسال واستقبال التيليجرام
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
# دالة تغيير الولاية عن طريق التيليجرام
# ======================================
async def set_wilaya_by_code(code):
    """تغيير الولاية المستهدفة باستخدام الرقم"""
    global TARGET_CODE, TARGET_NAME
    code = str(code).strip().zfill(2)
    if code in WILAYAS:
        TARGET_CODE = code
        TARGET_NAME = WILAYAS[code]
        return True, TARGET_NAME
    return False, None

# ======================================
# دالة معالجة الأوامر من التيليجرام (معدلة)
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
        if chat_id != str(CHAT_ID):
            continue
        print(f"[CMD] {text}")

        # عرض الحالة الحالية
        if text == "/status":
            now = state["last_check_time"] or "لم يتم بعد"
            status_icon = ICON_CHECK if state["last_status"] else ICON_CROSS
            running_icon = ICON_PLAY if state["running"] else ICON_PAUSE
            await send_telegram(
                f"{ICON_CHART} <b>الحالة الحالية</b>\n\n"
                f"{ICON_GLOBE} الولاية: {TARGET_NAME} ({TARGET_CODE})\n"
                f"{status_icon} التوفر: {'متاح' if state['last_status'] else 'غير متاح'}\n"
                f"{running_icon} المراقبة: {'شغالة' if state['running'] else 'موقوفة'}\n"
                f"{ICON_TIMER} الفحص كل: {state['interval']} دقيقة\n"
                f"{ICON_SEARCH} عدد الفحوصات: {state['check_count']}\n"
                f"{ICON_CLOCK} آخر فحص: {now}\n"
                f"السبب: {state['last_reason']}"
            )

        # فحص يدوي فوري
        elif text == "/check":
            await send_telegram(f"{ICON_SEARCH} جاري الفحص الآن...")
            result = await check_wilaya()
            state["last_status"] = result["available"]
            state["last_reason"] = result["reason"]
            state["last_check_time"] = datetime.now().strftime("%H:%M:%S")
            state["check_count"] += 1
            status_icon = ICON_CHECK if result["available"] else ICON_CROSS
            await send_telegram(
                f"{status_icon} <b>نتيجة الفحص</b>\n\n"
                f"{TARGET_NAME}: {'متاح' if result['available'] else 'غير متاح'}\n"
                f"السبب: {result['reason']}\n"
                f"{ICON_CLOCK} {datetime.now().strftime('%H:%M:%S')}"
            )

        # إيقاف المراقبة
        elif text == "/stop":
            state["running"] = False
            await send_telegram(f"{ICON_PAUSE} <b>تم إيقاف المراقبة</b>\n\nاستخدم /start لاستئنافها")

        # استئناف المراقبة
        elif text == "/start":
            state["running"] = True
            await send_telegram(f"{ICON_PLAY} <b>تم استئناف المراقبة</b>\n\nالفحص كل {state['interval']} دقيقة")

        # تغيير فترة الفحص
        elif text.startswith("/interval"):
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                mins = int(parts[1])
                if 1 <= mins <= 60:
                    state["interval"] = mins
                    await send_telegram(f"{ICON_TIMER} <b>تم تغيير فترة الفحص</b>\n\nالفحص الآن كل {mins} دقيقة")
                else:
                    await send_telegram("القيمة يجب تكون بين 1 و 60 دقيقة")
            else:
                await send_telegram("الاستخدام: /interval 3\nمثال: /interval 10")

        # ========== الأمر الجديد: تغيير الولاية ==========
        elif text.startswith("/setwilaya"):
            parts = text.split()
            if len(parts) == 2:
                wilaya_code = parts[1].strip()
                success, name = await set_wilaya_by_code(wilaya_code)
                if success:
                    await send_telegram(
                        f"{ICON_CHECK} <b>تم تغيير الولاية بنجاح</b>\n\n"
                        f"الولاية الجديدة: {name} ({wilaya_code})\n"
                        f"سيتم تطبيق التغيير على الفور"
                    )
                    # إعادة تعيين الحالة لتجنب إشعارات خاطئة
                    state["last_status"] = None
                    state["last_reason"] = f"تم التغيير إلى {name}"
                    print(f"[INFO] Wilaya changed to {name} ({wilaya_code})")
                else:
                    await send_telegram(
                        f"{ICON_CROSS} <b>ولاية غير صحيحة</b>\n\n"
                        f"الرمز '{wilaya_code}' غير موجود.\n"
                        f"استخدم /wilayas لعرض قائمة الولايات"
                    )
            else:
                await send_telegram(
                    f"{ICON_SEARCH} <b>طريقة الاستخدام</b>\n\n"
                    f"/setwilaya <رمز الولاية>\n\n"
                    f"مثال: /setwilaya 16  (للجزائر العاصمة)\n"
                    f"مثال: /setwilaya 31  (لوهران)\n\n"
                    f"استخدم /wilayas لعرض جميع الرموز"
                )

        # عرض قائمة الولايات
        elif text == "/wilayas":
            lines = [f"{ICON_GLOBE} <b>قائمة الولايات</b>\n"]
            for code, name in sorted(WILAYAS.items()):
                marker = " ✅" if code == TARGET_CODE else ""
                lines.append(f"{code} - {name}{marker}")
            await send_telegram("\n".join(lines))

        # عرض قائمة الأوامر
        elif text == "/help":
            await send_telegram(
                f"{ICON_ROBOT} <b>الأوامر المتاحة</b>\n\n"
                f"/status — الحالة الحالية\n"
                f"/check — فحص يدوي فوري\n"
                f"/stop — إيقاف المراقبة\n"
                f"/start — استئناف المراقبة\n"
                f"/interval 5 — تغيير فترة الفحص\n"
                f"/setwilaya 16 — تغيير الولاية (مثال: 16 للجزائر)\n"
                f"/wilayas — قائمة كل الولايات\n"
                f"/help — هذه القائمة\n\n"
                f"الولاية الحالية: {TARGET_NAME} ({TARGET_CODE})"
            )

# ======================================
# دالة فحص موقع adhahi.dz
# ======================================
async def check_wilaya():
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking {TARGET_NAME} ({TARGET_CODE})...")
            await page.goto("https://adhahi.dz/register", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            # التحقق من الـ API أولاً
            if api_data.get("last"):
                import json
                s = json.dumps(api_data["last"]["data"]).lower()
                has_target = f'"{TARGET_CODE}"' in s or TARGET_NAME.lower() in s
                if has_target:
                    available = (
                        '"available":true' in s or
                        '"status":"open"' in s or
                        '"disponible":true' in s
                    )
                    result = {
                        "available": available,
                        "reason": "Available in API" if available else "Found in API but not available",
                    }
                    await browser.close()
                    return result

            # التحقق من محتوى الصفحة
            content = await page.content()
            closed_words = ["complet", "ferme", "epuise", "sold out", "quota atteint"]
            open_words   = ["disponible", "ouvert", "احجز", "حجز"]
            is_closed = any(w in content.lower() for w in closed_words)
            is_open   = any(w in content.lower() for w in open_words)

            # محاولة اختيار الولاية من القائمة المنسدلة
            try:
                sel = page.locator(
                    'select[name*="wilaya"], select[id*="wilaya"], select[name*="province"]'
                ).first
                if await sel.is_visible(timeout=3000):
                    print(f"[OK] Found wilaya select, selecting {TARGET_CODE}...")
                    try:
                        await sel.select_option(value=TARGET_CODE)
                    except Exception:
                        try:
                            await sel.select_option(label=TARGET_NAME)
                        except Exception:
                            pass
                    await page.wait_for_timeout(2000)
                    after = await page.content()
                    closed_after = any(w in after.lower() for w in closed_words)
                    open_after   = any(w in after.lower() for w in open_words)
                    if open_after and not closed_after:
                        result = {"available": True,  "reason": f"{TARGET_NAME} open after select"}
                    elif closed_after:
                        result = {"available": False, "reason": f"{TARGET_NAME} full/closed"}
                    else:
                        result = {"available": False, "reason": "Status unclear after select"}
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
# الحلقة الرئيسية للمراقبة
# ======================================
async def monitor_loop():
    while True:
        if state["running"]:
            state["check_count"] += 1
            print(f"\n=== Check #{state['check_count']} ({TARGET_NAME}) ===")
            r = await check_wilaya()
            state["last_check_time"] = datetime.now().strftime("%H:%M:%S")
            state["last_reason"] = r["reason"]
            print(f"[STATUS] {'AVAILABLE' if r['available'] else 'NOT available'} - {r['reason']}")
            
            # إرسال إشعار عند تغير الحالة
            if r["available"] != state["last_status"]:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if r["available"]:
                    await send_telegram(
                        f"{ICON_GREEN} <b>{TARGET_NAME} - متاح!</b>\n\n"
                        f"{ICON_CHECK} فتح التسجيل لولاية {TARGET_NAME}!\n\n"
                        f"{ICON_LINK} https://adhahi.dz/register\n"
                        f"{ICON_CLOCK} {now}"
                    )
                elif state["last_status"] is not None:
                    await send_telegram(
                        f"{ICON_RED} <b>{TARGET_NAME} - مغلق</b>\n\n"
                        f"{ICON_CROSS} انتهى التسجيل لـ {TARGET_NAME}\n"
                        f"{ICON_CLOCK} {now}"
                    )
                state["last_status"] = r["available"]
            else:
                print("[=] No status change")
            
            # تقرير دوري كل 30 فحصاً
            if state["check_count"] % 30 == 0:
                status_label = "متاح" if r["available"] else "غير متاح"
                await send_telegram(
                    f"{ICON_CHART} <b>تقرير دوري - {TARGET_NAME}</b>\n"
                    f"الفحوصات: {state['check_count']}\n"
                    f"الحالة: {status_label}\n"
                    f"{ICON_CLOCK} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        else:
            print("[PAUSED] Monitoring is stopped")
        
        # انتظار الفترة المحددة مع معالجة الأوامر
        elapsed = 0
        interval_secs = state["interval"] * 60
        while elapsed < interval_secs:
            await handle_commands()
            await asyncio.sleep(3)
            elapsed += 3

# ======================================
# نقطة الدخول الرئيسية
# ======================================
async def main():
    print(f"Adhahi Monitor - {TARGET_NAME} ({TARGET_CODE}) | Every {state['interval']} min")
    await send_telegram(
        f"{ICON_ROBOT} <b>Adhahi Monitor</b>\n"
        f"{ICON_GLOBE} الولاية: {TARGET_NAME} ({TARGET_CODE})\n"
        f"{ICON_CHECK} Bot started\n"
        f"{ICON_TIMER} Every {state['interval']} min\n\n"
        f"الأوامر:\n"
        f"/status — الحالة\n"
        f"/check — فحص فوري\n"
        f"/stop — إيقاف\n"
        f"/start — تشغيل\n"
        f"/interval 5 — تغيير الفترة\n"
        f"/setwilaya 16 — تغيير الولاية\n"
        f"/wilayas — قائمة الولايات\n"
        f"/help — هذه القائمة"
    )
    await monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())
