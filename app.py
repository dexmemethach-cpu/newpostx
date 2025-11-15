from flask import Flask, request, jsonify
import requests
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
    
    # Kiểm tra extended_entities trước (ưu tiên hơn entities)
    entities = tweet_data.get('extended_entities') or tweet_data.get('entities')
    
    if not entities or 'media' not in entities:
        logger.info("Không tìm thấy media trong tweet")
        return media_list
    
    for media in entities['media']:
        media_type = media.get('type')
        
        if media_type == 'photo':
            # Xử lý ảnh tĩnh
            media_url = media.get('media_url_https')
            if media_url:
                media_list.append({
                    'type': 'photo',
                    'url': media_url
                })
                logger.info(f"Tìm thấy ảnh: {media_url}")
        
        elif media_type == 'animated_gif':
            # Xử lý GIF (Twitter lưu dưới dạng MP4)
            video_info = media.get('video_info', {})
            variants = video_info.get('variants', [])
            
            # Lấy URL MP4 từ variants
            for variant in variants:
                if variant.get('content_type') == 'video/mp4':
                    media_list.append({
                        'type': 'animated_gif',
                        'url': variant.get('url')
                    })
                    logger.info(f"Tìm thấy GIF: {variant.get('url')}")
                    break
        
        elif media_type == 'video':
            # Xử lý video - chọn variant có bitrate cao nhất
            video_info = media.get('video_info', {})
            variants = video_info.get('variants', [])
            
            # Lọc các variant MP4 và sắp xếp theo bitrate
            mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
            
            if mp4_variants:
                # Chọn video có bitrate cao nhất
                best_variant = max(mp4_variants, key=lambda x: x.get('bitrate', 0))
                media_list.append({
                    'type': 'video',
                    'url': best_variant.get('url')
                })
                logger.info(f"Tìm thấy video (bitrate: {best_variant.get('bitrate')}): {best_variant.get('url')}")
    
    return media_list

def send_telegram_photo(photo_url, caption=None):
    """Gửi ảnh tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendPhoto"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'photo': photo_url
    }
    if caption:
        payload['caption'] = caption
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi ảnh tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi ảnh tới Telegram: {e}")
        return None

def send_telegram_animation(animation_url, caption=None):
    """Gửi GIF (animation) tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendAnimation"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'animation': animation_url
    }
    if caption:
        payload['caption'] = caption
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi GIF tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi GIF tới Telegram: {e}")
        return None

def send_telegram_video(video_url, caption=None):
    """Gửi video tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendVideo"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'video': video_url
    }
    if caption:
        payload['caption'] = caption
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi video tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi video tới Telegram: {e}")
        return None

def send_telegram_message(text):
    """Gửi tin nhắn text tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi tin nhắn tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi tin nhắn tới Telegram: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def twitter_webhook():
    """Xử lý webhook từ Twitter"""
    try:
        data = request.json
        logger.info(f"📨 Nhận được webhook từ Twitter")
        
        # Kiểm tra xem có phải là tweet mới không
        if 'tweet_create_events' in data:
            for tweet in data['tweet_create_events']:
                # Lấy thông tin tweet
                tweet_id = tweet.get('id_str')
                tweet_text = tweet.get('text', '')
                user_name = tweet.get('user', {}).get('name', 'Unknown')
                user_screen_name = tweet.get('user', {}).get('screen_name', 'unknown')
                
                logger.info(f"🐦 Tweet mới từ @{user_screen_name}: {tweet_text[:50]}...")
                
                # Trích xuất media
                media_list = extract_media(tweet)
                
                # Tạo caption cho media
                caption = f"🐦 <b>{user_name}</b> (@{user_screen_name})\n\n{tweet_text}\n\n🔗 https://twitter.com/{user_screen_name}/status/{tweet_id}"
                
                # Giới hạn caption (Telegram có giới hạn 1024 ký tự cho caption)
                if len(caption) > 1024:
                    caption = caption[:1020] + "..."
                
                # Gửi media tới Telegram
                if media_list:
                    logger.info(f"📎 Tìm thấy {len(media_list)} media item(s)")
                    
                    for idx, media in enumerate(media_list):
                        media_type = media['type']
                        media_url = media['url']
                        
                        # Chỉ gửi caption cho media đầu tiên
                        current_caption = caption if idx == 0 else None
                        
                        if media_type == 'photo':
                            logger.info(f"📸 Đang gửi ảnh {idx + 1}/{len(media_list)}...")
                            send_telegram_photo(media_url, current_caption)
                        
                        elif media_type == 'animated_gif':
                            logger.info(f"🎞️ Đang gửi GIF {idx + 1}/{len(media_list)}...")
                            send_telegram_animation(media_url, current_caption)
                        
                        elif media_type == 'video':
                            logger.info(f"🎬 Đang gửi video {idx + 1}/{len(media_list)}...")
                            send_telegram_video(media_url, current_caption)
                else:
                    # Nếu không có media, chỉ gửi text
                    logger.info("📝 Không có media, gửi tin nhắn text")
                    send_telegram_message(caption)
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"❌ Lỗi xử lý webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook', methods=['GET'])
def twitter_webhook_challenge():
    """Xử lý CRC challenge từ Twitter"""
    crc_token = request.args.get('crc_token')
    if crc_token:
        # Twitter yêu cầu response với sha256 hash
        import hmac
        import hashlib
        import base64
        
        # Consumer Secret của Twitter App (cần thay thế bằng giá trị thực)
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
    return jsonify({'status': 'healthy', 'service': 'twitter-webhook-v3'}), 200

if __name__ == '__main__':
    logger.info("🚀 Khởi động Twitter Webhook Server v3 (hỗ trợ Ảnh, GIF, Video)")
    app.run(host='0.0.0.0', port=5000, debug=True)
