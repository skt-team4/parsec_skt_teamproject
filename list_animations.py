import os
import json

assets_dir = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main\assets"

# Categorize GIF files
basic_actions = []
combo_animations = {}
all_gifs = []

for file in os.listdir(assets_dir):
    if file.endswith('.gif'):
        all_gifs.append(file)
        
        # Parse filename
        if '_' in file:
            # This is a combo animation
            parts = file.replace('.gif', '').split('_')
            if len(parts) == 2:
                action, ingredient = parts
                if action not in combo_animations:
                    combo_animations[action] = []
                combo_animations[action].append(ingredient)
        else:
            # This is a basic action
            action_name = file.replace('.gif', '')
            if not action_name.endswith('_normal') and not action_name.endswith('_fri'):
                basic_actions.append(action_name)

# Remove duplicates
basic_actions = list(set(basic_actions))
basic_actions.sort()

print("="*60)
print("AVAILABLE ANIMATIONS ANALYSIS")
print("="*60)

print("\nBasic Actions:")
for action in basic_actions:
    print(f"  - {action}")

print(f"\nCombo Animations by Action:")
for action, ingredients in sorted(combo_animations.items()):
    print(f"\n  {action}:")
    for ingredient in sorted(set(ingredients)):
        print(f"    + {ingredient}")

print("\nAvailable Ingredients:")
all_ingredients = set()
for ingredients in combo_animations.values():
    all_ingredients.update(ingredients)
for ingredient in sorted(all_ingredients):
    print(f"  - {ingredient}")

print(f"\nStatistics:")
print(f"  Total GIF files: {len(all_gifs)}")
print(f"  Basic actions: {len(basic_actions)}")
print(f"  Unique ingredients: {len(all_ingredients)}")
print(f"  Total combos: {sum(len(v) for v in combo_animations.values())}")

# Save to JSON for reference
output = {
    "basic_actions": basic_actions,
    "ingredients": list(all_ingredients),
    "combos": {k: list(set(v)) for k, v in combo_animations.items()},
    "all_files": all_gifs
}

with open('animation_inventory.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
    
print("\nSaved to animation_inventory.json")