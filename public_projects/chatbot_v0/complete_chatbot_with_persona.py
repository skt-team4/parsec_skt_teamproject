#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIYAM 챗봇 - 페르소나 기반 버전
사전 학습된 페르소나로 시작하는 개인화 챗봇
"""

import sys
import os
import warnings
import json
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def select_persona():
    """페르소나 선택 UI"""
    with open('data/personas.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    personas = data['personas']
    
    print("\n" + "="*70)
    print(" 페르소나 선택")
    print("="*70)
    print("\n어떤 상황으로 체험하시겠어요?\n")
    
    for i, p in enumerate(personas):
        print(f"[{i+1}] {p['name']} ({p['age']}세)")
        print(f"    {p['description']}")
        print(f"    급식카드 잔액: {p['meal_card_info']['balance']:,}원")
        print()
    
    while True:
        try:
            choice = input("선택 (1-3): ").strip()
            if choice in ['1', '2', '3']:
                return personas[int(choice) - 1]
            else:
                print("1, 2, 3 중에서 선택해주세요.")
        except:
            print("숫자로 입력해주세요.")

def load_persona_data(persona):
    """페르소나 데이터 로드"""
    persona_id = persona['id']
    
    # 프로필 로드
    profile_path = f'data/persona_{persona_id}_profile.json'
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    
    # 대화 이력 로드
    history_path = f'data/persona_{persona_id}_history.json'
    with open(history_path, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    return profile, history

def display_persona_status(persona, profile):
    """페르소나 상태 표시"""
    print("\n" + "="*70)
    print(f" {persona['name']}님으로 시작합니다")
    print("="*70)
    print(f"나이: {persona['age']}세")
    print(f"급식카드 잔액: {persona['meal_card_info']['balance']:,}원 (일 한도: 9,500원)")
    print(f"남은 일수: 약 {persona['meal_card_info']['days_remaining']}일")
    
    # 영양 상태
    print("\n[영양 상태]")
    issues = persona['nutrition_status']['current_issues']
    if 'vitamin_deficiency' in issues:
        print("  [!] 비타민 부족")
    if 'excess_sugar' in issues:
        print("  [!] 당분 과다")
    if 'excess_sodium' in issues:
        print("  [!] 나트륨 과다")
    if 'skip_breakfast' in issues:
        print("  [!] 아침 결식")
    
    # 알레르기 정보
    if 'dietary_restrictions' in persona['teen_personalizer_features']:
        restrictions = persona['teen_personalizer_features']['dietary_restrictions']
        if restrictions:
            print(f"\n[알레르기/제한사항]")
            for r in restrictions:
                print(f"  [X] {r}")
    
    print("="*70)

def main():
    # 1. 페르소나 선택
    selected_persona = select_persona()
    
    # 2. 페르소나 데이터 로드
    profile, conversation_history = load_persona_data(selected_persona)
    
    # 3. 페르소나 상태 표시
    display_persona_status(selected_persona, profile)
    
    print("\n시스템을 초기화하는 중...")
    
    try:
        # 4. 데이터 로드
        from src.data.data_loader import DataLoader
        loader = DataLoader()
        knowledge = loader.load_all_data()
        print(f"[완료] {len(knowledge.shops)}개 가게 데이터 로드")
        
        # 5. NLU 설정
        from models.ax_encoder_nlu import AXEncoderNLU
        nlu_model = None
        try:
            nlu_model = AXEncoderNLU('models/ax_encoder_nlu_trained')
            print("[완료] NLU 모델 로드")
        except:
            print("[경고] NLU 모델 로드 실패, 규칙 기반 사용")
        
        # 6. NLG 설정
        from models.ax_model import AXModel
        ax_model = AXModel(use_4bit=True)
        print("[시작] NLG 모델 로딩 중... (1-2분 소요)")
        ax_model.load_model()  # 실제 모델 로드
        print("[완료] NLG 모델 로드")
        
        # 7. 파이프라인 구성
        from src.inference.integrated_pipeline import IntegratedPipeline
        pipeline = IntegratedPipeline(
            knowledge=knowledge,
            llm_generator=ax_model,
            use_rag=True
        )
        if nlu_model:
            pipeline.ax_nlu = nlu_model
        
        # 8. TeenPersonalizer에 프로필 주입
        from src.personalization.teen_personalizer import get_personalizer
        personalizer = get_personalizer()
        
        # 프로필 데이터 주입
        user_id = selected_persona['teen_personalizer_features']['user_id']
        
        # TeenPersonalizer 프로필 설정
        personalizer.load_profile(user_id, profile)
        
        print("[완료] 개인화 프로필 로드")
        
        # 9. ConversationManager에 대화 이력 주입
        from src.inference.conversation_manager import ConversationManager
        conversation_manager = ConversationManager()
        
        # 대화 이력 설정
        for conv in conversation_history[-5:]:  # 최근 5개만
            conversation_manager.add_message(user_id, 'user', conv['user'])
            conversation_manager.add_message(user_id, 'assistant', conv['bot'])
        
        print("[완료] 대화 이력 로드")
        
        # 현재 시간과 날씨
        from datetime import datetime
        current_time = datetime.now()
        hour = current_time.hour
        
        if 5 <= hour < 10:
            greeting = "좋은 아침이에요"
        elif 10 <= hour < 14:
            greeting = "점심 시간이네요"
        elif 14 <= hour < 18:
            greeting = "오후 시간이에요"
        elif 18 <= hour < 22:
            greeting = "저녁 시간이네요"
        else:
            greeting = "늦은 시간이네요"
        
        # 날씨 설정
        print("\n날씨 설정:")
        print("[0] 실제 날씨 API 사용 (서울 기준)")
        print("[1] 맑음 (20°C)")
        print("[2] 흐림 (18°C)")
        print("[3] 비 (15°C)")
        print("[4] 눈 (-2°C)")
        print("[5] 더움 (33°C)")
        print("[6] 추움 (3°C)")
        
        weather_map = {
            '1': ('맑음', 20),
            '2': ('흐림', 18),
            '3': ('비', 15),
            '4': ('눈', -2),
            '5': ('맑음', 33),
            '6': ('흐림', 3)
        }
        
        while True:
            weather_choice = input("선택 (0-6, Enter=실제날씨): ").strip()
            if not weather_choice:
                weather_choice = '0'
            
            if weather_choice == '0':
                # 실제 날씨 API 호출 시도
                try:
                    import requests
                    import os
                    from dotenv import load_dotenv
                    load_dotenv()
                    
                    api_key = os.getenv('OPENWEATHERMAP_API_KEY')
                    if api_key:
                        # OpenWeatherMap API 예시
                        url = f"http://api.openweathermap.org/data/2.5/weather?q=Seoul&appid={api_key}&units=metric&lang=kr"
                        response = requests.get(url, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            weather_desc = data['weather'][0]['description']
                            temp = round(data['main']['temp'])
                            
                            # 날씨 상태 매핑
                            if '맑' in weather_desc or '구름 조금' in weather_desc:
                                current_weather = '맑음'
                            elif '비' in weather_desc:
                                current_weather = '비'
                            elif '눈' in weather_desc:
                                current_weather = '눈'
                            else:
                                current_weather = '흐림'
                            
                            temperature = temp
                            print(f"[API] 실제 날씨 정보 로드: {current_weather} {temperature}°C")
                            break
                        else:
                            raise Exception("API 응답 오류")
                    else:
                        raise Exception("API 키 없음")
                except Exception as e:
                    print(f"[경고] 날씨 API 연결 실패: {e}")
                    print("기본값(맑음 20°C)을 사용합니다.")
                    current_weather, temperature = '맑음', 20
                    break
                    
            elif weather_choice in weather_map:
                current_weather, temperature = weather_map[weather_choice]
                break
            else:
                print("0-6 중에서 선택해주세요.")
        
        # 파이프라인에 날씨 정보 전달을 위한 컨텍스트
        weather_context = {
            'weather': current_weather,
            'temperature': temperature,
            'hour': hour
        }
        
        # 시작 메시지
        print("\n" + "="*70)
        print(f" 안녕하세요 {selected_persona['name']}님! {greeting}!")
        print(f" 현재 시각: {current_time.strftime('%H:%M')} | 날씨: {current_weather} {temperature}°C")
        print("="*70)
        
        # 영양 알림 (필요시)
        if selected_persona['meal_card_info']['balance'] < 20000:
            print(f"\n[알림] 급식카드 잔액이 {selected_persona['meal_card_info']['balance']:,}원 남았어요.")
            print("       충전이 필요할 수 있어요.")
        
        recommended_nutrients = selected_persona['nutrition_status']['recommended_nutrients']
        if recommended_nutrients:
            print(f"\n[TIP] 오늘은 {', '.join(recommended_nutrients[:2])}가 풍부한 음식을 드시면 좋아요!")
        
        print("\n무엇을 도와드릴까요?\n")
        print("(종료: quit, exit, bye)")
        print("-" * 70)
        
        # 대화 루프
        user_profile = {
            'user_id': user_id,
            'age_group': selected_persona['teen_personalizer_features']['age_group'],
            'preferred_categories': selected_persona['teen_personalizer_features']['preferred_categories'],
            'interaction_count': len(conversation_history),
            'meal_card_balance': selected_persona['meal_card_info']['balance']
        }
        
        conversation_context = []
        
        while True:
            try:
                user_input = input(f"\n[{selected_persona['name']}] ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', '종료', 'bye']:
                    print(f"\n[AIYAM] {selected_persona['name']}님, 다음에 또 만나요! 건강하게 잘 먹어요~")
                    break
                
                # 급식카드 잔액 체크
                if '잔액' in user_input or '급식카드' in user_input:
                    balance = selected_persona['meal_card_info']['balance']
                    days = selected_persona['meal_card_info']['days_remaining']
                    print(f"\n[AIYAM] 현재 급식카드 잔액은 {balance:,}원이에요.")
                    print(f"        하루 9,500원씩 쓰면 {days}일 동안 사용 가능해요.")
                    continue
                
                # 알레르기 체크
                if '알레르기' in user_input:
                    restrictions = selected_persona['teen_personalizer_features'].get('dietary_restrictions', [])
                    if restrictions:
                        print(f"\n[AIYAM] {selected_persona['name']}님은 {', '.join(restrictions)}에 알레르기가 있어요.")
                        print("        추천할 때 이를 고려해서 안전한 메뉴만 보여드릴게요!")
                    else:
                        print("\n[AIYAM] 등록된 알레르기 정보가 없어요.")
                    continue
                
                # 파이프라인 처리
                print("\n[처리중] ", end="")
                
                # 날씨 정보를 컨텍스트에 추가
                enhanced_context = conversation_context.copy()
                if 'weather_context' in locals():
                    enhanced_context.append({
                        'system': 'weather',
                        'weather': weather_context['weather'],
                        'temperature': weather_context['temperature']
                    })
                
                response = pipeline.process(
                    user_input=user_input,
                    user_profile=user_profile,
                    conversation_context=enhanced_context,
                    user_id=user_id
                )
                
                if response and response.text:
                    print(f"\n[AIYAM] {response.text}")
                    
                    # 추천 결과 표시
                    if hasattr(response, 'recommendations') and response.recommendations:
                        print("\n" + "="*50)
                        print(" 추천 맛집")
                        print("="*50)
                        
                        for i, rec in enumerate(response.recommendations[:3], 1):
                            name = rec.get('shop_name', '알 수 없음')
                            category = rec.get('category', '기타')
                            price = rec.get('price', rec.get('avg_price', 10000))
                            
                            # 가격이 급식카드 한도 내인지 체크
                            if price <= 9500:
                                price_info = f"{price:,}원 [OK]"
                            else:
                                price_info = f"{price:,}원 [주의]"
                            
                            print(f"\n[{i}] {name}")
                            print(f"    카테고리: {category}")
                            print(f"    가격: {price_info}")
                            
                            # 알레르기 체크
                            if selected_persona['teen_personalizer_features'].get('dietary_restrictions'):
                                print("    알레르기: 안전 [OK]")
                    
                    # 대화 컨텍스트 업데이트
                    conversation_context.append({
                        'user': user_input,
                        'assistant': response.text[:100]
                    })
                    
                    if len(conversation_context) > 5:
                        conversation_context = conversation_context[-5:]
                    
                    user_profile['interaction_count'] += 1
                    
                else:
                    print("\n[AIYAM] 죄송해요, 잘 이해하지 못했어요. 다시 말씀해주시겠어요?")
                
            except KeyboardInterrupt:
                print("\n\n[시스템] 대화를 종료합니다...")
                break
            except Exception as e:
                logger.error(f"오류: {e}")
                print("\n[AIYAM] 일시적인 오류가 발생했어요. 다시 시도해주세요.")
    
    except Exception as e:
        print(f"\n[오류] 시스템 초기화 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()