#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AIYAM 완전한 대화형 챗봇
NLU (A.X Encoder) → RAG → TeenPersonalizer → NLG (A.X 3.1 Lite)
"""

import sys
import os
import warnings
warnings.filterwarnings('ignore')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("\n" + "="*70)
    print(" AIYAM 챗봇 - 완전한 파이프라인 버전")
    print("="*70)
    print(" [NLU] A.X Encoder - 의도/엔티티 추출")
    print(" [RAG] FAISS - 2008개 가게 검색")
    print(" [개인화] TeenPersonalizer - 11개 피처")
    print(" [NLG] A.X 3.1 Lite - 자연어 생성")
    print("-"*70)
    
    try:
        # 1. 데이터 로드
        print("\n[1/5] 데이터 로딩...")
        from src.data.data_loader import DataLoader
        loader = DataLoader()
        knowledge = loader.load_all_data()
        print(f"[완료] {len(knowledge.shops)}개 가게, {len(knowledge.menus)}개 메뉴 로드")
        
        # 2. NLU 설정 (A.X Encoder)
        print("\n[2/5] NLU (A.X Encoder) 초기화...")
        nlu_model = None
        try:
            # A.X Encoder는 이미 학습되어 있으므로 바로 사용
            from models.ax_encoder_nlu import AXEncoderNLU
            
            # 모델이 있는 경로들 시도
            model_paths = [
                'models/ax_encoder_nlu_trained',  # 학습된 모델
                'models/ax_encoder_base',  # 기본 모델
                None  # 규칙 기반 폴백
            ]
            
            for path in model_paths:
                try:
                    nlu_model = AXEncoderNLU(path)
                    print(f"[완료] A.X Encoder NLU 로드: {path if path else '규칙 기반'}")
                    break
                except:
                    continue
                    
            if not nlu_model:
                print("⚠ A.X Encoder 로드 실패, 규칙 기반 사용")
                nlu_model = None
                
        except Exception as e:
            print(f"⚠ NLU 초기화 실패: {e}")
            nlu_model = None
        
        # 3. NLG 설정 (A.X 3.1 Lite)
        print("\n[3/5] NLG (A.X 3.1 Lite) 초기화...")
        from models.ax_model import AXModel
        ax_model = AXModel(use_4bit=True)  # 4bit 양자화
        
        # 명시적으로 모델 로드
        if not hasattr(ax_model, 'model') or ax_model.model is None:
            print("  모델 로딩 중... (30초~1분 소요)")
            ax_model.load_model()
        print("[완료] A.X 3.1 Lite 모델 로드 완료")
        
        # 4. 통합 파이프라인 설정
        print("\n[4/5] 통합 파이프라인 구성...")
        from src.inference.integrated_pipeline import IntegratedPipeline
        
        pipeline = IntegratedPipeline(
            knowledge=knowledge,
            llm_generator=ax_model,
            use_rag=True  # RAG 활성화 시도
        )
        
        # NLU 모델 직접 설정
        if nlu_model:
            pipeline.ax_nlu = nlu_model
        
        print("[완료] 파이프라인 구성 완료")
        
        # 5. TeenPersonalizer 확인
        print("\n[5/5] TeenPersonalizer 확인...")
        try:
            from src.personalization.teen_personalizer import get_personalizer
            personalizer = get_personalizer()
            print("[완료] TeenPersonalizer 활성화")
        except:
            personalizer = None
            print("⚠ TeenPersonalizer 비활성화")
        
        # 시스템 준비 완료
        print("\n" + "="*70)
        print(" 시스템 준비 완료! 대화를 시작하세요.")
        print("="*70)
        
        # 현재 시간과 날씨 정보 가져오기
        from datetime import datetime
        try:
            from src.utils.simple_weather_service import get_weather_service
            weather_service = get_weather_service()
            weather = weather_service.get_weather()
            weather_msg = f"{weather['temperature']}°C, {weather['description']}"
        except Exception as e:
            logger.debug(f"날씨 정보 로드 실패: {e}")
            weather_msg = ""
        
        # 현재 시간 표시
        current_time = datetime.now()
        time_msg = current_time.strftime("%Y년 %m월 %d일 %H시 %M분")
        
        # 시간대별 인사말
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
        
        # 사용자 정보
        user_id = input("\n닉네임 입력 (엔터=guest): ").strip() or "guest"
        
        # 환영 메시지 출력
        print("\n" + "="*70)
        print(f" [시간] {time_msg}")
        if weather_msg:
            print(f" [날씨] 코엑스 {weather_msg}")
        print("="*70)
        print(f"\n안녕하세요 {user_id}님! {greeting}!")
        print("무엇을 도와드릴까요?\n")
        
        # 날씨 기반 추천 컨텍스트 추가
        weather_context = {}
        if weather_msg:
            try:
                weather_context = weather_service.get_food_context()
                logger.debug(f"날씨 기반 추천: {weather_context.get('message', '')}")
            except:
                pass
        
        user_profile = {
            'user_id': user_id,
            'preferred_categories': weather_context.get('preferred_categories', []),
            'interaction_count': 0,
            'session_id': None,  # 세션 ID 추가
            'weather_context': weather_context  # 날씨 컨텍스트 추가
        }
        
        conversation_context = []
        
        # 대화 루프
        while True:
            try:
                # 사용자 입력
                print("-" * 50)
                user_input = input(f"[{user_id}] ").strip()
                
                if not user_input:
                    continue
                
                # 종료 명령
                if user_input.lower() in ['quit', 'exit', '종료', 'bye']:
                    print("\n[AIYAM] 다음에 또 만나요! 맛있는 하루 되세요~")
                    break
                
                # NLU 처리 (의도/엔티티 추출)
                print("\n[처리중] ", end="")
                
                # 파이프라인 실행
                try:
                    response = pipeline.process(
                        user_input=user_input,
                        user_profile=user_profile,
                        conversation_context=conversation_context,
                        user_id=user_id
                    )
                    
                    if response and response.text:
                        # NLG 응답 출력
                        print(f"\n[AIYAM] {response.text}")
                        
                        # 추천 결과 표시
                        recs = getattr(response, 'recommendations', [])
                        if not recs and response.metadata and 'recommendations' in response.metadata:
                            recs = response.metadata.get('recommendations', [])
                        
                        if recs and len(recs) > 0:
                                print("\n" + "="*50)
                                print(" 추천 맛집")
                                print("="*50)
                                
                                for i, rec in enumerate(recs[:3], 1):
                                    name = rec.get('shop_name', '알 수 없음')
                                    category = rec.get('category', '기타')
                                    # price_range가 없으면 price 사용, 둘 다 없으면 기본값
                                    price = rec.get('price', rec.get('avg_price', 10000))
                                    address = rec.get('address', '')[:30]
                                    
                                    print(f"\n[{i}] {name}")
                                    print(f"    카테고리: {category}")
                                    print(f"    가격대: {price:,}원")
                                    if address:
                                        print(f"    위치: {address}...")
                                    
                                    # 피드백 처리 (첫 번째 추천 자동 view)
                                    if i == 1 and rec.get('shop_id'):
                                        try:
                                            pipeline.process_feedback(
                                                user_id=user_id,
                                                shop_id=rec['shop_id'],
                                                feedback_type='view',
                                                metadata={'category': category}
                                            )
                                        except Exception as e:
                                            # 오류 무시 (로그 출력 안 함)
                                            pass
                        
                        # 개인화 수준 표시
                        if personalizer:
                            try:
                                level = personalizer.get_personalization_level(user_id)
                                profile = personalizer.get_profile(user_id)
                                
                                print(f"\n[개인화] {level}")
                                
                                if profile.category_scores:
                                    top_cat = max(profile.category_scores.items(), key=lambda x: x[1])
                                    if top_cat[1] > 0.5:
                                        print(f"[선호] {top_cat[0]} (점수: {top_cat[1]:.2f})")
                            except:
                                pass
                        
                        # 대화 컨텍스트 업데이트
                        conversation_context.append({
                            'user': user_input,
                            'assistant': response.text[:100]
                        })
                        
                        if len(conversation_context) > 5:
                            conversation_context = conversation_context[-5:]
                        
                        user_profile['interaction_count'] += 1
                        
                    else:
                        # 폴백 응답
                        print("\n[AIYAM] 죄송해요, 잘 이해하지 못했어요. 다시 말씀해주시겠어요?")
                
                except Exception as e:
                    logger.error(f"응답 생성 오류: {e}")
                    
                    # 간단한 규칙 기반 폴백
                    if any(word in user_input.lower() for word in ['안녕', '하이', 'hi']):
                        print("\n[AIYAM] 안녕하세요! 오늘 뭐 드시고 싶으세요?")
                    elif any(word in user_input.lower() for word in ['치킨', '피자', '버거']):
                        print(f"\n[AIYAM] {user_input}를 찾아드릴게요!")
                        
                        # 간단한 검색
                        keyword = None
                        for word in ['치킨', '피자', '버거']:
                            if word in user_input.lower():
                                keyword = word
                                break
                        
                        if keyword:
                            shops = [s for s in knowledge.shops.values() 
                                   if keyword in s.category.lower()][:3]
                            if shops:
                                print("\n추천 맛집:")
                                for i, shop in enumerate(shops, 1):
                                    print(f"  {i}. {shop.name} ({shop.category})")
                    else:
                        print("\n[AIYAM] 무엇을 도와드릴까요?")
                
                print()  # 줄바꿈
                
            except KeyboardInterrupt:
                print("\n\n[시스템] 대화를 종료합니다...")
                break
            except Exception as e:
                print(f"\n[오류] {str(e)[:50]}")
                continue
    
    except Exception as e:
        print(f"\n[오류] 시스템 초기화 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()