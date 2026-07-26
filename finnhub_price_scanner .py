#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finnhub Price Scanner
======================
يجلب قائمة حقيقية بالأسهم الأمريكية (NASDAQ / NYSE / NYSE American) اللي سعرها
الحالي أقل من سعر محدد (افتراضيًا 5 دولار)، مع بيانات دقيقة: التيكر الصحيح،
اسم الشركة، السعر، نسبة التغير، الحجم، وBeta.

الفكرة مبنية على مرحلتين لتوفير حصة الـ API المجانية (60 طلب/دقيقة):
  المرحلة 1: تحميل قائمة كل الأسهم الأمريكية مرة واحدة (طلب واحد فقط).
  المرحلة 2: المرور على كل سهم وجلب السعر الحالي (Quote) فقط — وهنا يستهلك أغلب الحصة.
  المرحلة 3: لمن نحصل على الأسهم المطابقة للسعر فقط (عدد أقل بكثير)، نجيب لها
             بيانات إضافية (Beta وغيره) من Basic Financials.

المرور على آلاف الأسهم يحتاج وقت (الحصة المجانية = طلب واحد كل ثانية تقريبًا).
لذلك السكربت يحفظ تقدمه أول بأول (checkpoint) ويقدر يكمل من حيث وقف لو انقطع.

الإعداد:
  1) pip install requests
  2) شغّل: python finnhub_price_scanner.py
     - أول مرة بيطلب منك تدخل مفتاح Finnhub (الكتابة ما تظهر على الشاشة)
     - بعد كذا يحفظه محليًا بجهازك فقط في: ~/.finnhub_scanner/config.json
     - ما يحتاج تدخله مرة ثانية إلا لو غيّرته أو حذفت الملف
  (بديل اختياري: تقدر تحط المفتاح بمتغير بيئة FINNHUB_API_KEY لو تفضل هذي الطريقة،
   وبهذي الحالة له الأولوية على الملف المحفوظ.)

خيارات مفيدة:
  --max-price 5          الحد الأعلى للسعر (افتراضي 5)
  --resume                يكمل من آخر نقطة توقف بدل البدء من جديد
  --limit 500             (اختياري) لتجربة سريعة على أول 500 سهم فقط
  --output results.csv    اسم ملف الإخراج
"""

import os
import sys
import csv
import json
import time
import stat
import getpass
import argparse
import requests

BASE_URL = "https://finnhub.io/api/v1"
CHECKPOINT_FILE = "scanner_checkpoint.json"
SYMBOLS_CACHE_FILE = "us_symbols_cache.json"

# ملف الإعدادات المحلي اللي يخزن فيه المفتاح (بجهازك فقط، ما يترسل لأي مكان غير Finnhub)
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".finnhub_scanner")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# الأسواق المسموحة فقط (نستبعد OTC / Pink Sheets / Caveat Emptor عبر فلترة الـ mic والنوع)
ALLOWED_MIC_PREFIXES = ("XNAS", "XNYS", "XASE")  # Nasdaq, NYSE, NYSE American


def get_api_key():
    """
    ترتيب البحث عن المفتاح:
      1) متغير بيئة FINNHUB_API_KEY (لو موجود، له الأولوية دائمًا)
      2) ملف الإعدادات المحلي ~/.finnhub_scanner/config.json
      3) لو ما لقى شي، يسأل المستخدم يدخله مرة وحدة (إدخال مخفي)، ويحفظه محليًا
    """
    env_key = os.environ.get("FINNHUB_API_KEY")
    if env_key:
        return env_key

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("api_key"):
                return saved["api_key"]
        except Exception:
            pass

    print("لم يتم العثور على مفتاح Finnhub محفوظ.")
    if not sys.stdin.isatty():
        sys.exit(
            "خطأ: يتم التشغيل في بيئة غير تفاعلية (مثل GitHub Actions) وما فيه "
            "FINNHUB_API_KEY بمتغيرات البيئة. أضف المفتاح كـ Secret وحطه كمتغير بيئة."
        )
    key = getpass.getpass("أدخل مفتاح Finnhub API (الكتابة ما تظهر على الشاشة): ").strip()
    if not key:
        sys.exit("لم يتم إدخال مفتاح، تم إلغاء التشغيل.")

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": key}, f)
    try:
        os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)  # صلاحية قراءة/كتابة لصاحب الحساب فقط
    except Exception:
        pass

    print(f"تم حفظ المفتاح محليًا في: {CONFIG_FILE}")
    print("(لن يُطلب منك إدخاله مرة أخرى في هذا الجهاز)")
    return key


def api_get(path, params, api_key, max_retries=5):
    params = {**params, "token": api_key}
    for attempt in range(max_retries):
        r = requests.get(f"{BASE_URL}{path}", params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  تجاوزنا حد الطلبات (429)، ننتظر {wait} ثانية...")
            time.sleep(wait)
            continue
        r.raise_for_status()
    raise RuntimeError(f"فشل الطلب بعد {max_retries} محاولات: {path}")


def load_symbols(api_key):
    """يجلب كل رموز الأسهم الأمريكية (مرة واحدة ويخزنها محليًا)."""
    if os.path.exists(SYMBOLS_CACHE_FILE):
        print("تحميل قائمة الرموز من الكاش المحلي...")
        with open(SYMBOLS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("جلب قائمة كل الأسهم الأمريكية من Finnhub (طلب واحد)...")
    data = api_get("/stock/symbol", {"exchange": "US"}, api_key)

    filtered = []
    for row in data:
        mic = (row.get("mic") or "").upper()
        sec_type = (row.get("type") or "")
        currency = (row.get("currency") or "USD")
        if not mic.startswith(ALLOWED_MIC_PREFIXES):
            continue
        if sec_type != "Common Stock":
            continue
        if currency != "USD":
            continue
        filtered.append({
            "symbol": row.get("symbol"),
            "description": row.get("description"),
            "mic": mic,
        })

    print(f"تم حفظ {len(filtered)} رمز سهم (بعد استبعاد OTC وغير الأسهم العادية).")
    with open(SYMBOLS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False)
    return filtered


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_index": 0, "matches": []}


def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def scan_prices(symbols, api_key, max_price, resume, limit):
    state = load_checkpoint() if resume else {"processed_index": 0, "matches": []}
    start = state["processed_index"]
    total = len(symbols) if not limit else min(limit, len(symbols))

    print(f"بدء مسح الأسعار من الرمز رقم {start} إلى {total}...")
    for i in range(start, total):
        row = symbols[i]
        symbol = row["symbol"]
        try:
            q = api_get("/quote", {"symbol": symbol}, api_key)
        except Exception as e:
            print(f"  [{i}] تخطي {symbol} بسبب خطأ: {e}")
            time.sleep(1.1)
            continue

        price = q.get("c")  # current price
        if price and 0 < price <= max_price:
            match = {
                "symbol": symbol,
                "name": row["description"],
                "mic": row["mic"],
                "price": price,
                "change_pct": q.get("dp"),
                "high": q.get("h"),
                "low": q.get("l"),
                "prev_close": q.get("pc"),
            }
            state["matches"].append(match)
            print(f"  ✅ [{i}] {symbol:6s} ${price:<6} {row['description']}")

        state["processed_index"] = i + 1
        if i % 25 == 0:
            save_checkpoint(state)
        time.sleep(1.05)  # نلتزم بحد ~60 طلب/دقيقة

    save_checkpoint(state)
    return state["matches"]


def enrich_with_beta(matches, api_key):
    """يجيب Beta وبيانات أساسية إضافية فقط للأسهم اللي طابقت فلتر السعر (عدد قليل)."""
    print(f"جلب بيانات Beta لِـ {len(matches)} سهم مطابق...")
    for m in matches:
        try:
            metrics = api_get(
                "/stock/metric", {"symbol": m["symbol"], "metric": "all"}, api_key
            )
            m["beta"] = metrics.get("metric", {}).get("beta")
            m["market_cap_musd"] = metrics.get("metric", {}).get("marketCapitalization")
            m["shares_outstanding_m"] = metrics.get("metric", {}).get("shareOutstanding")
        except Exception as e:
            print(f"  تعذّر جلب البيانات الإضافية لـ {m['symbol']}: {e}")
            m["beta"] = None
        time.sleep(1.05)
    return matches


def write_csv(matches, output):
    if not matches:
        print("ما فيه أي سهم مطابق للفلتر.")
        return
    fields = [
        "symbol", "name", "mic", "price", "change_pct", "high", "low",
        "prev_close", "beta", "market_cap_musd", "shares_outstanding_m",
    ]
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in sorted(matches, key=lambda x: x["price"]):
            writer.writerow({k: m.get(k, "") for k in fields})
    print(f"تم حفظ {len(matches)} سهم في: {output}")


def write_json(matches, output):
    import datetime
    payload = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "count": len(matches),
        "stocks": sorted(matches, key=lambda x: x["price"]),
    }
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"تم حفظ {len(matches)} سهم في: {output}")


def main():
    parser = argparse.ArgumentParser(description="Finnhub real-time price scanner (< $X)")
    parser.add_argument("--max-price", type=float, default=5.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="لتجربة سريعة على عدد محدود من الرموز")
    parser.add_argument("--output", type=str, default="matches_under_price.csv")
    parser.add_argument("--json-output", type=str, default=None, help="مسار ملف JSON إضافي للنشر على الويب (اختياري)")
    parser.add_argument("--skip-beta", action="store_true", help="تخطي جلب Beta لتسريع التشغيل")
    args = parser.parse_args()

    api_key = get_api_key()
    symbols = load_symbols(api_key)
    matches = scan_prices(symbols, api_key, args.max_price, args.resume, args.limit)

    if not args.skip_beta:
        matches = enrich_with_beta(matches, api_key)

    write_csv(matches, args.output)
    if args.json_output:
        write_json(matches, args.json_output)


if __name__ == "__main__":
    main()
