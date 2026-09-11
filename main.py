import os
import requests
import yfinance as yf
import pandas as pd
import time
import threading
from flask import Flask, request

# --- 1. تعريف تطبيق فلاسك أولاً وقبل أي استخدام لـ @app.route ---
app = Flask(__name__)

# إعدادات تيليجرام المشتركة
TOKEN = "8827525799:AAHb3eGB6tdtbSSosBaPj_7rJSbLgYzCL_I"
CHAT_ID = "6817854644"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

@app.route('/')
def home():
    return "Unified Stock Bot (Scanner + Analyzer) is Running 24/7! 🚀"

def send_telegram_message(chat_id, message):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

# --- 2. وظيفة بوت التحليل الشامل عند طلب السهم ---
def analyze_stock(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol.upper())
        hist = ticker.history(period="15d")
        
        if hist.empty or len(hist) < 5:
            return f"❌ عذراً، لم أتمكن من العثور على بيانات كافية للسهم: `{ticker_symbol.upper()}`."

        info = ticker.info
        
        # بيانات آخر 3 أيام
        last_3_days = hist.tail(3)
        prices_summary = ""
        for date, row in last_3_days.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            prices_summary += (
                f"📅 التاريخ: {date_str}\n"
                f"   • الافتتاح: `${row['Open']:.2f}` | الإغلاق: `${row['Close']:.2f}`\n"
                f"   • الأعلى: `${row['High']:.2f}` | الأدنى: `${row['Low']:.2f}`\n"
            )

        current_price = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2])
        price_change_pct = ((current_price - prev_close) / prev_close) * 100

        support = float(hist['Low'].tail(10).min())
        resistance = float(hist['High'].tail(10).max())

        avg_volume = hist['Volume'].mean()
        market_cap = info.get('marketCap', 0)
        volatility_type = "🔥 خفيف (مضاربي عالي الحركة)" if avg_volume > 5000000 and market_cap < 2e9 else "🛡️ متوسط/ثقيل (استثماري أو مؤسسي)"

        close_series = hist['Close']
        ema_20_series = close_series.ewm(span=20, adjust=False).mean()
        ema_50_series = close_series.ewm(span=50, adjust=False).mean() if len(hist) >= 50 else ema_20_series
        
        ema_20 = ema_20_series.iloc[-1]
        ema_50 = ema_50_series.iloc[-1]
        trend = "📈 صعودي (Bullish) قوي" if current_price > ema_20 and ema_20 > ema_50 else "📉 هبوطي (Bearish) أو تصحيحي"

        volume_today = hist['Volume'].iloc[-1]
        volume_avg_10 = hist['Volume'].tail(10).mean()
        momentum = "⚡ زخم عالي جداً (حجم تداول أعلى من المعتاد)" if volume_today > (1.5 * volume_avg_10) else "⚖️ زخم طبيعي / هادئ"

        nasdaq_warning = "✅ السهم مستقر (لا توجد إنذارات شطب معلنة)"
        if current_price < 1.0:
            nasdaq_warning = "⚠️ تحذير: السهم يتداول تحت 1$ (عرضة لخطر إنذار ناسداك)"

        institution_held = info.get('heldPercentInstitutions', 0)
        target_group = "🏦 تسيطر عليها المؤسسات والأموال الذكية" if institution_held and institution_held > 0.5 else "🎯 يسيطر عليها المضاربون والأفراد"

        report = (
            f"📊 **تقرير تحليل السهم: `{ticker_symbol.upper()}`**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 **السعر الحالي:** `${current_price:.2f}` ({price_change_pct:+.2f}%)\n"
            f"🧭 **الاتجاه العام:** {trend}\n"
            f"⚖️ **طبيعة السهم:** {volatility_type}\n"
            f"👥 **المهيمنون:** {target_group}\n"
            f"⚡ **حالة الزخم:** {momentum}\n"
            f"🛡️ **الدعم والمقاومة (10 أيام):**\n"
            f"   • دعم: `${support:.2f}`\n"
            f"   • مقاومة: `${resistance:.2f}`\n"
            f"🚨 **مخاطر ناسداك والشطب:**\n"
            f"   • {nasdaq_warning}\n\n"
            f"📋 **أسعار آخر 3 أيام تداول:**\n"
            f"{prices_summary}"
        )
        return report
    except Exception as e:
        return f"❌ حدث خطأ أثناء تحليل السهم `{ticker_symbol}`."

# --- 3. وظيفة المراقبة التلقائية (في الخلفية) ---
def monitor_stocks():
    tickers = ["SIRI", "NOK", "SNDL", "PLTR", "NIO", "SOFI", "F", "BAC", "AMD", "INTC", "ZOM", "GPRO"]
    print("🚀 بدء وضع المراقبة التلقائية للأسهم في الخلفية...")
    
    while True:
        try:
            found_opportunities = False
            report_lines = ["🚨 *تنبيه فرص أسهم (بين 1$ و 20$) - تجاوز المتوسطات وزخم عالي*\n"]

            for ticker in tickers:
                data = yf.download(ticker, period="30d", interval="1d", progress=False)
                if data.empty or len(data) < 25:
                    continue
                
                close = data['Close'].squeeze()
                high = data['High'].squeeze()
                low = data['Low'].squeeze()
                volume = data['Volume'].squeeze()
                
                current_price = float(close.iloc[-1])
                
                if 1.0 <= current_price <= 20.0:
                    ema_20 = close.ewm(span=20, adjust=False).mean()
                    current_ema = float(ema_20.iloc[-1])
                    
                    typical_price = (high + low + close) / 3
                    money_flow = typical_price * volume
                    delta = typical_price.diff()
                    
                    pos_flow = pd.Series(0.0, index=data.index)
                    neg_flow = pd.Series(0.0, index=data.index)
                    pos_flow[delta > 0] = money_flow[delta > 0]
                    neg_flow[delta < 0] = money_flow[delta < 0]
                    
                    pos_mf = pos_flow.rolling(window=14).sum()
                    neg_mf = neg_flow.rolling(window=14).sum()
                    
                    mfi = 100 - (100 / (1 + (pos_mf / neg_mf)))
                    current_mfi = float(mfi.iloc[-1])
                    
                    if current_price > current_ema and current_mfi > 60:
                        found_opportunities = True
                        report_lines.append(
                            f"🔹 السهم: `{ticker}`\n"
                            f"💵 السعر الحالي: `${current_price:.2f}`\n"
                            f"📈 متوسط 20 (EMA): `${current_ema:.2f}` (اخترق 🟢)\n"
                            f"📊 السيولة MFI: `{current_mfi:.2f}` (قوي ⚡)\n"
                            f"-----------------------------------"
                        )

            if found_opportunities:
                final_message = "\n".join(report_lines)
                send_telegram_message(CHAT_ID, final_message)
        except Exception as ex:
            print(f"خطأ في المراقبة: {ex}")

        time.sleep(300) # فحص كل 5 دقائق

# --- 4. استقبال رسائل التليجرام الفورية للتحليل ---
@app.route('/webhook', methods=['POST'])
def receive_update():
    json_data = request.get_json()
    print(f"📥 تم استلام طلب من تيليجرام: {json_data}")
    if json_data and 'message' in json_data:
        chat_id = json_data['message']['chat']['id']
        text = json_data['message'].get('text', '').strip()
        
        if text.startswith('/start'):
            send_telegram_message(chat_id, "مرحباً بك! أنا بوت الأسهم المدمج 🚀\nأرسل رمز السهم مباشرة (مثل: `AAPL`) وسأحلله لك.")
        else:
            ticker = text.replace('/', '').strip()
            if len(ticker) <= 6:
                send_telegram_message(chat_id, f"🔍 جاري تحليل السهم `{ticker.upper()}`، يرجى الانتظار...")
                analysis_result = analyze_stock(ticker)
                send_telegram_message(chat_id, analysis_result)
    return "OK", 200

if __name__ == "__main__":
    # تشغيل المراقبة التلقائية في خيط خلفي
    monitor_thread = threading.Thread(target=monitor_stocks)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # تشغيل سيرفر فلاسك
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
