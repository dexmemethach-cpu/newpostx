from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Thông tin Telegram bot
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

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
        send_to_telegram(f"Tweet mới từ {user}:\n{text}\n{link}")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
