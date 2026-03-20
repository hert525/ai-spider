"""Generate seeds.py entries from community_codes.json and append to seeds.py."""
from __future__ import annotations
import json

with open('/root/.openclaw/workspace/ai-spider/scripts/community_codes.json') as f:
    codes = json.load(f)

# Filter out entries whose names already exist in seeds.py (豆瓣电影Top250, GitHub Trending, etc.)
# Read existing names
with open('/root/.openclaw/workspace/ai-spider/src/core/seeds.py') as f:
    seeds_content = f.read()

# Build new entries
entries = []
for item in codes:
    # Check if name already exists in seeds.py
    if f'"{item["name"]}"' in seeds_content:
        print(f"⏭️ {item['name']}: already exists, skipping")
        continue
    
    # Escape the code for embedding in triple-quoted string
    code = item["code"]
    wrapped = item["wrapped_code"]
    
    entry = {
        "name": item["name"],
        "description": f"社区爬虫 - {item['name']}（来自 GitHub {item['repo']}）",
        "category": item["category"],
        "icon": item["icon"],
        "target_url": item["target_url"],
        "mode": "code_generator",
        "code": wrapped,
        "original_code": code,
        "original_format": item["original_format"],
        "source_url": f"https://github.com/{item['repo']}",
        "author": "community",
        "tags": [item["name"], item["original_format"], "community", "社区"],
        "difficulty": "medium",
    }
    entries.append(entry)
    print(f"✅ {item['name']}")

if not entries:
    print("No new entries to add")
    exit()

# Now build the Python source to append
# Insert before the closing ]
# Find the position of the last ] before CATEGORY_LABELS
insert_marker = "\n]\n\n# Category label mapping"

new_code_parts = []
for entry in entries:
    # We need to format code fields as triple-quoted strings
    code_repr = repr(entry["code"])
    original_code_repr = repr(entry["original_code"])
    tags_repr = repr(entry["tags"])
    
    part = f"""
    # ═══════════════════════════════════════
    # 社区: {entry["name"]}
    # ═══════════════════════════════════════
    {{
        "name": {repr(entry["name"])},
        "description": {repr(entry["description"])},
        "category": {repr(entry["category"])},
        "icon": {repr(entry["icon"])},
        "target_url": {repr(entry["target_url"])},
        "mode": "code_generator",
        "code": {code_repr},
        "original_code": {original_code_repr},
        "original_format": {repr(entry["original_format"])},
        "source_url": {repr(entry["source_url"])},
        "author": "community",
        "tags": {tags_repr},
        "difficulty": "medium",
    }},"""
    new_code_parts.append(part)

new_code = "".join(new_code_parts)
replacement = new_code + "\n]\n\n# Category label mapping"

seeds_content = seeds_content.replace(insert_marker, replacement)

with open('/root/.openclaw/workspace/ai-spider/src/core/seeds.py', 'w') as f:
    f.write(seeds_content)

print(f"\n写入 {len(entries)} 个社区模板到 seeds.py")
