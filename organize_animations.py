import os
import shutil
import json

# Base animations directory
animations_dir = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main\assets\animations"

# Create subdirectories
actions_dir = os.path.join(animations_dir, "actions")
ingredients_dir = os.path.join(animations_dir, "ingredients")
combos_dir = os.path.join(animations_dir, "combos")
basic_dir = os.path.join(animations_dir, "basic")

os.makedirs(actions_dir, exist_ok=True)
os.makedirs(ingredients_dir, exist_ok=True)
os.makedirs(combos_dir, exist_ok=True)
os.makedirs(basic_dir, exist_ok=True)

# Define categories
actions = ["Hi", "Sad", "Dance", "Jump", "Think", "Being", "Hello_fri", "Gunchim", "Sunglass"]
ingredients = ["계란말이", "김", "명란", "베이컨", "연어", "후라이", "매우편중", "편중식사"]

# Animation catalog for the shop
animation_catalog = {
    "actions": {
        "Hi": {"name": "인사", "price": 0, "description": "기본 인사 동작", "unlocked": True},
        "Sad": {"name": "슬픔", "price": 50, "description": "슬픈 표정", "unlocked": False},
        "Dance": {"name": "춤", "price": 100, "description": "신나는 춤 동작", "unlocked": False},
        "Jump": {"name": "점프", "price": 80, "description": "활기찬 점프", "unlocked": False},
        "Think": {"name": "생각", "price": 60, "description": "고민하는 모습", "unlocked": False},
        "Being": {"name": "존재", "price": 120, "description": "특별한 상태", "unlocked": False},
        "Hello_fri": {"name": "친구인사", "price": 150, "description": "친근한 인사", "unlocked": False},
        "Gunchim": {"name": "군침", "price": 200, "description": "배고픈 모습", "unlocked": False},
        "Sunglass": {"name": "선글라스", "price": 180, "description": "쿨한 모습", "unlocked": False}
    },
    "ingredients": {
        "계란말이": {"name": "계란말이", "price": 30, "description": "부드러운 계란말이", "unlocked": False},
        "김": {"name": "김", "price": 20, "description": "바삭한 김", "unlocked": False},
        "명란": {"name": "명란", "price": 80, "description": "짭짤한 명란", "unlocked": False},
        "베이컨": {"name": "베이컨", "price": 70, "description": "고소한 베이컨", "unlocked": False},
        "연어": {"name": "연어", "price": 100, "description": "신선한 연어", "unlocked": False},
        "후라이": {"name": "후라이", "price": 50, "description": "바삭한 후라이", "unlocked": False},
        "매우편중": {"name": "매우편중", "price": 150, "description": "극도로 편중된 식사", "unlocked": False},
        "편중식사": {"name": "편중식사", "price": 120, "description": "편중된 식사", "unlocked": False}
    },
    "combos": {},
    "specials": {
        "basic_pack": {
            "name": "기본 팩",
            "items": ["Hi", "normal"],
            "price": 0,
            "description": "기본 애니메이션 세트",
            "unlocked": True
        },
        "food_lover_pack": {
            "name": "음식 애호가 팩",
            "items": ["Dance_김", "Dance_계란말이", "Jump_베이컨"],
            "price": 200,
            "description": "음식과 함께 춤추기",
            "discount": 20
        },
        "premium_pack": {
            "name": "프리미엄 팩",
            "items": ["Sunglass", "연어", "명란"],
            "price": 300,
            "description": "고급 애니메이션 세트",
            "discount": 30
        }
    }
}

# Process files
files = os.listdir(animations_dir)
for file in files:
    if not file.endswith('.gif'):
        continue
        
    src = os.path.join(animations_dir, file)
    
    # Skip if it's a directory
    if os.path.isdir(src):
        continue
    
    # Check if it's a basic animation
    if file in ['Hi.gif', 'Sad.gif', 'Dance.gif', 'Jump.gif', 'Think.gif', 'Sunglass.gif', 'Gunchim.gif']:
        dst = os.path.join(basic_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to basic/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Check if it's a combo (action_ingredient)
    elif '_' in file:
        # Check if it's a special basic (like Hi_normal.gif)
        if 'normal' in file or 'fri' in file:
            dst = os.path.join(basic_dir, file)
        else:
            # It's a combo animation
            dst = os.path.join(combos_dir, file)
            # Extract action and ingredient
            parts = file.replace('.gif', '').split('_')
            if len(parts) >= 2:
                action = parts[0]
                ingredient = '_'.join(parts[1:])
                combo_key = f"{action}_{ingredient}"
                animation_catalog["combos"][combo_key] = {
                    "action": action,
                    "ingredient": ingredient,
                    "file": file,
                    "unlocked": False
                }
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to {os.path.dirname(dst)}/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Single word animations
    else:
        dst = os.path.join(basic_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to basic/")
        except Exception as e:
            print(f"Error moving {file}: {e}")

# Save animation catalog
catalog_path = os.path.join(animations_dir, "animation_catalog.json")
with open(catalog_path, 'w', encoding='utf-8') as f:
    json.dump(animation_catalog, f, ensure_ascii=False, indent=2)

print(f"\n✅ Animation organization complete!")
print(f"Catalog saved to: {catalog_path}")
print(f"Basic animations: {len(os.listdir(basic_dir))} files")
print(f"Combo animations: {len(os.listdir(combos_dir))} files")