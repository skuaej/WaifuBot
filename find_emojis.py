import os
import re

# Simple regex for some common emojis
emoji_regex = re.compile(r'[\u2600-\u26FF\u2700-\u27BF\U0001F000-\U0001F9FF]')

files_with_emojis = []
for root, dirs, files in os.walk('bot'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if emoji_regex.search(content):
                        files_with_emojis.append(path)
            except Exception:
                pass

print("Files with emojis:", files_with_emojis)
