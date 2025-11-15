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
            "name": "Twitter Community",
            "description": "",
            "created_at": ""
        }
    
    return False, None

def extract_author_info(tweet_data):
    """
    Trích xuất thông tin tác giả từ nhiều nguồn khác nhau
    
    Returns:
        dict: {'username': str, 'name': str, 'id': str}
    """
    author_info = {
        'username': 'unknown',
        'name': 'Unknown User',
        'id': ''
    }
    
    # Thử lấy từ field "author"
    if "author" in tweet_data and tweet_data["author"]:
        author = tweet_data["author"]
        author_info['username'] = author.get("username") or author.get("screen_name", "unknown")
        author_info['name'] = author.get("name", author_info['username'])
        author_info['id'] = author.get("id_str") or author.get("id", "")
    
    # Thử lấy từ field "user"
    elif "user" in tweet_data and tweet_data["user"]:
        user = tweet_data["user"]
        author_info['username'] = user.get("screen_name") or user.get("username", "unknown")
        author_info['name'] = user.get("name", author_info['username'])
        author_info['id'] = user.get("id_str") or user.get("id", "")
    
    # Thử lấy từ root level
    else:
        if "username" in tweet_data:
            author_info['username'] = tweet_data["username"]
        elif "screen_name" in tweet_data:
            author_info['username'] = tweet_data["screen_name"]
        
        if "name" in tweet_data:
            author_info['name'] = tweet_data["name"]
        
        if "user_id" in tweet_data:
            author_info['id'] = tweet_data["user_id"]
    
    return author_info

def extract_tweet_text(tweet_data):
    """
    Trích xuất text từ tweet với nhiều fallback options
    
    Returns:
        str: Nội dung tweet
    """
    # Thử các field khác nhau
    text = (
        tweet_data.get("text") or 
        tweet_data.get("full_text") or 
        tweet_data.get("extended_tweet", {}).get("full_text") or
        tweet_data.get("content") or
        ""
    )
    
    return text.strip()

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
    
    # Danh sách các nơi có thể chứa media
    media_sources = []
    
    # Kiểm tra extended_entities trước (ưu tiên cao nhất)
    if "extended_entities" in tweet_data and "media" in tweet_data["extended_entities"]:
        media_sources.append(tweet_data["extended_entities"]["media"])
    
    # Kiểm tra entities.media
    elif "entities" in tweet_data and "media" in tweet_data["entities"]:
        media_sources.append(tweet_data["entities"]["media"])
    
    # Kiểm tra extended_tweet
    elif "extended_tweet" in tweet_data:
        ext_tweet = tweet_data["extended_tweet"]
        if "extended_entities" in ext_tweet and "media" in ext_tweet["extended_entities"]:
            media_sources.append(ext_tweet["extended_entities"]["media"])
        elif "entities" in ext_tweet and "media" in ext_tweet["entities"]:
            media_sources.append(ext_tweet["entities"]["media"])
    
    # Kiểm tra attachments
    if "attachments" in tweet_data and "media" in tweet_data["attachments"]:
        media_sources.append(tweet_data["attachments"]["media"])
    
    # Xử lý media từ nguồn đầu tiên tìm thấy
    if media_sources:
        media_list = media_sources[0]
        media_info['has_media'] = True
        media_info['media_count'] = len(media_list)
        
        media_types = set()
        for media in media_list:
            media_type = media.get("type", "")
            media_types.add(media_type)
            
            # Lấy URL chất lượng cao nhất
            if media_type == "photo":
                url = media.get("media_url_https") or media.get("media_url") or media.get("url")
                if url:
                    media_info['media_urls'].append(url)
            
            elif media_type == "video" or media_type == "animated_gif":
                # Lấy video URL từ video_info
                video_info = media.get("video_info", {})
                variants = video_info.get("variants", [])
                # Lọc các variant có bitrate và lấy chất lượng cao nhất
                video_variants = [v for v in variants if "bitrate" in v]
                if video_variants:
                    best_variant = max(video_variants, key=lambda x: x.get("bitrate", 0))
                    url = best_variant.get("url")
                    if url:
                        media_info['media_urls'].append(url)
                elif variants:
                    # Fallback: lấy variant đầu tiên nếu không có bitrate
                    url = variants[0].get("url")
                    if url:
                        media_info['media_urls'].append(url)
        
        # Xác định loại media
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
    author = extract_author_info(tweet_data)
    username = author['username']
    name = author['name']
    
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
    text = extract_tweet_text(tweet_data)
    
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
            description = community_info["description"][:100]
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
    else:
        caption_parts.append("\n<i>(Không có nội dung text)</i>")
    
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
    tweet_id = tweet_data.get("id_str") or tweet_data.get("id") or tweet_data.get("tweet_id")
    if tweet_id:
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        caption_parts.append(f"\n🔗 <a href='{tweet_url}'>Xem tweet gốc</a>")
    
    # Thêm timestamp
    created_at = tweet_data.get("created_at") or tweet_data.get("timestamp")
    if created_at:
        try:
            # Thử parse nhiều format khác nhau
            formats = [
                "%a %b %d %H:%M:%S %z %Y",  # Twitter format
                "%Y-%m-%dT%H:%M:%S.%fZ",     # ISO format
                "%Y-%m-%d %H:%M:%S"          # Simple format
            ]
            
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(str(created_at), fmt)
                    break
                except:
                    continue
            
            if dt:
                time_str = dt.strftime("%d/%m/%Y %H:%M")
                caption_parts.append(f"🕐 {time_str}")
        except Exception as e:
            logger.warning(f"⚠️ Không thể parse timestamp: {created_at}")
    
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
        
        # Log toàn bộ data để debug
        logger.info(f"📦 Raw Data Keys: {list(data.keys()) if data else 'None'}")
        
        # Kiểm tra xem có phải là tweet event không
        if not data:
            logger.warning("⚠️ Không có dữ liệu trong request")
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Xử lý tweet data - thử nhiều cấu trúc khác nhau
        tweet_data = None
        
        # Cấu trúc 1: tweet_create_events (Twitter Account Activity API)
        if "tweet_create_events" in data and data["tweet_create_events"]:
            tweet_data = data["tweet_create_events"][0]
            logger.info("📍 Sử dụng cấu trúc: tweet_create_events")
        
        # Cấu trúc 2: data object (Twitter API v2)
        elif "data" in data:
            tweet_data = data["data"]
            logger.info("📍 Sử dụng cấu trúc: data")
        
        # Cấu trúc 3: Direct tweet object
        elif "id" in data or "id_str" in data:
            tweet_data = data
            logger.info("📍 Sử dụng cấu trúc: direct object")
        
        # Cấu trúc 4: Nested trong tweet
        elif "tweet" in data:
            tweet_data = data["tweet"]
            logger.info("📍 Sử dụng cấu trúc: tweet")
        
        else:
            logger.error(f"❌ Không nhận diện được cấu trúc data. Keys: {list(data.keys())}")
            # Log một phần data để debug (giới hạn 500 ký tự)
            import json
            data_str = json.dumps(data, indent=2)[:500]
            logger.error(f"📦 Data sample: {data_str}")
            return jsonify({"status": "error", "message": "Unknown data structure"}), 400
        
        # Log thông tin tweet
        tweet_id = tweet_data.get("id_str") or tweet_data.get("id")
        logger.info(f"🆔 Tweet ID: {tweet_id}")
        
        # Kiểm tra xem có phải là reply không
        is_reply = (
            tweet_data.get("in_reply_to_status_id") is not None or 
            tweet_data.get("in_reply_to_status_id_str") is not None or 
            tweet_data.get("in_reply_to_user_id") is not None or
            tweet_data.get("isReply", False) or
            tweet_data.get("referenced_tweets") is not None
        )
        
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
        
        # Lấy thông tin author để log
        author = extract_author_info(tweet_data)
        logger.info(f"👤 Author: {author['name']} (@{author['username']})")
        
        # Lấy text để log
        text = extract_tweet_text(tweet_data)
        logger.info(f"📝 Text: {text[:100]}..." if len(text) > 100 else f"📝 Text: {text}")
        
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
        "service": "Twitter Webhook with Community Detection v4.1",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Community post detection",
            "Regular post handling",
            "Reply detection",
            "Media support (photo, gif, video)",
            "Community info extraction",
            "Multiple data structure support",
            "Enhanced error handling"
        ]
    }), 200

@app.route('/', methods=['GET'])
def home():
    """
    Home endpoint
    """
    return jsonify({
        "message": "Twitter Webhook Service with Community Detection v4.1",
        "endpoints": {
            "/webhook": "POST - Nhận webhook từ Twitter",
            "/health": "GET - Health check",
            "/test": "POST - Test với dữ liệu mẫu",
            "/debug": "POST - Debug data structure"
        },
        "features": {
            "community_detection": "Phát hiện và xử lý Twitter Community posts",
            "media_support": "Hỗ trợ ảnh, GIF, video",
            "reply_detection": "Phát hiện reply trong cả regular và community posts",
            "formatted_output": "Format đẹp với icon và thông tin đầy đủ",
            "multi_structure": "Hỗ trợ nhiều cấu trúc data từ Twitter API"
        }
    }), 200

@app.route('/debug', methods=['POST'])
def debug():
    """
    Debug endpoint để xem cấu trúc data
    """
    try:
        data = request.get_json()
        
        import json
        
        response = {
            "received_keys": list(data.keys()) if data else [],
            "data_structure": {},
            "extracted_info": {}
        }
        
        # Phân tích cấu trúc
        if "tweet_create_events" in data:
            response["data_structure"]["type"] = "tweet_create_events"
            tweet_data = data["tweet_create_events"][0] if data["tweet_create_events"] else {}
        elif "data" in data:
            response["data_structure"]["type"] = "data"
            tweet_data = data["data"]
        elif "tweet" in data:
            response["data_structure"]["type"] = "tweet"
            tweet_data = data["tweet"]
        else:
            response["data_structure"]["type"] = "direct"
            tweet_data = data
        
        # Trích xuất thông tin
        if tweet_data:
            response["extracted_info"]["author"] = extract_author_info(tweet_data)
            response["extracted_info"]["text"] = extract_tweet_text(tweet_data)
            response["extracted_info"]["media"] = extract_media_info(tweet_data)
            is_community, community_info = is_community_post(tweet_data)
            response["extracted_info"]["is_community"] = is_community
            response["extracted_info"]["community_info"] = community_info
        
        # Log để debug
        logger.info(f"🔍 Debug Info: {json.dumps(response, indent=2)}")
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Lỗi trong debug: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test', methods=['POST'])
def test():
    """
    Test endpoint với dữ liệu mẫu
    """
    try:
        # Dữ liệu test cho community post
        test_data = request.get_json() or {
            "id_str": "1234567890",
            "text": "This is a test community post! 🚀 #crypto #trading",
            "created_at": "Mon Jan 01 12:00:00 +0000 2024",
            "user": {
                "id_str": "123456",
                "screen_name": "cryptotrader",
                "name": "Crypto Trader VN"
            },
            "community": {
                "id_str": "1234567890",
                "name": "Crypto Traders Vietnam",
                "description": "Cộng đồng trader crypto Việt Nam - Chia sẻ kiến thức và kinh nghiệm",
                "created_at": "2023-01-01"
            },
            "communityId": "1234567890",
            "in_reply_to_status_id": None,
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
        
        # Lấy author info
        author = extract_author_info(test_data)
        
        # Lấy text
        text = extract_tweet_text(test_data)
        
        # Format caption
        caption = format_tweet_caption(test_data, is_reply=False)
        
        # Gửi đến Telegram
        success = send_telegram_message(caption)
        
        return jsonify({
            "status": "success" if success else "error",
            "is_community": is_community,
            "community_info": community_info,
            "author": author,
            "text": text,
            "caption": caption,
            "sent_to_telegram": success
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Lỗi trong test: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Twitter Webhook Service with Community Detection v4.1")
    logger.info(f"📱 Telegram Chat ID: {TELEGRAM_CHAT_ID}")
    logger.info("✨ Features: Community detection, Media support, Reply handling, Enhanced data extraction")
    app.run(host='0.0.0.0', port=5000, debug=True)
