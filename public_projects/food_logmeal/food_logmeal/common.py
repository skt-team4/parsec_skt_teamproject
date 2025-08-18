import requests
import json
import os
from datetime import datetime

API_TOKEN = '4c50bb4d8b94d9000863b373212be8a7959734f6'
DEFAULT_IMAGE = 'images/sample_image.jpg'

def get_headers():
    return {'Authorization': f'Bearer {API_TOKEN}'}

def save_result(result, output_dir, file_prefix):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_dir, f'{file_prefix}_{timestamp}.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return output_file

def detect_dishes(image_path=DEFAULT_IMAGE):
    url = 'https://api.logmeal.com/v2/image/segmentation/complete'
    with open(image_path, 'rb') as f:
        resp = requests.post(url, files={'image': f}, headers=get_headers())
    return resp.json()

def get_ingredients(image_id):
    url = 'https://api.logmeal.com/v2/recipe/ingredients'
    resp = requests.post(url, json={'imageId': image_id}, headers=get_headers())
    return resp.json()

def get_nutrition(image_id):
    url = 'https://api.logmeal.com/v2/recipe/nutritionalInfo'
    resp = requests.post(url, json={'imageId': image_id}, headers=get_headers())
    return resp.json()