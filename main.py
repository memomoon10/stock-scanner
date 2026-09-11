import yfinance as yf
import pandas as pd
import requests
import time
import threading
from flask import Flask

# إنشاء سيرفر ويب وهمي لكي تعمل المنصة بشكل مستمر 24/7 دون توقف
app = Flask(__name__)

@app.route('/')
def home():
    return "Stock Scanner Bot (1$ - 20$ with EMA & MFI) is Running 24/7! 🚀"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def send_telegram_message(message):
    TOKEN = "8827525799:AAHb3eGB6tdtbSSosBaPj_7rJSbLgYzCL_I"
    CHAT_ID = "6817854644"
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("تم إرسال تنبيه الأسهم عبر تيليجرام بنجاح!")
        else:
            print(f"فشل الإرسال: {response.text}")
    except Exception as e:
        print(f"خطأ في الاتصال بتيليجرام: {e}")

def monitor_stocks():
    # قائمة أسهم مقترحة تتراوح أسعارها بين 1$ و 20$
    tickers = ["SIRI", "NOK", "SNDL", "PLTR", "NIO", "SOFI", "F", "BAC", "AMD", "INTC", "ZOM", "GPRO"]
    
    print("🚀 بدء وضع المراقبة الحية للأسهم (من 1$ إلى 20$ مع المتوسطات والزخم)...")
    
    while True:
        found_opportunities = False
        report_lines = ["🚨 *تنبيه فرص أسهم (بين 1$ و 20$) - تجاوز المتوسطات وزخم عالي*\n"]

        for ticker in tickers:
            try:
                # جلب بيانات كافية لحساب المتوسط لـ 20 يوم ومؤشر MFI لـ 14 يوم
                data = yf.download(ticker, period="30d", interval="1d", progress=False)
                if data.empty or len(data) < 25:
                    continue
                
                close = data['Close'].squeeze()
                high = data['High'].squeeze()
                low = data['Low'].squeeze()
                volume = data['Volume'].squeeze()
                
                current_price = float(close.iloc[-1])
                
                # الشرط الأول: السعر بين 1$ و 20$
                if 1.0 <= current_price <= 20.0:
                    
                    # حساب المتوسط المتحرك الأسي لـ 20 يوماً (EMA 20)
                    ema_20 = close.ewm(span=20, adjust=False).mean()
                    current_ema = float(ema_20.iloc[-1])
                    
                    # حساب مؤشر تدفق السيولة MFI (14)
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
                    
                    # الشرط الثاني: السعر الحالي أكبر من المتوسط الأسي 20 (تجاوز المتوسطات)
                    # الشرط الثالث: مؤشر السيولة MFI أكبر من 60 (زخم وسيولة قوية)
                    if current_price > current_ema and current_mfi > 60:
                        found_opportunities = True
                        report_lines.append(
                            f"🔹 السهم: `{ticker}`\n"
                            f"💵 السعر الحالي: `${current_price:.2f}`\n"
                            f"📈 متوسط 20 يوم (EMA): `${current_ema:.2f}` (اخترق المتوسط 🟢)\n"
                            f"📊 مؤشر السيولة (MFI): `{current_mfi:.2f}` (سيولة قوية ⚡)\n"
                            f"-----------------------------------"
                        )
            except Exception as ex:
                pass

        if found_opportunities:
            final_message = "\n".join(report_lines)
            send_telegram_message(final_message)
            print("تم العثور على فرص مطابقة للشروط وإرسال التنبيه.")
        else:
            print("جاري المراقبة... لا توجد إشارات جديدة مطابقة حالياً.")

        # الانتظار لمدة 5 دقائق قبل الفحص القادم
        time.sleep(300)

if __name__ == "__main__":
    # تشغيل سيرفر الويب في خلفية منفصلة لضمان استمرار البوت على المنصات السحابية
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # تشغيل حلقة مراقبة الأسهم
    monitor_stocks()
