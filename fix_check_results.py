import codecs
import re

with codecs.open("bot/modules/collection.py", "r", encoding="utf-8") as f:
    content = f.read()

# I will redefine the global_pipeline in check_cmd
old_global_results = """    # 1. Global Top 10 (Using normalized ID)
    global_pipeline = [
        {"$match": {"char_id": norm_id}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    global_results = await captures_collection.aggregate(global_pipeline).to_list(length=10)"""

new_global_results = """    # 1. Global Top 10 (From users' harems for total accuracy)
    # This finds the top 10 owners regardless of how they got the character
    global_pipeline = [
        {"$match": {"waifus": {"$in": [norm_id, char_id]}}},
        {"$unwind": "$waifus"},
        {"$match": {"waifus": {"$in": [norm_id, char_id]}}},
        {"$group": {"_id": "$id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    global_results = await users_collection.aggregate(global_pipeline).to_list(length=10)"""

content = content.replace(old_global_results, new_global_results)

with codecs.open("bot/modules/collection.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated check_cmd to fetch Top 10 from users_collection.")
