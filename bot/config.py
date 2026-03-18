import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Owner ID and Upload Channel ID (convert to int if possible)
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0

try:
    UPLOAD_CHANNEL_ID = int(os.getenv("UPLOAD_CHANNEL_ID", "0"))
except ValueError:
    UPLOAD_CHANNEL_ID = 0

try:
    SUPPORT_CHAT_ID = int(os.getenv("SUPPORT_CHAT_ID", "0"))
except ValueError:
    SUPPORT_CHAT_ID = 0

SUPPORT_CHAT_LINK = os.getenv("SUPPORT_CHAT_LINK", "Https://t.me/+xIDVAEvE5m0yMTNl")

try:
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1003750183482"))
except ValueError:
    LOG_CHAT_ID = -1003750183482

# How long a character stays before despawning (in seconds)
try:
    SPAWN_DURATION = int(os.getenv("SPAWN_DURATION", "3600"))
except ValueError:
    SPAWN_DURATION = 3600
