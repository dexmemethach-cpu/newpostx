# Logging rõ ràng
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("webhook-app")

# Cấu hình qua biến môi trường
TELEGRAM_API_TOKEN = os.getenv("8106631505:AAFq8iqagLhsCh8Vr_P0lpdMljGoyJmZOu8")
TELEGRAM_CHAT_ID = os.getenv("-1003174496663")

if not TELEGRAM_API_TOKEN:
    logger.warning("TELEGRAM_API_TOKEN chưa được thiết lập.")
if not TELEGRAM_CHAT_ID:
    logger.warning("TELEGRAM_CHAT_ID chưa được thiết lập.")

TELEGRAM_API_URL = (
    f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
    if TELEGRAM_API_TOKEN else None
)

def send_to_telegram(message: str):
    if not TELEGRAM_API_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Thiếu TELEGRAM_API_TOKEN hoặc TELEGRAM_CHAT_ID.")
        return {"ok": False, "error": "missing_token_or_chat_id"}

    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        resp = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        logger.info(f"[TELEGRAM] status={resp.status_code}, body={resp.text}")
        resp.raise_for_status()
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return {"ok": True, "response": resp.json()}
        return {"ok": True, "response_text": resp.text}
    except requests.exceptions.RequestException as e:
        logger.exception(f"[TELEGRAM][ERROR] {e}")
        return {"ok": False, "error": str(e)}

@app.route("/", methods=["GET"])
def home():
    return "✅ Twitter Webhook is running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    # Kiểm tra Content-Type
    ctype = request.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        return jsonify({"status": "bad_request", "error": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "bad_request", "error": "Invalid or empty JSON body"}), 400

    logger.info(f"[WEBHOOK] Received: {data}")

    tweet = data.get("tweet")
    if not isinstance(tweet, dict):
        return jsonify({"status": "bad_request", "error": "Missing 'tweet' object"}), 400

    required = ("user", "text", "id")
    missing = [k for k in required if k not in tweet]
    if missing:
        return jsonify({"status": "bad_request", "error": f"Missing fields in 'tweet': {missing}"}), 400

    user = str(tweet["user"])
    text = str(tweet["text"])
    tweet_id = str(tweet["id"])

    link = f"https://twitter.com/{user}/status/{tweet_id}"
    message = f"Tweet mới từ {user}:\n{text}\n{link}"

    tg = send_to_telegram(message)

    return jsonify({
        "status": "ok",
        "tweet": {"user": user, "text": text, "id": tweet_id, "link": link},
        "telegram": tg
    }), 200

return app
