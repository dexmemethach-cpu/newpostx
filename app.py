from flask import Flask, request, jsonify
import requests
import logging
import json
from datetime import datetime

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cấu hình Telegram Bot
TELEGRAM_BOT_TOKEN = "8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8"
TELEGRAM_CHAT_ID = "-1003174496663"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def extract_media(tweet_data):
    """
    Trích xuất thông tin media từ tweet (ảnh, GIF, video)
    
    Returns:
        list: Danh sách các dict chứa {'type': 'photo'|'animated_gif'|'video', 'url': 'media_url'}
    """
    media_list = []
    
    # Kiểm tra extendedEntities trước (ưu tiên hơn entities)
    extended_entities = tweet_data.get('extendedEntities') or tweet_data.get('extended_entities')
    entities = tweet_data.get('entities')
    
    # Chọn source có media
    media_source = None
    if extended_entities and extended_entities.get('media'):
        media_source = extended_entities.get('media')
        logger.info(f"🔍 Tìm thấy media trong extendedEntities")
    elif entities and entities.get('media'):
        media_source = entities.get('media')
        logger.info(f"🔍 Tìm thấy media trong entities")
    
    if not media_source:
        logger.info("❌ Không tìm thấy media trong tweet")
        return media_list
    
    logger.info(f"📦 Tìm thấy {len(media_source)} media items")
    
    for idx, media in enumerate(media_source):
        media_type = media.get('type')
        logger.info(f"📦 Media {idx + 1}: type = {media_type}")
        
        if media_type == 'photo':
            # Xử lý ảnh tĩnh
            media_url = media.get('media_url_https') or media.get('media_url')
            if media_url:
                media_list.append({
                    'type': 'photo',
                    'url': media_url
                })
                logger.info(f"✅ Tìm thấy ảnh: {media_url}")
        
        elif media_type == 'animated_gif':
            # Xử lý GIF (Twitter lưu dưới dạng MP4)
            video_info = media.get('video_info', {})
            variants = video_info.get('variants', [])
            
            logger.info(f"🎞️ GIF có {len(variants)} variants")
            
            # Lấy URL MP4 từ variants
            for variant in variants:
                if variant.get('content_type') == 'video/mp4':
                    gif_url = variant.get('url')
                    media_list.append({
                        'type': 'animated_gif',
                        'url': gif_url
                    })
                    logger.info(f"✅ Tìm thấy GIF: {gif_url}")
                    break
        
        elif media_type == 'video':
            # Xử lý video - chọn variant có bitrate cao nhất
            video_info = media.get('video_info', {})
            variants = video_info.get('variants', [])
            
            logger.info(f"🎬 Video có {len(variants)} variants")
            
            # Lọc các variant MP4 và sắp xếp theo bitrate
            mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
            
            if mp4_variants:
                # Chọn video có bitrate cao nhất
                best_variant = max(mp4_variants, key=lambda x: x.get('bitrate', 0))
                video_url = best_variant.get('url')
                bitrate = best_variant.get('bitrate', 0)
                
                media_list.append({
                    'type': 'video',
                    'url': video_url
                })
                logger.info(f"✅ Tìm thấy video (bitrate: {bitrate}): {video_url}")
            else:
                logger.warning(f"⚠️ Không tìm thấy MP4 variant cho video")
    
    logger.info(f"📊 Tổng cộng trích xuất được {len(media_list)} media items")
    return media_list

def send_telegram_message(text):
    """Gửi tin nhắn text tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    try:
        logger.info(f"📤 Đang gửi tin nhắn tới Telegram...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi tin nhắn tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi tin nhắn tới Telegram: {e}")
        return None

def format_tweet_message(tweet, media_list=None):
    """
    Format tweet thành message đẹp cho Telegram
    """
    # Lấy thông tin user
    author = tweet.get('author') or tweet.get('user', {})
    user_name = author.get('name', 'Unknown')
    user_screen_name = author.get('userName') or author.get('screen_name', 'unknown')
    followers = author.get('followers', 0)
    
    # Lấy thông tin tweet
    tweet_text = tweet.get('text', '')
    tweet_url = tweet.get('twitterUrl') or tweet.get('url', '')
    tweet_id = tweet.get('id_str') or tweet.get('id', '')
    
    # Kiểm tra loại tweet
    is_reply = tweet.get('isReply', False)
    is_retweet = tweet.get('retweeted_tweet') is not None
    is_quote = tweet.get('quoted_tweet') is not None
    
    # Xác định loại tweet
    tweet_type = "💬 Reply" if is_reply else ("🔄 Retweet" if is_retweet else ("💭 Quote" if is_quote else "📝 Tweet"))
    
    # Parse thời gian
    created_at = tweet.get('createdAt', '')
    try:
        # Format: "Sat Nov 15 07:36:22 +0000 2025"
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = created_at
    
    # Tạo message
    message = f"""{tweet_type}
👤 {user_name} (@{user_screen_name})
👥 Followers: {followers:,}

📝 Nội dung:
{tweet_text}

"""
    
    # Thêm link media nếu có
    if media_list and len(media_list) > 0:
        # Lấy link media đầu tiên (hoặc có thể gộp tất cả)
        media_url = media_list[0]['url']
        message += f"🔗 <a href=\"{media_url}\">Xem Media gốc</a>\n"
    
    # Thêm link tweet
    message += f"🔗 <a href=\"{tweet_url}\">Xem tweet gốc</a>\n"
    
    # Thêm thời gian
    message += f"\n\n⏰ {time_str}"
    
    return message

def process_tweet(tweet):
    """Xử lý một tweet và gửi tới Telegram"""
    logger.info(f"🐦 Đang xử lý tweet...")
    
    # Lấy thông tin cơ bản
    author = tweet.get('author') or tweet.get('user', {})
    user_screen_name = author.get('userName') or author.get('screen_name', 'unknown')
    tweet_id = tweet.get('id_str') or tweet.get('id', '')
    
    logger.info(f"👤 User: @{user_screen_name}")
    logger.info(f"🆔 Tweet ID: {tweet_id}")
    
    # Trích xuất media
    media_list = extract_media(tweet)
    
    # Tạo message
    message = format_tweet_message(tweet, media_list)
    
    # Gửi message tới Telegram
    logger.info(f"📤 Gửi message tới Telegram...")
    send_telegram_message(message)
    
    logger.info(f"✅ Hoàn thành xử lý tweet")

@app.route('/webhook', methods=['POST'])
def twitter_webhook():
    """Xử lý webhook từ Twitter"""
    try:
        data = request.json
        logger.info(f"=" * 80)
        logger.info(f"📨 NHẬN ĐƯỢC WEBHOOK TỪ TWITTER")
        logger.info(f"=" * 80)
        
        if not data:
            logger.warning(f"⚠️ Data rỗng")
            return jsonify({'status': 'success', 'message': 'Empty data'}), 200
        
        logger.info(f"🔑 Keys: {list(data.keys())}")
        
        # Xử lý format: {"tweets": [...], "event_type": "tweet"}
        if 'tweets' in data and isinstance(data['tweets'], list):
            logger.info(f"✅ Tìm thấy {len(data['tweets'])} tweet(s)")
            
            for idx, tweet in enumerate(data['tweets']):
                logger.info(f"\n--- Tweet {idx + 1}/{len(data['tweets'])} ---")
                process_tweet(tweet)
        
        # Xử lý format: {"tweet_create_events": [...]}
        elif 'tweet_create_events' in data:
            logger.info(f"✅ Tìm thấy {len(data['tweet_create_events'])} tweet(s)")
            
            for idx, tweet in enumerate(data['tweet_create_events']):
                logger.info(f"\n--- Tweet {idx + 1}/{len(data['tweet_create_events'])} ---")
                process_tweet(tweet)
        
        else:
            logger.warning(f"⚠️ Không tìm thấy tweets trong data")
            logger.info(f"Event type: {data.get('event_type', 'unknown')}")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ WEBHOOK XỬ LÝ THÀNH CÔNG")
        logger.info(f"{'=' * 80}\n")
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"❌ LỖI: {e}")
        logger.exception("Chi tiết lỗi:")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook', methods=['GET'])
def twitter_webhook_challenge():
    """Xử lý CRC challenge từ Twitter"""
    crc_token = request.args.get('crc_token')
    
    if crc_token:
        import hmac
        import hashlib
        import base64
        
        CONSUMER_SECRET = "YOUR_TWITTER_CONSUMER_SECRET"
        
        sha256_hash_digest = hmac.new(
            CONSUMER_SECRET.encode(),
            msg=crc_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        response = {
            'response_token': 'sha256=' + base64.b64encode(sha256_hash_digest).decode()
        }
        
        logger.info("✅ CRC challenge thành công")
        return jsonify(response), 200
    
    return jsonify({'error': 'No crc_token provided'}), 400

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'twitter-webhook-v3',
        'version': '3.0',
        'features': ['photos', 'gifs', 'videos', 'simple_format']
    }), 200

@app.route('/test', methods=['POST'])
def test_endpoint():
    """Test gửi message tới Telegram"""
    try:
        data = request.json
        
        # Test với tweet giả có media
        test_tweet = {
            'id': '1234567890',
            'text': data.get('text', '$OKAYGUY https://t.co/furkq7Zdd6'),
            'url': 'https://x.com/test/status/1234567890',
            'twitterUrl': 'https://twitter.com/test/status/1234567890',
            'createdAt': 'Sat Nov 15 07:57:33 +0000 2025',
            'isReply': False,
            'author': {
                'name': 'Zenox 🌙',
                'userName': 'Zenoxcallz',
                'followers': 424
            },
            'extendedEntities': {
                'media': [
                    {
                        'type': 'photo',
                        'media_url_https': 'https://pbs.twimg.com/media/test.jpg'
                    }
                ]
            }
        }
        
        process_tweet(test_tweet)
        
        return jsonify({'status': 'success', 'message': 'Test message sent'}), 200
    except Exception as e:
        logger.error(f"❌ Lỗi test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    logger.info("\n" + "=" * 80)
    logger.info("🚀 KHỞI ĐỘNG TWITTER WEBHOOK SERVER V3")
    logger.info("=" * 80)
    logger.info("📋 Tính năng:")
    logger.info("  ✅ Format message đơn giản, gọn gàng")
    logger.info("  ✅ Link 'Xem Media gốc' và 'Xem tweet gốc' riêng biệt")
    logger.info("  ✅ Hỗ trợ ảnh, GIF, video")
    logger.info("  ✅ Tự động chọn video chất lượng cao nhất")
    logger.info("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
