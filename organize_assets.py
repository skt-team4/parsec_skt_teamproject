import os
import shutil

# Base assets directory
assets_dir = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main\assets"

# Create subdirectories if they don't exist
animations_dir = os.path.join(assets_dir, "animations")
static_dir = os.path.join(assets_dir, "static")
characters_dir = os.path.join(assets_dir, "characters")
maps_dir = os.path.join(assets_dir, "maps")

os.makedirs(animations_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)
os.makedirs(characters_dir, exist_ok=True)
os.makedirs(maps_dir, exist_ok=True)

# List all files in assets directory
files = os.listdir(assets_dir)

# Move files to appropriate directories
for file in files:
    src = os.path.join(assets_dir, file)
    
    # Skip if it's a directory
    if os.path.isdir(src):
        continue
    
    # Move GIF animations
    if file.endswith('.gif'):
        dst = os.path.join(animations_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to animations/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Move static PNG files that end with _static.png
    elif file.endswith('_static.png'):
        dst = os.path.join(static_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to static/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Move character images (그르시 files)
    elif '그르시' in file:
        dst = os.path.join(characters_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to characters/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Move map files
    elif 'map' in file.lower() or file.endswith('.html'):
        dst = os.path.join(maps_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to maps/")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    # Move other image files to static
    elif file.endswith(('.png', '.jpg', '.jpeg', '.svg')) and file not in ['logo.svg', 'rice.svg', 'settings.svg']:
        dst = os.path.join(static_dir, file)
        try:
            shutil.move(src, dst)
            print(f"Moved {file} to static/")
        except Exception as e:
            print(f"Error moving {file}: {e}")

print("\n✅ Assets organization complete!")
print(f"Animations: {len(os.listdir(animations_dir))} files")
print(f"Static: {len(os.listdir(static_dir))} files")
print(f"Characters: {len(os.listdir(characters_dir))} files")
print(f"Maps: {len(os.listdir(maps_dir))} files")