from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import datetime

app = Flask(__name__)

# Enable CORS for all domains
CORS(app)

# Thông tin Telegram bot
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'
WEBHOOK_URL = f'https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/'

# Đường dẫn tệp lưu trữ số bài post mỗi ngày
POST_COUNT_FILE = 'post_count.json'

# Cấu hình các endpoint Telegram
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
            # Lấy số bài post trong ngày (sử dụng hàm từ app.py để lấy số lượng bài post)
            count = get_post_count()  # Đảm bảo rằng bạn đã có hàm get_post_count() từ app.py
            response_message = f"Số bài post trong ngày hôm nay: {count}"
            send_telegram_message(chat_id, response_message)

        # Trả lời tin nhắn bất kỳ
        else:
            response_message = "Lệnh không hợp lệ! Vui lòng thử lại."
            send_telegram_message(chat_id, response_message)

    return jsonify({"status": "ok"}), 200

def send_telegram_message(chat_id, message):
    url = f"{WEBHOOK_URL}sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# Kiểm tra số lượng bài post trong ngày
def get_post_count():
    try:
        with open(POST_COUNT_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    
    today = datetime.date.today().isoformat()
    return data.get(today, 0)

# Cập nhật số bài post
def update_post_count():
    try:
        with open(POST_COUNT_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    
    today = datetime.date.today().isoformat()
    data[today] = data.get(today, 0) + 1

    with open(POST_COUNT_FILE, 'w') as f:
        json.dump(data, f)

# Hàm gửi tin nhắn đến Telegram
def send_to_telegram(message, photo_url=None):
    try:
        # Nếu có ảnh, gửi ảnh qua API sendPhoto
        if photo_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendPhoto"
            payload = {"chat_id": CHAT_ID, "photo": photo_url, "caption": message}
        else:
            # Nếu không có ảnh, gửi tin nhắn văn bản
            url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
            payload = {"chat_id": CHAT_ID, "text": message}

        # Gửi yêu cầu POST đến Telegram
        response = requests.post(url, data=payload)
        
        # Kiểm tra xem có lỗi trong quá trình gửi tin nhắn không
        response.raise_for_status()

        # In phản hồi từ Telegram để kiểm tra
        print("Response from Telegram:", response.json())
        return {"ok": True, "response": response.json()}
    
    except requests.exceptions.RequestException as e:
        # Nếu có lỗi khi gửi yêu cầu, in lỗi ra console
        print(f"Error sending message to Telegram: {e}")
        return {"ok": False, "error": str(e)}

# Webhook xử lý bài post
@app.route('/webhook', methods=['POST'])
def webhook():
    # Nhận dữ liệu từ Webhook
    data = request.get_json(silent=True)
    print(f"Received data: {data}")

    if not data:
        return jsonify({"status": "bad_request", "error": "Invalid or empty JSON body"}), 400

    tweets = data.get("tweets")
    if not isinstance(tweets, list) or len(tweets) == 0:
        return jsonify({"status": "bad_request", "error": "Missing or empty 'tweets' array"}), 400

    results = []
    for t in tweets:
        if not isinstance(t, dict) or not t.get("id"):
            results.append({"ok": False, "error": "invalid_tweet_object"})
            continue

        # Tạo message từ tweet và gửi Telegram
        message, photo_url = format_tweet_message(t)
        send_res = send_to_telegram(message, photo_url)

        results.append({
            "tweet": {
                "id": str(t.get("id")),
                "text": t.get("text", ""),
                "author": (t.get("author") or {}).get("userName"),
                "url": t.get("twitterUrl") or t.get("url")
            },
            "telegram": send_res
        })

    overall_ok = all(item.get("telegram", {}).get("ok") for item in results if isinstance(item, dict))
    
    response = {
        "status": "ok" if overall_ok else "partial_ok",
        "event_type": data.get("event_type"),
        "timestamp": data.get("timestamp"),
        "results": results
    }

    return jsonify(response), 200 if overall_ok else 207

# Hàm format message từ tweet (có thể tùy chỉnh theo yêu cầu)
def format_tweet_message(tweet):
    user = tweet.get("author", {}).get("userName", "Unknown User")
    text = tweet.get("text", "")
    tweet_id = tweet.get("id", "")
    link = f"https://twitter.com/{user}/status/{tweet_id}"

    # Lấy URL ảnh từ tweet (nếu có)
    photo_url = None
    media = tweet.get("media", [])
    if media:
        photo_url = media[0].get("media_url", None)  # Giả sử ảnh đầu tiên trong media
    
    # Kiểm tra nếu tweet là bài post hay comment
    if tweet.get("inReplyToStatusId"):
        message_type = "Bình luận"
        original_tweet_id = tweet.get("inReplyToStatusId")
        original_tweet_link = f"https://twitter.com/{user}/status/{original_tweet_id}"
        reply_to = f"Trả lời tweet: {original_tweet_link}"
    else:
        message_type = "Bài post"
        reply_to = "Không phải bình luận, là bài post gốc."

    # Định dạng lại thông điệp với thông tin bài post hoặc comment
    message = f"""
{message_type} từ @{user}:

{text}

Link: {link}

{reply_to}

--------------------------------------------

X (formerly Twitter)
{user} (@{user}) on X
{text}
"""
    return message, photo_url

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
