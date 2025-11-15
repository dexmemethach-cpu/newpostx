from flask import Flask, request, jsonify
import requests
import logging
import os
from datetime import datetime
import json

app = Flask(__name__)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cấu hình Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '-1003174496663')

def detect_community_post(tweet_data):
    """
    Phát hiện xem tweet có phải từ Twitter Community không
    
    Returns:
        dict: {'is_community': bool, 'community_name': str, 'community_id': str}
    """
    community_info = {
        'is_community': False,
        'community_name': None,
        'community_id': None
    }
    
    try:
        # Kiểm tra trong tweet object trực tiếp
        if 'community_id' in tweet_data:
            community_info['is_community'] = True
            community_info['community_id'] = tweet_data['community_id']
            logger.info(f"✅ Community post detected - ID: {tweet_data['community_id']}")
        
        # Kiểm tra trong community object
        if 'community' in tweet_data:
            community_info['is_community'] = True
            community = tweet_data['community']
            community_info['community_id'] = community.get('id')
            community_info['community_name'] = community.get('name')
            logger.info(f"✅ Community post detected - Name: {community.get('name')}, ID: {community.get('id')}")
        
        # Kiểm tra trong conversation_context
        if 'conversation_context' in tweet_data:
            conv_context = tweet_data['conversation_context']
            if 'community' in conv_context:
                community_info['is_community'] = True
                community = conv_context['community']
                community_info['community_id'] = community.get('id')
                community_info['community_name'] = community.get('name')
                logger.info(f"✅ Community post detected in conversation_context - Name: {community.get('name')}")
        
        # Kiểm tra trong context_annotations
        if 'context_annotations' in tweet_data:
            for annotation in tweet_data['context_annotations']:
                if annotation.get('domain', {}).get('name') == 'Community':
                    community_info['is_community'] = True
                    community_info['community_name'] = annotation.get('entity', {}).get('name')
                    logger.info(f"✅ Community post detected in context_annotations")
        
    except Exception as e:
        logger.error(f"❌ Error detecting community post: {str(e)}")
    
    return community_info

def extract_media(tweet_data):
    """
    Trích xuất media từ tweet (photos, GIFs, videos)
    
    Returns:
        dict: {'photos': [], 'gifs': [], 'videos': [], 'has_media': bool}
    """
    media_info = {
        'photos': [],
        'gifs': [],
        'videos': [],
        'has_media': False
    }
    
    try:
        # Kiểm tra extended_entities (chứa media đầy đủ)
        if 'extended_entities' in tweet_data and 'media' in tweet_data['extended_entities']:
            media_list = tweet_data['extended_entities']['media']
        # Fallback sang entities nếu không có extended_entities
        elif 'entities' in tweet_data and 'media' in tweet_data['entities']:
            media_list = tweet_data['entities']['media']
        else:
            return media_info
        
        for media in media_list:
            media_type = media.get('type')
            
            if media_type == 'photo':
                media_info['photos'].append(media.get('media_url_https', media.get('media_url')))
                media_info['has_media'] = True
                
            elif media_type == 'animated_gif':
                # Lấy video URL từ GIF
                video_info = media.get('video_info', {})
                variants = video_info.get('variants', [])
                if variants:
                    # Lấy variant đầu tiên (thường là mp4)
                    media_info['gifs'].append(variants[0].get('url'))
                    media_info['has_media'] = True
                    
            elif media_type == 'video':
                video_info = media.get('video_info', {})
                variants = video_info.get('variants', [])
                # Lọc và sắp xếp theo bitrate để lấy video chất lượng cao nhất
                mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
                if mp4_variants:
                    best_video = max(mp4_variants, key=lambda x: x.get('bitrate', 0))
                    media_info['videos'].append(best_video.get('url'))
                    media_info['has_media'] = True
        
        logger.info(f"📸 Media extracted - Photos: {len(media_info['photos'])}, GIFs: {len(media_info['gifs'])}, Videos: {len(media_info['videos'])}")
        
    except Exception as e:
        logger.error(f"❌ Error extracting media: {str(e)}")
    
    return media_info

def format_tweet_caption(tweet_data, author_data, community_info=None):
    """
    Format caption cho Telegram message theo format của bạn
    
    Args:
        tweet_data: Dữ liệu tweet
        author_data: Thông tin tác giả
        community_info: Thông tin community (optional)
    
    Returns:
        str: Caption đã format
    """
    try:
        # Thông tin tác giả
        author_name = author_data.get('name', 'Unknown')
        author_username = author_data.get('username', author_data.get('screen_name', 'unknown'))
        followers_count = author_data.get('followers_count', 0)
        
        # Nội dung tweet
        tweet_text = tweet_data.get('text', tweet_data.get('full_text', ''))
        
        # Tweet ID và link
        tweet_id = tweet_data.get('id_str', str(tweet_data.get('id', '')))
        tweet_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
        
        # Thời gian
        created_at = tweet_data.get('created_at', '')
        
        # Format thời gian nếu có
        formatted_time = created_at
        if created_at:
            try:
                # Parse Twitter time format: "Wed Oct 10 20:19:24 +0000 2018"
                dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_time = created_at
        
        # Tạo caption
        caption = "🔔 Tweet Mới từ KOL\n\n"
        
        # CHỈ thay đổi dòng này nếu là community post
        if community_info and community_info['is_community']:
            caption += "📝 Tweet on community\n"
            if community_info['community_name']:
                caption += f"👥 {community_info['community_name']}\n"
            else:
                caption += f"👥 Community\n"
        else:
            caption += "📝 Tweet\n"
        
        caption += f"👤 {author_name} (@{author_username})\n"
        caption += f"👥 Followers: {followers_count:,}\n\n"
        caption += f"📝 Nội dung:\n{tweet_text}\n\n"
        caption += f"🔗 <a href='{tweet_url}'>Xem tweet gốc</a>\n\n"
        
        if formatted_time:
            caption += f"⏰ {formatted_time}"
        
        return caption
        
    except Exception as e:
        logger.error(f"❌ Error formatting caption: {str(e)}")
        return "🔔 Tweet Mới từ KOL"

def send_to_telegram(tweet_data, author_data):
    """
    Gửi tweet đến Telegram với media
    """
    try:
        # Phát hiện community post
        community_info = detect_community_post(tweet_data)
        
        # Log nếu là community post
        if community_info['is_community']:
            logger.info(f"🏘️ Processing community post from: {community_info.get('community_name', 'Unknown Community')}")
        
        # Trích xuất media
        media_info = extract_media(tweet_data)
        
        # Format caption
        caption = format_tweet_caption(tweet_data, author_data, community_info)
        
        telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        
        # Gửi với media nếu có
        if media_info['has_media']:
            # Gửi photos
            if media_info['photos']:
                if len(media_info['photos']) == 1:
                    # Gửi 1 ảnh
                    response = requests.post(
                        f"{telegram_api_url}/sendPhoto",
                        data={
                            'chat_id': TELEGRAM_CHAT_ID,
                            'photo': media_info['photos'][0],
                            'caption': caption,
                            'parse_mode': 'HTML'
                        }
                    )
                else:
                    # Gửi nhiều ảnh (media group)
                    media_group = []
                    for i, photo_url in enumerate(media_info['photos'][:10]):  # Telegram limit 10 media
                        media_item = {
                            'type': 'photo',
                            'media': photo_url
                        }
                        if i == 0:
                            media_item['caption'] = caption
                            media_item['parse_mode'] = 'HTML'
                        media_group.append(media_item)
                    
                    response = requests.post(
                        f"{telegram_api_url}/sendMediaGroup",
                        json={
                            'chat_id': TELEGRAM_CHAT_ID,
                            'media': media_group
                        }
                    )
            
            # Gửi GIFs
            elif media_info['gifs']:
                response = requests.post(
                    f"{telegram_api_url}/sendAnimation",
                    data={
                        'chat_id': TELEGRAM_CHAT_ID,
                        'animation': media_info['gifs'][0],
                        'caption': caption,
                        'parse_mode': 'HTML'
                    }
                )
            
            # Gửi videos
            elif media_info['videos']:
                response = requests.post(
                    f"{telegram_api_url}/sendVideo",
                    data={
                        'chat_id': TELEGRAM_CHAT_ID,
                        'video': media_info['videos'][0],
                        'caption': caption,
                        'parse_mode': 'HTML'
                    }
                )
        else:
            # Gửi text only
            response = requests.post(
                f"{telegram_api_url}/sendMessage",
                data={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': caption,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': False
                }
            )
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully sent to Telegram (Community: {community_info['is_community']})")
            return True
        else:
            logger.error(f"❌ Failed to send to Telegram: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error sending to Telegram: {str(e)}")
        return False

def process_webhook_data(data):
    """
    Xử lý dữ liệu webhook chung
    """
    try:
        # LOG DỮ LIỆU WEBHOOK ĐỂ DEBUG
        logger.info(f"📨 Received webhook data")
        logger.info(f"🔍 Webhook keys: {list(data.keys())}")
        logger.info(f"📦 Full webhook data: {json.dumps(data, indent=2)}")
        
        # Xử lý tweet_create_events
        if 'tweet_create_events' in data:
            logger.info(f"✅ Found tweet_create_events with {len(data['tweet_create_events'])} tweets")
            for tweet in data['tweet_create_events']:
                # Lấy thông tin author
                author_data = tweet.get('user', {})
                logger.info(f"👤 Processing tweet from @{author_data.get('screen_name', 'unknown')}")
                
                # Gửi đến Telegram
                send_to_telegram(tweet, author_data)
        
        # Xử lý favorite_events (likes)
        elif 'favorite_events' in data:
            logger.info("❤️ Received favorite event")
        
        # Xử lý follow_events
        elif 'follow_events' in data:
            logger.info("👥 Received follow event")
        
        # Xử lý direct_message_events
        elif 'direct_message_events' in data:
            logger.info("💬 Received direct message event")
        
        # Xử lý các event khác
        else:
            logger.warning(f"⚠️ Unknown webhook event type. Keys: {list(data.keys())}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return False

# Route cho /webhook (endpoint mới)
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint nhận webhook từ Twitter (path: /webhook)
    """
    try:
        data = request.json
        if not data:
            logger.warning("⚠️ Received empty webhook data")
            return jsonify({'status': 'error', 'message': 'Empty data'}), 400
        
        process_webhook_data(data)
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route cho /webhook/twitter (endpoint cũ - giữ lại để tương thích)
@app.route('/webhook/twitter', methods=['POST'])
def twitter_webhook():
    """
    Endpoint nhận webhook từ Twitter (path: /webhook/twitter)
    """
    try:
        data = request.json
        if not data:
            logger.warning("⚠️ Received empty webhook data")
            return jsonify({'status': 'error', 'message': 'Empty data'}), 400
        
        process_webhook_data(data)
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# CRC Challenge cho /webhook
@app.route('/webhook', methods=['GET'])
def webhook_challenge():
    """
    Endpoint xử lý CRC challenge từ Twitter (path: /webhook)
    """
    try:
        crc_token = request.args.get('crc_token')
        if crc_token:
            import hmac
            import hashlib
            import base64
            
            consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET', 'YOUR_CONSUMER_SECRET')
            
            # Tạo response token
            sha256_hash_digest = hmac.new(
                consumer_secret.encode(),
                msg=crc_token.encode(),
                digestmod=hashlib.sha256
            ).digest()
            
            response_token = base64.b64encode(sha256_hash_digest).decode()
            
            logger.info("✅ CRC challenge successful")
            return jsonify({'response_token': f'sha256={response_token}'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No crc_token provided'}), 400
            
    except Exception as e:
        logger.error(f"❌ Error processing CRC challenge: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# CRC Challenge cho /webhook/twitter
@app.route('/webhook/twitter', methods=['GET'])
def twitter_webhook_challenge():
    """
    Endpoint xử lý CRC challenge từ Twitter (path: /webhook/twitter)
    """
    try:
        crc_token = request.args.get('crc_token')
        if crc_token:
            import hmac
            import hashlib
            import base64
            
            consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET', 'YOUR_CONSUMER_SECRET')
            
            # Tạo response token
            sha256_hash_digest = hmac.new(
                consumer_secret.encode(),
                msg=crc_token.encode(),
                digestmod=hashlib.sha256
            ).digest()
            
            response_token = base64.b64encode(sha256_hash_digest).decode()
            
            logger.info("✅ CRC challenge successful")
            return jsonify({'response_token': f'sha256={response_token}'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No crc_token provided'}), 400
            
    except Exception as e:
        logger.error(f"❌ Error processing CRC challenge: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint
    """
    return jsonify({
        'service': 'Twitter to Telegram Webhook',
        'version': '2.0',
        'endpoints': {
            'webhook': '/webhook',
            'webhook_twitter': '/webhook/twitter',
            'health': '/health'
        }
    }), 200

if __name__ == '__main__':
    # Kiểm tra biến môi trường
    if TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN chưa được cấu hình!")
    if TELEGRAM_CHAT_ID == 'YOUR_CHAT_ID':
        logger.warning("⚠️ TELEGRAM_CHAT_ID chưa được cấu hình!")
    
    logger.info("🚀 Starting Flask application...")
    app.run(host='0.0.0.0', port=5000, debug=True)
