import yfinance as yf
import pandas as pd
import requests
import time
import threading
from flask import Flask

# إنشاء سيرفر ويب وهمي لكي تقبل منصة Render تشغيله مجاناً
app = Flask(__name__)

@app.route('/')
def home():
    return "Stock Scanner Bot is Running 24/7! 🚀"

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
            print("تم إرسال تنبيه السيولة عبر تيليجرام بنجاح!")
        else:
            print(f"فشل الإرسال: {response.text}")
    except Exception as e:
        print(f"خطأ في الاتصال بتيليجرام: {e}")

def monitor_stocks():
    # قائمة الأسهم المستهدفة (بين 1$ و 5$)
    tickers = ["SIRI", "NOK", "SNDL", "CENN", "HITI", "MULN", "ZOM", "AMC", "GPRO", "BBIG"]
    
    print("🚀 بدء وضع المراقبة الحية للأسهم (كل 5 دقائق)...")
    
    while True:
        found_opportunities = False
        report_lines = ["🚨 *تنبيه سيولة وزخم جديد (بين 1$ و 5$)*\n"]

        for ticker in tickers:
            try:
                data = yf.download(ticker, period="15d", interval="1d", progress=False)
                if data.empty or len(data) < 14:
                    continue
                
                close = data['Close'].squeeze()
                high = data['High'].squeeze()
                low = data['Low'].squeeze()
                volume = data['Volume'].squeeze()
                
                current_price = float(close.iloc[-1])
                
                # الشرط: السعر بين 1$ و 5$
                if 1.0 <= current_price < 5.0:
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
                    
                    # الشرط: مؤشر السيولة MFI أكبر من 60
                    if current_mfi > 60:
                        found_opportunities = True
                        report_lines.append(
                            f"🔹 السهم: `{ticker}`\n"
                            f"💵 السعر الحالي: `${current_price:.2f}`\n"
                            f"📊 مؤشر السيولة (MFI): `{current_mfi:.2f}` (سيولة قوية 🟢)\n"
                            f"-----------------------------------"
                        )
            except Exception as ex:
                pass

        if found_opportunities:
            final_message = "\n".join(report_lines)
            send_telegram_message(final_message)
            print("تم العثور على فرص وإرسال التنبيه.")
        else:
            print("جاري المراقبة... لا توجد إشارات جديدة مطابقة حالياً.")

        # الانتظار لمدة 5 دقائق (300 ثانية) قبل الفحص القادم
        time.sleep(300)

if __name__ == "__main__":
    # تشغيل سيرفر الويب في خلفية منفصلة
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # تشغيل مراقبة الأسهم
    monitor_stocks()
