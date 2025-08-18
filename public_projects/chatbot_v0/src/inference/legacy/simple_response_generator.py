"""
간단한 LLM 중심 응답 생성기
복잡한 로직을 제거하고 LLM 우선으로 동작
"""

import logging
from typing import Dict, List, Optional
from src.data.data_structure import ExtractedInfo, ChatbotResponse, UserProfile

logger = logging.getLogger(__name__)


class SimpleLLMResponseGenerator:
    """LLM 중심의 간단한 응답 생성기"""
    
    def __init__(self, knowledge, model=None, use_wide_deep=True):
        self.knowledge = knowledge
        self.model = model
        self.generation_count = 0
        self.llm_success_count = 0
        
        # Wide&Deep 통합 파이프라인
        self.integrated_pipeline = None
        if use_wide_deep:
            try:
                from inference.integrated_pipeline import IntegratedPipeline
                self.integrated_pipeline = IntegratedPipeline(knowledge, self)
                logger.info("Wide&Deep 통합 파이프라인 활성화")
            except Exception as e:
                logger.warning(f"Wide&Deep 파이프라인 로드 실패: {e}")
        
    def generate_response(
        self,
        extracted_info: ExtractedInfo,
        user_profile: UserProfile = None,
        conversation_context: List[Dict] = None,
        rag_context: str = ""
    ) -> ChatbotResponse:
        """LLM 우선 응답 생성 (Wide&Deep 통합)"""
        
        self.generation_count += 1
        user_text = extracted_info.raw_text
        
        # Wide&Deep 파이프라인이 있으면 사용
        if self.integrated_pipeline and hasattr(self.integrated_pipeline, 'wide_deep_model') and self.integrated_pipeline.wide_deep_model:
            try:
                # 사용자 프로필을 딕셔너리로 변환
                user_dict = None
                if user_profile:
                    user_dict = {
                        'user_id': user_profile.user_id if hasattr(user_profile, 'user_id') else 'default',
                        'age_group': '20s',
                        'preferred_cuisines': user_profile.preference_history[:3] if hasattr(user_profile, 'preference_history') else [],
                        'price_sensitivity': 'medium',
                        'meal_frequency': 3.0
                    }
                
                # 통합 파이프라인으로 처리
                response = self.integrated_pipeline.process(
                    user_input=user_text,
                    user_profile=user_dict,
                    conversation_context=conversation_context
                )
                
                if response:
                    self.llm_success_count += 1
                    response.metadata['pipeline'] = 'integrated_wide_deep'
                    return response
                    
            except Exception as e:
                logger.warning(f"Wide&Deep 파이프라인 실행 실패: {e}")
                # 폴백: 기존 방식으로 계속
        
        # 1. 특정 가격 질문 처리
        price_response = self._handle_price_inquiry(user_text)
        if price_response:
            self.llm_success_count += 1
            return price_response
        
        # 2. 참조 표현 처리 ("그게", "그거", "거기" 등)
        is_reference = self._is_reference_expression(user_text)
        recommendations = []
        
        if is_reference and conversation_context:
            # 이전 대화에서 언급된 가게/메뉴 찾기
            recommendations = self._get_referenced_items(user_text, conversation_context)
        elif self._needs_recommendation(user_text):
            # 새로운 추천 생성
            recommendations = self._get_simple_recommendations(user_text)
        
        # 3. LLM으로 응답 생성 (대화 맥락 포함)
        if self.model:
            try:
                llm_response = self._generate_llm_response(
                    user_text, 
                    recommendations,
                    conversation_context,
                    rag_context  # RAG 컨텍스트 전달!
                )
                
                if llm_response:
                    self.llm_success_count += 1
                    return ChatbotResponse(
                        text=llm_response,
                        recommendations=recommendations,
                        metadata={
                            "generation_method": "llm",
                            "llm_usage_rate": f"{(self.llm_success_count/self.generation_count)*100:.1f}%",
                            "has_context": bool(conversation_context),
                            "is_reference": is_reference
                        }
                    )
            except Exception as e:
                logger.warning(f"LLM 응답 실패: {e}")
        
        # 4. LLM 실패시 맥락 고려한 기본 응답
        return self._generate_contextual_fallback(user_text, recommendations, conversation_context)
    
    def _handle_price_inquiry(self, text: str) -> Optional[ChatbotResponse]:
        """특정 메뉴 가격 질문 처리"""
        # 가격 관련 키워드 확인
        if not any(word in text for word in ['얼마', '가격', '원', '비용']):
            return None
        
        # 가게 이름과 메뉴 추출
        shop_name = None
        menu_name = None
        
        # 가게 이름 찾기
        for shop in self.knowledge.shops.values():
            if shop.name in text or shop.name.replace(' ', '') in text.replace(' ', ''):
                shop_name = shop.name
                shop_id = shop.id
                break
        
        if not shop_name:
            return None
        
        # 해당 가게의 메뉴 찾기
        shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop_id]
        
        # 메뉴 이름 매칭
        for menu in shop_menus:
            if menu.name in text or any(keyword in text for keyword in menu.name.split()):
                menu_name = menu.name
                price = menu.price
                
                # 정확한 가격 응답 생성
                response_text = f"{shop_name}의 {menu_name}는 {price:,}원입니다."
                
                return ChatbotResponse(
                    text=response_text,
                    recommendations=[{
                        'shop_id': shop_id,
                        'shop_name': shop_name,
                        'menu_name': menu_name,
                        'price': price,
                        'category': self.knowledge.shops[shop_id].category,
                        'address': self.knowledge.shops[shop_id].address
                    }],
                    metadata={
                        "generation_method": "database_lookup",
                        "query_type": "price_inquiry"
                    }
                )
        
        return None
    
    def _needs_recommendation(self, text: str) -> bool:
        """추천이 필요한지 판단"""
        food_keywords = ['먹', '추천', '뭐', '어떤', '저녁', '점심', '아침', '야식', 
                        '배고', '음식', '맛있', '가게', '치킨', '피자', '한식', '중식',
                        '아무거나', '샐러드', '건강식', '다이어트']
        return any(keyword in text for keyword in food_keywords)
    
    def _analyze_user_intent(self, text: str) -> Optional[str]:
        """사용자 의도 분석"""
        if '샐러드' in text or '다이어트' in text or '건강식' in text:
            return '샐러드/건강식 요청'
        elif '다른' in text or '또' in text or '더' in text:
            return '추가 추천 요청'
        elif any(word in text for word in ['그게', '뭔데', '뭐야', '뭐냐']):
            return '이전 언급 내용 설명 요청'
        elif '아무거나' in text:
            return '랜덤 추천 요청'
        elif any(word in text for word in ['치킨', '피자', '한식', '중식', '일식']):
            return '특정 카테고리 요청'
        elif '얼마' in text or '가격' in text:
            return '가격 문의'
        return None
    
    def _get_simple_recommendations(self, text: str, limit: int = 3) -> List[Dict]:
        """메뉴 중심 추천 생성 (사용자 요구 맞춤)"""
        recommendations = []
        
        # 샐러드 요청 특별 처리
        if '샐러드' in text:
            # 샐러드가 없으므로 건강한 대안 추천
            healthy_keywords = ['나물', '비빔밥', '쌈밥', '두부', '콩나물']
            for menu in self.knowledge.menus.values():
                if any(keyword in menu.name for keyword in healthy_keywords):
                    if menu.shop_id in self.knowledge.shops:
                        shop = self.knowledge.shops[menu.shop_id]
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'price': menu.price,
                            'category': shop.category,
                            'address': shop.address,
                            'note': '건강식 대안'
                        })
                        if len(recommendations) >= limit:
                            break
            return recommendations
        
        # 특정 메뉴 직접 검색
        if self._is_specific_menu_request(text):
            # 메뉴 레벨에서 직접 검색
            matching_menus = self._search_menus_directly(text)
            
            for menu in matching_menus[:limit]:
                if menu.shop_id in self.knowledge.shops:
                    shop = self.knowledge.shops[menu.shop_id]
                    recommendations.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': menu.name,
                        'price': menu.price,
                        'category': shop.category,
                        'address': shop.address,
                        'is_good_influence_shop': shop.is_good_influence_shop
                    })
            
            if recommendations:
                return recommendations
        
        # 카테고리 기반 검색 (fallback)
        category = self._extract_category(text)
        
        if category:
            # 카테고리에 맞는 가게 찾기
            matching_shops = [s for s in self.knowledge.shops.values() 
                            if category.lower() in s.category.lower()]
            
            # 메뉴 기반으로 필터링
            for shop in matching_shops:
                shop_menus = [m for m in self.knowledge.menus.values() 
                             if m.shop_id == shop.id]
                
                # 특정 요청에 맞는 메뉴 선택
                selected_menu = self._select_best_menu(shop_menus, text)
                
                if selected_menu:
                    recommendations.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': selected_menu.name,
                        'price': selected_menu.price,
                        'category': shop.category,
                        'address': shop.address,
                        'is_good_influence_shop': shop.is_good_influence_shop
                    })
                    
                    if len(recommendations) >= limit:
                        break
        else:
            # 일반 추천
            import random
            all_menus = list(self.knowledge.menus.values())
            random_menus = random.sample(all_menus, min(limit*2, len(all_menus)))
            
            for menu in random_menus:
                if menu.shop_id in self.knowledge.shops:
                    shop = self.knowledge.shops[menu.shop_id]
                    recommendations.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': menu.name,
                        'price': menu.price,
                        'category': shop.category,
                        'address': shop.address
                    })
                    if len(recommendations) >= limit:
                        break
        
        return recommendations
    
    def _is_specific_menu_request(self, text: str) -> bool:
        """특정 메뉴 요청인지 확인"""
        menu_keywords = ['양념', '후라이드', '간장', '파닭', '불고기', '알밥', 
                        '김치찌개', '된장찌개', '짜장면', '짬뽕', '탕수육']
        return any(keyword in text for keyword in menu_keywords)
    
    def _search_menus_directly(self, text: str) -> List:
        """메뉴 이름으로 직접 검색"""
        matching_menus = []
        
        # 정확한 매칭 우선
        for menu in self.knowledge.menus.values():
            menu_name_lower = menu.name.lower()
            text_lower = text.lower()
            
            # 양념치킨 특별 처리
            if '양념' in text and '치킨' in text:
                if '양념' in menu_name_lower or '간장' in menu_name_lower or \
                   '매운' in menu_name_lower or '불' in menu_name_lower:
                    matching_menus.append(menu)
            # 후라이드치킨 특별 처리
            elif '후라이드' in text or '후라이' in text:
                if '후라이' in menu_name_lower or '크리스피' in menu_name_lower or \
                   '오리지널' in menu_name_lower:
                    matching_menus.append(menu)
            # 일반 매칭
            elif any(keyword in menu_name_lower for keyword in text_lower.split()):
                matching_menus.append(menu)
        
        # 가격순 정렬
        matching_menus.sort(key=lambda x: x.price)
        return matching_menus
    
    def _extract_category(self, text: str) -> Optional[str]:
        """텍스트에서 카테고리 추출 (개선된 매칭)"""
        if '치킨' in text:
            return '치킨'
        elif '피자' in text:
            return '피자'  # 피자 전용 카테고리
        elif '햄버거' in text or '버거' in text:
            return '버거'  # 버거 전용 카테고리
        elif '한식' in text or '김치' in text or '된장' in text or '찌개' in text:
            return '한식'
        elif '중식' in text or '짜장' in text or '짬뽕' in text:
            return '중식'
        elif '일식' in text or '초밥' in text or '라멘' in text:
            return '일식'
        elif '양식' in text or '파스타' in text or '스테이크' in text:
            return '양식'
        return None
    
    def _select_best_menu(self, menus: List, text: str):
        """요청에 가장 적합한 메뉴 선택"""
        if not menus:
            return None
        
        text_lower = text.lower()
        
        # 특정 키워드가 있으면 해당 메뉴 우선
        for menu in menus:
            menu_name_lower = menu.name.lower()
            
            if '양념' in text_lower and '양념' in menu_name_lower:
                return menu
            elif '후라이드' in text_lower and ('후라이' in menu_name_lower or '오리지널' in menu_name_lower):
                return menu
            elif '간장' in text_lower and '간장' in menu_name_lower:
                return menu
        
        # 인기 메뉴 우선
        popular = [m for m in menus if m.is_popular]
        if popular:
            return min(popular, key=lambda x: x.price)
        
        # 가장 저렴한 메뉴
        return min(menus, key=lambda x: x.price)
    
    def _is_reference_expression(self, text: str) -> bool:
        """참조 표현인지 확인"""
        reference_words = [
            '그게', '그거', '거기', '그곳', '아까', '방금', 
            '그건', '그런데', '그런거', '뭔데', '뭐냐고',
            '그 가게', '그 메뉴', '그 음식'
        ]
        return any(word in text for word in reference_words)
    
    def _get_referenced_items(self, text: str, conversation_context: List[Dict]) -> List[Dict]:
        """이전 대화에서 언급된 아이템 찾기"""
        recommendations = []
        
        if not conversation_context:
            return recommendations
        
        # 최근 대화에서 추천된 가게/메뉴 찾기
        for ctx in reversed(conversation_context[-3:]):
            bot_response = ctx.get('bot_response', '')
            
            # 응답에서 가게 이름 추출 시도
            for shop in self.knowledge.shops.values():
                if shop.name in bot_response:
                    # 해당 가게의 메뉴 찾기
                    shop_menus = [m for m in self.knowledge.menus.values() 
                                 if m.shop_id == shop.id]
                    
                    for menu in shop_menus[:1]:  # 대표 메뉴만
                        recommendations.append({
                            'shop_id': shop.id,
                            'shop_name': shop.name,
                            'menu_name': menu.name,
                            'price': menu.price,
                            'category': shop.category,
                            'address': shop.address
                        })
                        break
            
            if recommendations:
                break
        
        return recommendations
    
    def _generate_contextual_fallback(self, user_text: str, recommendations: List[Dict], 
                                      conversation_context: List[Dict] = None) -> ChatbotResponse:
        """맥락을 고려한 폴백 응답"""
        
        # 참조 표현인 경우
        if self._is_reference_expression(user_text) and conversation_context:
            last_response = conversation_context[-1].get('bot_response', '') if conversation_context else ''
            
            # 이전에 추천한 가게 찾기
            for shop in self.knowledge.shops.values():
                if shop.name in last_response:
                    # 해당 가게 정보로 응답
                    shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                    if shop_menus:
                        cheapest = min(shop_menus, key=lambda x: x.price)
                        response = f"{shop.name}은(는) {shop.category} 전문점입니다. "
                        response += f"{shop.address}에 위치하고 있고, "
                        response += f"대표 메뉴는 {cheapest.name} ({cheapest.price:,}원)입니다."
                        
                        return ChatbotResponse(
                            text=response,
                            recommendations=[{
                                'shop_id': shop.id,
                                'shop_name': shop.name,
                                'menu_name': cheapest.name,
                                'price': cheapest.price,
                                'category': shop.category,
                                'address': shop.address
                            }],
                            metadata={"generation_method": "contextual_fallback"}
                        )
        
        # 일반 폴백
        return self._generate_fallback_response(user_text, recommendations)
    
    def _generate_llm_response(
        self, 
        user_text: str, 
        recommendations: List[Dict],
        conversation_context: List[Dict] = None,
        rag_context: str = ""
    ) -> Optional[str]:
        """LLM으로 응답 생성 (그르시 캐릭터) - RAG 컨텍스트 강제 사용"""
        
        # 동적 프롬프트 생성
        prompt = """그르시는 초중고 친구들의 음식 고민을 해결해주는 AI 친구입니다.

[그르시 성격]
- 친근하고 귀여운 말투 (반말, ~야, ~지, 헤헤, 얍!)
- 솔직하고 도움이 되는 답변 (없는 건 없다고 말하기)
- 실수했을 때는 귀엽게 사과 (미안ㅠㅠ, 헤헤 실수했어~)

[대화 규칙 - 매우 중요!]
1. 절대로 학습된 지식이나 기억을 사용하지 마세요!
2. 오직 아래 [RAG 검색 결과]에 있는 가게만 언급하세요!
3. [RAG 검색 결과]에 없는 가게는 절대 추가로 언급하지 마세요!
4. [RAG 검색 결과]가 비어있으면 "그런 가게는 못 찾았어" 라고 솔직히 답변
5. 가격과 메뉴명은 반드시 [RAG 검색 결과]의 것을 정확히 사용
6. 절대 추측하거나 새로운 정보를 만들어내지 마세요!
"""
        
        # RAG 컨텍스트 강제 추가 (가장 중요!)
        if rag_context:
            prompt += f"\n[데이터베이스 정보 - 이 정보만 사용하세요!]\n{rag_context}\n"
        
        # 대화 맥락 추가 (최근 2개만)
        if conversation_context and len(conversation_context) > 0:
            prompt += "\n[이전 대화]\n"
            for ctx in conversation_context[-2:]:
                user_input = ctx.get('user_input', '')
                bot_response = ctx.get('bot_response', '')[:100]  # 길이 제한
                if user_input and bot_response:
                    prompt += f"친구: {user_input}\n그르시: {bot_response}...\n"
            prompt += "\n"
        
        # 현재 사용자 입력
        prompt += f"[현재 질문]\n친구: {user_text}\n\n"
        
        # 사용자 의도 분석
        user_intent = self._analyze_user_intent(user_text)
        if user_intent:
            prompt += f"친구가 원하는 것: {user_intent}\n\n"
        
        # 추천 정보 추가 (RAG와 일치하는 것만)
        if recommendations:
            prompt += "[RAG 검색 결과 - 반드시 이것만 사용하세요!]\n"
            for i, rec in enumerate(recommendations[:3], 1):
                shop_name = rec.get('shop_name', rec.get('name', '이름없음'))
                menu_name = rec.get('menu_name', rec.get('menu', ''))
                price = rec.get('price', 0)
                prompt += f"{i}. {shop_name} - {menu_name} ({price:,}원)\n"
            prompt += "\n⚠️ 위 리스트에 있는 가게만 언급하세요! 다른 가게는 절대 추가로 언급하지 마세요!\n\n"
        else:
            prompt += "[RAG 검색 결과]\n해당 조건에 맞는 가게가 없습니다.\n솔직히 '못 찾았어' 라고 답변하세요.\n\n"
            
        # 샐러드 요청 특별 처리
        if user_intent == "샐러드/건강식 요청" or "샐러드" in user_text:
            prompt += "참고: 데이터베이스에 샐러드 전문점이 없어요. 건강한 대안을 제시해주세요.\n\n"
        
        prompt += """너는 '그르시'라는 음식 추천 캐릭터야. 친근하게 반말로 대답해줘.

그르시의 답변:"""
        
        # LLM 호출
        try:
            # generate_text 메서드 사용 (A.X 모델)
            if self.model and hasattr(self.model, 'generate_text'):
                result = self.model.generate_text(
                    prompt=prompt,
                    max_new_tokens=200,  # 100 -> 200으로 증가
                    temperature=0.7
                )
                if isinstance(result, dict) and 'text' in result:
                    return result['text'].strip()
            else:
                # 모델이 없을 때 기본 응답 생성
                if recommendations:
                    shop_names = [rec['shop_name'] for rec in recommendations[:3]]
                    return f"다음 가게들을 추천해드립니다: {', '.join(shop_names)}"
                else:
                    return "원하시는 조건에 맞는 가게를 찾지 못했습니다."
                    
        except Exception as e:
            logger.error(f"LLM 호출 오류: {e}")
            # 오류 시에도 기본 응답
            if recommendations:
                shop_names = [rec['shop_name'] for rec in recommendations[:3]]
                return f"추천 가게: {', '.join(shop_names)}"
            
        return None
    
    def generate_general_response(self, user_input: str, system_prompt: str, 
                                 conversation_context: List[Dict] = None) -> Optional[str]:
        """일반 대화를 위한 LLM 응답 생성 (추천 없이)"""
        
        prompt = f"""당신은 친근한 음식 추천 챗봇 '나비얌'입니다.
        
[시스템 지시사항]
{system_prompt}

[대화 규칙]
- 친근하고 자연스러운 한국어 사용
- 이모티콘은 적절히 사용 (과하지 않게)
- 음식 추천과 관련된 도움을 줄 준비가 되어있음을 자연스럽게 표현
"""
        
        # 대화 맥락 추가
        if conversation_context and len(conversation_context) > 0:
            prompt += "\n[이전 대화]\n"
            for ctx in conversation_context[-3:]:  # 최근 3개만
                user = ctx.get('user_input', '')
                bot = ctx.get('bot_response', '')[:100]  # 길이 제한
                if user and bot:
                    prompt += f"사용자: {user}\n나비얌: {bot}...\n"
            prompt += "\n"
        
        # 현재 입력
        prompt += f"[현재 대화]\n사용자: {user_input}\n\n나비얌의 응답:"
        
        # LLM 호출
        try:
            if self.model and hasattr(self.model, 'generate_text'):
                result = self.model.generate_text(
                    prompt=prompt,
                    max_new_tokens=150,
                    temperature=0.8  # 일반 대화는 좀 더 창의적으로
                )
                if isinstance(result, dict) and 'text' in result:
                    return result['text'].strip()
            else:
                # 모델이 없을 때 기본 응답
                if '안녕' in user_input:
                    return "안녕하세요! 오늘 뭐 드시고 싶으세요?"
                elif '고마' in user_input or '감사' in user_input:
                    return "천만에요! 맛있게 드세요!"
                elif '잘가' in user_input or '바이' in user_input:
                    return "다음에 또 맛있는 거 추천해드릴게요! 안녕히 가세요!"
                else:
                    return "네! 어떤 음식을 추천해드릴까요?"
                    
        except Exception as e:
            logger.error(f"일반 대화 LLM 호출 오류: {e}")
            # 오류 시 기본 응답
            return "무엇을 도와드릴까요?"
        
        return None
    
    def _generate_fallback_response(self, user_text: str, recommendations: List[Dict]) -> ChatbotResponse:
        """폴백 응답 생성 (그르시 캐릭터)"""
        
        # 사용자 의도 파악
        intent = self._analyze_user_intent(user_text)
        
        if '샐러드' in user_text and not recommendations:
            response = "앗, 미안! 샐러드 가게는 아직 없어... 😅 대신 건강한 한식은 어때? 비빔밥이나 나물 같은 거 말이야!"
        elif recommendations:
            if intent == '샐러드/건강식 요청':
                response = "샐러드는 없지만 건강한 메뉴 찾았어! 얍! 🥗\n\n"
            else:
                response = "짠! 맛있는 거 찾았다! 😋\n\n"
            
            for i, rec in enumerate(recommendations, 1):
                note = rec.get('note', '')
                if note:
                    response += f"{i}. {rec['shop_name']} - {rec['menu_name']} ({rec['price']:,}원) [{note}]\n"
                else:
                    response += f"{i}. {rec['shop_name']} - {rec['menu_name']} ({rec['price']:,}원)\n"
        else:
            # 그르시 스타일 기본 응답들
            if '안녕' in user_text:
                response = "안녕! 나는 그르시야~ 오늘 뭐 먹을래? 😊"
            elif '다른' in user_text or '더' in user_text:
                response = "음... 다른 거? 치킨, 피자, 한식 중에 뭐가 좋아?"
            elif any(word in user_text for word in ['먹', '추천', '뭐']):
                response = "헤헤, 뭐 먹을지 고민이구나! 치킨? 피자? 아니면 따뜻한 국물 요리?"
            elif '그게' in user_text or '뭔데' in user_text:
                response = "아, 그건 말이야... 음... 더 자세히 물어봐줄래? 😅"
            else:
                response = "응? 뭐 찾고 있어? 맛있는 거 추천해줄게!"
        
        return ChatbotResponse(
            text=response,
            recommendations=recommendations,
            metadata={
                "generation_method": "fallback",
                "character": "그르시",
                "user_intent": intent,
                "llm_usage_rate": f"{(self.llm_success_count/self.generation_count)*100:.1f}%"
            }
        )