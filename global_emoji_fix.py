import os
import codecs
import re

# Comprehensive map of emojis to Unicode escapes
EMOJI_TO_ESCAPE = {
    '🔵': '\\U0001f535',
    '🟣': '\\U0001f7e3',
    '🟠': '\\U0001f7e0',
    '🟡': '\\U0001f7e1',
    '💮': '\\U0001f4ae',
    '⚜️': '\\u269c\\ufe0f',
    '⚡': '\\u26a1',
    '🪞': '\\U0001fa9e',
    '✨': '\\u2728',
    '❌': '\\u274c',
    '✅': '\\u2705',
    '☘️': '\\u2618\\ufe0f',
    '🆔': '\\U0001f194',
    '⬅️': '\\u2b05\\ufe0f',
    '➡️': '\\u27a1\\ufe0f',
    '⛩': '\\u26e9',
    '💖': '\\U0001f496',
    '🌎': '\\U0001f30e',
    '🎖️': '\\U0001f396\\ufe0f',
    '➥': '\\u27a5',
    '⚠️': '\\u26a0\\ufe0f',
    '🎁': '\\U0001f381',
    '🏷️': '\\U0001f3f7\\ufe0f',
    '🫧': '\\U0001fae7',
    '⏳': '\\u23f3',
    '👉': '\\ud83d\\udc49',
    '🚀': '\\ud83d\\ude80',
    '💠': '\\U0001f4a0',
    '🚫': '\\U0001f6ab',
    '💡': '\\U0001f4a1',
    '🔨': '\\U0001f528',
    '💰': '\\U0001f4b0',
    '📊': '\\U0001f4ca',
    '🏆': '\\U0001f3c6',
    '🎴': '\\U0001f3b4',
    '👤': '\\U0001f464',
    '📝': '\\U0001f4dd',
    '⛩': '\\u26e9',
    '🌐': '\\U0001f310',
    '💫': '\\U0001f4ab',
    '🏅': '\\U0001f396\\ufe0f',
    '🌿': '\\U0001f33f',
    '⛩': '\\u26e9'
}

FILES_TO_FIX = [
    'bot/main.py', 
    'bot/modules/admin.py', 
    'bot/modules/capture.py', 
    'bot/modules/collection.py', 
    'bot/modules/economy.py', 
    'bot/modules/gift.py', 
    'bot/modules/search.py', 
    'bot/modules/smash.py', 
    'bot/modules/trade.py', 
    'bot/utils/formatters.py', 
    'bot/utils/spam.py'
]

for file_path in FILES_TO_FIX:
    full_path = os.path.join(os.getcwd(), file_path.replace('/', os.sep))
    if not os.path.exists(full_path):
        print(f"Skipping {file_path}, not found.")
        continue
        
    try:
        with codecs.open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        for emoji, escape in EMOJI_TO_ESCAPE.items():
            content = content.replace(emoji, escape)
            
        if content != original_content:
            with codecs.open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed emojis in {file_path}")
        else:
            print(f"No changes needed for {file_path}")
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

print("Global emoji fix completed.")
