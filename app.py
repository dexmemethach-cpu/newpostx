from flask import Flask, request, jsonify
from flask_cors import CORS  # Import Flask-CORS
import requests

app = Flask(__name__)

# Enable CORS for all domains
CORS(app)

# Thông tin Telegram bot
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'

def send_to_telegram(message):
    try:
        # Tạo URL API Telegram
        url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        
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

    # Kiểm tra xem dữ liệu có tweet không
    if data and 'tweet' in data:
        tweet = data['tweet']
        user = tweet['user']
        text = tweet['text']
        tweet_id = tweet['id']
        username = user['username']
        
        # Tạo liên kết tweet
        link = f"https://twitter.com/{username}/status/{tweet_id}"

        # Tạo thông báo để gửi vào Telegram
        status_message = f"Tweet mới từ {username}:\n{text}\nLink: {link}"
        
        # Gửi thông báo đến Telegram
        send_to_telegram(status_message)

    # Trả về phản hồi JSON
    response_data = {
        "status": "ok",
        "tweet": data.get("tweet")
    }

    return jsonify(response_data), 200  # Trả về file JSON

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
