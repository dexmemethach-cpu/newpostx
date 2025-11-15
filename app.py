from flask import Flask, request, jsonify
import requests
import logging
import json

# Cấu hình logging chi tiết
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
    
    # Kiểm tra extended_entities trước (ưu tiên hơn entities)
    entities = tweet_data.get('extended_entities') or tweet_data.get('entities')
    
    if not entities or 'media' not in entities:
        logger.info("❌ Không tìm thấy media trong tweet")
        return media_list
    
    logger.info(f"🔍 Tìm thấy {len(entities['media'])} media items trong entities")
    
    for idx, media in enumerate(entities['media']):
        media_type = media.get('type')
        logger.info(f"📦 Media {idx + 1}: type = {media_type}")
        
        if media_type == 'photo':
            # Xử lý ảnh tĩnh
            media_url = media.get('media_url_https')
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

def send_telegram_photo(photo_url, caption=None):
    """Gửi ảnh tới Telegram"""
    url = f"{TELEGRAM_API_URL}/sendPhoto"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'photo': photo_url
    }
    if caption:
        payload['caption'] = caption
        payload['parse_mode'] = 'HTML'
    
    try:
        logger.info(f"📤 Đang gửi ảnh tới Telegram: {photo_url[:100]}...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi ảnh tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi ảnh tới Telegram: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
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
        payload['parse_mode'] = 'HTML'
    
    try:
        logger.info(f"📤 Đang gửi GIF tới Telegram: {animation_url[:100]}...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi GIF tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi GIF tới Telegram: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
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
        payload['parse_mode'] = 'HTML'
    
    try:
        logger.info(f"📤 Đang gửi video tới Telegram: {video_url[:100]}...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi video tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi video tới Telegram: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
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
        logger.info(f"📤 Đang gửi tin nhắn text tới Telegram...")
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"✅ Đã gửi tin nhắn tới Telegram thành công")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi tin nhắn tới Telegram: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        return None

@app.route('/webhook', methods=['POST'])
def twitter_webhook():
    """Xử lý webhook từ Twitter"""
    try:
        data = request.json
        logger.info(f"=" * 80)
        logger.info(f"📨 NHẬN ĐƯỢC WEBHOOK TỪ TWITTER")
        logger.info(f"=" * 80)
        
        # LOG TOÀN BỘ DATA ĐỂ DEBUG
        if data:
            logger.info(f"🔑 Các keys trong data: {list(data.keys())}")
            logger.info(f"📦 Data đầy đủ: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            logger.warning(f"⚠️ Data rỗng hoặc None")
            return jsonify({'status': 'success', 'message': 'Empty data'}), 200
        
        # Kiểm tra xem có phải là tweet mới không
        if 'tweet_create_events' in data:
            logger.info(f"✅ Tìm thấy tweet_create_events với {len(data['tweet_create_events'])} tweet(s)")
            
            for tweet_idx, tweet in enumerate(data['tweet_create_events']):
                logger.info(f"\n{'=' * 60}")
                logger.info(f"🐦 XỬ LÝ TWEET #{tweet_idx + 1}")
                logger.info(f"{'=' * 60}")
                
                # Lấy thông tin tweet
                tweet_id = tweet.get('id_str')
                tweet_text = tweet.get('text', '')
                user_name = tweet.get('user', {}).get('name', 'Unknown')
                user_screen_name = tweet.get('user', {}).get('screen_name', 'unknown')
                
                logger.info(f"👤 User: {user_name} (@{user_screen_name})")
                logger.info(f"🆔 Tweet ID: {tweet_id}")
                logger.info(f"📝 Text: {tweet_text[:100]}...")
                
                # Trích xuất media
                logger.info(f"\n🔍 BẮT ĐẦU TRÍCH XUẤT MEDIA...")
                media_list = extract_media(tweet)
                
                # Tạo caption cho media
                caption = f"🐦 <b>{user_name}</b> (@{user_screen_name})\n\n{tweet_text}\n\n🔗 https://twitter.com/{user_screen_name}/status/{tweet_id}"
                
                # Giới hạn caption (Telegram có giới hạn 1024 ký tự cho caption)
                if len(caption) > 1024:
                    caption = caption[:1020] + "..."
                    logger.info(f"✂️ Caption đã được cắt ngắn xuống 1024 ký tự")
                
                # Gửi media tới Telegram
                if media_list:
                    logger.info(f"\n📤 BẮT ĐẦU GỬI {len(media_list)} MEDIA TỚI TELEGRAM...")
                    
                    for idx, media in enumerate(media_list):
                        media_type = media['type']
                        media_url = media['url']
                        
                        logger.info(f"\n--- Media {idx + 1}/{len(media_list)} ---")
                        logger.info(f"Type: {media_type}")
                        logger.info(f"URL: {media_url}")
                        
                        # Chỉ gửi caption cho media đầu tiên
                        current_caption = caption if idx == 0 else None
                        
                        if media_type == 'photo':
                            logger.info(f"📸 Đang gửi ảnh {idx + 1}/{len(media_list)}...")
                            result = send_telegram_photo(media_url, current_caption)
                            if result:
                                logger.info(f"✅ Ảnh {idx + 1} đã gửi thành công")
                            else:
                                logger.error(f"❌ Ảnh {idx + 1} gửi thất bại")
                        
                        elif media_type == 'animated_gif':
                            logger.info(f"🎞️ Đang gửi GIF {idx + 1}/{len(media_list)}...")
                            result = send_telegram_animation(media_url, current_caption)
                            if result:
                                logger.info(f"✅ GIF {idx + 1} đã gửi thành công")
                            else:
                                logger.error(f"❌ GIF {idx + 1} gửi thất bại")
                        
                        elif media_type == 'video':
                            logger.info(f"🎬 Đang gửi video {idx + 1}/{len(media_list)}...")
                            result = send_telegram_video(media_url, current_caption)
                            if result:
                                logger.info(f"✅ Video {idx + 1} đã gửi thành công")
                            else:
                                logger.error(f"❌ Video {idx + 1} gửi thất bại")
                    
                    logger.info(f"\n✅ HOÀN THÀNH GỬI TẤT CẢ MEDIA")
                else:
                    # Nếu không có media, chỉ gửi text
                    logger.info(f"\n📝 Không có media, chỉ gửi tin nhắn text")
                    result = send_telegram_message(caption)
                    if result:
                        logger.info(f"✅ Tin nhắn text đã gửi thành công")
                    else:
                        logger.error(f"❌ Tin nhắn text gửi thất bại")
        
        else:
            # LOG CÁC EVENT KHÁC
            logger.warning(f"\n⚠️ KHÔNG TÌM THẤY tweet_create_events")
            logger.info(f"📋 Các event types có trong data:")
            
            for key in data.keys():
                logger.info(f"  - {key}")
            
            # Kiểm tra các event types phổ biến khác
            if 'favorite_events' in data:
                logger.info("❤️ Đây là favorite event (like)")
            elif 'follow_events' in data:
                logger.info("👥 Đây là follow event")
            elif 'direct_message_events' in data:
                logger.info("💬 Đây là direct message event")
            elif 'for_user_id' in data:
                logger.info("👤 Đây là user-specific event")
            else:
                logger.info("❓ Event type không xác định")
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ WEBHOOK XỬ LÝ THÀNH CÔNG")
        logger.info(f"{'=' * 80}\n")
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"\n{'=' * 80}")
        logger.error(f"❌ LỖI XỬ LÝ WEBHOOK")
        logger.error(f"{'=' * 80}")
        logger.error(f"Lỗi: {str(e)}")
        logger.exception("Chi tiết lỗi đầy đủ:")
        logger.error(f"{'=' * 80}\n")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook', methods=['GET'])
def twitter_webhook_challenge():
    """Xử lý CRC challenge từ Twitter"""
    crc_token = request.args.get('crc_token')
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"🔐 NHẬN CRC CHALLENGE TỪ TWITTER")
    logger.info(f"{'=' * 80}")
    
    if crc_token:
        logger.info(f"🔑 CRC Token: {crc_token[:20]}...")
        
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
        logger.info(f"{'=' * 80}\n")
        return jsonify(response), 200
    
    logger.error("❌ Không có crc_token trong request")
    logger.info(f"{'=' * 80}\n")
    return jsonify({'error': 'No crc_token provided'}), 400

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'twitter-webhook-v3',
        'version': '3.0',
        'features': ['photos', 'gifs', 'videos']
    }), 200

@app.route('/test', methods=['POST'])
def test_endpoint():
    """Endpoint để test gửi media tới Telegram"""
    try:
        data = request.json
        media_type = data.get('type', 'photo')
        media_url = data.get('url')
        caption = data.get('caption', 'Test message')
        
        logger.info(f"🧪 TEST: Gửi {media_type} tới Telegram")
        
        if media_type == 'photo':
            result = send_telegram_photo(media_url, caption)
        elif media_type == 'gif':
            result = send_telegram_animation(media_url, caption)
        elif media_type == 'video':
            result = send_telegram_video(media_url, caption)
        else:
            result = send_telegram_message(caption)
        
        if result:
            return jsonify({'status': 'success', 'result': result}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send'}), 500
            
    except Exception as e:
        logger.error(f"❌ Lỗi test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    logger.info("\n" + "=" * 80)
    logger.info("🚀 KHỞI ĐỘNG TWITTER WEBHOOK SERVER V3")
    logger.info("=" * 80)
    logger.info("📋 Tính năng:")
    logger.info("  ✅ Hỗ trợ ảnh (photos)")
    logger.info("  ✅ Hỗ trợ GIF (animated_gif)")
    logger.info("  ✅ Hỗ trợ video (video)")
    logger.info("  ✅ Tự động chọn video chất lượng cao nhất")
    logger.info("  ✅ Logging chi tiết để debug")
    logger.info("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
