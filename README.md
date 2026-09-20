# Railway TCP Proxy Checker

ابزاری برای مانیتور کردن نودهای Edge پراکسی TCP مشترک ریلوی:

- **`ping_check.py`** — تمام IP های داخل `hosts.txt` رو پینگ می‌کنه و می‌گه کدوم‌ها آنلاین هستن.
- **`railway_auto_v2.py`** — با `railway login` (مرورگری) وارد اکانت ریلوی می‌شه، روی یکی از سرویس‌های خودت یه TCP Proxy می‌سازه تا دامنه‌ای که ریلوی اختصاص داده رو کشف کنه، اون رو به IP تبدیل می‌کنه، تو `hosts.txt` ذخیره می‌کنه و بعد پینگ‌چک رو اجرا می‌کنه.
- **`hosts.txt`** — لیست `hostname,ip` نودهای شناخته‌شده‌ی پراکسی ریلوی.

## پیش‌نیازها

- Python نسخه 3.8 به بالا
- دستور `ping` روی سیستم (روی Windows، Linux، macOS، Termux و iSH از قبل هست)
- [Railway CLI](https://docs.railway.com/guides/cli) — فقط برای اجرای `railway_auto_v2.py` لازمه

## نصب

### Windows (cmd / PowerShell)

```cmd
:: پایتون (اگه نصب نیست)
winget install Python.Python.3

:: Railway CLI (فقط برای railway_auto_v2.py لازمه)
npm install -g @railway/cli

:: گرفتن پروژه
git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto
```

### Linux / macOS (bash/zsh)

```bash
git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto

# Railway CLI (فقط برای railway_auto_v2.py لازمه)
bash <(curl -fsSL cli.new)
```

### Termux (اندروید)

```bash
pkg update && pkg upgrade
pkg install python git inetutils   # inetutils دستور ping رو می‌ده
pkg install nodejs                 # پیش‌نیاز نصب Railway CLI
npm install -g @railway/cli        # فقط برای railway_auto_v2.py لازمه

git clone https://github.com/mamad3743/proxy-checker-auto.git
cd proxy-checker-auto
```

### iSH (آیفون / آیپد)

```bash
apk update
apk add python3 git iputils        # iputils دستور ping رو می‌ده
apk add nodejs npm                 # فقط برای railway_auto_v2.py لازمه
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
python3 railway_auto_v2.py
```

اجرا یه رابط خط‌فرمانی رنگی و مرحله‌به‌مرحله‌ست:

1. **لوگو + Step 1 — Login:** خودش دستور `railway login` رو اجرا می‌کنه — یه کد/لینک برات باز می‌شه، تو مرورگر تأییدش می‌کنی، همین. (قبلاً از طریق توکن دستی بود ولی چون بعضی وقتا Railway با توکن‌های Account خطای عجیب می‌داد، حالا از همون روش لاگین مرورگری استاندارد استفاده می‌کنه که مطمئن‌تره.)

2. **Step 2 — انتخاب پروژه:** لیست پروژه‌های اکانتت رو خودش می‌خونه (`railway list --json`) و به‌صورت یه منوی شماره‌دار نشون می‌ده — فقط عدد موردنظر رو می‌زنی. اگه به هر دلیلی نتونست خودکار بخونه، خروجی خام `railway list` رو نشون می‌ده و ازت Project ID/نام رو می‌پرسه.

3. سپس با `railway link` وصل می‌شه — اگه پروژه چند Environment یا چند Service داشته باشه، همون‌جا منوی رسمی خود ریلوی برای انتخاب Environment/Service بالا میاد.

4. **Step 3 — یه منو نشون می‌ده:**

   | گزینه | کار |
   |---|---|
   | ۱ | ساخت TCP Proxy جدید |
   | ۲ | حذف یکی از پراکسی‌های موجود روی همون سرویس |
   | ۳ | فقط پینگ‌چک `hosts.txt` (بدون تماس با API) |

### گزینه‌ی ۱ — ساخت پراکسی

پورت داخلی سرویس رو می‌پرسه (راهنمای پورت‌های رایج هم نشون می‌ده: 5432 Postgres، 6379 Redis، 3306 MySQL، 27017 MongoDB) و پراکسی رو می‌سازه. دامنه‌ای که ریلوی اختصاص داده (مثلاً `acela.proxy.rlwy.net`) رو می‌خونه و به IP تبدیل می‌کنه — **چک باید با IP انجام بشه**، چون خود دامنه به پینگ ICMP جواب نمی‌ده. اگه دامنه جدید بود با علامت ★ به `hosts.txt` اضافه‌ش می‌کنه، بعد همه‌ی هاست‌های `hosts.txt` رو پینگ می‌کنه. در آخر می‌پرسه همون پراکسی موقتی که ساخته شده حذف بشه یا نه.

### گزینه‌ی ۲ — حذف پراکسی

همه‌ی TCP Proxy های سرویس انتخاب‌شده رو لیست می‌کنه، یه شماره وارد می‌کنی (یا `a` برای همه)، یه بار تأیید می‌گیره و بعد حذف می‌کنه.

## نکات

- هر سرویس تا **۳ تا TCP Proxy** می‌تونه داشته باشه (قبلاً فقط ۱ تا مجاز بود، ریلوی این محدودیت رو باز کرده). اگه سرویس از قبل ۳ تا پراکسی داشته باشه، اسکریپت خودش قبل از تلاش برای ساخت، بهت خبر می‌ده که باید یکی رو حذف کنی.
- توکن API فقط تو محیط اجرای همون پردازش نگه داشته می‌شه؛ هیچ‌وقت روی دیسک نوشته یا لاگ نمی‌شه.
- فرمت `hosts.txt`: هر خط یک رکورد به شکل `hostname,ip`.

## امنیت

لاگین از طریق `railway login` (مرورگری) انجام می‌شه، پس نیازی نیست هیچ توکنی رو جایی وارد کنی یا نگه داری.
