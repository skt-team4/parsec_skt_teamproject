#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
선택적 파이프라인 구현
설정에 따라 RAG → Wide&Deep → A.X 활성화/비활성화
"""

import configparser
import logging
from typing import List, Dict, Optional
from pathlib import Path
import torch

from src.data.data_structure import ChatbotResponse, ExtractedInfo, IntentType
from datetime import datetime
from src.inference.integrated_pipeline import IntegratedPipeline
from src.utils.category_helper import generate_fallback_message, get_similar_categories
from src.recommendation.ranking_model import PersonalizedRanker, RankingModelConfig
from src.utils.location_utils import haversine_filter, get_coords_from_text, get_distance_description
from src.utils.tmap_api import TMapRouteAPI
from src.inference.data_collector import LearningDataCollector
from src.inference.user_manager import NaviyamUserManager
from src.data.session_data_structure import (
    SessionData, SessionDataManager, Interaction, 
    SystemOutput, UserFeedback
)
import time

logger = logging.getLogger(__name__)


class SelectivePipeline:
    """설정 기반 선택적 파이프라인"""
    
    def __init__(self, knowledge, llm_generator, config_path="config/pipeline_config.ini", 
                 enable_data_collection=True):
        self.knowledge = knowledge
        self.llm_generator = llm_generator
        self.enable_data_collection = enable_data_collection
        
        # 설정 로드
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding='utf-8')
        
        # 파이프라인 모드
        self.mode = self.config.get('pipeline', 'mode', fallback='basic')
        logger.info(f"Pipeline mode: {self.mode}")
        
        # RAG 설정
        self.rag_enabled = self.config.getboolean('rag', 'enabled', fallback=True)
        self.rag_max_candidates = self.config.getint('rag', 'max_candidates', fallback=10)
        self.strict_category = self.config.getboolean('rag', 'strict_category_filter', fallback=True)
        
        # Wide&Deep 설정
        self.wide_deep_enabled = self.config.getboolean('wide_deep', 'enabled', fallback=False)
        self.wide_deep_top_k = self.config.getint('wide_deep', 'top_k', fallback=3)
        
        # Wide&Deep 모델 로드 (활성화된 경우만)
        self.wide_deep_model = None
        self.personalized_ranker = None
        if self.wide_deep_enabled:
            model_path = self.config.get('wide_deep', 'model_path', 
                                        fallback='training/models/wide_deep/model_20250810.pt')
            self._load_wide_deep_model(model_path)
        
        # 디버그 설정
        self.debug = self.config.getboolean('debug', 'log_pipeline_steps', fallback=False)
        
        # IntegratedPipeline 인스턴스 생성 (개선된 RAG 사용을 위해)
        self.integrated_pipeline = None
        try:
            logger.info("Initializing IntegratedPipeline for improved RAG search...")
            self.integrated_pipeline = IntegratedPipeline(
                knowledge=self.knowledge,
                llm_generator=self.llm_generator,
                use_rag=True  # RAG 활성화
            )
            if hasattr(self.integrated_pipeline, 'rag_retriever'):
                logger.info("✓ IntegratedPipeline with RAG retriever successfully initialized")
            else:
                logger.warning("IntegratedPipeline created but rag_retriever not found")
        except Exception as e:
            logger.error(f"Failed to initialize IntegratedPipeline: {e}")
            self.integrated_pipeline = None
        
        # 데이터 수집 및 사용자 관리 초기화
        if self.enable_data_collection:
            self.data_collector = LearningDataCollector(
                save_path="data/learning_data",
                buffer_size=100
            )
            self.user_manager = NaviyamUserManager(
                save_path="data/user_profiles",
                enable_personalization=True
            )
            # 세션 기반 데이터 매니저 추가
            self.session_manager = SessionDataManager()
            self.active_sessions = {}  # user_id -> session_id 매핑
            logger.info("Data collection and user management enabled")
        else:
            self.data_collector = None
            self.user_manager = None
            self.session_manager = None
            self.active_sessions = {}
    
    def process(self, user_input: str, extracted_info: ExtractedInfo, 
                user_profile: Dict = None, conversation_context: List[Dict] = None,
                user_location: Dict = None, user_id: str = "anonymous") -> ChatbotResponse:
        """
        선택적 파이프라인 처리
        
        Args:
            user_input: 사용자 입력 텍스트
            extracted_info: NLU 추출 정보
            user_profile: 사용자 프로필
            conversation_context: 대화 컨텍스트
            user_location: GPS 좌표 {'latitude': float, 'longitude': float}
        """
        
        # 시작 시간 기록
        start_time = time.time()
        
        if self.debug:
            logger.info(f"=== Pipeline Start: {self.mode} ===")
            logger.info(f"Intent: {extracted_info.intent}")
        logger.info(f"NLU 추출 결과:")
        logger.info(f"  - food_type: {extracted_info.entities.food_type if extracted_info.entities else None}")
        logger.info(f"  - location: {extracted_info.entities.location_preference if extracted_info.entities else None}")
        logger.info(f"  - budget: {extracted_info.entities.budget if extracted_info.entities else None}")
        logger.info(f"  - companions: {extracted_info.entities.companions if extracted_info.entities else []}")
        logger.info(f"  - time: {extracted_info.entities.time_preference if extracted_info.entities else None}")
        logger.info(f"  - menu_options: {extracted_info.entities.menu_options if extracted_info.entities else []}")
        
        # 사용자 프로필 로드 또는 생성
        if self.user_manager and not user_profile:
            user_profile = self.user_manager.get_or_create_user_profile(user_id)
        
        # 세션 처리
        session = None
        turn_id = 1
        if self.session_manager:
            # 사용자의 활성 세션 확인 또는 생성
            if user_id not in self.active_sessions:
                session = self.session_manager.create_session(user_id)
                self.active_sessions[user_id] = session.session_id
            else:
                session_id = self.active_sessions[user_id]
                session = self.session_manager.active_sessions.get(session_id)
                if session:
                    turn_id = len(session.interactions) + 1
        
        # === 의도별 처리 분기 ===
        
        # 1. 단순 LLM 처리 (대화 관리)
        if extracted_info.intent in [IntentType.GREETING, IntentType.CHITCHAT, 
                                    IntentType.THANKS, IntentType.GOODBYE]:
            return self._handle_general_chat(user_input, extracted_info, conversation_context)
        
        # 2. 무의미한 입력 처리
        elif extracted_info.intent == IntentType.NONSENSE:
            return self._handle_nonsense(user_input)
        
        # 3. 길 안내 요청
        elif extracted_info.intent == IntentType.NAVIGATION_REQUEST:
            return self._handle_navigation(user_input, extracted_info, user_location)
        
        # 4. 이전 추천 조회
        elif extracted_info.intent == IntentType.RECOMMENDATION_HISTORY:
            return self._handle_recommendation_history(user_id, conversation_context)
        
        # 5. 요청 수정
        elif extracted_info.intent == IntentType.MODIFY_REQUEST:
            return self._handle_modify_request(user_input, extracted_info, conversation_context)
        
        # 6. 알레르기/식이제한 정보
        elif extracted_info.intent in [IntentType.ALLERGY_INFO, IntentType.DIETARY_RESTRICTION]:
            return self._handle_dietary_restriction(user_input, extracted_info, user_profile)
        
        # 7. 예약 요청
        elif extracted_info.intent == IntentType.RESERVATION_REQUEST:
            return self._handle_reservation(user_input, extracted_info)
        
        # 8. 급식카드 관련
        elif extracted_info.intent == IntentType.BALANCE_CHECK:
            return self._handle_balance_check(user_input, user_id)
        elif extracted_info.intent == IntentType.BALANCE_CHARGE:
            return self._handle_balance_charge()
        
        # 9. 비교 요청
        elif extracted_info.intent == IntentType.COMPARISON:
            return self._handle_comparison(user_input, extracted_info)
        
        # 10. 결제 수단 문의
        elif extracted_info.intent == IntentType.PAYMENT_METHOD:
            return self._handle_payment_method(user_input, extracted_info)
        
        # 11. 평점/리뷰 요청
        elif extracted_info.intent in [IntentType.RATING_REQUEST, IntentType.REVIEW_REQUEST]:
            return self._handle_review_request(user_input, extracted_info)
        
        # 12. 영양 정보
        elif extracted_info.intent == IntentType.NUTRITIONAL_INFO:
            return self._handle_nutritional_info(user_input, extracted_info)
        
        # 나머지는 추천 엔진 사용 (기존 로직)
        # FOOD_REQUEST, SHOP_INQUIRY, MENU_INQUIRY, PRICE_INQUIRY, 
        # BUDGET_INQUIRY, TIME_INQUIRY, DELIVERY_INQUIRY, COUPON_INQUIRY,
        # SPECIAL_REQUEST, MENU_REVIEW, MENU_OPTION, LOCATION_INQUIRY
        # Step 1: RAG 검색
        rag_results = []
        if self.rag_enabled:
            rag_results = self._perform_rag_search(user_input, extracted_info)
            if self.debug:
                logger.info(f"RAG results: {len(rag_results)} candidates")
        
        # Fallback 처리: 검색 결과가 없을 때
        if not rag_results:
            logger.info("No RAG results found. Generating fallback response.")
            
            # Fallback 메시지 생성
            location = extracted_info.entities.location_preference if extracted_info.entities else None
            food_type = extracted_info.entities.food_type if extracted_info.entities else None
            fallback_message = generate_fallback_message(location, food_type)
            
            # Fallback 응답 생성
            response = self._generate_ax_response(
                user_input=user_input,
                recommendations=[],
                conversation_context=conversation_context,
                fallback_prompt=fallback_message
            )
        else:
            # 정상 처리: 검색 결과가 있을 때
            # Step 2: Wide&Deep 개인화 (선택적)
            final_recommendations = []
            if self.wide_deep_enabled and self.mode == 'wide_deep':
                final_recommendations = self._apply_wide_deep(rag_results, user_profile, extracted_info)
                if self.debug:
                    logger.info(f"Wide&Deep results: {len(final_recommendations)} recommendations")
            else:
                # Wide&Deep 비활성화 시 RAG 결과 직접 사용
                final_recommendations = self._convert_rag_to_recommendations(rag_results[:self.wide_deep_top_k])
                if self.debug:
                    logger.info(f"Using RAG results directly: {len(final_recommendations)} items")
                    # RAG 결과 상세 로그 추가
                    for i, rec in enumerate(final_recommendations[:3], 1):
                        shop_name = rec.get('shop_name', 'Unknown')
                        menu_name = rec.get('menu_name', 'Unknown') 
                        price = rec.get('price', 0)
                        logger.info(f"  RAG #{i}: {shop_name} - {menu_name} ({price:,}원)")
            
            # Step 2.5: T맵 경로 정보 추가 (상위 3개만)
            if user_location and final_recommendations:
                final_recommendations = self._enrich_with_tmap_info(
                    final_recommendations, user_location
                )
            
            # Step 3: A.X 모델로 자연어 생성
            response = self._generate_ax_response(
                user_input=user_input,
                recommendations=final_recommendations,
                conversation_context=conversation_context
            )
        
        # 실행 시간 계산
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # 메타데이터 추가
        response.metadata['pipeline_mode'] = self.mode
        response.metadata['rag_used'] = self.rag_enabled
        response.metadata['wide_deep_used'] = self.wide_deep_enabled and self.mode == 'wide_deep'
        response.metadata['response_time_ms'] = response_time_ms
        
        # 세션 기반 데이터 수집
        if self.session_manager and session:
            try:
                # NLU 출력 준비
                nlu_output = {
                    'intent': extracted_info.intent.value if hasattr(extracted_info.intent, 'value') else str(extracted_info.intent),
                    'entities': {},
                    'confidence': extracted_info.confidence
                }
                if extracted_info.entities:
                    if hasattr(extracted_info.entities, 'location_preference') and extracted_info.entities.location_preference:
                        nlu_output['entities']['location'] = extracted_info.entities.location_preference
                    if hasattr(extracted_info.entities, 'food_type') and extracted_info.entities.food_type:
                        nlu_output['entities']['food_type'] = extracted_info.entities.food_type
                
                # 시스템 출력 준비
                system_output = SystemOutput()
                
                # RAG 결과 저장 (음식 추천의 경우)
                if extracted_info.intent == IntentType.FOOD_REQUEST and 'rag_results' in locals():
                    # RAG 후보 저장 (상위 20개)
                    for i, shop in enumerate(rag_results[:20]):
                        system_output.rag_candidates.append({
                            'shop_id': shop.id,
                            'score': getattr(shop, 'haversine_distance', 0) if hasattr(shop, 'haversine_distance') else i
                        })
                    
                    # 추천 결과 저장
                    if response.recommendations:
                        system_output.displayed_recommendations = [
                            rec.get('shop_id') for rec in response.recommendations
                            if rec.get('shop_id')
                        ]
                        # Wide&Deep 점수 저장 (있으면)
                        for rec in response.recommendations:
                            if rec.get('shop_id'):
                                system_output.recommendation_scores.append({
                                    'shop_id': rec.get('shop_id'),
                                    'score': rec.get('wide_deep_score', 0.0)
                                })
                
                system_output.generated_response = response.text
                system_output.response_time_ms = response_time_ms
                
                # Interaction 생성 및 세션에 추가
                interaction = Interaction(
                    turn_id=turn_id,
                    timestamp=datetime.now(),
                    user_input={'text': user_input},
                    nlu_output=nlu_output,
                    system_output=system_output
                )
                
                self.session_manager.add_interaction(session.session_id, interaction)
                
                # 기존 데이터 콜렉터도 호출 (호환성)
                if self.data_collector:
                    # NLU 특징 수집
                    nlu_features = {
                        'user_text': user_input,
                        'intent': nlu_output['intent'],
                        'confidence': nlu_output['confidence'],
                        'entities': nlu_output['entities']
                    }
                    self.data_collector.collect_nlu_features(user_id, nlu_features)
                
                # 사용자 프로필 업데이트
                if self.user_manager:
                    self.user_manager.update_user_interaction(
                        user_id=user_id,
                        extracted_info=extracted_info
                    )
                
                logger.debug(f"Session data collected: session={session.session_id}, turn={turn_id}")
                
            except Exception as e:
                logger.error(f"Session data collection failed: {e}")
                import traceback
                traceback.print_exc()
        
        if self.debug:
            logger.info(f"=== Pipeline Complete ===")
        
        return response
    
    def _perform_rag_search(self, user_input: str, extracted_info: ExtractedInfo) -> List:
        """
        RAG 검색 수행 (개선된 버전: FAISS 우선)
        1. FAISS 벡터 검색으로 의미적 후보 확보
        2. 후처리로 위치/카테고리 필터링
        """
        
        # 위치와 카테고리 정보 추출
        location = extracted_info.entities.location_preference if extracted_info.entities else None
        food_type = extracted_info.entities.food_type if extracted_info.entities else None
        
        # 디버그 로그
        if self.debug:
            logger.info(f"RAG Search - Location: {location}, Food Type: {food_type}")
        
        # integrated_pipeline의 retriever 사용 (개선된 검색 로직)
        if hasattr(self, 'integrated_pipeline') and hasattr(self.integrated_pipeline, 'rag_retriever'):
            # retriever.search()가 이미 FAISS 우선 + 후처리 필터링을 수행
            from rag.retriever import Document
            documents = self.integrated_pipeline.rag_retriever.search(user_input)
            
            # Document를 Shop 객체로 변환
            filtered_shops = []
            logger.info(f"Converting {len(documents)} documents to shops...")
            
            for i, doc in enumerate(documents):
                logger.debug(f"Document #{i}: type={type(doc)}, id={getattr(doc, 'id', 'N/A')}")
                
                if hasattr(doc, 'get_metadata'):
                    metadata = doc.get_metadata()
                    logger.debug(f"  Metadata: {metadata}")
                    
                    # Document 타입별 처리
                    doc_type = metadata.get('type')
                    if doc_type == 'shop':
                        # ShopDocument인 경우, shop_id를 직접 추출
                        shop_id_str = doc.id.replace('shop_', '') if doc.id.startswith('shop_') else doc.id
                        try:
                            shop_id = int(shop_id_str)
                            if shop_id in self.knowledge.shops:
                                filtered_shops.append(self.knowledge.shops[shop_id])
                                logger.debug(f"  Added shop: {self.knowledge.shops[shop_id].name}")
                            else:
                                logger.warning(f"  Shop ID {shop_id} not found in knowledge base")
                        except ValueError:
                            logger.warning(f"  Invalid shop ID format: {shop_id_str}")
                    
                    elif doc_type == 'menu':
                        # MenuDocument인 경우, shop_id를 메타데이터에서 추출
                        shop_id = metadata.get('shop_id')
                        if shop_id and shop_id in self.knowledge.shops:
                            filtered_shops.append(self.knowledge.shops[shop_id])
                            logger.debug(f"  Added shop via menu: {self.knowledge.shops[shop_id].name}")
                        else:
                            logger.warning(f"  Shop ID {shop_id} from menu not found in knowledge base")
                    else:
                        logger.warning(f"  Unknown document type: {doc_type}")
                else:
                    logger.warning(f"  Document has no get_metadata method: {type(doc)}")
            
            # 중복 제거
            unique_shops = []
            seen_ids = set()
            for shop in filtered_shops:
                if shop.id not in seen_ids:
                    unique_shops.append(shop)
                    seen_ids.add(shop.id)
            
            logger.info(f"개선된 RAG 검색: {len(documents)}개 문서 → {len(filtered_shops)}개 변환 → {len(unique_shops)}개 고유 가게")
            return unique_shops[:self.rag_max_candidates]
        
        # 필터링된 가게 목록
        filtered_shops = []
        
        # 위치 기반 필터링 모드 결정
        use_distance_filter = False
        center_coords = None
        
        if location:
            # 위치 텍스트를 좌표로 변환 시도
            center_coords = get_coords_from_text(location)
            if center_coords:
                use_distance_filter = True
                logger.info(f"Using distance filter: {location} → {center_coords}")
        
        if use_distance_filter and center_coords:
            # 거리 기반 필터링 (Haversine)
            all_shops = list(self.knowledge.shops.values())
            
            # 1차: Haversine 거리로 반경 내 가게만 필터
            nearby_shops = haversine_filter(all_shops, center_coords, radius_km=5.0)
            
            # 2차: 카테고리 필터링
            for shop in nearby_shops:
                if not food_type or self._match_category(shop, food_type):
                    filtered_shops.append(shop)
            
            logger.info(f"Distance filter: {len(all_shops)} → {len(nearby_shops)} → {len(filtered_shops)} shops")
        else:
            # 기존 텍스트 매칭 방식 (fallback)
            for shop in self.knowledge.shops.values():
                # 위치 매칭
                if location:
                    if location not in shop.address:
                        continue
                
                # 카테고리 매칭
                if food_type and not self._match_category(shop, food_type):
                    continue
                
                filtered_shops.append(shop)
        
        # 필터링된 결과가 없으면 조건 완화
        if not filtered_shops and location and food_type:
            # 위치만으로 재검색
            for shop in self.knowledge.shops.values():
                if location in shop.address:
                    filtered_shops.append(shop)
                    if len(filtered_shops) >= self.rag_max_candidates:
                        break
        
        # 여전히 없으면 카테고리만으로 검색
        if not filtered_shops and food_type:
            for shop in self.knowledge.shops.values():
                if food_type == "치킨" and shop.category == "치킨":
                    filtered_shops.append(shop)
                elif food_type == "피자" and shop.category == "피자":
                    filtered_shops.append(shop)
                elif food_type == "햄버거" and shop.category in ["패스트푸드", "버거", "햄버거"]:
                    filtered_shops.append(shop)
                
                if len(filtered_shops) >= self.rag_max_candidates:
                    break
        
        # 아무것도 없으면 인기 가게 추천
        if not filtered_shops:
            logger.info(f"No specific results for location='{location}', food_type='{food_type}'. Returning random shops.")
            # 기본 추천: 랜덤하게 몇 개 가게
            all_shops = list(self.knowledge.shops.values())
            if all_shops:
                import random
                random.shuffle(all_shops)
                filtered_shops = all_shops[:min(5, len(all_shops))]
        
        # 결과 반환
        return filtered_shops[:self.rag_max_candidates]
    
    def _match_category(self, shop, food_type: str) -> bool:
        """카테고리 매칭 확인"""
        if not food_type:
            return True
        
        if self.strict_category:
            if food_type == "치킨" and shop.category != "치킨":
                return False
            elif food_type == "피자" and shop.category != "피자":
                return False
            elif food_type == "햄버거" and shop.category not in ["패스트푸드", "버거", "햄버거"]:
                return False
            elif food_type == "한식" and shop.category != "한식":
                return False
            elif food_type == "중식" and shop.category != "중식":
                return False
            elif food_type == "일식" and shop.category != "일식":
                return False
            elif food_type == "양식" and shop.category != "양식":
                return False
            elif food_type == "분식" and shop.category != "분식":
                return False
        
        return True
        
        # 결과 반환 (최대 개수 제한)
        results = filtered_shops[:self.rag_max_candidates]
        
        if self.debug:
            logger.info(f"RAG Search Results: {len(results)} shops found")
        
        return results
    
    def _apply_wide_deep(self, rag_candidates: List, user_profile: Dict, extracted_info: ExtractedInfo) -> List[Dict]:
        """Wide&Deep 모델 적용 (Layer 1 + Layer 2)"""
        
        if not rag_candidates:
            return []
        
        if not self.personalized_ranker:
            logger.info("Using RAG results directly (Wide&Deep not loaded)")
            return self._convert_rag_to_recommendations(rag_candidates[:self.wide_deep_top_k])
        
        try:
            # === Layer 1: 4-Funnel 후보 생성 및 점수 계산 ===
            logger.info(f"Layer 1 시작: {len(rag_candidates)}개 RAG 후보에 대해 4-Funnel 점수 계산")
            
            # CandidateGenerator 초기화 (처음 한 번만)
            if not hasattr(self, 'candidate_generator'):
                from recommendation.candidate_generator import CandidateGenerator, CandidateGenerationConfig
                config = CandidateGenerationConfig()
                config.MAX_TOTAL_CANDIDATES = len(rag_candidates)  # RAG 후보 수만큼
                self.candidate_generator = CandidateGenerator(config)
            
            # 사용자 정보 추출
            user_id = user_profile.get('user_id', 'default') if user_profile else 'default'
            location = extracted_info.entities.location_preference if extracted_info.entities else None
            food_type = extracted_info.entities.food_type if extracted_info.entities else None
            
            # Layer 1 실행: 각 Funnel의 점수 계산
            # 여기서는 RAG 후보들에 대해 각 Funnel 점수를 계산
            layer1_scores = {}
            
            # Popularity Funnel 점수 계산
            try:
                from recommendation.popularity_funnel import PopularityFunnel
                pop_funnel = PopularityFunnel()
                for shop in rag_candidates:
                    # 실제 인기도 점수 계산 (예: 리뷰 수, 평점 등)
                    pop_score = pop_funnel._calculate_popularity_score({
                        'shop_id': shop.id,
                        'rating': getattr(shop, 'rating', 3.5),
                        'review_count': getattr(shop, 'review_count', 10),
                        'is_good_influence_shop': getattr(shop, 'is_good_influence_shop', False)
                    })
                    if shop.id not in layer1_scores:
                        layer1_scores[shop.id] = {}
                    layer1_scores[shop.id]['popularity_score'] = pop_score
            except Exception as e:
                logger.warning(f"Popularity Funnel 계산 실패: {e}")
                for shop in rag_candidates:
                    if shop.id not in layer1_scores:
                        layer1_scores[shop.id] = {}
                    layer1_scores[shop.id]['popularity_score'] = 0.5
            
            # Content Funnel 점수 계산 (쿼리와의 유사도)
            try:
                from recommendation.content_funnel import ContentFunnel
                content_funnel = ContentFunnel()
                query = extracted_info.raw_text if hasattr(extracted_info, 'raw_text') else ''
                for shop in rag_candidates:
                    # 콘텐츠 유사도 점수 계산
                    content_score = content_funnel._calculate_content_similarity(
                        query=query,
                        shop_info={
                            'name': shop.name,
                            'category': shop.category,
                            'description': getattr(shop, 'description', '')
                        }
                    )
                    layer1_scores[shop.id]['content_score'] = content_score
            except Exception as e:
                logger.warning(f"Content Funnel 계산 실패: {e}")
                for shop in rag_candidates:
                    layer1_scores[shop.id]['content_score'] = 0.5
            
            # Contextual Funnel 점수 계산 (시간, 위치 등)
            try:
                from recommendation.contextual_funnel import ContextualFunnel
                from datetime import datetime
                ctx_funnel = ContextualFunnel()
                current_time = datetime.now()
                for shop in rag_candidates:
                    # 상황 기반 점수 계산
                    ctx_score = ctx_funnel._calculate_contextual_score(
                        shop_info={
                            'shop_id': shop.id,
                            'address': shop.address,
                            'category': shop.category,
                            'business_hours': getattr(shop, 'business_hours', '')
                        },
                        user_location=location,
                        current_time=current_time
                    )
                    layer1_scores[shop.id]['contextual_score'] = ctx_score
            except Exception as e:
                logger.warning(f"Contextual Funnel 계산 실패: {e}")
                for shop in rag_candidates:
                    layer1_scores[shop.id]['contextual_score'] = 0.5
            
            # Collaborative Funnel 점수 계산 (사용자 유사도)
            try:
                from recommendation.collaborative_funnel import CollaborativeFunnel
                collab_funnel = CollaborativeFunnel()
                for shop in rag_candidates:
                    # 협업 필터링 점수 계산
                    collab_score = collab_funnel._calculate_collaborative_score(
                        user_id=user_id,
                        shop_id=shop.id,
                        user_type=user_profile.get('user_type', 'general') if user_profile else 'general'
                    )
                    layer1_scores[shop.id]['collaborative_score'] = collab_score
            except Exception as e:
                logger.warning(f"Collaborative Funnel 계산 실패: {e}")
                for shop in rag_candidates:
                    layer1_scores[shop.id]['collaborative_score'] = 0.5
            
            logger.info(f"Layer 1 완료: {len(layer1_scores)}개 가게에 대한 4-Funnel 점수 계산 완료")
            
            # Layer 1 점수를 포함한 후보 리스트 생성
            candidates = []
            for shop in rag_candidates:
                scores = layer1_scores.get(shop.id, {})
                candidate = {
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'category': shop.category,
                    'address': shop.address,
                    'latitude': getattr(shop, 'latitude', 0.0),
                    'longitude': getattr(shop, 'longitude', 0.0),
                    # Layer 1 실제 점수들
                    'popularity_score': scores.get('popularity_score', 0.5),
                    'content_score': scores.get('content_score', 0.5),
                    'collaborative_score': scores.get('collaborative_score', 0.5),
                    'contextual_score': scores.get('contextual_score', 0.5),
                    # Layer 1 종합 점수 (평균)
                    'layer1_score': sum(scores.values()) / len(scores) if scores else 0.5
                }
                candidates.append(candidate)
                
                if self.debug:
                    logger.debug(f"Layer 1 점수 - {shop.name}: "
                               f"Pop={candidate['popularity_score']:.2f}, "
                               f"Cont={candidate['content_score']:.2f}, "
                               f"Ctx={candidate['contextual_score']:.2f}, "
                               f"Collab={candidate['collaborative_score']:.2f}, "
                               f"종합={candidate['layer1_score']:.2f}")
            
            # Layer 1 점수로 1차 정렬 (상위 후보 선별)
            candidates.sort(key=lambda x: x['layer1_score'], reverse=True)
            
            # === Layer 2: Wide&Deep 개인화 랭킹 ===
            logger.info(f"Layer 2 시작: Wide&Deep 모델로 {len(candidates)}개 후보 개인화 랭킹")
            
            # 사용자 프로필 준비
            if not user_profile:
                user_profile = {
                    'user_id': 'default_user',
                    'preferences': {},
                    'history': []
                }
            
            # 컨텍스트 정보 준비 (실제 시간 반영)
            from datetime import datetime
            now = datetime.now()
            hour = now.hour
            
            # 시간대 판단
            if 6 <= hour < 11:
                time_period = 'breakfast'
            elif 11 <= hour < 14:
                time_period = 'lunch'
            elif 14 <= hour < 17:
                time_period = 'snack'
            elif 17 <= hour < 21:
                time_period = 'dinner'
            else:
                time_period = 'late_night'
            
            # 요일 판단
            day_of_week = 'weekend' if now.weekday() >= 5 else 'weekday'
            
            context = {
                'location': extracted_info.entities.location_preference if extracted_info.entities else None,
                'food_type': extracted_info.entities.food_type if extracted_info.entities else None,
                'time': time_period,
                'day_of_week': day_of_week,
                'hour': hour,
                'layer1_scores_available': True  # Layer 1 점수 사용 가능 플래그
            }
            
            # Wide&Deep 모델로 랭킹
            logger.info(f"Layer 2 컨텍스트: 시간={time_period}, 요일={day_of_week}")
            ranked_candidates = self.personalized_ranker.rank_candidates(
                candidates=candidates,
                user_profile=user_profile,
                context=context
            )
            
            logger.info(f"Layer 2 완료: Wide&Deep 랭킹 완료")
            
            # 상위 K개 선택 및 추천 형식으로 변환
            top_candidates = ranked_candidates[:self.wide_deep_top_k]
            recommendations = []
            
            for i, candidate in enumerate(top_candidates, 1):
                shop_id = candidate['shop_id']
                # 해당 가게의 메뉴 찾기
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop_id]
                if shop_menus:
                    menu = min(shop_menus, key=lambda x: x.price)
                    recommendations.append({
                        'shop_id': shop_id,
                        'shop_name': candidate['shop_name'],
                        'menu_name': menu.name,
                        'price': menu.price,
                        'category': candidate['category'],
                        'address': candidate['address'],
                        'wide_deep_score': candidate.get('personalized_score', 0.0),
                        # Layer 1 점수들도 포함 (디버깅/분석용)
                        'layer1_scores': {
                            'popularity': candidate.get('popularity_score', 0),
                            'content': candidate.get('content_score', 0),
                            'contextual': candidate.get('contextual_score', 0),
                            'collaborative': candidate.get('collaborative_score', 0),
                            'total': candidate.get('layer1_score', 0)
                        },
                        'ranking': i  # 최종 순위
                    })
                    
                    if self.debug:
                        logger.debug(f"최종 추천 #{i}: {candidate['shop_name']} "
                                   f"(Layer1={candidate.get('layer1_score', 0):.2f}, "
                                   f"Layer2={candidate.get('personalized_score', 0):.2f})")
            
            logger.info(f"Wide&Deep ranking complete: {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Wide&Deep inference failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to RAG results
            return self._convert_rag_to_recommendations(rag_candidates[:self.wide_deep_top_k])
    
    def _convert_rag_to_recommendations(self, shops: List) -> List[Dict]:
        """Shop 객체를 추천 딕셔너리로 변환"""
        
        recommendations = []
        for shop in shops:
            # 해당 가게의 메뉴 찾기
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                # 가장 저렴한 메뉴 선택
                menu = min(shop_menus, key=lambda x: x.price)
                recommendations.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'menu_name': menu.name,
                    'price': menu.price,
                    'category': shop.category,
                    'address': shop.address
                })
        
        return recommendations
    
    def _generate_ax_response(self, user_input: str, recommendations: List[Dict], 
                             conversation_context: List[Dict] = None,
                             fallback_prompt: str = None) -> ChatbotResponse:
        """A.X 모델로 응답 생성 (fallback 지원)"""
        
        # Fallback 시나리오 처리
        if fallback_prompt:
            return ChatbotResponse(
                text=fallback_prompt,
                recommendations=[],
                metadata={'generator': 'fallback', 'fallback': True}
            )
        
        # 정상 응답 생성
        # LLM generator의 _generate_llm_response 직접 호출
        if hasattr(self.llm_generator, '_generate_llm_response'):
            response_text = self.llm_generator._generate_llm_response(
                user_text=user_input,
                recommendations=recommendations,
                conversation_context=conversation_context,
                rag_context=""  # RAG 컨텍스트는 recommendations로 대체
            )
        else:
            response_text = f"다음 가게들을 추천해드립니다: {', '.join([r['shop_name'] for r in recommendations])}"
        
        return ChatbotResponse(
            text=response_text or "추천 결과를 생성할 수 없습니다.",
            recommendations=recommendations,
            metadata={'generator': 'ax_model'}
        )
    
    def _enrich_with_tmap_info(self, recommendations: List[Dict], user_location: Dict) -> List[Dict]:
        """
        추천 목록에 T맵 경로 정보 추가 (상위 3개만)
        
        Args:
            recommendations: 추천 가게 리스트
            user_location: 사용자 GPS 좌표
        
        Returns:
            T맵 정보가 추가된 추천 리스트
        """
        try:
            tmap = TMapRouteAPI()
            
            # 상위 3개 가게에만 T맵 API 호출
            for i, rec in enumerate(recommendations[:3]):
                try:
                    # 가게 좌표 확인
                    shop_id = rec.get('shop_id')
                    if shop_id and shop_id in self.knowledge.shops:
                        shop = self.knowledge.shops[shop_id]
                        
                        if hasattr(shop, 'latitude') and hasattr(shop, 'longitude'):
                            # 도보 경로 정보
                            walk_info = tmap.get_route_info(
                                user_location['latitude'], user_location['longitude'],
                                shop.latitude, shop.longitude,
                                route_type='pedestrian'
                            )
                            
                            # 대중교통 경로 정보 (선택적)
                            transit_info = tmap.get_route_info(
                                user_location['latitude'], user_location['longitude'],
                                shop.latitude, shop.longitude,
                                route_type='transit'
                            )
                            
                            # 경로 정보 추가
                            if walk_info:
                                rec['walk_time'] = walk_info.get('time_text', '')
                                rec['walk_distance'] = walk_info.get('distance_text', '')
                            
                            if transit_info:
                                rec['transit_time'] = transit_info.get('time_text', '')
                            
                            # T맵 링크 생성
                            from utils.tmap_utils import TmapURLGenerator
                            url_gen = TmapURLGenerator()
                            rec['tmap_url'] = url_gen.generate_web_url(
                                user_location['latitude'], user_location['longitude'],
                                shop.latitude, shop.longitude,
                                start_name="현재 위치",
                                end_name=shop.name,
                                route_type='transit'
                            )
                            
                            logger.info(f"T맵 정보 추가: {shop.name} - 도보 {rec.get('walk_time', 'N/A')}")
                            
                except Exception as e:
                    logger.warning(f"T맵 정보 추가 실패 ({rec.get('shop_name', 'Unknown')}): {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"T맵 연동 오류: {e}")
        
        return recommendations
    
    def _load_wide_deep_model(self, model_path: str):
        """Wide&Deep 모델 로드"""
        try:
            from recommendation.ranking_model import PersonalizedRanker
            
            # PersonalizedRanker 초기화
            self.personalized_ranker = PersonalizedRanker()
            self.personalized_ranker.initialize_model()
            
            # 모델 파일이 존재하면 로드
            if Path(model_path).exists():
                checkpoint = torch.load(model_path, map_location='cpu')
                
                # 체크포인트 구조에 따른 로드
                if isinstance(checkpoint, dict):
                    if 'model_state_dict' in checkpoint:
                        self.personalized_ranker.model.load_state_dict(checkpoint['model_state_dict'])
                    elif 'state_dict' in checkpoint:
                        self.personalized_ranker.model.load_state_dict(checkpoint['state_dict'])
                    else:
                        # 전체 체크포인트를 state_dict로 시도
                        self.personalized_ranker.model.load_state_dict(checkpoint)
                else:
                    # 체크포인트가 직접 state_dict인 경우
                    self.personalized_ranker.model.load_state_dict(checkpoint)
                
                self.personalized_ranker.model.eval()
                self.wide_deep_model = self.personalized_ranker.model
                logger.info(f"Wide&Deep model loaded successfully: {model_path}")
            else:
                logger.warning(f"Wide&Deep model file not found: {model_path}")
                logger.info("Using rule-based ranking instead")
                
        except Exception as e:
            logger.error(f"Failed to load Wide&Deep model: {e}")
            import traceback
            traceback.print_exc()
            # 모델 로드 실패 시도 규칙 기반 ranker 사용
            try:
                from recommendation.ranking_model import PersonalizedRanker
                self.personalized_ranker = PersonalizedRanker()
                logger.info("Fallback to rule-based ranking")
            except:
                self.personalized_ranker = None
                logger.error("Failed to initialize PersonalizedRanker")

    def _handle_general_chat(self, user_input: str, extracted_info: ExtractedInfo, 
                           conversation_context: List[Dict] = None) -> ChatbotResponse:
        """
        일반 대화 처리 - LLM 활용
        
        Args:
            user_input: 사용자 입력
            extracted_info: NLU 추출 정보
            conversation_context: 대화 컨텍스트
        
        Returns:
            LLM 생성 응답
        """
        
        # LLM이 있으면 활용
        if self.llm_generator:
            # 의도별 시스템 프롬프트 설정
            intent_prompts = {
                IntentType.GREETING: "친근한 음식 추천 챗봇으로서 인사를 나누고, 자연스럽게 음식 추천으로 이어가세요.",
                IntentType.CHITCHAT: "친근하게 대화하면서도 음식과 관련된 도움을 제공할 준비가 되어있다는 것을 보여주세요.",
                IntentType.THANKS: "감사 인사에 적절히 응답하고, 추가로 도움이 필요한지 물어보세요.",
                IntentType.GOODBYE: "따뜻한 작별 인사를 하고, 다시 찾아달라고 말씀드리세요."
            }
            
            system_prompt = intent_prompts.get(extracted_info.intent, 
                                               "친근한 음식 추천 챗봇으로서 사용자와 대화하세요.")
            
            # LLM 응답 생성
            try:
                response_text = self.llm_generator.generate_general_response(
                    user_input=user_input,
                    system_prompt=system_prompt,
                    conversation_context=conversation_context
                )
            except AttributeError:
                # generate_general_response 메서드가 없으면 기본 _generate_llm_response 사용
                response_text = self.llm_generator._generate_llm_response(
                    user_text=user_input,
                    recommendations=[],
                    conversation_context=conversation_context,
                    rag_context=system_prompt
                )
            
            return ChatbotResponse(
                text=response_text,
                recommendations=[],
                metadata={
                    'generator': 'llm',
                    'intent': extracted_info.intent.value
                }
            )
        
        # LLM이 없으면 하드코딩된 응답 사용 (폴백)
        else:
            return self._get_hardcoded_response(user_input, extracted_info.intent)
    
    def _handle_nonsense(self, user_input: str) -> ChatbotResponse:
        """무의미한 입력 처리"""
        responses = [
            "죄송하지만 이해하지 못했습니다. 음식 추천이 필요하신가요?",
            "무슨 말씀이신지 잘 모르겠어요. 맛있는 음식을 찾고 계신가요?",
            "음... 다시 한 번 말씀해주시겠어요?",
            "제가 도와드릴 수 있는 음식 추천이 필요하신가요?"
        ]
        
        import random
        return ChatbotResponse(
            text=random.choice(responses),
            recommendations=[],
            metadata={'intent': 'nonsense', 'generator': 'hardcoded'}
        )
    
    def _handle_navigation(self, user_input: str, extracted_info: ExtractedInfo, 
                          user_location: Dict) -> ChatbotResponse:
        """길 안내 처리"""
        
        if not user_location:
            return ChatbotResponse(
                text="현재 위치 정보가 없어 길 안내를 제공할 수 없습니다. 위치 권한을 확인해주세요.",
                recommendations=[],
                metadata={'intent': 'navigation', 'error': 'no_location'}
            )
        
        # 가게명 추출
        shop_name = extracted_info.entities.shop_name if extracted_info.entities and hasattr(extracted_info.entities, 'shop_name') else None
        
        if not shop_name:
            # 문자열에서 가게명 추출 시도
            for shop in self.knowledge.shops.values():
                if shop.name in user_input:
                    shop_name = shop.name
                    break
        
        if not shop_name:
            return ChatbotResponse(
                text="어느 가게로 가는 길을 안내해드릴까요? 가게 이름을 알려주세요.",
                recommendations=[],
                metadata={'intent': 'navigation', 'error': 'no_shop_name'}
            )
        
        # 가게 검색
        target_shop = None
        for shop in self.knowledge.shops.values():
            if shop_name in shop.name or shop.name in shop_name:
                target_shop = shop
                break
        
        if not target_shop:
            return ChatbotResponse(
                text=f"'{shop_name}'을(를) 찾을 수 없습니다. 다른 가게를 말씀해주세요.",
                recommendations=[],
                metadata={'intent': 'navigation', 'error': 'shop_not_found'}
            )
        
        # T맵 경로 정보 생성
        try:
            from utils.tmap_api import TMapRouteAPI
            from utils.tmap_utils import TmapURLGenerator
            
            tmap = TMapRouteAPI()
            
            # 도보 경로
            walk_info = tmap.get_route_info(
                user_location['latitude'], user_location['longitude'],
                target_shop.latitude, target_shop.longitude,
                route_type='pedestrian'
            )
            
            # 대중교통 경로
            transit_info = tmap.get_route_info(
                user_location['latitude'], user_location['longitude'],
                target_shop.latitude, target_shop.longitude,
                route_type='transit'
            )
            
            # T맵 URL 생성
            url_gen = TmapURLGenerator()
            tmap_url = url_gen.generate_web_url(
                user_location['latitude'], user_location['longitude'],
                target_shop.latitude, target_shop.longitude,
                start_name="현재 위치",
                end_name=target_shop.name,
                route_type='transit'
            )
            
            # 응답 텍스트 생성
            response_text = f"📍 **{target_shop.name}** 길 안내\n"
            response_text += f"📌 주소: {target_shop.address}\n\n"
            
            if walk_info:
                response_text += f"🚶 도보: {walk_info.get('time_text', '정보 없음')} ({walk_info.get('distance_text', '')})\n"
            
            if transit_info:
                response_text += f"🚌 대중교통: {transit_info.get('time_text', '정보 없음')}\n"
            
            response_text += f"\n[T맵에서 길찾기]({tmap_url})"
            
            return ChatbotResponse(
                text=response_text,
                recommendations=[{
                    'shop_id': target_shop.id,
                    'shop_name': target_shop.name,
                    'address': target_shop.address,
                    'walk_time': walk_info.get('time_text', '') if walk_info else '',
                    'transit_time': transit_info.get('time_text', '') if transit_info else '',
                    'tmap_url': tmap_url
                }],
                metadata={'intent': 'navigation', 'status': 'success'}
            )
            
        except Exception as e:
            logger.error(f"T맵 API 오류: {e}")
            return ChatbotResponse(
                text=f"📍 **{target_shop.name}**\n주소: {target_shop.address}\n\n길 안내 정보를 가져올 수 없습니다.",
                recommendations=[],
                metadata={'intent': 'navigation', 'error': str(e)}
            )
    
    def _handle_recommendation_history(self, user_id: str, conversation_context: List[Dict]) -> ChatbotResponse:
        """이전 추천 조회"""
        
        # 세션에서 이전 추천 찾기
        if self.session_manager and user_id in self.active_sessions:
            session_id = self.active_sessions[user_id]
            session = self.session_manager.active_sessions.get(session_id)
            
            if session and session.interactions:
                # 마지막 추천 찾기
                for interaction in reversed(session.interactions):
                    if interaction.system_output.displayed_recommendations:
                        shops = []
                        for shop_id in interaction.system_output.displayed_recommendations[:3]:
                            if shop_id in self.knowledge.shops:
                                shop = self.knowledge.shops[shop_id]
                                shops.append(f"• {shop.name} ({shop.address})")
                        
                        if shops:
                            response_text = "이전에 추천드린 가게들입니다:\n\n"
                            response_text += "\n".join(shops)
                            response_text += "\n\n다른 추천이 필요하신가요?"
                            
                            return ChatbotResponse(
                                text=response_text,
                                recommendations=[],
                                metadata={'intent': 'recommendation_history', 'found': True}
                            )
        
        return ChatbotResponse(
            text="이전 추천 내역을 찾을 수 없습니다. 새로운 추천을 원하시나요?",
            recommendations=[],
            metadata={'intent': 'recommendation_history', 'found': False}
        )
    
    def _handle_dietary_restriction(self, user_input: str, extracted_info: ExtractedInfo, 
                                   user_profile: Dict) -> ChatbotResponse:
        """알레르기/식이제한 처리"""
        
        # 알레르기/제한 키워드 추출
        restrictions = {
            '땅콩': "땅콩 알레르기",
            '새우': "갑각류 알레르기",
            '우유': "유제품 알레르기",
            '계란': "계란 알레르기",
            '밀': "글루텐 알레르기",
            '비건': "비건 식단",
            '베지테리언': "채식주의",
            '할랄': "할랄 인증",
            '당뇨': "저당 식단"
        }
        
        found_restrictions = []
        for keyword, description in restrictions.items():
            if keyword in user_input:
                found_restrictions.append(description)
        
        if found_restrictions:
            # 사용자 프로필에 저장
            if user_profile:
                if 'dietary_restrictions' not in user_profile:
                    user_profile['dietary_restrictions'] = []
                user_profile['dietary_restrictions'].extend(found_restrictions)
            
            response_text = f"다음 식이 제한 사항을 확인했습니다: {', '.join(found_restrictions)}\n"
            response_text += "이를 고려하여 음식을 추천해드리겠습니다. 어떤 음식을 드시고 싶으신가요?"
        else:
            response_text = "구체적인 알레르기나 식이 제한 사항을 알려주시면, 그에 맞는 음식을 추천해드리겠습니다."
        
        return ChatbotResponse(
            text=response_text,
            recommendations=[],
            metadata={'intent': 'dietary_restriction', 'restrictions': found_restrictions}
        )
    
    def _handle_balance_check(self, user_input: str, user_id: str) -> ChatbotResponse:
        """급식카드 잔액 확인"""
        return ChatbotResponse(
            text="급식카드 잔액 조회는 다음 방법으로 확인 가능합니다:\n\n"
                 "1. 📱 **급식카드 앱**에서 실시간 조회\n"
                 "2. 🏪 **편의점 ATM**에서 조회\n"
                 "3. ☎️ **고객센터**: 1544-8722\n\n"
                 "잔액 확인 후 맛있는 음식 추천해드릴게요!",
            recommendations=[],
            metadata={'intent': 'balance_check', 'type': 'guide'}
        )
    
    def _handle_balance_charge(self) -> ChatbotResponse:
        """급식카드 충전 안내"""
        return ChatbotResponse(
            text="급식카드 충전 방법을 안내해드릴게요:\n\n"
                 "💳 **충전 방법**\n"
                 "1. 🏪 CU, GS25, 세븐일레븐 등 편의점에서 현금 충전\n"
                 "2. 📱 급식카드 앱에서 계좌이체\n"
                 "3. 🏛️ 동주민센터 방문 충전\n"
                 "4. 🏦 농협/우리은행 ATM\n\n"
                 "충전 후 바로 사용 가능합니다! 맛있는 거 드세요!",
            recommendations=[],
            metadata={'intent': 'balance_charge', 'type': 'guide'}
        )
    
    def _handle_reservation(self, user_input: str, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """예약 요청 처리"""
        return ChatbotResponse(
            text="예약을 원하시는군요! 아쉽게도 직접 예약 기능은 제공하지 않지만,\n"
                 "가게 전화번호를 안내해드릴 수 있습니다.\n\n"
                 "어느 가게에 예약하고 싶으신가요?",
            recommendations=[],
            metadata={'intent': 'reservation_request', 'status': 'not_available'}
        )
    
    def _handle_comparison(self, user_input: str, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """비교 요청 처리"""
        # 간단한 구현 - 추후 개선 필요
        return ChatbotResponse(
            text="두 가게를 비교해드리려면 구체적인 가게 이름을 알려주세요.\n"
                 "예: '신전떡볶이 vs 엽기떡볶이 뭐가 나아?'",
            recommendations=[],
            metadata={'intent': 'comparison'}
        )
    
    def _handle_payment_method(self, user_input: str, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """결제 수단 문의"""
        return ChatbotResponse(
            text="대부분의 가게에서 다음 결제 수단을 사용할 수 있습니다:\n\n"
                 "💳 **사용 가능**: 신용/체크카드, 현금, 급식카드(가맹점)\n"
                 "📱 **모바일**: 카카오페이, 네이버페이, 토스\n\n"
                 "특정 가게의 결제 수단이 궁금하시면 가게명을 알려주세요!",
            recommendations=[],
            metadata={'intent': 'payment_method'}
        )
    
    def _handle_review_request(self, user_input: str, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """평점/리뷰 요청"""
        return ChatbotResponse(
            text="죄송합니다. 현재 리뷰 정보는 제공하지 않습니다.\n"
                 "네이버 지도나 카카오맵에서 리뷰를 확인해보세요!\n\n"
                 "대신 인기 있는 맛집을 추천해드릴까요?",
            recommendations=[],
            metadata={'intent': 'review_request', 'status': 'not_available'}
        )
    
    def _handle_nutritional_info(self, user_input: str, extracted_info: ExtractedInfo) -> ChatbotResponse:
        """영양 정보 처리"""
        return ChatbotResponse(
            text="영양 정보가 궁금하시군요!\n"
                 "현재 일부 메뉴의 칼로리 정보만 제공 가능합니다.\n\n"
                 "구체적인 메뉴명을 알려주시면 확인해드리겠습니다.",
            recommendations=[],
            metadata={'intent': 'nutritional_info'}
        )
    
    def _handle_modify_request(self, user_input: str, extracted_info: ExtractedInfo,
                              conversation_context: List[Dict]) -> ChatbotResponse:
        """요청 수정 처리"""
        
        # 새로운 요청 추출
        new_food = None
        for food in ['피자', '치킨', '햄버거', '한식', '중식', '일식', '분식']:
            if food in user_input:
                new_food = food
                break
        
        if new_food:
            # 새로운 추천 요청으로 처리
            new_extracted = ExtractedInfo(
                intent=IntentType.FOOD_REQUEST,
                confidence=0.9
            )
            if not new_extracted.entities:
                from data.data_structure import ExtractedEntities
                new_extracted.entities = ExtractedEntities()
            new_extracted.entities.food_type = new_food
            
            # RAG 검색으로 전환
            rag_results = self._perform_rag_search(user_input, new_extracted)
            recommendations = self._convert_rag_to_recommendations(rag_results[:3])
            
            response_text = f"알겠습니다! {new_food} 추천으로 변경해드릴게요.\n\n"
            if recommendations:
                response_text += "다음 가게들을 추천해드립니다:\n"
                for i, rec in enumerate(recommendations, 1):
                    response_text += f"{i}. {rec['shop_name']} - {rec['menu_name']} ({rec['price']:,}원)\n"
            
            return ChatbotResponse(
                text=response_text,
                recommendations=recommendations,
                metadata={'intent': 'modify_request', 'new_food': new_food}
            )
        else:
            return ChatbotResponse(
                text="어떤 음식으로 변경하고 싶으신가요?",
                recommendations=[],
                metadata={'intent': 'modify_request', 'needs_clarification': True}
            )
    
    def _get_hardcoded_response(self, user_input: str, intent: IntentType) -> ChatbotResponse:
        """하드코딩된 폴백 응답"""
        
        import random
        
        responses = {
            IntentType.GREETING: [
                "안녕하세요! 오늘 뭐 드시고 싶으세요?",
                "반가워요! 맛있는 거 추천해드릴게요!"
            ],
            IntentType.CHITCHAT: [
                "네! 어떤 음식을 추천해드릴까요?",
                "오늘은 어떤 음식이 땡기시나요?"
            ],
            IntentType.THANKS: [
                "천만에요! 맛있게 드세요!",
                "도움이 되어서 기뻐요!"
            ],
            IntentType.GOODBYE: [
                "안녕히 가세요! 또 이용해주세요!",
                "다음에 또 맛있는 거 추천해드릴게요!"
            ]
        }
        
        response_list = responses.get(intent, ["무엇을 도와드릴까요?"])
        
        return ChatbotResponse(
            text=random.choice(response_list),
            recommendations=[],
            metadata={'generator': 'hardcoded', 'intent': intent.value}
        )
    
    def record_user_selection(self, user_id: str, shop_id: int, action: str = "select"):
        """
        사용자 선택 기록 (중요!)
        
        Args:
            user_id: 사용자 ID
            shop_id: 선택한 가게 ID
            action: 'select', 'reject', 'more_info', 'navigate'
        """
        if not self.session_manager or user_id not in self.active_sessions:
            logger.warning(f"No active session for user {user_id}")
            return
        
        session_id = self.active_sessions[user_id]
        session = self.session_manager.active_sessions.get(session_id)
        
        if not session or not session.interactions:
            logger.warning(f"No interactions in session {session_id}")
            return
        
        # 마지막 상호작용의 추천 목록 가져오기
        last_interaction = session.interactions[-1]
        displayed = last_interaction.system_output.displayed_recommendations
        
        if action == "select":
            # 선택된 가게와 선택되지 않은 가게들 구분
            unselected = [sid for sid in displayed if sid != shop_id]
            
            self.session_manager.record_user_selection(
                session_id=session_id,
                turn_id=last_interaction.turn_id,
                selected_shop_id=shop_id,
                unselected_shop_ids=unselected,
                reason=action
            )
            
            logger.info(f"User selection recorded: user={user_id}, shop={shop_id}, action={action}")
            
            # 학습 데이터로도 저장
            if self.data_collector:
                feedback_data = {
                    'selected_shop_id': shop_id,
                    'unselected_shop_ids': unselected,
                    'action': action,
                    'timestamp': datetime.now().isoformat()
                }
                self.data_collector.collect_feedback_data(
                    user_id=user_id,
                    feedback_type='shop_selection',
                    feedback_content=feedback_data,
                    context={'session_id': session_id}
                )
        
        elif action in ["more_info", "navigate"]:
            # 암시적 긍정 신호
            if not last_interaction.user_feedback:
                from data.session_data_structure import UserFeedback
                last_interaction.user_feedback = UserFeedback()
            
            last_interaction.user_feedback.implicit_signals[action] = {
                'shop_id': shop_id,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Implicit signal recorded: user={user_id}, shop={shop_id}, signal={action}")
    
    def end_user_session(self, user_id: str):
        """사용자 세션 종료"""
        if self.session_manager and user_id in self.active_sessions:
            session_id = self.active_sessions[user_id]
            session = self.session_manager.end_session(session_id)
            
            if session:
                # 세션 데이터 저장
                from pathlib import Path
                save_dir = Path("data/session_logs")
                save_dir.mkdir(parents=True, exist_ok=True)
                
                filename = save_dir / f"{session.session_id}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(session.to_json())
                
                logger.info(f"Session ended and saved: {session_id}")
                
                # 학습 데이터 추출
                training_data = self.session_manager.get_training_data()
                if training_data:
                    logger.info(f"Extracted {len(training_data)} training samples from session")
            
            del self.active_sessions[user_id]
    
    def toggle_wide_deep(self, enable: bool):
        """Wide&Deep 활성화/비활성화 토글"""
        self.wide_deep_enabled = enable
        self.mode = 'wide_deep' if enable else 'basic'
        logger.info(f"Wide&Deep {'enabled' if enable else 'disabled'}, mode: {self.mode}")
