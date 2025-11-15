from flask import Flask, request, jsonify
import requests
import logging
import json
import re
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

def detect_community_post(tweet_data):
    """
    Phát hiện xem tweet có phải từ Twitter Community không
    Tối ưu cho twitterapi.io
    
    Returns:
        dict: {'is_community': bool, 'community_name': str, 'community_id': str}
    """
    community_info = {
        'is_community': False,
        'community_name': None,
        'community_id': None
    }
    
    try:
        # LOG tất cả các trường để tìm community
        logger.info(f"🔍 Checking for community in tweet...")
        
        # 1. Kiểm tra trực tiếp các trường community
        community_fields = [
            'community', 'communityId', 'community_id', 
            'communityName', 'community_name', 'communityData', 'community_data'
        ]
        
        for field in community_fields:
            if field in tweet_data and tweet_data[field]:
                logger.info(f"✅ Found community field: {field} = {tweet_data[field]}")
                
                if isinstance(tweet_data[field], dict):
                    community_info['is_community'] = True
                    community_info['community_id'] = tweet_data[field].get('id') or tweet_data[field].get('id_str')
                    community_info['community_name'] = tweet_data[field].get('name')
                elif isinstance(tweet_data[field], str):
                    community_info['is_community'] = True
                    community_info['community_id'] = tweet_data[field]
        
        # 2. Kiểm tra trong conversation_context
        conv_context = tweet_data.get('conversation_context') or tweet_data.get('conversationContext')
        if conv_context:
            logger.info(f"🔍 Found conversation_context")
            if isinstance(conv_context, dict) and 'community' in conv_context:
                community_info['is_community'] = True
                community = conv_context['community']
                if isinstance(community, dict):
                    community_info['community_id'] = community.get('id') or community.get('id_str')
                    community_info['community_name'] = community.get('name')
                    logger.info(f"✅ Community in conversation_context: {community_info['community_name']}")
        
        # 3. Kiểm tra trong context_annotations
        annotations = tweet_data.get('context_annotations') or tweet_data.get('contextAnnotations', [])
        if annotations:
            logger.info(f"🔍 Found {len(annotations)} context_annotations")
            for annotation in annotations:
                domain = annotation.get('domain', {})
                entity = annotation.get('entity', {})
                
                # Log để debug
                logger.info(f"  - Domain: {domain.get('name')} (id: {domain.get('id')})")
                logger.info(f"  - Entity: {entity.get('name')} (id: {entity.get('id')})")
                
                # Kiểm tra domain là Community
                if domain.get('name') == 'Community' or domain.get('id') == '150':
                    community_info['is_community'] = True
                    community_info['community_name'] = entity.get('name')
                    community_info['community_id'] = entity.get('id')
                    logger.info(f"✅ Community in context_annotations: {community_info['community_name']}")
        
        # 4. Kiểm tra trong card (một số API trả về community trong card)
        card = tweet_data.get('card')
        if card and isinstance(card, dict):
            logger.info(f"🔍 Found card data")
            if 'community' in card:
                community_info['is_community'] = True
                community = card['community']
                if isinstance(community, dict):
                    community_info['community_id'] = community.get('id')
                    community_info['community_name'] = community.get('name')
                    logger.info(f"✅ Community in card: {community_info['community_name']}")
        
        # 5. Kiểm tra trong place (đôi khi community được lưu ở đây)
        place = tweet_data.get('place')
        if place and isinstance(place, dict) and place:
            logger.info(f"🔍 Found place data: {place}")
            if 'community' in place:
                community_info['is_community'] = True
                community = place['community']
                if isinstance(community, dict):
                    community_info['community_id'] = community.get('id')
                    community_info['community_name'] = community.get('name')
                    logger.info(f"✅ Community in place: {community_info['community_name']}")
        
        # 6. Kiểm tra URL có chứa /communities/
        tweet_url = tweet_data.get('url') or tweet_data.get('twitterUrl', '')
        if '/communities/' in tweet_url or '/i/communities/' in tweet_url:
            community_info['is_community'] = True
            logger.info(f"✅ Detected community from URL: {tweet_url}")
            
            # Thử extract community ID từ URL
            import re
            match = re.search(r'/communities/(\d+)', tweet_url)
            if match:
                community_info['community_id'] = match.group(1)
                logger.info(f"  - Extracted community ID: {community_info['community_id']}")
        
        # 7. Kiểm tra trong entities
        entities = tweet_data.get('entities')
        if entities and isinstance(entities, dict):
            # Kiểm tra URLs trong entities
            urls = entities.get('urls', [])
            for url_obj in urls:
                expanded_url = url_obj.get('expanded_url', '')
                if '/communities/' in expanded_url:
                    community_info['is_community'] = True
                    logger.info(f"✅ Detected community from entities URL: {expanded_url}")
        
        # Kết quả
        if community_info['is_community']:
            logger.info(f"🏘️ ✅ COMMUNITY POST DETECTED!")
            logger.info(f"   - Name: {community_info['community_name'] or 'Unknown'}")
            logger.info(f"   - ID: {community_info['community_id'] or 'Unknown'}")
        else:
            logger.info(f"ℹ️ Regular tweet (not a community post)")
        
    except Exception as e:
        logger.error(f"❌ Error detecting community post: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    return community_info

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

def clean_tweet_text(text):
    """
    Loại bỏ link media (t.co) khỏi nội dung tweet và giữ nguyên format xuống dòng
    """
    # Loại bỏ các link t.co (Twitter rút gọn link)
    text = re.sub(r'https://t\.co/\w+', '', text)
    
    # Loại bỏ khoảng trắng thừa ở đầu/cuối mỗi dòng
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    
    # Loại bỏ các dòng trống liên tiếp
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if line:
            cleaned_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append(line)
            prev_empty = True
    
    # Ghép lại với xuống dòng
    text = '\n'.join(cleaned_lines)
    
    # Loại bỏ khoảng trắng thừa ở đầu và cuối
    text = text.strip()
    
    return text

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
        logger.info(f"📤 Đang gửi ảnh tới Telegram...")
        response = requests.post(url, json=payload, timeout=30)
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
        payload['parse_mode'] = 'HTML'
    
    try:
        logger.info(f"📤 Đang gửi GIF tới Telegram...")
        response = requests.post(url, json=payload, timeout=30)
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
        payload['parse_mode'] = 'HTML'
    
    try:
        logger.info(f"📤 Đang gửi video tới Telegram...")
        response = requests.post(url, json=payload, timeout=30)
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

def format_tweet_caption(tweet, community_info=None, media_url=None):
    """
    Format tweet thành caption cho media
    """
    # Lấy thông tin user
    author = tweet.get('author') or tweet.get('user', {})
    user_name = author.get('name', 'Unknown')
    user_screen_name = author.get('userName') or author.get('screen_name', 'unknown')
    followers = author.get('followers', 0)
    
    # Lấy thông tin tweet - ưu tiên full_text nếu có
    tweet_text = tweet.get('full_text') or tweet.get('text', '')
    
    # Loại bỏ link media khỏi text nhưng giữ nguyên format xuống dòng
    tweet_text = clean_tweet_text(tweet_text)
    
    tweet_url = tweet.get('twitterUrl') or tweet.get('url', '')
    
    # Kiểm tra loại tweet
    is_reply = tweet.get('isReply', False)
    is_retweet = tweet.get('retweeted_tweet') is not None
    is_quote = tweet.get('quoted_tweet') is not None
    
    # Xác định loại tweet
    if is_reply:
        tweet_type = "💬 Reply"
    elif is_retweet:
        tweet_type = "🔄 Retweet"
    elif is_quote:
        tweet_type = "💭 Quote"
    elif community_info and community_info['is_community']:
        tweet_type = "📝 Tweet on community"
    else:
        tweet_type = "📝 Tweet"
    
    # Parse thời gian
    created_at = tweet.get('createdAt', '')
    try:
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = created_at
    
    # Tạo caption với header
    caption = f"🔔 <b>Tweet Mới từ KOL</b>\n\n"
    caption += f"{tweet_type}\n"
    
    # Thêm thông tin community nếu có
    if community_info and community_info['is_community']:
        if community_info['community_name']:
            caption += f"👥 {community_info['community_name']}\n"
        else:
            caption += f"👥 Community\n"
    
    caption += f"👤 {user_name} (@{user_screen_name})\n"
    caption += f"👥 Followers: {followers:,}\n\n"
    caption += f"📝 Nội dung:\n{tweet_text}\n\n"
    
    # Thêm link media nếu có
    if media_url:
        caption += f"🔗 <a href=\"{media_url}\">Xem Media gốc</a>\n"
    
    # Thêm link tweet
    caption += f"🔗 <a href=\"{tweet_url}\">Xem tweet gốc</a>\n"
    
    # Thêm thời gian
    caption += f"\n\n⏰ {time_str}"
    
    return caption

def process_tweet(tweet):
    """Xử lý một tweet và gửi tới Telegram"""
    logger.info(f"🐦 Đang xử lý tweet...")
    
    # Lấy thông tin cơ bản
    author = tweet.get('author') or tweet.get('user', {})
    user_screen_name = author.get('userName') or author.get('screen_name', 'unknown')
    tweet_id = tweet.get('id_str') or tweet.get('id', '')
    
    logger.info(f"👤 User: @{user_screen_name}")
    logger.info(f"🆔 Tweet ID: {tweet_id}")
    
    # Phát hiện community post
    community_info = detect_community_post(tweet)
    
    # Log text gốc để debug
    tweet_text = tweet.get('full_text') or tweet.get('text', '')
    logger.info(f"📝 Text gốc: {tweet_text[:100]}...")
    
    # Trích xuất media
    media_list = extract_media(tweet)
    
    # Gửi tới Telegram
    if media_list and len(media_list) > 0:
        logger.info(f"📎 Tweet có {len(media_list)} media, gửi kèm media...")
        
        # Gửi media đầu tiên kèm caption đầy đủ
        first_media = media_list[0]
        media_type = first_media['type']
        media_url = first_media['url']
        
        # Tạo caption với link media và thông tin community
        caption = format_tweet_caption(tweet, community_info, media_url)
        
        # Gửi media tương ứng
        if media_type == 'photo':
            logger.info(f"📸 Gửi ảnh kèm caption...")
            send_telegram_photo(media_url, caption)
        elif media_type == 'animated_gif':
            logger.info(f"🎞️ Gửi GIF kèm caption...")
            send_telegram_animation(media_url, caption)
        elif media_type == 'video':
            logger.info(f"🎬 Gửi video kèm caption...")
            send_telegram_video(media_url, caption)
        
        # Gửi các media còn lại (nếu có) - không có caption
        for idx in range(1, len(media_list)):
            media = media_list[idx]
            media_type = media['type']
            media_url = media['url']
            
            logger.info(f"📎 Gửi media {idx + 1}/{len(media_list)}...")
            
            if media_type == 'photo':
                send_telegram_photo(media_url)
            elif media_type == 'animated_gif':
                send_telegram_animation(media_url)
            elif media_type == 'video':
                send_telegram_video(media_url)
    else:
        # Không có media, chỉ gửi text
        logger.info(f"📝 Tweet không có media, chỉ gửi text...")
        message = format_tweet_caption(tweet, community_info, None)
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
        'version': '3.3-twitterapi.io',
        'features': ['photos', 'gifs', 'videos', 'clean_text', 'kol_header', 'preserve_format', 'community_detection_enhanced']
    }), 200

@app.route('/test', methods=['POST'])
def test_endpoint():
    """Test gửi message tới Telegram"""
    try:
        data = request.json
        
        # Test với tweet giả có xuống dòng và community
        test_tweet = {
            'id': '1234567890',
            'text': data.get('text', '$DAUMEN CA: GV1uiHtqnFqHYijcBzt2A56Fe9LjoCnszjVbekzvpump\n\nIf you like it, just go for it, guys\n\nLooks appealing and definitely grabs the community\'s attention https://t.co/xxxxx'),
            'url': 'https://x.com/test/status/1234567890',
            'twitterUrl': 'https://twitter.com/test/status/1234567890',
            'createdAt': 'Sat Nov 15 08:08:31 +0000 2025',
            'isReply': False,
            'author': {
                'name': 'Test User',
                'userName': 'testuser',
                'followers': 1000
            },
            # Test community data
            'community': {
                'id': '123456',
                'name': 'Crypto Traders'
            }
        }
        
        process_tweet(test_tweet)
        
        return jsonify({'status': 'success', 'message': 'Test message sent'}), 200
    except Exception as e:
        logger.error(f"❌ Lỗi test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    logger.info("\n" + "=" * 80)
    logger.info("🚀 KHỞI ĐỘNG TWITTER WEBHOOK SERVER V3.3")
    logger.info("=" * 80)
    logger.info("📋 Tính năng:")
    logger.info("  ✅ Header '🔔 Tweet Mới từ KOL'")
    logger.info("  ✅ Giữ nguyên định dạng xuống dòng của tweet gốc")
    logger.info("  ✅ Hiển thị media (ảnh/GIF/video) trong Telegram")
    logger.info("  ✅ Tự động loại bỏ link t.co khỏi nội dung")
    logger.info("  ✅ Kèm link 'Xem Media gốc' và 'Xem tweet gốc'")
    logger.info("  ✅ Nhận dạng Twitter Community posts (twitterapi.io)")
    logger.info("  🔍 Kiểm tra nhiều vị trí: URL, entities, context_annotations, card, place")
    logger.info("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
