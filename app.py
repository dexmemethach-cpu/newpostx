from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Thông tin Telegram Bot
TELEGRAM_BOT_TOKEN = "8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8"
TELEGRAM_CHAT_ID = "-1003174496663"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def extract_photo_urls(tweet_data):
    """
    Trích xuất URL ảnh từ tweet
    Kiểm tra cả extendedEntities và entities để lấy media
    """
    photo_urls = []
    
    # Kiểm tra extendedEntities trước (chứa media chất lượng cao hơn)
    if "extendedEntities" in tweet_data and "media" in tweet_data["extendedEntities"]:
        for media in tweet_data["extendedEntities"]["media"]:
            if media.get("type") == "photo":
                photo_urls.append(media.get("media_url_https") or media.get("mediaUrl"))
    
    # Nếu không có trong extendedEntities, kiểm tra entities
    if not photo_urls and "entities" in tweet_data and "media" in tweet_data["entities"]:
        for media in tweet_data["entities"]["media"]:
            if media.get("type") == "photo":
                photo_urls.append(media.get("media_url_https") or media.get("mediaUrl"))
    
    # Lọc bỏ giá trị None
    return [url for url in photo_urls if url]

def format_tweet_message(tweet_data):
    """
    Định dạng thông báo tweet để gửi qua Telegram
    Phân loại rõ ràng giữa bài đăng gốc và bài trả lời
    """
    # Lấy thông tin tác giả
    author = tweet_data.get("author", {})
    author_name = author.get("name", "Unknown")
    author_username = author.get("userName", "unknown")
    
    # Lấy nội dung tweet
    text = tweet_data.get("text", "")
    tweet_url = tweet_data.get("twitterUrl") or tweet_data.get("url", "")
    
    # KIỂM TRA LOẠI TWEET: Bài gốc hay trả lời
    # Sử dụng trường "isReply" để xác định chính xác
    is_reply = tweet_data.get("isReply", False)
    in_reply_to_id = tweet_data.get("inReplyToId")
    in_reply_to_username = tweet_data.get("inReplyToUsername")
    
    # Trích xuất URL ảnh
    photo_urls = extract_photo_urls(tweet_data)
    
    # Tạo thông báo dựa trên loại tweet
    if is_reply and in_reply_to_username:
        # ĐÂY LÀ BÀI TRẢ LỜI
        message = f"💬 <b>REPLY</b> từ @{author_username}\n\n"
        message += f"👤 Trả lời cho: @{in_reply_to_username}\n"
        if in_reply_to_id:
            message += f"🔗 Reply to tweet: https://twitter.com/{in_reply_to_username}/status/{in_reply_to_id}\n"
        message += f"\n📝 Nội dung:\n{text}\n"
    else:
        # ĐÂY LÀ BÀI ĐĂNG GỐC
        message = f"🆕 <b>BÀI ĐĂNG MỚI</b> từ @{author_username}\n\n"
        message += f"👤 Tác giả: {author_name}\n"
        message += f"\n📝 Nội dung:\n{text}\n"
    
    # Thêm URL tweet gốc
    if tweet_url:
        message += f"\n🔗 Link: {tweet_url}"
    
    # Thêm thông tin ảnh nếu có
    if photo_urls:
        message += f"\n\n📷 Có {len(photo_urls)} ảnh đính kèm"
        for idx, url in enumerate(photo_urls, 1):
            message += f"\n  {idx}. {url}"
    
    return message

def send_telegram_message(message):
    """
    Gửi thông báo đến Telegram
    """
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        
        response = requests.post(TELEGRAM_API_URL, json=payload)
        
        if response.status_code == 200:
            print("✅ Đã gửi thông báo đến Telegram thành công")
            return True
        else:
            print(f"❌ Lỗi khi gửi đến Telegram: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception khi gửi Telegram: {str(e)}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint nhận webhook từ Twitter/X
    """
    try:
        # Lấy dữ liệu JSON từ request
        tweet_data = request.get_json()
        
        if not tweet_data:
            return jsonify({"error": "No data received"}), 400
        
        # Log dữ liệu nhận được (để debug)
        print("📥 Nhận được tweet data:")
        print(json.dumps(tweet_data, indent=2, ensure_ascii=False))
        
        # Định dạng và gửi thông báo
        message = format_tweet_message(tweet_data)
        success = send_telegram_message(message)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Tweet processed and sent to Telegram"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send to Telegram"
            }), 500
            
    except Exception as e:
        print(f"❌ Lỗi xử lý webhook: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """
    Endpoint kiểm tra health của service
    """
    return jsonify({
        "status": "healthy",
        "service": "Twitter Webhook to Telegram"
    }), 200

if __name__ == '__main__':
    print("🚀 Starting Twitter Webhook Server...")
    print(f"📱 Telegram Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"🔗 Webhook endpoint: http://localhost:5000/webhook")
    print(f"💚 Health check: http://localhost:5000/health")
    app.run(host='0.0.0.0', port=5000, debug=True)
