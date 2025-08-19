#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix all asset paths by copying character images to assets root
"""

import os
import shutil
from pathlib import Path

base_dir = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main"
assets_dir = os.path.join(base_dir, "assets")
characters_dir = os.path.join(assets_dir, "characters")

def fix_character_images():
    """Copy all character images to assets root"""
    
    if not os.path.exists(characters_dir):
        print(f"Characters directory not found: {characters_dir}")
        return
    
    copied_files = []
    errors = []
    
    # List all files in characters folder
    print("Files in characters folder:")
    for file in os.listdir(characters_dir):
        print(f"  - {file}")
        
        if file.endswith('.png'):
            src = os.path.join(characters_dir, file)
            dst = os.path.join(assets_dir, file)
            
            try:
                # Copy instead of move to keep originals
                shutil.copy2(src, dst)
                copied_files.append(file)
                print(f"  [OK] Copied {file} to assets root")
            except Exception as e:
                errors.append(f"Error copying {file}: {e}")
    
    print("\n" + "="*50)
    print(f"Copied {len(copied_files)} files to assets root")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")
    
    # Check what's now in assets folder
    print("\nPNG files now in assets folder:")
    for file in os.listdir(assets_dir):
        if file.endswith('.png'):
            print(f"  - {file}")

if __name__ == "__main__":
    print("Fixing character image paths...")
    print("="*50)
    fix_character_images()