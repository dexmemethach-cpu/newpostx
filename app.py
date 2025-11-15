from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

app = Flask(__name__)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cấu hình Telegram Bot
TELEGRAM_BOT_TOKEN = "8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8"
TELEGRAM_CHAT_ID = "-1003174496663"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def is_community_post(tweet_data):
    """
    Kiểm tra xem tweet có phải là community post không
    
    Args:
        tweet_data: Dictionary chứa dữ liệu tweet
        
    Returns:
        tuple: (is_community: bool, community_info: dict hoặc None)
    """
    # Kiểm tra field "community"
    if "community" in tweet_data and tweet_data["community"]:
        community = tweet_data["community"]
        logger.info(f"✅ Phát hiện Community Post - Community: {community.get('name', 'Unknown')}")
        return True, {
            "id": community.get("id_str") or community.get("id"),
            "name": community.get("name", "Unknown Community"),
            "description": community.get("description", ""),
            "created_at": community.get("created_at", "")
        }
    
    # Kiểm tra field "communityId"
    if "communityId" in tweet_data and tweet_data["communityId"]:
        logger.info(f"✅ Phát hiện Community Post - Community ID: {tweet_data['communityId']}")
        return True, {
            "id": tweet_data["communityId"],
            "name": "Twitter Community",  # Tên mặc định nếu không có thông tin chi tiết
            "description": "",
            "created_at": ""
        }
    
    return False, None

def extract_media_info(tweet_data):
    """
    Trích xuất thông tin media từ tweet
    
    Returns:
        dict: {
            'has_media': bool,
            'media_type': str ('photo', 'gif', 'video', 'mixed'),
            'media_count': int,
            'media_urls': list
        }
    """
    media_info = {
        'has_media': False,
        'media_type': None,
        'media_count': 0,
        'media_urls': []
    }
    
    # Kiểm tra trong entities.media
    if "entities" in tweet_data and "media" in tweet_data["entities"]:
        media_list = tweet_data["entities"]["media"]
        media_info['has_media'] = True
        media_info['media_count'] = len(media_list)
        
        media_types = set()
        for media in media_list:
            media_type = media.get("type", "")
            media_types.add(media_type)
            
            # Lấy URL chất lượng cao nhất
            if media_type == "photo":
                media_info['media_urls'].append(media.get("media_url_https") or media.get("media_url"))
            elif media_type == "video" or media_type == "animated_gif":
                # Lấy video URL từ video_info
                video_info = media.get("video_info", {})
                variants = video_info.get("variants", [])
                # Lọc các variant có bitrate và lấy chất lượng cao nhất
                video_variants = [v for v in variants if "bitrate" in v]
                if video_variants:
                    best_variant = max(video_variants, key=lambda x: x.get("bitrate", 0))
                    media_info['media_urls'].append(best_variant.get("url"))
        
        # Xác định loại media
        if len(media_types) > 1:
            media_info['media_type'] = "mixed"
        elif "animated_gif" in media_types:
            media_info['media_type'] = "gif"
        elif "video" in media_types:
            media_info['media_type'] = "video"
        elif "photo" in media_types:
            media_info['media_type'] = "photo"
    
    # Kiểm tra trong extended_entities (cho nhiều ảnh)
    if "extended_entities" in tweet_data and "media" in tweet_data["extended_entities"]:
        media_list = tweet_data["extended_entities"]["media"]
        media_info['has_media'] = True
        media_info['media_count'] = len(media_list)
        media_info['media_urls'] = []
        
        media_types = set()
        for media in media_list:
            media_type = media.get("type", "")
            media_types.add(media_type)
            
            if media_type == "photo":
                media_info['media_urls'].append(media.get("media_url_https") or media.get("media_url"))
            elif media_type == "video" or media_type == "animated_gif":
                video_info = media.get("video_info", {})
                variants = video_info.get("variants", [])
                video_variants = [v for v in variants if "bitrate" in v]
                if video_variants:
                    best_variant = max(video_variants, key=lambda x: x.get("bitrate", 0))
                    media_info['media_urls'].append(best_variant.get("url"))
        
        if len(media_types) > 1:
            media_info['media_type'] = "mixed"
        elif "animated_gif" in media_types:
            media_info['media_type'] = "gif"
        elif "video" in media_types:
            media_info['media_type'] = "video"
        elif "photo" in media_types:
            media_info['media_type'] = "photo"
    
    return media_info

def format_tweet_caption(tweet_data, is_reply=False):
    """
    Format caption cho tweet với hỗ trợ community posts
    
    Args:
        tweet_data: Dictionary chứa dữ liệu tweet
        is_reply: Boolean cho biết đây có phải là reply không
        
    Returns:
        str: Caption đã được format
    """
    # Kiểm tra xem có phải community post không
    is_community, community_info = is_community_post(tweet_data)
    
    # Lấy thông tin tác giả
    author = tweet_data.get("author", {})
    username = author.get("username", "unknown")
    name = author.get("name", username)
    
    # Xác định header dựa trên loại post
    if is_community:
        if is_reply:
            header = "💬 Reply trong Community"
        else:
            header = "👥 Post trong Community"
    else:
        if is_reply:
            header = f"💬 Reply từ @{username}"
        else:
            header = "🔔 Tweet Mới từ KOL"
    
    # Lấy nội dung tweet
    text = tweet_data.get("text", "")
    
    # Lấy thông tin media
    media_info = extract_media_info(tweet_data)
    
    # Tạo caption
    caption_parts = [f"<b>{header}</b>", ""]
    
    # Thêm thông tin community nếu có
    if is_community and community_info:
        community_name = community_info.get("name", "Unknown Community")
        community_id = community_info.get("id", "")
        
        caption_parts.append(f"👥 <b>Community:</b> {community_name}")
        
        # Thêm link đến community nếu có ID
        if community_id:
            community_url = f"https://twitter.com/i/communities/{community_id}"
            caption_parts.append(f"🔗 <a href='{community_url}'>Xem Community</a>")
        
        # Thêm description nếu có
        if community_info.get("description"):
            description = community_info["description"][:100]  # Giới hạn độ dài
            caption_parts.append(f"📝 {description}")
        
        caption_parts.append("")
    
    # Thêm thông tin tác giả
    caption_parts.append(f"👤 <b>{name}</b> (@{username})")
    
    # Thêm nội dung tweet
    if text:
        # Giới hạn độ dài text nếu quá dài
        if len(text) > 500:
            text = text[:497] + "..."
        caption_parts.append(f"\n{text}")
    
    # Thêm thông tin media
    if media_info['has_media']:
        media_type = media_info['media_type']
        media_count = media_info['media_count']
        
        if media_type == "photo":
            if media_count > 1:
                caption_parts.append(f"\n📸 {media_count} ảnh")
            else:
                caption_parts.append("\n📸 Có ảnh đính kèm")
        elif media_type == "gif":
            caption_parts.append("\n🎞️ GIF")
        elif media_type == "video":
            caption_parts.append("\n🎥 Video")
        elif media_type == "mixed":
            caption_parts.append(f"\n📎 {media_count} media files")
    
    # Thêm link đến tweet
    tweet_id = tweet_data.get("id") or tweet_data.get("id_str")
    if tweet_id:
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        caption_parts.append(f"\n🔗 <a href='{tweet_url}'>Xem tweet gốc</a>")
    
    # Thêm timestamp
    created_at = tweet_data.get("created_at", "")
    if created_at:
        try:
            # Parse timestamp (format có thể khác nhau)
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            time_str = dt.strftime("%d/%m/%Y %H:%M")
            caption_parts.append(f"🕐 {time_str}")
        except:
            pass
    
    return "\n".join(caption_parts)

def send_telegram_message(text):
    """
    Gửi message đến Telegram
    
    Args:
        text: Nội dung message
        
    Returns:
        bool: True nếu gửi thành công
    """
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Đã gửi message đến Telegram thành công")
            return True
        else:
            logger.error(f"❌ Lỗi khi gửi message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception khi gửi message: {str(e)}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint nhận webhook từ Twitter
    """
    try:
        # Lấy dữ liệu từ request
        data = request.get_json()
        
        logger.info("=" * 50)
        logger.info("📨 Nhận được webhook từ Twitter")
        logger.info(f"📦 Data: {data}")
        
        # Kiểm tra xem có phải là tweet event không
        if not data:
            logger.warning("⚠️ Không có dữ liệu trong request")
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Xử lý tweet data
        tweet_data = data.get("tweet_create_events", [{}])[0] if "tweet_create_events" in data else data
        
        # Kiểm tra xem có phải là reply không
        is_reply = tweet_data.get("in_reply_to_status_id") is not None or \
                   tweet_data.get("in_reply_to_status_id_str") is not None or \
                   tweet_data.get("isReply", False)
        
        # Kiểm tra community post
        is_community, community_info = is_community_post(tweet_data)
        
        # Log thông tin
        if is_community:
            logger.info(f"👥 COMMUNITY POST phát hiện!")
            if community_info:
                logger.info(f"   - Community: {community_info.get('name')}")
                logger.info(f"   - ID: {community_info.get('id')}")
        
        if is_reply:
            logger.info("💬 Đây là một reply")
        
        # Format caption
        caption = format_tweet_caption(tweet_data, is_reply=is_reply)
        
        # Gửi đến Telegram
        success = send_telegram_message(caption)
        
        if success:
            logger.info("✅ Xử lý webhook thành công")
            return jsonify({"status": "success"}), 200
        else:
            logger.error("❌ Không thể gửi message đến Telegram")
            return jsonify({"status": "error", "message": "Failed to send to Telegram"}), 500
            
    except Exception as e:
        logger.error(f"❌ Lỗi khi xử lý webhook: {str(e)}")
        logger.exception(e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "healthy",
        "service": "Twitter Webhook with Community Detection v4",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Community post detection",
            "Regular post handling",
            "Reply detection",
            "Media support (photo, gif, video)",
            "Community info extraction"
        ]
    }), 200

@app.route('/', methods=['GET'])
def home():
    """
    Home endpoint
    """
    return jsonify({
        "message": "Twitter Webhook Service with Community Detection v4",
        "endpoints": {
            "/webhook": "POST - Nhận webhook từ Twitter",
            "/health": "GET - Health check",
            "/test": "POST - Test với dữ liệu mẫu"
        },
        "features": {
            "community_detection": "Phát hiện và xử lý Twitter Community posts",
            "media_support": "Hỗ trợ ảnh, GIF, video",
            "reply_detection": "Phát hiện reply trong cả regular và community posts",
            "formatted_output": "Format đẹp với icon và thông tin đầy đủ"
        }
    }), 200

@app.route('/test', methods=['POST'])
def test():
    """
    Test endpoint với dữ liệu mẫu
    """
    try:
        # Dữ liệu test cho community post
        test_data = request.get_json() or {
            "id": "1234567890",
            "id_str": "1234567890",
            "text": "This is a test community post! 🚀",
            "created_at": "Mon Jan 01 12:00:00 +0000 2024",
            "author": {
                "id": "123456",
                "username": "testuser",
                "name": "Test User"
            },
            "community": {
                "id_str": "1234567890",
                "name": "Crypto Traders Vietnam",
                "description": "Cộng đồng trader crypto Việt Nam",
                "created_at": "2023-01-01"
            },
            "communityId": "1234567890",
            "isReply": False,
            "entities": {
                "media": [
                    {
                        "type": "photo",
                        "media_url_https": "https://pbs.twimg.com/media/example.jpg"
                    }
                ]
            }
        }
        
        logger.info("🧪 Test mode - Xử lý dữ liệu mẫu")
        
        # Kiểm tra community
        is_community, community_info = is_community_post(test_data)
        
        # Format caption
        caption = format_tweet_caption(test_data, is_reply=False)
        
        # Gửi đến Telegram
        success = send_telegram_message(caption)
        
        return jsonify({
            "status": "success" if success else "error",
            "is_community": is_community,
            "community_info": community_info,
            "caption": caption,
            "sent_to_telegram": success
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Lỗi trong test: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Twitter Webhook Service with Community Detection v4")
    logger.info(f"📱 Telegram Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info("✨ Features: Community detection, Media support, Reply handling")
    app.run(host='0.0.0.0', port=5000, debug=True)
