# Railway TCP Proxy Checker

ابزاری برای مانیتور کردن نودهای Edge پراکسی TCP مشترک ریلوی:

- **`ping_check.py`** — تمام IP های داخل `hosts.txt` رو پینگ می‌کنه و می‌گه کدوم‌ها آنلاین هستن.
- **`railway_auto.py`** — با توکن API اکانت ریلوی لاگین می‌کنه، روی یکی از سرویس‌های خودت یه TCP Proxy می‌سازه تا دامنه‌ای که ریلوی اختصاص داده رو کشف کنه، اون رو به IP تبدیل می‌کنه، تو `hosts.txt` ذخیره می‌کنه و بعد پینگ‌چک رو اجرا می‌کنه.
- **`hosts.txt`** — لیست `hostname,ip` نودهای شناخته‌شده‌ی پراکسی ریلوی.

## پیش‌نیازها

- Python نسخه 3.8 به بالا
- دستور `ping` روی سیستم (روی Windows، Linux، macOS، Termux و iSH از قبل هست)
- [Railway CLI](https://docs.railway.com/guides/cli) — فقط برای اجرای `railway_auto.py` لازمه

## نصب

### Windows (cmd / PowerShell)

```cmd
:: پایتون (اگه نصب نیست)
winget install Python.Python.3

:: Railway CLI (فقط برای railway_auto.py لازمه)
npm install -g @railway/cli

:: گرفتن پروژه
git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto
```

### Linux / macOS (bash/zsh)

```bash
git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto

# Railway CLI (فقط برای railway_auto.py لازمه)
bash <(curl -fsSL cli.new)
```

### Termux (اندروید)

```bash
pkg update && pkg upgrade
pkg install python git inetutils   # inetutils دستور ping رو می‌ده
pkg install nodejs                 # پیش‌نیاز نصب Railway CLI
npm install -g @railway/cli        # فقط برای railway_auto.py لازمه

git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto
```

### iSH (آیفون / آیپد)

```bash
apk update
apk add python3 git iputils        # iputils دستور ping رو می‌ده
apk add nodejs npm                 # فقط برای railway_auto.py لازمه
npm install -g @railway/cli

git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto
```

> iSH یک محیط x86 روی معماری ARM شبیه‌سازی می‌کنه و کند هست — نصب CLI و اجرای ping کار می‌کنن ولی ممکنه نسبت به یه دستگاه واقعی کندتر باشن.

## نحوه‌ی اجرا

### ۱. فقط چک کردن لیست فعلی با پینگ

```bash
python3 ping_check.py
```

فایل `hosts.txt` رو می‌خونه، هر IP رو پینگ می‌کنه، وضعیت ONLINE/OFFLINE هرکدوم رو چاپ می‌کنه و لیست فعال‌ها رو تو `working_ping.txt` ذخیره می‌کنه.

### ۲. کشف یه پراکسی جدید + پینگ‌چک کامل

```bash
python3 railway_auto.py
```

اجرا یه رابط خط‌فرمانی رنگی و مرحله‌به‌مرحله‌ست:

1. **لوگو + Step 1 — Login:** توکن Railway API رو می‌پرسه (ورودی مخفی)، بعد با اسپینر `railway whoami` رو چک می‌کنه.

   | چی وارد کنی |
   |---|
   | یه **Account/Workspace Token** از داشبورد ریلوی (Account Settings → Tokens) |

2. **Step 2 — انتخاب پروژه:** لیست پروژه‌های اکانتت رو خودش می‌خونه (`railway list --json`) و به‌صورت یه منوی شماره‌دار نشون می‌ده — فقط عدد موردنظر رو می‌زنی. اگه به هر دلیلی نتونست خودکار بخونه، خروجی خام `railway list` رو نشون می‌ده و ازت Project ID/نام رو می‌پرسه.

3. سپس با `railway link` وصل می‌شه — اگه پروژه چند Environment یا چند Service داشته باشه، همون‌جا منوی رسمی خود ریلوی برای انتخاب Environment/Service بالا میاد.

4. **Step 3 — ساخت TCP Proxy:** پورت داخلی سرویس رو می‌پرسه (راهنمای پورت‌های رایج هم نشون می‌ده: 5432 Postgres، 6379 Redis، 3306 MySQL، 27017 MongoDB) و پراکسی رو می‌سازه.

5. دامنه‌ای که ریلوی اختصاص داده (مثلاً `acela.proxy.rlwy.net`) رو می‌خونه و به IP تبدیل می‌کنه — **چک باید با IP انجام بشه**، چون خود دامنه به پینگ ICMP جواب نمی‌ده.

6. اگه دامنه جدید بود با علامت ★ به `hosts.txt` اضافه‌ش می‌کنه.

7. همه‌ی هاست‌های داخل `hosts.txt` رو پینگ می‌کنه و نتیجه رو با رنگ سبز/قرمز (ONLINE/OFFLINE) نشون می‌ده.

8. در آخر می‌پرسه پراکسی موقتی که ساخته شده حذف بشه یا نه.

## نکات

- هر سرویس فقط می‌تونه یک TCP Proxy داشته باشه — اگه سرویس از قبل پراکسی داشته باشه، ساخت پراکسی دوم روش خطا می‌ده.
- توکن API فقط تو محیط اجرای همون پردازش نگه داشته می‌شه؛ هیچ‌وقت روی دیسک نوشته یا لاگ نمی‌شه.
- فرمت `hosts.txt`: هر خط یک رکورد به شکل `hostname,ip`.

## امنیت

هیچ‌وقت توکن API ریلوی رو داخل این ریپو کامیت نکن. `railway_auto.py` توکن رو فقط و فقط به‌صورت تعاملی و در لحظه‌ی اجرا از تو می‌پرسه.
