from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import MONGO_URI

# Initialize the MongoDB client
client = AsyncIOMotorClient(MONGO_URI)

# Select the database (you can change the name as needed)
db = client['waifu_bot']

# Define collections
users_collection = db['users']
characters_collection = db['characters']
groups_collection = db['groups']
captures_collection = db['captures']
sudos_collection = db['sudos']
settings_collection = db['settings']
blocks_collection = db['blocks']

async def init_db():
    """
    Initialize indexes or any necessary DB setup.
    """
    await characters_collection.create_index("name", unique=False)
    await users_collection.create_index("id", unique=True)
    await groups_collection.create_index("id", unique=True)
    await captures_collection.create_index([("user_id", 1), ("chat_id", 1)])
    await captures_collection.create_index("char_id")
    print("Database initialized successfully.")
