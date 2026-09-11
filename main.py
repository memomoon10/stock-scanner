# --- استقبال رسائل التليجرام الفورية للتحليل ---
@app.route('/webhook', methods=['POST'])
def receive_update():
    json_data = request.get_json()
    if json_data and 'message' in json_data:
        chat_id = json_data['message']['chat']['id']
        text = json_data['message'].get('text', '').strip()
        
        if text.startswith('/start'):
            send_telegram_message(chat_id, "مرحباً بك! أنا بوت الأسهم المدمج (المراقبة + التحليل الفوري) 🚀\nأرسل رمز السهم مباشرة (مثل: `AAPL` أو `TSLA`) وسأحلله لك بالكامل.")
        else:
            ticker = text.replace('/', '').strip()
            if len(ticker) <= 6:
                send_telegram_message(chat_id, f"🔍 جاري تحليل السهم `{ticker.upper()}`، يرجى الانتظار...")
                analysis_result = analyze_stock(ticker)
                send_telegram_message(chat_id, analysis_result)
    return "OK", 200
