from flask import Flask, request, jsonify
from flask_cors import CORS  # Import Flask-CORS
import requests

app = Flask(__name__)

# Enable CORS for all domains
CORS(app)

# Thông tin Telegram bot
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'

def send_to_telegram(message, status="Success"):
    try:
        # Tạo URL API Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": f"Status: {status}\n{message}"}
        
        # Gửi yêu cầu POST đến Telegram
        response = requests.post(url, data=payload)
        
        # Kiểm tra xem có lỗi trong quá trình gửi tin nhắn không
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Nếu có lỗi khi gửi yêu cầu, in lỗi ra console
        print(f"Error sending message to Telegram: {e}")

@app.route('/')
def home():
    return "✅ Twitter Webhook is running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # Nhận dữ liệu từ Webhook
    data = request.get_json()
    print(f"Received tweet: {data}")

    # Nếu có tweet mới
    if data and data.get("tweet"):
        user = data["tweet"]["user"]
        text = data["tweet"]["text"]
        tweet_id = data["tweet"]["id"]
        link = f"https://twitter.com/{user}/status/{tweet_id}"

        # Gửi thông báo vào Telegram
        status_message = f"Tweet mới từ {user}:\n{text}\n{link}"
        send_to_telegram(status_message, status="Tweet Received")

    # Trả về dữ liệu JSON
    response_data = {
        "status": "ok",
        "tweet": data.get("tweet")
    }

    return jsonify(response_data), 200  # Trả về file JSON

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
