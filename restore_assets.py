#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Restore animation and image files to original assets folder
"""

import os
import shutil
from pathlib import Path

# Define paths
base_dir = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\ljm_skt_teamproject-main\ljm_skt_teamproject-main"
assets_dir = os.path.join(base_dir, "assets")
animations_dir = os.path.join(assets_dir, "animations")
static_dir = os.path.join(assets_dir, "static")

def restore_files():
    """Move all files back to assets root directory"""
    
    moved_count = 0
    errors = []
    
    # Move files from animations/basic back to assets
    basic_dir = os.path.join(animations_dir, "basic")
    if os.path.exists(basic_dir):
        print(f"Restoring files from {basic_dir}...")
        for file in os.listdir(basic_dir):
            if file.endswith('.gif'):
                src = os.path.join(basic_dir, file)
                dst = os.path.join(assets_dir, file)
                try:
                    shutil.move(src, dst)
                    moved_count += 1
                    print(f"  [OK] Moved {file}")
                except Exception as e:
                    errors.append(f"Error moving {file}: {e}")
    
    # Move files from animations/combos back to assets
    combos_dir = os.path.join(animations_dir, "combos")
    if os.path.exists(combos_dir):
        print(f"Restoring files from {combos_dir}...")
        for file in os.listdir(combos_dir):
            if file.endswith('.gif'):
                src = os.path.join(combos_dir, file)
                dst = os.path.join(assets_dir, file)
                try:
                    shutil.move(src, dst)
                    moved_count += 1
                    print(f"  [OK] Moved {file}")
                except Exception as e:
                    errors.append(f"Error moving {file}: {e}")
    
    # Move PNG files from static back to assets
    if os.path.exists(static_dir):
        print(f"Restoring files from {static_dir}...")
        for file in os.listdir(static_dir):
            if file.endswith('.png'):
                src = os.path.join(static_dir, file)
                dst = os.path.join(assets_dir, file)
                try:
                    shutil.move(src, dst)
                    moved_count += 1
                    print(f"  [OK] Moved {file}")
                except Exception as e:
                    errors.append(f"Error moving {file}: {e}")
    
    # Remove empty directories
    try:
        if os.path.exists(basic_dir) and not os.listdir(basic_dir):
            os.rmdir(basic_dir)
            print("  [OK] Removed empty basic directory")
        
        if os.path.exists(combos_dir) and not os.listdir(combos_dir):
            os.rmdir(combos_dir)
            print("  [OK] Removed empty combos directory")
            
        if os.path.exists(static_dir) and not os.listdir(static_dir):
            os.rmdir(static_dir)
            print("  [OK] Removed empty static directory")
            
        # Try to remove animations directory if empty
        if os.path.exists(animations_dir):
            subdirs = [d for d in os.listdir(animations_dir) if os.path.isdir(os.path.join(animations_dir, d))]
            if not subdirs:
                # Keep actions and ingredients folders if they exist
                keep_dirs = ['actions', 'ingredients']
                for keep_dir in keep_dirs:
                    full_path = os.path.join(animations_dir, keep_dir)
                    if os.path.exists(full_path) and not os.listdir(full_path):
                        os.rmdir(full_path)
    except Exception as e:
        errors.append(f"Error removing directories: {e}")
    
    # Print summary
    print("\n" + "="*50)
    print(f"Restoration Complete!")
    print(f"   Files moved: {moved_count}")
    
    if errors:
        print(f"\n[WARNING] Errors encountered:")
        for error in errors:
            print(f"   - {error}")
    
    # Check for missing required files
    print("\nChecking for required files...")
    required_files = [
        "그르시.png",
        "rice.png",
        "Hi.gif",
        "Sad.gif",
        "Dance.gif",
        "Jump.gif",
        "Sunglass.gif"
    ]
    
    for file in required_files:
        file_path = os.path.join(assets_dir, file)
        if os.path.exists(file_path):
            print(f"  [OK] {file} - Found")
        else:
            # Try to find with different encoding
            found = False
            for existing_file in os.listdir(assets_dir):
                if file.lower() in existing_file.lower():
                    print(f"  [WARNING] {file} - Found as {existing_file}")
                    found = True
                    break
            if not found:
                print(f"  [ERROR] {file} - Missing!")

if __name__ == "__main__":
    print("Starting Asset Restoration...")
    print("="*50)
    restore_files()