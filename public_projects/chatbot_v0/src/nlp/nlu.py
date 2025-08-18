"""
자연어 이해 (NLU) 모듈
사용자 입력에서 의도와 엔티티 추출
"""

import re
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass
from datetime import datetime, time

from src.data.data_structure import IntentType, ExtractedEntity, ExtractedInfo, ConfidenceLevel, LearningData
from .preprocessor import NaviyamTextPreprocessor, EmotionType
from .llm_normalizer import LLMNormalizedOutput
from src.utils.categories import FOOD_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class IntentPattern:
    """의도 패턴"""
    intent: IntentType
    keywords: List[str]
    patterns: List[str]
    weight: float = 1.0


class NaviyamNLU:
    """나비얌 자연어 이해 엔진"""

    def __init__(self, nlu_config=None, use_preprocessor: bool = True, use_4bit: bool = True, model=None):
        """
        Args:
            nlu_config: NLUConfig 객체 (옵션)
            use_preprocessor: 전처리기 사용 여부
            use_4bit: 4비트 양자화 사용 여부 (호환성)
            model: A.X 모델 인스턴스 (AI 기반 의도 파악용)
        """
        # NLUConfig가 전달된 경우 설정 저장
        self.config = nlu_config
        self.use_4bit = use_4bit
        self.model = model  # A.X 모델 저장
        
        # 전처리기 설정 - config가 있으면 config에서, 없으면 인자에서
        if nlu_config and hasattr(nlu_config, 'use_preprocessor'):
            use_preprocessor = getattr(nlu_config, 'use_preprocessor', True)
        
        self.preprocessor = NaviyamTextPreprocessor() if use_preprocessor else None

        # 의도 분류 패턴들
        self.intent_patterns = self._build_intent_patterns()

        # 엔티티 추출 패턴들
        self.entity_patterns = self._build_entity_patterns()

        # 맥락 정보 (대화 이력)
        self.context_memory = {}

        # 학습 데이터 수집기 (새로 추가)
        self.learning_data_collector = None  # 나중에 주입받을 예정

    def _build_intent_patterns(self) -> List[IntentPattern]:
        """의도 분류 패턴 구축"""
        patterns = [
            # 음식 추천 요청
            IntentPattern(
                intent=IntentType.FOOD_REQUEST,
                keywords=['먹고싶어', '추천', '맛집', '뭐먹', '음식', '메뉴'] + 
                        [cat.replace("/", "") for cat in FOOD_CATEGORIES] + 
                        ['김치찌개', '된장찌개', '라면', '떡볶이', '짜장면', '짬뽕', '탕수육', '초밥', '돈까스', '카레', '쌀국수', '팟타이', '샌드위치', '도시락'],
                patterns=[
                    r'.*(먹고\s*싶|드시고\s*싶).*',
                    r'.*(추천|소개).*',
                    r'.*(뭐\s*먹|무엇.*먹).*',
                    r'.*(맛집|맛있는.*곳).*',
                    r'.*(메뉴.*있|있.*메뉴).*',
                    r'.*(치킨|피자|햄버거|파스타|한식|중식|일식|양식|분식|아시안|베이커리|편의점|마트).*',
                    r'.*(김치찌개|된장찌개|라면|떡볶이|짜장면|짬뽕|탕수육|초밥|돈까스|카레).*'
                ],
                weight=2.0
            ),

            # 예산 관련 질문
            IntentPattern(
                intent=IntentType.BUDGET_INQUIRY,
                keywords=['원', '돈', '예산', '비싸', '싸', '저렴', '가격', '얼마'],
                patterns=[
                    r'.*\d+\s*(원|만원|천원).*',
                    r'.*(얼마|가격|비용).*',
                    r'.*(비싸|싸|저렴|가성비).*',
                    r'.*(예산|돈|부족).*'
                ],
                weight=1.3
            ),

            # 위치 관련 질문
            IntentPattern(
                intent=IntentType.LOCATION_INQUIRY,
                keywords=['근처', '주변', '가까운', '여기서', '우리동네', '지역'],
                patterns=[
                    r'.*(근처|주변|가까운).*',
                    r'.*(여기서|이곳에서).*',
                    r'.*(우리.*동네|동네.*맛집).*',
                    r'.*(거리|위치|어디).*'
                ],
                weight=1.2
            ),

            # 시간/운영시간 질문
            IntentPattern(
                intent=IntentType.TIME_INQUIRY,
                keywords=['지금', '언제', '시간', '열려', '영업', '문열어', '몇시'],
                patterns=[
                    r'.*(지금|현재).*',
                    r'.*(언제|몇시|시간).*',
                    r'.*(열려|영업|문.*열).*',
                    r'.*(닫혀|문.*닫|영업.*끝).*'
                ],
                weight=1.1
            ),

            # 쿠폰/할인 관련
            IntentPattern(
                intent=IntentType.COUPON_INQUIRY,
                keywords=['쿠폰', '할인', '혜택', '이벤트', '공짜', '무료', '싸게'],
                patterns=[
                    r'.*(쿠폰|할인).*',
                    r'.*(혜택|이벤트).*',
                    r'.*(공짜|무료|공돈).*',
                    r'.*(싸게|저렴하게).*'
                ],
                weight=1.0
            ),

            # 메뉴 옵션 (맵기, 양 조절 등)
            IntentPattern(
                intent=IntentType.MENU_OPTION,
                keywords=['맵게', '안맵게', '곱배기', '많이', '적게', '크게', '작게'],
                patterns=[
                    r'.*(맵게|안.*맵|매운|순한).*',
                    r'.*(곱배기|많이|적게).*',
                    r'.*(크게|작게|사이즈).*',
                    r'.*(토핑|추가|옵션).*'
                ],
                weight=0.9
            ),

            # 급식카드 잔액 확인
            IntentPattern(
                intent=IntentType.BALANCE_CHECK,
                keywords=['잔액', '급식카드', '카드', '얼마', '남았', '확인'],
                patterns=[
                    r'.*(잔액|잔돈).*',
                    r'.*(급식.*카드|카드.*잔액).*',
                    r'.*(얼마.*남|남은.*돈).*',
                    r'.*(카드.*확인|확인.*카드).*'
                ],
                weight=1.2
            ),
            
            # 급식카드 충전
            IntentPattern(
                intent=IntentType.BALANCE_CHARGE,
                keywords=['충전', '채우', '넣어', '더', '부족'],
                patterns=[
                    r'.*(충전|채우|넣어).*',
                    r'.*(카드.*충전|충전.*카드).*',
                    r'.*(돈.*부족|잔액.*부족).*',
                    r'.*(더.*넣|돈.*더).*'
                ],
                weight=1.1
            ),
            
            # 일반 대화
            IntentPattern(
                intent=IntentType.GENERAL_CHAT,
                keywords=['안녕', '고마워', '감사', '잘먹었어', '맛있었어', '좋았어'],
                patterns=[
                    r'.*(안녕|하이|헬로).*',
                    r'.*(고마워|감사|ㄱㅅ).*',
                    r'.*(잘.*먹었|맛있었|좋았).*',
                    r'.*(어떻게|어때|괜찮).*'
                ],
                weight=0.8
            ),

            # 대화 종료
            IntentPattern(
                intent=IntentType.GOODBYE,
                keywords=['안녕', '바이', '끝', '그만', '나가'],
                patterns=[
                    r'.*(안녕|바이|빠이).*',
                    r'.*(끝|그만|나가|종료).*',
                    r'.*(고마워|감사).*'
                ],
                weight=0.7
            )
        ]

        return patterns

    def _build_entity_patterns(self) -> Dict[str, List[str]]:
        """엔티티 추출 패턴 구축"""
        return {
            'food_types': [
                # 카테고리 패턴
                r'(' + '|'.join(FOOD_CATEGORIES).replace("/", "|") + ')',
                # 구체적인 메뉴 패턴
                r'(김치찌개|된장찌개|라면|떡볶이|치킨|피자)',
                r'(짜장면|짬뽕|탕수육|초밥|돈까스|카레)',
                r'(쌀국수|팟타이|샌드위치|도시락|삼각김밥)',
                r'(아메리카노|라떼|케이크|빵|과자)'
            ],
            'budget_amounts': [
                r'(\d+)\s*(원|만원|천원)',
                r'(\d{1,2})\s*천',
                r'(\d{1,3})\s*만'
            ],
            'locations': [
                # 구체적인 지역명을 먼저 매칭
                r'(강남|홍대|신촌|명동|이태원|부평|판교|분당|성수|건대|잠실|노원|송파|마포|서초|관악|동작|용산|중구|종로|성북|도봉|은평|서대문|동대문|중랑|광진|성동|영등포|구로|금천|강동|강북|부천|코엑스)(?=\s|$|에서|에|쪽|근처|주변)',
                # 정확한 행정구역 패턴
                r'([가-힣]{2,4}(?:시|구|동|읍|면|리|로|길))(?=\s|$|에서|에|쪽|근처|주변)',
                # 지하철역 패턴
                r'([가-힣]+역)(?=\s|$|에서|에|쪽|근처|주변)',
                # 특정 위치 키워드와 함께 나오는 경우만
                r'(?:우리|이|그|저)\s*([가-힣]+)(?=에서|에)',  # '우리 학교에서', '이 동네에서' 등
                # 일반적인 위치 표현
                r'(근처|주변|가까운|여기|거기|저기)(?=\s|$)',
                # 상대적 위치
                r'(우리\s*동네|동네|학교|회사|집)(?=\s|$|에서|근처)'
            ],
            'companions': [
                r'(친구|가족|엄마|아빠|애인)',
                r'(혼자|같이|함께)',
                r'(형|누나|언니|오빠|동생)'
            ],
            'time_expressions': [
                r'(지금|현재|바로)',
                r'(오늘|내일|모레)',
                r'(아침|점심|저녁|밤)',
                r'(\d{1,2})시'
            ],
            'taste_preferences': [
                r'(매운|매운거|매운음식|매운걸)',
                r'(순한|순한거|순한음식|안매운|매운거안좋아)',
                r'(상관없어|괜찮아|다좋아|어떤거든)'
            ],
            'menu_options': [
                r'(맵게|안.*맵게|매운|순한)',
                r'(곱배기|많이|적게)',
                r'(크게|작게|라지|스몰)'
            ]
        }

    def extract_info(self, user_input: Any) -> ExtractedInfo:
        """
        사용자 입력을 받아 의도와 엔티티를 추출하는 메인 인터페이스.
        UserInput 객체 또는 순수 텍스트를 처리할 수 있습니다.
        
        Args:
            user_input: UserInput 객체 또는 텍스트 문자열
            
        Returns:
            ExtractedInfo: 추출된 의도와 엔티티 정보
        """
        if hasattr(user_input, 'text'):  # UserInput 객체인 경우
            text = user_input.text
            user_id = getattr(user_input, 'user_id', None)
        else:  # 순수 텍스트인 경우
            text = str(user_input)
            user_id = None
            
        return self.extract_intent_and_entities(text, user_id)
    
    def extract_intent_and_entities(self, text: str, user_id: str = None) -> ExtractedInfo:
        """의도와 엔티티 동시 추출"""
        # 전처리
        if self.preprocessor:
            preprocess_result = self.preprocessor.preprocess(text)
            processed_text = preprocess_result.normalized_text
        else:
            processed_text = text
            preprocess_result = None

        # 의도 추출
        intent, intent_confidence = self._extract_intent(processed_text, preprocess_result)

        # 엔티티 추출
        entities = self._extract_entities(processed_text, intent)

        # 전체 신뢰도 계산
        overall_confidence = self._calculate_overall_confidence(
            intent_confidence, entities, processed_text
        )

        if overall_confidence >= 0.8:
            confidence_level_enum = ConfidenceLevel.HIGH
        elif overall_confidence >= 0.6:
            confidence_level_enum = ConfidenceLevel.MEDIUM
        elif overall_confidence >= 0.4:
            confidence_level_enum = ConfidenceLevel.MEDIUM_LOW
        elif overall_confidence >= 0.2:
            confidence_level_enum = ConfidenceLevel.LOW
        else:
            confidence_level_enum = ConfidenceLevel.VERY_LOW

        # 맥락 정보 업데이트
        if user_id:
            self._update_context(user_id, intent, entities)

        # ExtractedInfo 생성
        extracted_info = ExtractedInfo(
            intent=intent,
            entities=entities,
            confidence=overall_confidence,
            raw_text=text,
            confidence_level=confidence_level_enum
        )

        # 학습 데이터 수집 (새로 추가)
        if user_id:
            self._collect_learning_data(text, extracted_info, user_id, preprocess_result)

        return extracted_info

    def _extract_intent(self, text: str, preprocess_result=None) -> Tuple[IntentType, float]:
        """의도 추출 - AI 기반 우선, 패턴 폴백"""
        # 1. AI 모델이 있으면 AI 기반 의도 파악 시도
        if self.model:
            try:
                ai_intent, ai_confidence = self._extract_intent_with_ai(text)
                if ai_confidence > 0.6:  # AI가 확신하면 바로 사용
                    return ai_intent, ai_confidence
            except Exception as e:
                logger.warning(f"AI 의도 파악 실패: {e}")
        
        # 2. AI가 없거나 실패하면 기존 패턴 기반으로 폴백
        text_lower = text.lower()
        intent_scores = {}

        # 패턴 기반 점수 계산
        for pattern in self.intent_patterns:
            score = 0

            # 키워드 매칭
            for keyword in pattern.keywords:
                if keyword in text_lower:
                    score += 1

            # 정규식 패턴 매칭
            for regex_pattern in pattern.patterns:
                if re.search(regex_pattern, text_lower):
                    score += 2

            # 가중치 적용
            final_score = score * pattern.weight

            if final_score > 0:
                intent_scores[pattern.intent] = final_score

        # 전처리 결과 활용한 보정
        if preprocess_result:
            self._adjust_intent_with_preprocessing(intent_scores, preprocess_result)

        # 최고 점수 의도 선택
        if not intent_scores:
            return IntentType.GENERAL_CHAT, 0.3

        best_intent = max(intent_scores, key=intent_scores.get)
        max_score = intent_scores[best_intent]

        # 신뢰도 정규화 (0-1 범위)
        total_score = sum(intent_scores.values())
        confidence = min(max_score / max(total_score, 1), 1.0)

        return best_intent, confidence
    
    def _extract_intent_with_ai(self, text: str) -> Tuple[IntentType, float]:
        """
        AI 모델을 사용한 의도 파악
        세부적인 맥락 이해와 복잡한 요청 처리 가능
        """
        # 프롬프트 생성
        prompt = f"""사용자의 다음 메시지를 분석해주세요:
사용자: "{text}"

다음 의도 중 가장 적합한 것을 선택하고, 확신도(0-1)를 함께 제시해주세요:
1. food_request: 음식 추천 요청 (예: 치킨 먹고 싶어, 맛있는 거 추천해줘)
2. budget_inquiry: 예산 관련 질문 (예: 5천원으로 뭐 먹지?, 저렴한 게 없나?)
3. location_inquiry: 위치 관련 질문 (예: 근처 맛집, 강남역 치킨)
4. coupon_inquiry: 쿠폰/할인 관련 (예: 쿠폰 있어?, 할인 되는 곳)
5. balance_check: 급식카드 잔액 확인 (예: 잔액, 급식카드 얼마 남았어?)
6. general_chat: 일반 대화 (예: 안녕, 고마워)
7. goodbye: 대화 종료 (예: 잘가, 바이)

특히 주의할 점:
- "양념치킨 없나", "후라이드 추천해줘" 같은 구체적인 음식 요청도 food_request입니다.
- "추천해줘", "뭐 먹지?" 같은 간단한 요청도 food_request입니다.
- 불만이나 부정적인 표현이 있어도 맥락에 따라 판단하세요.

응답 형식: 
의도: [intent_type]
확신도: [0.0-1.0]
설명: [간단한 이유]"""
        
        try:
            # AI 모델로 분석
            response = self.model.generate(prompt, max_new_tokens=50)
            
            # 응답 파싱
            lines = response.strip().split('\n')
            intent_str = None
            confidence = 0.5
            
            for line in lines:
                if '의도:' in line:
                    intent_str = line.split(':')[1].strip()
                elif '확신도:' in line:
                    try:
                        confidence = float(line.split(':')[1].strip())
                    except:
                        confidence = 0.5
            
            # IntentType으로 변환
            intent_map = {
                'food_request': IntentType.FOOD_REQUEST,
                'budget_inquiry': IntentType.BUDGET_INQUIRY,
                'location_inquiry': IntentType.LOCATION_INQUIRY,
                'coupon_inquiry': IntentType.COUPON_INQUIRY,
                'balance_check': IntentType.BALANCE_CHECK,
                'general_chat': IntentType.GENERAL_CHAT,
                'goodbye': IntentType.GOODBYE
            }
            
            intent = intent_map.get(intent_str, IntentType.GENERAL_CHAT)
            return intent, confidence
            
        except Exception as e:
            logger.error(f"AI 의도 추출 오류: {e}")
            return IntentType.GENERAL_CHAT, 0.3

    def _adjust_intent_with_preprocessing(self, intent_scores: Dict, preprocess_result):
        """전처리 결과로 의도 점수 보정"""
        # 감정 정보 활용
        if preprocess_result.emotion == EmotionType.EXCITED:
            intent_scores[IntentType.FOOD_REQUEST] = intent_scores.get(IntentType.FOOD_REQUEST, 0) + 0.5
        elif preprocess_result.emotion == EmotionType.DISAPPOINTED:
            intent_scores[IntentType.GENERAL_CHAT] = intent_scores.get(IntentType.GENERAL_CHAT, 0) + 0.3

        # 키워드 정보 활용
        for keyword in preprocess_result.extracted_keywords:
            if keyword.startswith('budget:'):
                intent_scores[IntentType.BUDGET_INQUIRY] = intent_scores.get(IntentType.BUDGET_INQUIRY, 0) + 1.0
            elif keyword.startswith('foods:') or keyword.startswith('categories:'):
                intent_scores[IntentType.FOOD_REQUEST] = intent_scores.get(IntentType.FOOD_REQUEST, 0) + 1.0
            elif keyword.startswith('companion:'):
                intent_scores[IntentType.LOCATION_INQUIRY] = intent_scores.get(IntentType.LOCATION_INQUIRY, 0) + 0.5

    def _extract_entities(self, text: str, intent: IntentType) -> ExtractedEntity:
        """엔티티 추출"""
        entities = ExtractedEntity()
        text_lower = text.lower()

        # 음식 종류 추출
        entities.food_type = self._extract_food_type(text_lower)

        # 예산 추출
        entities.budget = self._extract_budget(text_lower)

        # 위치 선호도 추출
        entities.location_preference = self._extract_location_preference(text_lower)

        # 동반자 추출
        entities.companions = self._extract_companions(text_lower)

        # 시간 선호도 추출
        entities.time_preference = self._extract_time_preference(text_lower)

        # 메뉴 옵션 추출
        entities.menu_options = self._extract_menu_options(text_lower)

        # 특별 요구사항 추출
        entities.special_requirements = self._extract_special_requirements(text_lower, intent)

        return entities

    def _extract_food_type(self, text: str) -> Optional[str]:
        """음식 종류 추출 - AI 기반 세부 인식"""
        # 1. AI 모델이 있으면 세부 요청까지 파악
        if self.model:
            try:
                # 양념치킨, 후라이드치킨 등 세부 요청 분석
                food_detail = self._extract_food_detail_with_ai(text)
                if food_detail:
                    return food_detail
            except Exception as e:
                logger.warning(f"AI 음식 타입 추출 실패: {e}")
        
        # 2. 기존 패턴 매칭으로 폴백
        for pattern in self.entity_patterns['food_types']:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    def _extract_food_detail_with_ai(self, text: str) -> Optional[str]:
        """
        AI로 세부적인 음식 요청 파악
        예: '양념치킨' -> '치킨-양념', '후라이드' -> '치킨-후라이드'
        """
        try:
            prompt = f"""사용자가 요청한 음식을 분석해주세요:
사용자: "{text}"

음식 카테고리와 세부 요청을 구분해주세요:
예시:
- "양념치킨 먹고 싶어" -> 카테고리: 치킨, 세부: 양념
- "후라이드 추천해줘" -> 카테고리: 치킨, 세부: 후라이드
- "매운 짜장면" -> 카테고리: 중식, 세부: 매운짜장면
- "그냥 추천해줘" -> 카테고리: 일반, 세부: 없음

응답 형식:
카테고리: [카테고리명]
세부: [세부요청 또는 '없음']"""
            
            response = self.model.generate(prompt, max_new_tokens=30)
            
            # 파싱
            category = None
            detail = None
            
            for line in response.strip().split('\n'):
                if '카테고리:' in line:
                    category = line.split(':')[1].strip()
                elif '세부:' in line:
                    detail = line.split(':')[1].strip()
            
            # 세부 요청이 있으면 포함해서 반환
            if detail and detail != '없음':
                return f"{category}-{detail}"
            elif category:
                return category
            
            return None
            
        except Exception as e:
            logger.error(f"AI 음식 세부 추출 오류: {e}")
            return None

    def _extract_budget(self, text: str) -> Optional[int]:
        """예산 추출 (원 단위)"""
        if self.preprocessor:
            return self.preprocessor.extract_budget_info(text)

        # 간단한 예산 추출
        for pattern in self.entity_patterns['budget_amounts']:
            match = re.search(pattern, text)
            if match:
                amount = int(match.group(1))
                if '만' in match.group(0):
                    return amount * 10000
                elif '천' in match.group(0):
                    return amount * 1000
                else:
                    return amount
        return None

    def _extract_location_preference(self, text: str) -> Optional[str]:
        """위치 선호도 추출 - 맥락 이해 개선"""
        # 음식 카테고리 사전 (더 포괄적으로 확장)
        food_categories = [
            '한식', '중식', '일식', '양식', '치킨', '피자', '떡볶이', '김밥', 
            '라면', '죽', '도시락', '샐러드', '디저트', '카페', '빵', '버거',
            '분식', '패스트푸드', '편의점', '마라탕', '짜장면', '짬뽕', '초밥',
            '베이커리', '브런치', '스테이크', '파스타', '리조또', '샤브샤브',
            '곱창', '막창', '족발', '보쌈', '찜닭', '불고기', '갈비', '삼겹살',
            '국수', '칼국수', '냉면', '우동', '라멘', '돈까스', '커리', '스시',
            '회', '포케', '샌드위치', '타코', '부리또', '햄버거', '핫도그'
        ]
        
        # 실제 지역명 키워드 (위치로 확실한 것들)
        location_keywords = [
            '강남', '홍대', '신촌', '명동', '이태원', '부평', '판교', '분당', 
            '성수', '건대', '잠실', '노원', '송파', '마포', '서초', '관악', 
            '동작', '용산', '중구', '종로', '성북', '도봉', '은평', '서대문',
            '동대문', '중랑', '광진', '성동', '영등포', '구로', '금천', '강동',
            '강북', '부천', '코엑스', '여의도', '을지로', '충무로', '혜화',
            '대학로', '압구정', '청담', '삼성', '역삼', '선릉', '강변'
        ]
        
        # '쪽으로' 패턴 특별 처리
        jjok_pattern = r'([가-힣]+)쪽으로'
        jjok_match = re.search(jjok_pattern, text)
        
        if jjok_match:
            extracted_word = jjok_match.group(1)
            
            # 음식 카테고리인지 먼저 확인
            if extracted_word in food_categories:
                logger.debug(f"'{extracted_word}쪽으로'는 음식 카테고리 요청으로 판단, 위치 추출 안함")
                return None
            
            # 명확한 지역명인 경우만 위치로 인식
            if extracted_word in location_keywords:
                logger.debug(f"위치 추출: '{extracted_word}' (from '{text}')")
                return extracted_word
            
            # 방향 표현 (동/서/남/북)인 경우 위치로 인식
            if extracted_word in ['동', '서', '남', '북', '동쪽', '서쪽', '남쪽', '북쪽']:
                logger.debug(f"방향 추출: '{extracted_word}' (from '{text}')")
                return extracted_word
        
        # 기존 패턴 매칭 (쪽으로가 없는 경우)
        for pattern in self.entity_patterns['locations']:
            match = re.search(pattern, text)
            if match:
                extracted = match.group(1)
                
                # 음식 카테고리가 아니고, 실제 위치 키워드인 경우만
                if extracted and extracted not in food_categories:
                    # 위치 키워드에 포함되거나 일반적인 위치 표현인 경우
                    if (extracted in location_keywords or 
                        extracted in ['근처', '주변', '가까운', '여기', '거기', '저기', '동네', '학교', '회사', '집']):
                        logger.debug(f"위치 추출: '{extracted}' (from '{text}')")
                        return extracted
        
        return None

    def _extract_companions(self, text: str) -> List[str]:
        """동반자 추출"""
        if self.preprocessor:
            return self.preprocessor.extract_companions(text)

        companions = []
        for pattern in self.entity_patterns['companions']:
            matches = re.findall(pattern, text)
            companions.extend(matches)

        return list(set(companions))

    def _extract_time_preference(self, text: str) -> Optional[str]:
        """시간 선호도 추출"""
        for pattern in self.entity_patterns['time_expressions']:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_menu_options(self, text: str) -> List[str]:
        """메뉴 옵션 추출"""
        options = []
        for pattern in self.entity_patterns['menu_options']:
            matches = re.findall(pattern, text)
            options.extend(matches)

        return list(set(options))

    def _extract_special_requirements(self, text: str, intent: IntentType) -> List[str]:
        """특별 요구사항 추출"""
        requirements = []

        # 의도별 특별 요구사항
        if intent == IntentType.FOOD_REQUEST:
            if '빨리' in text or '급해' in text:
                requirements.append('urgent')
            if '건강한' in text or '다이어트' in text:
                requirements.append('healthy')
            if '뜨거운' in text:
                requirements.append('hot')
            if '차가운' in text or '시원한' in text:
                requirements.append('cold')

        elif intent == IntentType.BUDGET_INQUIRY:
            if '싸게' in text or '저렴하게' in text:
                requirements.append('cheap')
            if '가성비' in text:
                requirements.append('value_for_money')

        elif intent == IntentType.LOCATION_INQUIRY:
            if '걸어서' in text:
                requirements.append('walking_distance')
            if '지하철' in text or '버스' in text:
                requirements.append('public_transport')

        return requirements

    def _calculate_overall_confidence(self, intent_confidence: float, entities: ExtractedEntity, text: str) -> float:
        """전체 신뢰도 계산"""
        # 기본 의도 신뢰도
        confidence = intent_confidence

        # 엔티티 추출 성공도로 보정
        entity_count = 0
        extracted_count = 0

        # 엔티티별 가중치
        entity_weights = {
            'food_type': 2.0,
            'budget': 1.5,
            'location_preference': 1.0,
            'companions': 0.5,
            'time_preference': 0.5,
            'menu_options': 0.3
        }

        for attr, weight in entity_weights.items():
            entity_count += weight
            value = getattr(entities, attr, None)
            if value:
                if isinstance(value, list) and len(value) > 0:
                    extracted_count += weight
                elif value is not None:
                    extracted_count += weight

        # 엔티티 추출 비율로 신뢰도 보정
        if entity_count > 0:
            entity_ratio = extracted_count / entity_count
            confidence = confidence * 0.7 + entity_ratio * 0.3

        # 텍스트 길이로 추가 보정 (너무 짧거나 길면 신뢰도 감소)
        text_len = len(text.strip())
        if text_len < 3:
            confidence *= 0.5
        elif text_len > 100:
            confidence *= 0.9

        return min(confidence, 1.0)

    def _update_context(self, user_id: str, intent: IntentType, entities: ExtractedEntity):
        """사용자 맥락 정보 업데이트"""
        if user_id not in self.context_memory:
            self.context_memory[user_id] = {
                'last_intent': None,
                'last_entities': None,
                'conversation_count': 0,
                'preferred_food_types': [],
                'typical_budget': None,
                'last_update': datetime.now()
            }

        context = self.context_memory[user_id]
        context['last_intent'] = intent
        context['last_entities'] = entities
        context['conversation_count'] += 1
        context['last_update'] = datetime.now()

        # 선호도 누적
        if entities.food_type:
            if entities.food_type not in context['preferred_food_types']:
                context['preferred_food_types'].append(entities.food_type)

        if entities.budget and context['typical_budget'] is None:
            context['typical_budget'] = entities.budget

    def get_context_suggestions(self, user_id: str, current_intent: IntentType) -> List[str]:
        """맥락 기반 제안 생성"""
        if user_id not in self.context_memory:
            return []

        context = self.context_memory[user_id]
        suggestions = []

        # 이전 대화 기반 제안
        if context['last_intent'] == IntentType.FOOD_REQUEST and current_intent == IntentType.BUDGET_INQUIRY:
            if context['typical_budget']:
                suggestions.append(f"지난번에 {context['typical_budget']}원 정도 찾으셨는데, 비슷한 가격대로 드릴까요?")

        # 선호 음식 기반 제안
        if context['preferred_food_types'] and current_intent == IntentType.FOOD_REQUEST:
            fav_food = context['preferred_food_types'][0]
            suggestions.append(f"평소 {fav_food} 좋아하시니까 비슷한 메뉴 추천드릴까요?")

        return suggestions

    def validate_extracted_info(self, extracted_info: ExtractedInfo) -> Tuple[bool, List[str]]:
        """추출된 정보 검증"""
        warnings = []
        is_valid = True

        # 예산 검증
        if extracted_info.entities.budget:
            budget = extracted_info.entities.budget
            if budget < 1000:
                warnings.append("예산이 너무 적습니다")
                is_valid = False
            elif budget > 100000:
                warnings.append("예산이 너무 많습니다")

        # 의도-엔티티 일관성 검증
        intent = extracted_info.intent
        entities = extracted_info.entities

        if intent == IntentType.BUDGET_INQUIRY and not entities.budget:
            warnings.append("예산 질문이지만 구체적인 금액이 없습니다")

        if intent == IntentType.FOOD_REQUEST and not entities.food_type:
            warnings.append("음식 요청이지만 구체적인 음식 종류가 없습니다")

        # 신뢰도 검증
        if extracted_info.confidence < 0.3:
            warnings.append("추출 신뢰도가 낮습니다")
            is_valid = False

        return is_valid, warnings

    def clear_context(self, user_id: str = None):
        """맥락 정보 초기화"""
        if user_id:
            if user_id in self.context_memory:
                del self.context_memory[user_id]
        else:
            self.context_memory.clear()

        logger.info(f"맥락 정보 초기화: {user_id or 'ALL'}")

    def get_debug_info(self, extracted_info: ExtractedInfo, text: str) -> Dict[str, Any]:
        """디버그 정보 생성"""
        return {
            "original_text": text,
            "intent": extracted_info.intent.value,
            "confidence": extracted_info.confidence,
            "confidence_level": extracted_info.confidence_level.value,
            "entities": {
                "food_type": extracted_info.entities.food_type,
                "budget": extracted_info.entities.budget,
                "location_preference": extracted_info.entities.location_preference,
                "companions": extracted_info.entities.companions,
                "time_preference": extracted_info.entities.time_preference,
                "menu_options": extracted_info.entities.menu_options,
                "special_requirements": extracted_info.entities.special_requirements
            },
            "preprocessing_used": self.preprocessor is not None,
            "context_available": len(self.context_memory) > 0
        }

    def _collect_learning_data(self, text: str, extracted_info: ExtractedInfo, user_id: str, preprocess_result=None):
        """NLU 단계에서 학습 데이터 수집"""
        if not self.learning_data_collector:
            return

        # NLU에서 추출 가능한 학습 Feature들
        learning_features = {}

        # 기본 추출 정보
        learning_features["nlu_intent"] = extracted_info.intent.value
        learning_features["nlu_confidence"] = extracted_info.confidence
        learning_features["text_length"] = len(text)
        learning_features["normalized_text"] = preprocess_result.normalized_text if preprocess_result else text

        # 엔티티 기반 Feature들
        if extracted_info.entities:
            entities = extracted_info.entities

            # 음식 관련 Feature
            if entities.food_type:
                learning_features["food_category_mentioned"] = entities.food_type
                learning_features["has_specific_food_request"] = True
            else:
                learning_features["has_specific_food_request"] = False

            # 예산 관련 Feature
            if entities.budget:
                learning_features["budget_mentioned"] = entities.budget
                learning_features["budget_range"] = self._categorize_budget(entities.budget)

            # 동반자 관련 Feature
            if entities.companions:
                learning_features["companions_mentioned"] = entities.companions
                learning_features["dining_alone"] = "혼자" in entities.companions
                learning_features["group_dining"] = len(entities.companions) > 1

            # 위치 관련 Feature
            if entities.location_preference:
                learning_features["location_specified"] = True
                learning_features["location_type"] = entities.location_preference

            # 시간/상황 관련 Feature
            if entities.time_preference:
                learning_features["time_specified"] = True
                learning_features["urgency_indicated"] = entities.time_preference in ["지금", "바로", "급해"]

            # 메뉴 옵션 관련 Feature
            if entities.menu_options:
                learning_features["menu_customization_requested"] = True
                learning_features["spice_preference"] = any(
                    opt in entities.menu_options for opt in ["맵게", "안맵게", "매운", "순한"])

        # 전처리 결과 기반 Feature들
        if preprocess_result:
            learning_features["emotion_detected"] = preprocess_result.emotion.value
            learning_features["keywords_count"] = len(preprocess_result.extracted_keywords)
            learning_features["has_emotional_expression"] = preprocess_result.emotion != "neutral"

        # 맥락 정보 기반 Feature들
        if user_id in self.context_memory:
            context = self.context_memory[user_id]
            learning_features["conversation_turn"] = context['conversation_count']
            learning_features["repeat_user"] = context['conversation_count'] > 1
            learning_features["has_food_history"] = len(context['preferred_food_types']) > 0

        # 학습 데이터 수집기에 전달
        self.learning_data_collector.collect_nlu_features(user_id, learning_features)

    def _categorize_budget(self, budget: int) -> str:
        """예산을 카테고리로 분류"""
        if budget < 5000:
            return "low"
        elif budget < 15000:
            return "medium"
        elif budget < 30000:
            return "high"
        else:
            return "premium"

    def set_learning_data_collector(self, collector):
        """학습 데이터 수집기 설정"""
        self.learning_data_collector = collector

    def extract_learning_features(self, text: str, user_id: str = None) -> Dict[str, Any]:
        """학습용 Feature 추출 (별도 메서드)"""
        extracted_info = self.extract_intent_and_entities(text, user_id)

        features = {
            # 기본 정보
            "text": text,
            "text_length": len(text),
            "word_count": len(text.split()),

            # NLU 결과
            "intent": extracted_info.intent.value,
            "confidence": extracted_info.confidence,
            "confidence_level": extracted_info.confidence_level.value,

            # 엔티티 정보
            "has_food_type": extracted_info.entities.food_type is not None,
            "has_budget": extracted_info.entities.budget is not None,
            "has_location": extracted_info.entities.location_preference is not None,
            "has_companions": len(extracted_info.entities.companions) > 0,
            "has_time_pref": extracted_info.entities.time_preference is not None,
            "has_menu_options": len(extracted_info.entities.menu_options) > 0,

            # 복잡성 지표
            "entity_count": sum([
                1 if extracted_info.entities.food_type else 0,
                1 if extracted_info.entities.budget else 0,
                1 if extracted_info.entities.location_preference else 0,
                len(extracted_info.entities.companions),
                1 if extracted_info.entities.time_preference else 0,
                len(extracted_info.entities.menu_options)
            ]),

            # 맥락 정보
            "user_context_available": user_id in self.context_memory if user_id else False
        }

        return features

    def analyze_intent_patterns(self, texts: List[str]) -> Dict[str, Any]:
        """여러 텍스트의 의도 패턴 분석 (분석용)"""
        intent_distribution = {}
        confidence_scores = []

        for text in texts:
            extracted_info = self.extract_intent_and_entities(text)

            intent = extracted_info.intent.value
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
            confidence_scores.append(extracted_info.confidence)

        return {
            "total_samples": len(texts),
            "intent_distribution": intent_distribution,
            "avg_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            "low_confidence_count": sum(1 for score in confidence_scores if score < 0.5),
            "high_confidence_count": sum(1 for score in confidence_scores if score >= 0.8)
        }

    def extract_from_llm_normalized(
            self,
            user_input: str,
            llm_output: LLMNormalizedOutput,
            user_id: str = None
    ) -> ExtractedInfo:
        """LLM 구조화 결과를 받아서 더 정교한 NLU 수행"""

        # LLM이 정리한 텍스트로 기본 NLU 수행
        base_extracted = self.extract_intent_and_entities(
            llm_output.normalized_text, user_id
        )

        # LLM 식별 엔티티와 통합
        enhanced_entities = self._merge_entities(
            base_extracted.entities,
            llm_output.identified_entities
        )

        # 신뢰도 조합 (NLU + LLM)
        combined_confidence = (
                base_extracted.confidence * 0.6 +
                llm_output.confidence * 0.4
        )

        # 신뢰도 레벨 재계산
        confidence_level = self._calculate_confidence_level(combined_confidence)

        # 학습 데이터 생성
        if user_id and self.learning_data_collector:
            learning_features = self._extract_llm_nlu_features(
                user_input, llm_output, base_extracted, enhanced_entities
            )
            self.learning_data_collector.collect_nlu_features(user_id, learning_features)

        return ExtractedInfo(
            intent=base_extracted.intent,
            entities=enhanced_entities,
            confidence=combined_confidence,
            raw_text=user_input,
            confidence_level=confidence_level
        )

    def _merge_entities(
            self,
            nlu_entities: ExtractedEntity,
            llm_entities: Dict[str, Any]
    ) -> ExtractedEntity:
        """NLU와 LLM 엔티티 병합"""

        # 새로운 ExtractedEntity 생성
        merged = ExtractedEntity()

        # 음식 종류 (LLM 우선, NLU로 보완)
        merged.food_type = (
                llm_entities.get("food_type") or
                nlu_entities.food_type
        )

        # 예산 (LLM 우선, NLU로 보완)
        merged.budget = (
                llm_entities.get("budget") or
                nlu_entities.budget
        )

        # 동반자 (두 결과 합치기)
        llm_companions = llm_entities.get("companions", []) or []
        nlu_companions = nlu_entities.companions or []
        merged.companions = list(set(llm_companions + nlu_companions))

        # 위치 (LLM 우선)
        merged.location_preference = (
                llm_entities.get("location") or
                nlu_entities.location_preference
        )

        # 시간 (기존 NLU 우선)
        merged.time_preference = nlu_entities.time_preference

        # 메뉴 옵션 (기존 NLU 우선)
        merged.menu_options = nlu_entities.menu_options or []

        # 특별 요청사항 (두 결과 합치기)
        llm_requests = llm_entities.get("special_requests", []) or []
        nlu_requests = nlu_entities.special_requirements or []

        # LLM의 새로운 필드들 추가
        if llm_entities.get("taste_preference"):
            llm_requests.append(f"taste:{llm_entities['taste_preference']}")

        if llm_entities.get("urgency"):
            llm_requests.append(f"urgency:{llm_entities['urgency']}")

        merged.special_requirements = list(set(llm_requests + nlu_requests))

        return merged

    def _extract_llm_nlu_features(
            self,
            original_input: str,
            llm_output: LLMNormalizedOutput,
            nlu_result: ExtractedInfo,
            merged_entities: ExtractedEntity
    ) -> Dict[str, Any]:
        """LLM→NLU 파이프라인 학습 데이터 생성"""

        features = {
            # 원본 vs 정규화 비교
            "original_text": original_input,
            "llm_normalized_text": llm_output.normalized_text,
            "text_complexity_reduced": len(original_input) > len(llm_output.normalized_text),

            # LLM 성능
            "llm_confidence": llm_output.confidence,
            "llm_json_parsing_success": bool(llm_output.identified_entities),
            "context_resolution_attempted": bool(llm_output.context_resolution),

            # 엔티티 추출 비교
            "llm_entities_count": len(llm_output.identified_entities),
            "nlu_entities_count": self._count_entities(nlu_result.entities),
            "merged_entities_count": self._count_entities(merged_entities),

            # 품질 지표
            "entity_agreement": self._calculate_entity_agreement(
                nlu_result.entities, llm_output.identified_entities
            ),
            "confidence_improvement": merged_entities != nlu_result.entities,

            # 파이프라인 메타데이터
            "pipeline_method": "llm_nlu",
            "processing_successful": llm_output.confidence > 0.5
        }

        return features

    def _count_entities(self, entities: ExtractedEntity) -> int:
        """엔티티 개수 세기"""
        count = 0
        if entities.food_type:
            count += 1
        if entities.budget:
            count += 1
        if entities.location_preference:
            count += 1
        if entities.companions:
            count += len(entities.companions)
        if entities.time_preference:
            count += 1
        if entities.menu_options:
            count += len(entities.menu_options)
        if entities.special_requirements:
            count += len(entities.special_requirements)
        return count

    def _calculate_entity_agreement(self, nlu_entities: ExtractedEntity, llm_entities: Dict) -> float:
        """엔티티 일치도 계산"""
        agreements = 0
        total_checks = 0

        # 음식 종류 비교
        if nlu_entities.food_type and llm_entities.get("food_type"):
            total_checks += 1
            if nlu_entities.food_type == llm_entities["food_type"]:
                agreements += 1

        # 예산 비교
        if nlu_entities.budget and llm_entities.get("budget"):
            total_checks += 1
            if abs(nlu_entities.budget - llm_entities["budget"]) < 1000:  # 1000원 오차 허용
                agreements += 1

        # 동반자 비교
        if nlu_entities.companions and llm_entities.get("companions"):
            total_checks += 1
            nlu_set = set(nlu_entities.companions)
            llm_set = set(llm_entities["companions"])
            if nlu_set & llm_set:  # 교집합이 있으면 일치
                agreements += 1

        return agreements / max(total_checks, 1)

    def _calculate_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """신뢰도 레벨 계산"""
        if confidence >= 0.8:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return ConfidenceLevel.MEDIUM_LOW
        elif confidence >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW


# 편의 함수들
def quick_nlu(text: str, user_id: str = None) -> ExtractedInfo:
    """빠른 NLU 처리 (편의 함수)"""
    nlu = NaviyamNLU()
    return nlu.extract_intent_and_entities(text, user_id)


def analyze_user_intent(text: str, include_debug: bool = False) -> Dict[str, Any]:
    """사용자 의도 분석 (편의 함수)"""
    nlu = NaviyamNLU()
    extracted_info = nlu.extract_intent_and_entities(text)

    result = {
        "intent": extracted_info.intent.value,
        "confidence": extracted_info.confidence,
        "entities": {
            "food_type": extracted_info.entities.food_type,
            "budget": extracted_info.entities.budget,
            "companions": extracted_info.entities.companions
        }
    }

    if include_debug:
        result["debug"] = nlu.get_debug_info(extracted_info, text)

    return result


def batch_nlu_processing(texts: List[str], user_id: str = None) -> List[ExtractedInfo]:
    """배치 NLU 처리 (편의 함수)"""
    nlu = NaviyamNLU()
    results = []

    for text in texts:
        extracted_info = nlu.extract_intent_and_entities(text, user_id)
        results.append(extracted_info)

    return results