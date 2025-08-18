from flask import Flask, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# LogMeal 영양 데이터 파일 경로
NUTRITION_DATA_PATH = r"C:\lsj\skt_team\lsj_skt_teamproject_2\public_projects\food_logmeal\food_logmeal\result\nut\nutrition_result_20250814_175152.json"

# 한국 음식별 영양 정보 매핑 (LogMeal 데이터 기반 + 추가 데이터)
KOREAN_FOOD_NUTRITION = {
    '떡볶이': {
        'calories': 303,
        'carbs': 45.2,
        'protein': 8.5,
        'fat': 10.3,
        'fiber': 2.1,
        'sodium': 980,
        'sugar': 12.5,
        'saturated_fat': 3.2,
        'cholesterol': 15,
        'vitamin_c': 5,
        'calcium': 45,
        'iron': 1.8
    },
    '김치': {
        'calories': 18,
        'carbs': 3.6,
        'protein': 1.1,
        'fat': 0.5,
        'fiber': 1.6,
        'sodium': 498,
        'sugar': 1.1,
        'saturated_fat': 0.1,
        'cholesterol': 0,
        'vitamin_c': 14,
        'calcium': 33,
        'iron': 0.5
    },
    '불고기': {
        'calories': 256,
        'carbs': 15.3,
        'protein': 25.4,
        'fat': 10.2,
        'fiber': 0.8,
        'sodium': 760,
        'sugar': 8.2,
        'saturated_fat': 3.8,
        'cholesterol': 68,
        'vitamin_c': 2,
        'calcium': 15,
        'iron': 2.8
    },
    '비빔밥': {
        'calories': 634,
        'carbs': 78.5,
        'protein': 21.3,
        'fat': 24.2,
        'fiber': 5.8,
        'sodium': 1120,
        'sugar': 6.3,
        'saturated_fat': 5.2,
        'cholesterol': 186,
        'vitamin_c': 15,
        'calcium': 68,
        'iron': 3.2
    },
    '삼겹살': {
        'calories': 518,
        'carbs': 0.8,
        'protein': 17.3,
        'fat': 49.3,
        'fiber': 0,
        'sodium': 58,
        'sugar': 0,
        'saturated_fat': 17.9,
        'cholesterol': 72,
        'vitamin_c': 0,
        'calcium': 8,
        'iron': 0.9
    },
    '김밥': {
        'calories': 480,
        'carbs': 65.2,
        'protein': 12.8,
        'fat': 18.5,
        'fiber': 2.3,
        'sodium': 890,
        'sugar': 3.2,
        'saturated_fat': 3.5,
        'cholesterol': 125,
        'vitamin_c': 8,
        'calcium': 45,
        'iron': 2.1
    },
    '된장찌개': {
        'calories': 128,
        'carbs': 12.3,
        'protein': 9.8,
        'fat': 4.5,
        'fiber': 2.1,
        'sodium': 1250,
        'sugar': 2.8,
        'saturated_fat': 0.8,
        'cholesterol': 8,
        'vitamin_c': 6,
        'calcium': 98,
        'iron': 2.3
    },
    '김치찌개': {
        'calories': 96,
        'carbs': 8.5,
        'protein': 7.2,
        'fat': 3.8,
        'fiber': 2.5,
        'sodium': 980,
        'sugar': 2.1,
        'saturated_fat': 1.2,
        'cholesterol': 15,
        'vitamin_c': 12,
        'calcium': 56,
        'iron': 1.5
    },
    '치킨': {
        'calories': 435,
        'carbs': 15.8,
        'protein': 31.2,
        'fat': 28.5,
        'fiber': 0.5,
        'sodium': 890,
        'sugar': 1.2,
        'saturated_fat': 7.8,
        'cholesterol': 125,
        'vitamin_c': 0,
        'calcium': 25,
        'iron': 1.8
    },
    '라면': {
        'calories': 385,
        'carbs': 55.2,
        'protein': 8.5,
        'fat': 14.8,
        'fiber': 1.8,
        'sodium': 1780,
        'sugar': 2.5,
        'saturated_fat': 6.8,
        'cholesterol': 0,
        'vitamin_c': 0,
        'calcium': 18,
        'iron': 2.5
    },
    '파스타': {
        'calories': 309,
        'carbs': 32.8,
        'protein': 10.9,
        'fat': 14.9,
        'fiber': 1.9,
        'sodium': 814,
        'sugar': 0.6,
        'saturated_fat': 8.8,
        'cholesterol': 39,
        'vitamin_c': 0,
        'calcium': 163,
        'iron': 1.4
    },
    '냉면': {
        'calories': 542,
        'carbs': 86.3,
        'protein': 14.2,
        'fat': 15.8,
        'fiber': 3.2,
        'sodium': 1520,
        'sugar': 8.5,
        'saturated_fat': 2.8,
        'cholesterol': 186,
        'vitamin_c': 5,
        'calcium': 42,
        'iron': 2.5
    },
    '물냉면': {
        'calories': 480,
        'carbs': 82.5,
        'protein': 12.8,
        'fat': 10.2,
        'fiber': 2.8,
        'sodium': 1450,
        'sugar': 7.2,
        'saturated_fat': 2.1,
        'cholesterol': 125,
        'vitamin_c': 4,
        'calcium': 38,
        'iron': 2.2
    },
    '비빔냉면': {
        'calories': 605,
        'carbs': 89.5,
        'protein': 15.8,
        'fat': 20.5,
        'fiber': 3.8,
        'sodium': 1620,
        'sugar': 12.5,
        'saturated_fat': 3.8,
        'cholesterol': 245,
        'vitamin_c': 8,
        'calcium': 48,
        'iron': 2.8
    },
    '갈비': {
        'calories': 465,
        'carbs': 12.5,
        'protein': 28.5,
        'fat': 35.2,
        'fiber': 0.8,
        'sodium': 890,
        'sugar': 8.5,
        'saturated_fat': 12.5,
        'cholesterol': 95,
        'vitamin_c': 2,
        'calcium': 18,
        'iron': 3.2
    },
    '삼계탕': {
        'calories': 918,
        'carbs': 45.2,
        'protein': 68.5,
        'fat': 48.5,
        'fiber': 1.2,
        'sodium': 1250,
        'sugar': 2.5,
        'saturated_fat': 12.8,
        'cholesterol': 245,
        'vitamin_c': 5,
        'calcium': 48,
        'iron': 3.8
    },
    '파전': {
        'calories': 491,
        'carbs': 45.8,
        'protein': 12.5,
        'fat': 28.5,
        'fiber': 2.5,
        'sodium': 780,
        'sugar': 3.2,
        'saturated_fat': 4.5,
        'cholesterol': 125,
        'vitamin_c': 8,
        'calcium': 65,
        'iron': 2.1
    },
    '순대': {
        'calories': 248,
        'carbs': 28.5,
        'protein': 10.8,
        'fat': 9.5,
        'fiber': 1.5,
        'sodium': 680,
        'sugar': 2.8,
        'saturated_fat': 3.2,
        'cholesterol': 85,
        'vitamin_c': 2,
        'calcium': 25,
        'iron': 4.5
    },
    '떡국': {
        'calories': 465,
        'carbs': 68.5,
        'protein': 15.2,
        'fat': 14.8,
        'fiber': 1.8,
        'sodium': 1120,
        'sugar': 3.5,
        'saturated_fat': 5.2,
        'cholesterol': 125,
        'vitamin_c': 3,
        'calcium': 32,
        'iron': 1.8
    },
    '칼국수': {
        'calories': 366,
        'carbs': 58.5,
        'protein': 12.8,
        'fat': 8.5,
        'fiber': 2.2,
        'sodium': 980,
        'sugar': 2.8,
        'saturated_fat': 2.5,
        'cholesterol': 65,
        'vitamin_c': 2,
        'calcium': 28,
        'iron': 2.2
    },
    '만두': {
        'calories': 175,
        'carbs': 22.5,
        'protein': 7.8,
        'fat': 5.8,
        'fiber': 1.2,
        'sodium': 420,
        'sugar': 1.8,
        'saturated_fat': 1.8,
        'cholesterol': 25,
        'vitamin_c': 3,
        'calcium': 22,
        'iron': 1.5
    },
    '계란찜': {
        'calories': 146,
        'carbs': 3.2,
        'protein': 12.5,
        'fat': 9.8,
        'fiber': 0,
        'sodium': 380,
        'sugar': 1.2,
        'saturated_fat': 3.2,
        'cholesterol': 372,
        'vitamin_c': 0,
        'calcium': 56,
        'iron': 1.8
    },
    '초밥': {
        'calories': 349,
        'carbs': 48.5,
        'protein': 18.5,
        'fat': 8.2,
        'fiber': 0.8,
        'sodium': 580,
        'sugar': 4.5,
        'saturated_fat': 1.8,
        'cholesterol': 45,
        'vitamin_c': 2,
        'calcium': 18,
        'iron': 1.2
    },
    '스테이크': {
        'calories': 271,
        'carbs': 0,
        'protein': 26.5,
        'fat': 18.5,
        'fiber': 0,
        'sodium': 58,
        'sugar': 0,
        'saturated_fat': 7.2,
        'cholesterol': 82,
        'vitamin_c': 0,
        'calcium': 12,
        'iron': 2.8
    },
    '샐러드': {
        'calories': 33,
        'carbs': 6.5,
        'protein': 1.8,
        'fat': 0.5,
        'fiber': 2.5,
        'sodium': 28,
        'sugar': 3.2,
        'saturated_fat': 0.1,
        'cholesterol': 0,
        'vitamin_c': 15,
        'calcium': 35,
        'iron': 1.2
    },
    '샌드위치': {
        'calories': 252,
        'carbs': 28.5,
        'protein': 12.5,
        'fat': 9.8,
        'fiber': 2.2,
        'sodium': 520,
        'sugar': 3.5,
        'saturated_fat': 3.2,
        'cholesterol': 35,
        'vitamin_c': 5,
        'calcium': 85,
        'iron': 2.5
    },
    '케이크': {
        'calories': 257,
        'carbs': 35.8,
        'protein': 3.2,
        'fat': 11.5,
        'fiber': 0.5,
        'sodium': 220,
        'sugar': 24.5,
        'saturated_fat': 6.8,
        'cholesterol': 55,
        'vitamin_c': 0,
        'calcium': 45,
        'iron': 0.8
    },
    '아이스크림': {
        'calories': 207,
        'carbs': 24.5,
        'protein': 3.5,
        'fat': 11.2,
        'fiber': 0,
        'sodium': 80,
        'sugar': 21.5,
        'saturated_fat': 6.8,
        'cholesterol': 44,
        'vitamin_c': 0.6,
        'calcium': 128,
        'iron': 0.1
    }
}

def get_nutrition_score(nutrition_data):
    """영양 점수 계산 (A-E 등급)"""
    score = 100
    
    # 나트륨이 높으면 감점
    if nutrition_data.get('sodium', 0) > 1000:
        score -= 20
    elif nutrition_data.get('sodium', 0) > 600:
        score -= 10
    
    # 포화지방이 높으면 감점
    if nutrition_data.get('saturated_fat', 0) > 10:
        score -= 15
    elif nutrition_data.get('saturated_fat', 0) > 5:
        score -= 8
    
    # 당류가 높으면 감점
    if nutrition_data.get('sugar', 0) > 15:
        score -= 10
    elif nutrition_data.get('sugar', 0) > 10:
        score -= 5
    
    # 섬유질이 있으면 가점
    if nutrition_data.get('fiber', 0) > 3:
        score += 10
    elif nutrition_data.get('fiber', 0) > 1:
        score += 5
    
    # 단백질이 높으면 가점
    if nutrition_data.get('protein', 0) > 20:
        score += 10
    elif nutrition_data.get('protein', 0) > 10:
        score += 5
    
    # 점수를 등급으로 변환
    if score >= 80:
        return 'A', score
    elif score >= 65:
        return 'B', score
    elif score >= 50:
        return 'C', score
    elif score >= 35:
        return 'D', score
    else:
        return 'E', score

@app.route('/nutrition/<food_name>')
def get_nutrition(food_name):
    """음식명으로 영양 정보 조회"""
    
    # 기본 영양 정보 (LogMeal 데이터 형식)
    default_nutrition = KOREAN_FOOD_NUTRITION.get(food_name, {
        'calories': 250,
        'carbs': 30,
        'protein': 15,
        'fat': 10,
        'fiber': 2,
        'sodium': 500,
        'sugar': 5,
        'saturated_fat': 3,
        'cholesterol': 30,
        'vitamin_c': 5,
        'calcium': 50,
        'iron': 2
    })
    
    # 영양 점수 계산
    nutri_score_category, nutri_score = get_nutrition_score(default_nutrition)
    
    # 일일 권장량 대비 비율 계산
    daily_intake = {
        'calories': round((default_nutrition.get('calories', 0) / 2000) * 100, 1),
        'carbs': round((default_nutrition.get('carbs', 0) / 325) * 100, 1),
        'protein': round((default_nutrition.get('protein', 0) / 50) * 100, 1),
        'fat': round((default_nutrition.get('fat', 0) / 65) * 100, 1),
        'saturated_fat': round((default_nutrition.get('saturated_fat', 0) / 20) * 100, 1),
        'fiber': round((default_nutrition.get('fiber', 0) / 25) * 100, 1),
        'sodium': round((default_nutrition.get('sodium', 0) / 2300) * 100, 1),
        'sugar': round((default_nutrition.get('sugar', 0) / 50) * 100, 1),
        'cholesterol': round((default_nutrition.get('cholesterol', 0) / 300) * 100, 1),
        'vitamin_c': round((default_nutrition.get('vitamin_c', 0) / 90) * 100, 1),
        'calcium': round((default_nutrition.get('calcium', 0) / 1000) * 100, 1),
        'iron': round((default_nutrition.get('iron', 0) / 18) * 100, 1)
    }
    
    # LogMeal 형식의 응답 생성
    response = {
        'status': 'success',
        'foodName': food_name,
        'hasNutritionalInfo': True,
        'nutri_score': {
            'category': nutri_score_category,
            'score': nutri_score
        },
        'nutritional_info': {
            'calories': default_nutrition.get('calories', 0),
            'totalNutrients': {
                'CHOCDF': {
                    'label': '탄수화물',
                    'quantity': default_nutrition.get('carbs', 0),
                    'unit': 'g'
                },
                'PROCNT': {
                    'label': '단백질',
                    'quantity': default_nutrition.get('protein', 0),
                    'unit': 'g'
                },
                'FAT': {
                    'label': '지방',
                    'quantity': default_nutrition.get('fat', 0),
                    'unit': 'g'
                },
                'FASAT': {
                    'label': '포화지방',
                    'quantity': default_nutrition.get('saturated_fat', 0),
                    'unit': 'g'
                },
                'FIBTG': {
                    'label': '식이섬유',
                    'quantity': default_nutrition.get('fiber', 0),
                    'unit': 'g'
                },
                'NA': {
                    'label': '나트륨',
                    'quantity': default_nutrition.get('sodium', 0),
                    'unit': 'mg'
                },
                'SUGAR': {
                    'label': '당류',
                    'quantity': default_nutrition.get('sugar', 0),
                    'unit': 'g'
                },
                'CHOLE': {
                    'label': '콜레스테롤',
                    'quantity': default_nutrition.get('cholesterol', 0),
                    'unit': 'mg'
                },
                'VITC': {
                    'label': '비타민 C',
                    'quantity': default_nutrition.get('vitamin_c', 0),
                    'unit': 'mg'
                },
                'CA': {
                    'label': '칼슘',
                    'quantity': default_nutrition.get('calcium', 0),
                    'unit': 'mg'
                },
                'FE': {
                    'label': '철분',
                    'quantity': default_nutrition.get('iron', 0),
                    'unit': 'mg'
                }
            },
            'dailyIntakeReference': daily_intake
        }
    }
    
    return jsonify(response)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'nutrition-api'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)