from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re

app = Flask(__name__)

# Enable CORS for all domains
CORS(app)

# Thông tin Telegram bot
TELEGRAM_API_TOKEN = '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8'
CHAT_ID = '-1003174496663'

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

@app.route('/')
def home():
    return "✅ Twitter Webhook is running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # Nhận dữ liệu từ Webhook
    data = request.get_json(silent=True)
    print(f"Received data: {data}")

    # Kiểm tra dữ liệu có đúng không
    if not data:
        return jsonify({"status": "bad_request", "error": "Invalid or empty JSON body"}), 400

    # Kiểm tra trường 'tweets' có phải là mảng không và không rỗng
    tweets = data.get("tweets")
    if not isinstance(tweets, list) or len(tweets) == 0:
        return jsonify({"status": "bad_request", "error": "Missing or empty 'tweets' array"}), 400

    results = []
    for t in tweets:
        # Kiểm tra xem mỗi tweet có phải là dict và có trường 'id'
        if not isinstance(t, dict) or not t.get("id"):
            results.append({"ok": False, "error": "invalid_tweet_object"})
            continue

        # Tạo message từ tweet và gửi Telegram
        message, photo_url = format_tweet_message(t)
        send_res = send_to_telegram(message, photo_url)  # Gửi thông điệp và ảnh (nếu có)

        # Lưu kết quả gửi tin nhắn và thông tin tweet
        results.append({
            "tweet": {
                "id": str(t.get("id")),
                "text": t.get("text", ""),
                "author": (t.get("author") or {}).get("userName"),
                "url": t.get("twitterUrl") or t.get("url")
            },
            "telegram": send_res
        })

    # Kiểm tra tất cả kết quả gửi Telegram
    overall_ok = all(item.get("telegram", {}).get("ok") for item in results if isinstance(item, dict))
    
    # Tạo phản hồi tổng thể
    response = {
        "status": "ok" if overall_ok else "partial_ok",
        "event_type": data.get("event_type"),
        "timestamp": data.get("timestamp"),
        "results": results
    }

    # Trả về mã 200 nếu tất cả gửi thành công, 207 nếu có lỗi
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
        # Lấy ảnh URL từ trường media
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
