from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

app = Flask(__name__)

# Cấu hình logging chi tiết
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cấu hình Telegram
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

def send_telegram_message(message):
    """Gửi tin nhắn đến Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi tin nhắn Telegram thành công")
        return True
    except Exception as e:
        logger.error(f"❌ Lỗi khi gửi Telegram: {str(e)}")
        return False

def extract_tweet_data(tweet):
    """Trích xuất dữ liệu từ một tweet object"""
    try:
        # Lấy thông tin cơ bản
        tweet_id = tweet.get('id', 'Unknown')
        tweet_text = tweet.get('text', 'No text')
        tweet_url = tweet.get('url', tweet.get('twitterUrl', 'No URL'))
        is_reply = tweet.get('isReply', False)
        
        # Lấy thông tin tác giả
        author = tweet.get('author', {})
        author_name = author.get('name', 'Unknown')
        author_username = author.get('userName', 'Unknown')
        author_followers = author.get('followers', 0)
        
        # Log chi tiết dữ liệu đã trích xuất
        logger.info(f"📊 Dữ liệu trích xuất:")
        logger.info(f"  - Tweet ID: {tweet_id}")
        logger.info(f"  - Text: {tweet_text[:50]}...")
        logger.info(f"  - Author: {author_name} (@{author_username})")
        logger.info(f"  - Followers: {author_followers}")
        logger.info(f"  - Is Reply: {is_reply}")
        logger.info(f"  - URL: {tweet_url}")
        
        return {
            'id': tweet_id,
            'text': tweet_text,
            'url': tweet_url,
            'is_reply': is_reply,
            'author_name': author_name,
            'author_username': author_username,
            'author_followers': author_followers
        }
    except Exception as e:
        logger.error(f"❌ Lỗi khi trích xuất dữ liệu tweet: {str(e)}")
        return None

def format_telegram_message(tweet_data):
    """Định dạng tin nhắn Telegram từ dữ liệu tweet"""
    reply_indicator = "💬 Reply" if tweet_data['is_reply'] else "🐦 Tweet"
    
    message = f"""
🔔 <b>Tweet Mới từ X</b>

{reply_indicator}
👤 <b>{tweet_data['author_name']}</b> (@{tweet_data['author_username']})
👥 Followers: {tweet_data['author_followers']:,}

📝 <b>Nội dung:</b>
{tweet_data['text']}

🔗 <a href="{tweet_data['url']}">Xem tweet gốc</a>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return message.strip()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint nhận webhook từ X/Twitter"""
    try:
        # Lấy dữ liệu JSON từ request
        payload = request.get_json()
        
        logger.info("=" * 60)
        logger.info("📥 Nhận webhook mới")
        logger.info(f"📦 Payload đầy đủ: {payload}")
        
        # Kiểm tra xem có trường "tweets" không
        if 'tweets' not in payload:
            logger.warning("⚠️ Không tìm thấy trường 'tweets' trong payload")
            return jsonify({
                "status": "error",
                "message": "Missing 'tweets' field in payload"
            }), 400
        
        tweets_array = payload['tweets']
        
        # Kiểm tra xem tweets có phải là array và không rỗng
        if not isinstance(tweets_array, list):
            logger.warning("⚠️ Trường 'tweets' không phải là array")
            return jsonify({
                "status": "error",
                "message": "'tweets' field is not an array"
            }), 400
        
        if len(tweets_array) == 0:
            logger.warning("⚠️ Array 'tweets' rỗng")
            return jsonify({
                "status": "success",
                "message": "No tweets to process",
                "processed": 0
            }), 200
        
        logger.info(f"📊 Tìm thấy {len(tweets_array)} tweet(s) trong payload")
        
        # Xử lý từng tweet trong array
        processed_count = 0
        failed_count = 0
        
        for index, tweet in enumerate(tweets_array, 1):
            logger.info(f"\n🔄 Xử lý tweet {index}/{len(tweets_array)}")
            logger.info(f"📄 Tweet raw data: {tweet}")
            
            # Trích xuất dữ liệu từ tweet
            tweet_data = extract_tweet_data(tweet)
            
            if tweet_data is None:
                logger.error(f"❌ Không thể trích xuất dữ liệu từ tweet {index}")
                failed_count += 1
                continue
            
            # Định dạng và gửi tin nhắn Telegram
            telegram_message = format_telegram_message(tweet_data)
            logger.info(f"📤 Tin nhắn Telegram sẽ gửi:\n{telegram_message}")
            
            if send_telegram_message(telegram_message):
                processed_count += 1
                logger.info(f"✅ Đã xử lý thành công tweet {index}")
            else:
                failed_count += 1
                logger.error(f"❌ Không thể gửi Telegram cho tweet {index}")
        
        # Tổng kết
        logger.info("=" * 60)
        logger.info(f"📊 KẾT QUẢ XỬ LÝ:")
        logger.info(f"  - Tổng số tweets: {len(tweets_array)}")
        logger.info(f"  - Thành công: {processed_count}")
        logger.info(f"  - Thất bại: {failed_count}")
        logger.info("=" * 60)
        
        return jsonify({
            "status": "success",
            "message": f"Processed {processed_count} tweet(s)",
            "total": len(tweets_array),
            "processed": processed_count,
            "failed": failed_count
        }), 200
        
    except Exception as e:
        logger.error(f"❌ LỖI NGHIÊM TRỌNG: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint kiểm tra health"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    logger.info("🚀 Khởi động Twitter Webhook Server (Fixed v2)")
    logger.info("📡 Endpoint: /webhook (POST)")
    logger.info("🏥 Health check: /health (GET)")
    app.run(host='0.0.0.0', port=5000, debug=True)
