import requests
import json
from flask import Flask, request

# Telegram bot token và chat ID
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'
WEBHOOK_URL = f'https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/'

# Flask app cho bot
app = Flask(__name__)

# Xử lý các lệnh từ người dùng Telegram
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    print(f"Received update: {update}")

    # Kiểm tra xem có lệnh nào trong tin nhắn không
    if 'message' in update:
        message = update['message']
        text = message.get('text', '')
        chat_id = message['chat']['id']

        # Nếu nhận được lệnh /posttoday
        if text == "/posttoday":
            # Trả về số bài post trong ngày (sử dụng hàm từ app.py để lấy số lượng bài post)
            post_count = get_post_count()  # Đảm bảo rằng bạn đã có hàm get_post_count() từ app.py
            response_message = f"Số bài post trong ngày hôm nay: {post_count}"
            send_telegram_message(chat_id, response_message)

        # Trả lời tin nhắn bất kỳ
        else:
            response_message = "Lệnh không hợp lệ! Vui lòng thử lại."
            send_telegram_message(chat_id, response_message)

    return json.dumps({'status': 'ok'}), 200

def send_telegram_message(chat_id, message):
    url = f"{WEBHOOK_URL}sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# Đảm bảo app.py cũng có hàm get_post_count()
def get_post_count():
    # Lấy số bài post từ cơ sở dữ liệu hoặc tệp JSON của bạn
    try:
        with open('post_count.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    
    today = datetime.date.today().isoformat()
    return data.get(today, 0)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
