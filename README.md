# Railway TCP Proxy Checker

ابزاری برای مانیتور کردن نودهای Edge پراکسی TCP مشترک ریلوی:

- **`ping_check.py`** — تمام IP های داخل `hosts.txt` رو پینگ می‌کنه و می‌گه کدوم‌ها آنلاین هستن.
- **`railway_auto.py`** — با توکن API اکانت ریلوی لاگین می‌کنه، روی یکی از سرویس‌های خودت یه TCP Proxy می‌سازه تا دامنه‌ای که ریلوی اختصاص داده رو کشف کنه، اون رو به IP تبدیل می‌کنه، تو `hosts.txt` ذخیره می‌کنه و بعد پینگ‌چک رو اجرا می‌کنه.
- **`toolkit.py`** — کدهای مشترک دو اسکریپت بالا (پینگ، خوندن/نوشتن `hosts.txt`، رنگ‌ها).
- **`hosts.txt`** — لیست `hostname,ip` نودهای شناخته‌شده‌ی پراکسی ریلوی.

## اجرا با یک دستور

بعد از نصب Python و Git، فقط همین یه خط رو بزن (اگه Railway CLI نصب نباشه، خود اسکریپت می‌پرسه نصبش کنه):

**Linux / macOS / Termux / iSH**

```bash
git clone https://github.com/mamad3743/proxy-checker-auto.git && cd proxy-checker-auto && python3 railway_auto.py
```

**Windows (cmd یا PowerShell 7)**

```cmd
git clone https://github.com/mamad3743/proxy-checker-auto.git && cd proxy-checker-auto && python railway_auto.py
```

> توی PowerShell قدیمی (نسخه 5.1) `&&` کار نمی‌کنه؛ به‌جاش `;` بذار. توی ویندوز دستور `python3` معمولاً کار نمی‌کنه، از `python` یا `py` استفاده کن.

اگه پروژه رو از قبل داری، فقط داخل پوشه‌ش اجرا کن:

```bash
python3 railway_auto.py      # ویندوز: python railway_auto.py
```

## پیش‌نیازها

- Python نسخه 3.8 به بالا
- دستور `ping` روی سیستم (روی Windows، Linux، macOS از قبل هست؛ روی Termux با `pkg install inetutils` و روی iSH با `apk add iputils`)
- [Railway CLI](https://docs.railway.com/guides/cli) — فقط برای `railway_auto.py` لازمه. اگه نصب نباشه اسکریپت خودش پیشنهاد نصب می‌ده (با `npm` یا اسکریپت رسمی).

## نصب دستی (اختیاری)

### Windows

```cmd
:: پایتون (اگه نصب نیست)
winget install Python.Python.3.12

:: Railway CLI (فقط برای railway_auto.py لازمه)
npm install -g @railway/cli
:: یا: scoop install railway
```

### Linux / macOS

```bash
# Railway CLI (فقط برای railway_auto.py لازمه)
bash <(curl -fsSL railway.com/install.sh)
```

### Termux (اندروید)

```bash
pkg update && pkg upgrade
pkg install python git inetutils   # inetutils دستور ping رو می‌ده
pkg install nodejs                 # پیش‌نیاز نصب Railway CLI
npm install -g @railway/cli        # فقط برای railway_auto.py لازمه
```

### iSH (آیفون / آیپد)

```bash
apk update
apk add python3 git iputils        # iputils دستور ping رو می‌ده
apk add nodejs npm                 # فقط برای railway_auto.py لازمه
npm install -g @railway/cli
```

> iSH یک محیط x86 روی معماری ARM شبیه‌سازی می‌کنه و کند هست — نصب CLI و اجرای ping کار می‌کنن ولی ممکنه نسبت به یه دستگاه واقعی کندتر باشن.

## نحوه‌ی اجرا

### ۱. فقط چک کردن لیست فعلی با پینگ

```bash
python3 ping_check.py
```

فایل `hosts.txt` رو می‌خونه، هر IP رو پینگ می‌کنه، وضعیت ONLINE/OFFLINE هرکدوم رو چاپ می‌کنه و لیست فعال‌ها رو تو `working_ping.txt` (کنار اسکریپت) ذخیره می‌کنه. از هر پوشه‌ای می‌تونی اجراش کنی.

### ۲. کشف یه پراکسی جدید + پینگ‌چک کامل

```bash
python3 railway_auto.py
```

اجرا یه رابط خط‌فرمانی رنگی و مرحله‌به‌مرحله‌ست:

1. **Step 1 — Login:** توکن Railway API رو می‌پرسه (ورودی مخفی)، بعد `railway whoami` رو چک می‌کنه. اگه متغیر محیطی `RAILWAY_API_TOKEN` از قبل ست شده باشه، همون رو استفاده می‌کنه و نمی‌پرسه.

   | چی وارد کنی |
   |---|
   | یه **Account/Workspace Token** از داشبورد ریلوی (Account Settings → Tokens) |

2. **Step 2 — انتخاب پروژه:** لیست پروژه‌های اکانتت رو خودش می‌خونه (`railway list --json`) و به‌صورت یه منوی شماره‌دار نشون می‌ده. اگه نتونست خودکار بخونه، خروجی خام `railway list` رو نشون می‌ده و Project ID رو ازت می‌پرسه. بعد با `railway link` وصل می‌شه — منوی رسمی ریلوی برای انتخاب Environment/Service همون‌جا بالا میاد.

3. **Step 3 — TCP Proxy:**
   - اگه سرویس **از قبل پراکسی داشته باشه**، لیستشون رو نشون می‌ده: یا یکی از موجودها رو انتخاب می‌کنی یا `n` می‌زنی تا جدید بسازه. پراکسی‌های موجود **هیچ‌وقت** حذف نمی‌شن.
   - برای ساخت جدید پورت داخلی سرویس رو می‌پرسه (5432 Postgres، 6379 Redis، 3306 MySQL، 27017 MongoDB)، پراکسی رو می‌سازه و صبر می‌کنه دامنه‌ش اختصاص داده بشه.

4. دامنه‌ی اختصاص‌داده‌شده (مثلاً `acela.proxy.rlwy.net`) رو به IP تبدیل می‌کنه — **چک باید با IP انجام بشه**، چون خود دامنه به پینگ ICMP جواب نمی‌ده. اگه دامنه جدید بود با ★ به `hosts.txt` اضافه می‌شه.

5. همه‌ی هاست‌های `hosts.txt` رو پینگ می‌کنه و با رنگ سبز/قرمز (ONLINE/OFFLINE) نشون می‌ده.

6. اگه پراکسی رو همین اجرا ساخته باشه، در آخر می‌پرسه حذفش کنه یا نه.

### ۳. فقط پینگ‌چک، بدون نیاز به ریلوی / توکن

```bash
python3 railway_auto.py --ping-only
```

معادل `ping_check.py` هست. اگه ریلوی از شبکه‌ات در دسترس نیست (بخش بعد) این راه بازم کار می‌کنه.

## عیب‌یابی

- **`Failed to fetch: error decoding response body` / `expected value at line 1 column 1`** — یعنی API ریلوی به‌جای JSON یه صفحه‌ی وب (معمولاً بلاک Cloudflare) برگردونده. نسخهٔ جدید اسکریپت اول توکن را مستقیم با GraphQL چک می‌کند و بعد CLI را؛ اگر بلاک باشد تشخیص می‌دهد و راهنمایی می‌کند. رایج‌ترین علت: Cloudflare آی‌پی/شبکه‌ات را بلاک کرده. راه‌حل: آی‌پی خروجی را عوض کن (VPN دیگر، اینترنت موبایل، دستگاه دیگر) یا به پشتیبانی ریلوی با Ray ID پیام بده. توکن و اسکریپت مقصر نیستند.
- **توکن Unauthorized / Not Authorized** — حتماً **Account token** بساز (در صفحه Tokens گزینه Workspace را خالی / No workspace بگذار). Project token برای `whoami` و لیست پروژه‌ها کار نمی‌کند.
- **پینگ همه OFFLINE** — مطمئن شو دستور `ping` نصبه و فایروال ICMP رو نمی‌بنده.

## نکات

- ریلوی برای هر سرویس سقف تعداد TCP Proxy داره (این سقف قبلاً تغییر کرده)، برای همین اسکریپت عدد ثابتی فرض نمی‌کنه: اگه پراکسی موجود باشه می‌تونی از همون استفاده کنی یا `n` بزنی تا یکی جدید بسازه؛ اگه به سقف رسیده باشی، خطای خود ریلوی رو نشون می‌ده.
- دامنه‌های `*.proxy.rlwy.net` بین کاربرا مشترکن و فقط پورت فرق می‌کنه؛ برای همین حذف پراکسی با ID یا `دامنه:پورت` انجام می‌شه.
- توکن API فقط تو محیط اجرای همون پردازش نگه داشته می‌شه؛ هیچ‌وقت روی دیسک نوشته یا لاگ نمی‌شه. (خود `railway link` اطلاعات پروژه‌ی لینک‌شده رو تو کانفیگ Railway CLI ذخیره می‌کنه؛ با `railway unlink` پاکش می‌کنی.)
- فرمت `hosts.txt`: هر خط یک رکورد به شکل `hostname,ip`. خط‌های نامعتبر نادیده گرفته می‌شن.
- اگه پراکسی بعد از ساخت فعال نشد، سرویس رو یه‌بار Redeploy کن.

## امنیت

هیچ‌وقت توکن API ریلوی رو داخل این ریپو کامیت نکن. `railway_auto.py` توکن رو فقط به‌صورت تعاملی (یا از متغیر محیطی همون لحظه) می‌گیره.
