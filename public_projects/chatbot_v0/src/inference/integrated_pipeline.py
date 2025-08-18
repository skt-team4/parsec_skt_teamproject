"""
통합 추론 파이프라인
LLM (자연어 이해) + Wide&Deep (추천) 통합
"""

import torch
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from src.data.data_structure import ExtractedInfo, ChatbotResponse, IntentType, ExtractedEntity, ConfidenceLevel
from src.recommendation.ranking_model import WideAndDeepRankingModel, RankingModelConfig
from src.recommendation.candidate_generator import CandidateGenerator, CandidateGenerationConfig
from src.utils.location_utils import (
    normalize_location, 
    filter_shops_by_distance, 
    filter_shops_by_address,
    get_distance_description
)
from src.inference.conversation_manager import conversation_manager
from src.utils.tmap_utils import create_tmap_navigation_response
from src.utils.user_location import user_location_manager
from src.nlp.intent_postprocessor import IntentPostProcessor
from src.data.session_data_structure import SessionDataManager, SystemOutput, UserFeedback, Interaction
from src.inference.data_collector import LearningDataCollector
from datetime import datetime

logger = logging.getLogger(__name__)

# Golden Path 시나리오 (시연용)
try:
    from demo.golden_path_scenarios import GoldenPathScenarios
    golden_path_manager = GoldenPathScenarios()
    logger.info("Golden Path 시나리오 관리자 초기화 완료")
except Exception as e:
    golden_path_manager = None
    logger.warning(f"Golden Path 시나리오 관리자 비활성화: {e}")


class IntegratedPipeline:
    """LLM + Wide&Deep 통합 파이프라인"""
    
    def __init__(self, knowledge, llm_generator, wide_deep_path: Optional[str] = None, use_rag: bool = True):
        self.knowledge = knowledge
        self.llm_generator = llm_generator
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # 세션 데이터 관리자 초기화
        self.session_manager = SessionDataManager()
        self.current_turn_id = 0
        
        # 학습 데이터 수집기 초기화
        self.data_collector = LearningDataCollector(
            save_path='src/data/learning_data',
            buffer_size=100,
            auto_save_interval=300  # 5분마다 자동 저장
        )
        
        # A.X Encoder NLU 초기화
        self.ax_nlu = None
        try:
            from models.ax_encoder_nlu import AXEncoderNLU
            # A.X Encoder NLU 모델 경로 시도
            encoder_paths = [
                'models/ax_encoder_nlu_trained',  # 학습된 모델 우선
                'models/ax_encoder_nlu_best',
                'models/ax_encoder_base', 
                None  # 규칙 기반 폴백
            ]
            
            for path in encoder_paths:
                try:
                    self.ax_nlu = AXEncoderNLU(path)
                    if self.ax_nlu.model:
                        logger.info(f"A.X Encoder NLU 로드 완료: {path}")
                        break
                    else:
                        logger.info(f"A.X Encoder NLU 규칙 기반 모드: {path}")
                        break
                except Exception as e:
                    if path is None:
                        logger.warning(f"A.X Encoder NLU 초기화 실패: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"A.X Encoder NLU 로드 실패, 폴백 NLU 사용: {e}")
            self.ax_nlu = None
        
        # IntentPostProcessor 초기화 (10→28개 세부 의도)
        self.intent_postprocessor = IntentPostProcessor()
        logger.info("IntentPostProcessor 초기화 완료 (28개 세부 의도)")
        
        # Layer 1: 4-Funnel Candidate Generator 초기화
        self.candidate_generator = CandidateGenerator(CandidateGenerationConfig())
        logger.info("Layer 1: 4-Funnel Candidate Generator 초기화 완료")
        
        # RAG 시스템 초기화
        self.rag_retriever = None
        if use_rag:
            try:
                from rag.retriever import NaviyamRetriever
                from rag.vector_stores import create_vector_store
                from rag.query_parser import QueryStructurizer
                
                # FAISS 사용 시도, 실패하면 MockVectorStore
                try:
                    vector_store = create_vector_store('faiss', index_path='C:/temp_naviyam/prebuilt_faiss.faiss')
                    logger.info("FAISS vector store loaded successfully")
                except Exception as faiss_error:
                    logger.warning(f"FAISS 로드 실패, MockVectorStore 사용: {faiss_error}")
                    vector_store = create_vector_store('mock')
                query_structurizer = QueryStructurizer()
                self.rag_retriever = NaviyamRetriever(vector_store, query_structurizer)
                
                # 지식베이스 추가
                knowledge_dict = {
                    'shops': {str(s.id): s.__dict__ for s in knowledge.shops.values()},
                    'menus': {str(m.id): m.__dict__ for m in knowledge.menus.values()}
                }
                self.rag_retriever.add_knowledge_base(knowledge_dict)
                logger.info("RAG 시스템 초기화 완료")
            except Exception as e:
                logger.warning(f"RAG 시스템 초기화 실패: {e}")
        
        # Wide&Deep 모델 로드 (비활성화 - TeenPersonalizer 사용)
        self.wide_deep_model = None
        # Wide&Deep 대신 TeenPersonalizer 사용으로 전환
        # 아래 코드는 참고용으로 보존
        """
        if wide_deep_path:
            self.wide_deep_model = self._load_wide_deep_model(wide_deep_path)
        else:
            # 기본 경로 시도
            default_paths = [
                'training/models/wide_deep/model_20250810.pt',
                'models/wide_deep/model_20250810.pt'
            ]
            for path in default_paths:
                if Path(path).exists():
                    self.wide_deep_model = self._load_wide_deep_model(path)
                    break
        """
        logger.info("Wide&Deep 모델 비활성화 - TeenPersonalizer 사용")
    
    def _load_wide_deep_model(self, path: str):
        """Wide&Deep 모델 로드"""
        try:
            checkpoint = torch.load(path, map_location=self.device)
            config = checkpoint['config']
            
            model = WideAndDeepRankingModel(config).to(self.device)
            model.load_state_dict(checkpoint['model_state_dict'])
            model.eval()
            
            logger.info(f"Wide&Deep 모델 로드: {path}")
            return model
        except Exception as e:
            logger.error(f"Wide&Deep 모델 로드 실패: {e}")
            return None
    
    def process(self, user_input: str, user_profile: Dict = None, conversation_context: List[Dict] = None, user_id: str = None) -> ChatbotResponse:
        """통합 처리 파이프라인 (올바른 순서)"""
        
        # 사용자 ID 설정
        if not user_id:
            user_id = user_profile.get('user_id', 'default') if user_profile else 'default'
        
        # 날씨 정보 추출 (conversation_context에서)
        weather_info = None
        if conversation_context:
            for ctx in conversation_context:
                if ctx.get('system') == 'weather':
                    weather_info = {
                        'condition': ctx.get('weather', '맑음'),
                        'temp': ctx.get('temperature', 20)
                    }
                    logger.info(f"날씨 정보 감지: {weather_info['condition']} {weather_info['temp']}°C")
                    break
        
        # -1단계: Golden Path 시나리오 확인 (시연용)
        if golden_path_manager:
            is_golden, scenario_id = golden_path_manager.is_golden_path_query(user_input)
            if is_golden:
                logger.info(f"Golden Path 시나리오 감지: {scenario_id}")
                # 황금 경로 모드를 메타데이터에 추가 (이후 처리에서 활용)
                golden_path_mode = {
                    'is_golden': True,
                    'scenario_id': scenario_id,
                    'fallback_response': golden_path_manager.get_fallback_response(scenario_id)
                }
            else:
                golden_path_mode = None
        else:
            golden_path_mode = None
        
        # 0단계: 대화 컨텍스트 확인 (길찾기 응답 등)
        navigation_response = self._check_navigation_context(user_id, user_input)
        if navigation_response:
            return navigation_response
        
        # 0.5단계: 사용자 위치 자동 추출 (길찾기 대기 중이 아닐 때만)
        state = conversation_manager.get_state(user_id)
        if not state.waiting_for_navigation:  # 길찾기 대기 중이 아닐 때만 위치 추출
            if user_location_manager.update_from_user_input(user_id, user_input):
                user_loc = user_location_manager.get_user_location(user_id)
                if user_loc:
                    logger.info(f"사용자 위치 자동 감지: {user_loc.get('location_name')}")
                    # conversation_manager에도 저장
                    conversation_manager.set_user_location(user_id, user_loc.get('location_name'))
        
        # 0.6단계: 가게 선택 확인 (새로운 추천 생성 전에)
        state = conversation_manager.get_state(user_id)
        if state.last_recommendations and not state.waiting_for_navigation:
            # 선택 의도 확인
            is_selected, selected_shop = conversation_manager.check_shop_selection(user_id, user_input)
            if is_selected and selected_shop:
                # 선택이 확인되면 길찾기 제안
                offer_msg = conversation_manager.generate_navigation_offer_message(
                    selected_shop.get('shop_name', '선택한 가게')
                )
                response = ChatbotResponse(
                    text=offer_msg,
                    metadata={'waiting_for_navigation': True, 'selected_shop': selected_shop}
                )
                # 선택 상태 유지
                state.waiting_for_navigation = True
                return response
        
        # 세션 관리: 새 세션 또는 기존 세션 가져오기
        session_id = user_profile.get('session_id') if user_profile else None
        if not session_id:
            # 새 세션 생성
            session = self.session_manager.create_session(user_id)
            session_id = session.session_id
            logger.info(f"새 세션 생성: {session_id}")
            # user_profile에 session_id 저장 (중요!)
            if user_profile:
                user_profile['session_id'] = session_id
        elif session_id not in self.session_manager.active_sessions:
            # 세션이 만료되었으면 새로 생성
            session = self.session_manager.create_session(user_id)
            session_id = session.session_id
            logger.info(f"세션 만료로 새 세션 생성: {session_id}")
            # user_profile에 session_id 업데이트
            if user_profile:
                user_profile['session_id'] = session_id
        else:
            session = self.session_manager.active_sessions[session_id]
        
        # 상호작용 시작 시간 기록
        interaction_start = datetime.now()
        self.current_turn_id += 1
        
        # 1단계: NLU - 자연어 이해로 의도와 엔티티 추출
        extracted_info = self._extract_intent_and_entities(user_input, conversation_context, user_id)
        
        # 데이터 수집: NLU 결과
        if self.data_collector and extracted_info:
            nlu_features = {
                'intent': extracted_info.intent.name if hasattr(extracted_info.intent, 'name') else str(extracted_info.intent),
                'confidence': extracted_info.confidence,
                'entities': {
                    'food_type': extracted_info.entities.food_type if hasattr(extracted_info, 'entities') else None,
                    'budget': extracted_info.entities.budget if hasattr(extracted_info, 'entities') else None,
                    'location': extracted_info.entities.location_preference if hasattr(extracted_info, 'entities') else None
                }
            }
            self.data_collector.collect_nlu_features(user_id, nlu_features)
        
        # 1.2단계: Context Enrich - NLU 결과를 풍부하게 만들기
        enriched_context = None
        try:
            from src.context import get_context_enricher
            context_enricher = get_context_enricher()
            
            # 페르소나 ID 추출 (user_profile에서)
            persona_id = None
            if user_profile:
                # user_id가 페르소나 ID를 포함하는 경우 (예: min_ho_17)
                user_id_parts = user_id.split('_')
                if len(user_id_parts) >= 2:
                    persona_id = '_'.join(user_id_parts[:-1])  # 마지막 부분(나이) 제외
            
            # NLU 결과를 딕셔너리로 변환
            nlu_dict = {
                'text': user_input,
                'intent': extracted_info.intent.value if hasattr(extracted_info.intent, 'value') else str(extracted_info.intent),
                'entities': {}
            }
            
            # entities 처리 - iterable이 아닐 수 있으므로 안전하게 처리
            if extracted_info.entities:
                try:
                    # entities가 리스트인 경우
                    if hasattr(extracted_info.entities, '__iter__'):
                        for e in extracted_info.entities:
                            if hasattr(e, 'entity_type') and hasattr(e, 'value'):
                                nlu_dict['entities'][e.entity_type] = e.value
                    # entities가 단일 객체인 경우
                    elif hasattr(extracted_info.entities, 'entity_type') and hasattr(extracted_info.entities, 'value'):
                        nlu_dict['entities'][extracted_info.entities.entity_type] = extracted_info.entities.value
                except Exception as e:
                    logger.debug(f"엔티티 처리 중 오류 (무시됨): {e}")
                    nlu_dict['entities'] = {}
            
            # Context Enrich 수행 (날씨 정보 포함)
            enriched_context = context_enricher.enrich(nlu_dict, user_id, persona_id, weather_info)
            
            # 날씨 정보 로깅
            if weather_info:
                logger.info(f"날씨 정보 Context에 추가: {weather_info}")
            
            logger.info(f"Context Enriched: {enriched_context.get('enhanced_query', '')[:100]}...")
            
        except Exception as e:
            logger.warning(f"Context Enrich 실패: {e}")
            enriched_context = None
        
        # 1.3단계: 대화 컨텍스트 기반 의도 보정
        # 최근에 음식 추천이 있었고 부정 패턴이 감지되면 modify_request로 보정
        if extracted_info.intent in [IntentType.GENERAL_CHAT, IntentType.CHITCHAT]:
            # ConversationManager에서 최근 추천 확인
            state = conversation_manager.get_state(user_id)
            if state and state.last_recommendations:
                # 부정 패턴 체크
                negative_patterns = ['별로', '별론데', '싫어', '안좋', '다른', '말고', '그닥', '안땡', '아닌데', '빼고', '제외']
                if any(pattern in user_input.lower() for pattern in negative_patterns):
                    logger.info(f"[의도 보정] 최근 추천 후 부정 피드백 감지: {extracted_info.intent} → MODIFY_REQUEST")
                    extracted_info.intent = IntentType.MODIFY_REQUEST
                    extracted_info.confidence = 0.9  # 높은 신뢰도로 설정
        
        # 1.5단계: modify_request 처리 (부정 피드백)
        exclude_filters = {}
        if extracted_info.intent == IntentType.MODIFY_REQUEST:
            logger.info("modify_request 인텐트 감지 - 이전 추천 제외 필터 생성")
            state = conversation_manager.get_state(user_id)
            if state.last_recommendations:
                # 이전 추천에서 카테고리 추출
                exclude_categories = set()
                exclude_shop_ids = set()
                for rec in state.last_recommendations:
                    if 'category' in rec:
                        exclude_categories.add(rec['category'])
                    if 'shop_id' in rec:
                        exclude_shop_ids.add(rec['shop_id'])
                
                if exclude_categories:
                    exclude_filters['exclude_category'] = list(exclude_categories)
                    logger.info(f"제외할 카테고리: {exclude_filters['exclude_category']}")
                if exclude_shop_ids:
                    exclude_filters['exclude_shop_ids'] = list(exclude_shop_ids)
                    logger.info(f"제외할 가게 ID: {exclude_filters['exclude_shop_ids']}")
            else:
                logger.info("modify_request 감지했으나 이전 추천이 없음")
            
            # 대화 맥락에 부정 피드백 추가
            conversation_manager.add_message(user_id, 'user', user_input + " (부정 피드백)")
            
            # TeenPersonalizer에 부정 피드백 반영
            if state.last_recommendations:
                try:
                    from src.personalization.teen_personalizer import get_personalizer
                    personalizer = get_personalizer()
                    
                    # 첫 번째 추천 가게에 대해 부정 피드백
                    first_rec = state.last_recommendations[0]
                    if 'shop_id' in first_rec and 'category' in first_rec:
                        personalizer.update_from_interaction(
                            user_id=user_id,
                            shop_id=first_rec['shop_id'],
                            interaction_type='dislike',
                            metadata={'category': first_rec['category']}
                        )
                        logger.info(f"TeenPersonalizer에 부정 피드백 반영: {first_rec['category']}")
                except Exception as e:
                    logger.warning(f"TeenPersonalizer 부정 피드백 실패: {e}")
        
        # 2단계: NLU 결과 기반 구조화된 RAG 검색
        rag_context = ""
        rag_documents = []
        rag_candidates = []  # Wide&Deep을 위한 후보군
        
        # 인사, 일상대화는 RAG 검색 스킵 (MODIFY_REQUEST는 검색 필요)
        skip_rag_intents = [IntentType.GREETING, IntentType.CHITCHAT, IntentType.GENERAL_CHAT, 
                           IntentType.THANKS, IntentType.GOODBYE, IntentType.NONSENSE]
        
        if self.rag_retriever and extracted_info.intent not in skip_rag_intents:
            try:
                # Context Enrich가 있으면 enhanced_query 사용, 없으면 원본 사용
                search_query = user_input
                if enriched_context and enriched_context.get('enhanced_query'):
                    search_query = enriched_context['enhanced_query']
                    logger.info(f"Enhanced Query 사용: {search_query}")
                
                # NLU 엔티티를 활용한 구조화된 검색 (exclude_filters 전달)
                rag_documents, rag_candidates = self._perform_structured_rag_search(
                    extracted_info, search_query, exclude_filters, enriched_context
                )
                if rag_documents:
                    rag_context = self._build_rag_context(rag_documents)
                    logger.info(f"RAG 구조화 검색 완료: {len(rag_documents)}개 문서")
            except Exception as e:
                logger.warning(f"RAG 검색 실패: {e}")
        
        # 3단계: Layer 1 (4-Funnel) 후보 생성 + Layer 2 (Wide&Deep) 랭킹
        recommendations = []
        if self._needs_recommendation(extracted_info):
            # Layer 1: 4-Funnel 후보 생성 (RAG/위치 필터링된 후보 전달)
            layer1_candidates = self._get_four_funnel_candidates(
                extracted_info,
                user_profile or self._get_default_user_profile(),
                pre_filtered_candidates=rag_candidates,  # 위치 필터링된 후보 전달
                enriched_context=enriched_context  # Context Enrich 정보 전달
            )
            
            # RAG 결과도 Content Funnel의 일부로 통합
            if rag_candidates:
                # RAG 후보들에 content_score 추가
                for i, candidate in enumerate(rag_candidates[:20]):
                    candidate_dict = {
                        'shop_id': candidate.id,
                        'shop_name': candidate.name,
                        'category': candidate.category,
                        'address': candidate.address,
                        'content_score': 10.0 - (i * 0.5),  # RAG 순위 기반 점수
                        'funnel_source': 'rag_content'
                    }
                    # 중복 체크 후 추가
                    if not any(c['shop_id'] == candidate_dict['shop_id'] for c in layer1_candidates):
                        layer1_candidates.append(candidate_dict)
            
            # Layer 2: Wide&Deep 랭킹 (또는 규칙 기반)
            if layer1_candidates:
                recommendations = self._get_wide_deep_recommendations_from_candidates(
                    layer1_candidates,
                    extracted_info,
                    user_profile or self._get_default_user_profile(),
                    enriched_context  # Context Enrich 정보 전달
                )
                logger.info(f"Layer 1({len(layer1_candidates)}개) → Layer 2({len(recommendations)}개) 완료")
        
        # 3.5단계: 대화 히스토리를 LLM에 전달할 형식으로 준비
        # conversation_manager에서 최근 대화 가져오기
        llm_conversation_context = conversation_manager.get_formatted_history(user_id)
        
        # 현재 사용자 입력도 히스토리에 추가
        conversation_manager.add_message(user_id, 'user', user_input)
        
        # 대화 상태 요약을 메타데이터로 추가
        context_summary = conversation_manager.get_context_summary(user_id)
        if context_summary:
            logger.info(f"대화 컨텍스트: {context_summary}")
        
        # conversation_context가 없으면 conversation_manager의 히스토리 사용
        if not conversation_context:
            conversation_context = llm_conversation_context
        
        # 먼저 최종 추천 리스트를 확정
        final_recommendations = recommendations[:3] if recommendations else []
        
        # 데이터 수집: 추천 결과
        if self.data_collector and final_recommendations:
            rec_data = [{
                'shop_id': rec.get('shop_id'),
                'shop_name': rec.get('shop_name'),
                'category': rec.get('category'),
                'price_range': rec.get('price_range'),
                'score': rec.get('teen_score', rec.get('popularity_score', 0))
            } for rec in final_recommendations]
            self.data_collector.collect_recommendation_data(user_id, rec_data)
        
        # 추천 정보를 컨텍스트에 추가 (강화된 프롬프트)
        enhanced_context = conversation_context.copy() if conversation_context else []
        if final_recommendations:
            # 추천 리스트를 상세하고 명확한 포맷으로 구성
            rec_details = []
            for i, rec in enumerate(final_recommendations, 1):
                shop_name = rec.get('shop_name', '알 수 없는 가게')
                category = rec.get('category', '기타')
                address = rec.get('address', '')
                reason = rec.get('reason', '')  # 추천 이유
                
                # 상세 정보 구성
                detail = f"{i}. {shop_name} ({category})"
                if reason:
                    detail += f" - {reason}"
                if address:
                    detail += f" [{address}]"
                rec_details.append(detail)
            
            recommendation_list_str = "\n".join(rec_details)
            
            # NLG에 전달할 시스템 프롬프트 강화
            system_prompt = (
                "너는 청소년 급식카드 사용자를 위한 친절한 맛집 추천 챗봇이야.\n"
                "아래 추천 리스트를 바탕으로 자연스럽고 친근한 답변을 만들어줘.\n\n"
                "【중요 규칙】\n"
                "1. 반드시 아래 추천 리스트의 가게들만 언급해야 함\n"
                "2. 리스트에 없는 다른 가게를 언급하면 안 됨\n"
                "3. JSON 형식이나 코드 같은 텍스트를 출력하면 안 됨\n"
                "4. 청소년 눈높이에 맞는 친근한 말투 사용\n"
                "5. 카테고리가 섞여있다면 자연스럽게 다양성을 언급\n\n"
                "【실제 추천 리스트】\n"
                f"{recommendation_list_str}\n"
                "─────────────────"
            )
            
            enhanced_context.append({
                'role': 'system',
                'content': system_prompt
            })
        
        # 4단계: NLG - 자연스러운 응답 생성 (최종 추천 리스트 기반)
        # 재귀 호출 방지: integrated_pipeline 임시 비활성화 (속성이 있는 경우만)
        original_pipeline = getattr(self.llm_generator, 'integrated_pipeline', None)
        if hasattr(self.llm_generator, 'integrated_pipeline'):
            self.llm_generator.integrated_pipeline = None
        
        response = self.llm_generator.generate_response(
            extracted_info=extracted_info,
            user_profile=user_profile,
            conversation_context=enhanced_context,  # 추천 정보가 포함된 컨텍스트
            rag_context=rag_context,
            recommendations=final_recommendations  # 최종 추천 리스트 전달
        )
        
        # 원래대로 복구 (속성이 있었던 경우만)
        if original_pipeline is not None:
            self.llm_generator.integrated_pipeline = original_pipeline
        
        # 4.5단계: LLM 응답도 히스토리에 저장 (맥락 메타데이터 포함)
        if response and response.text:
            # NLG가 생성한 맥락 메타데이터 추출
            nlg_context = None
            if response.metadata and 'context_metadata' in response.metadata:
                nlg_context = response.metadata['context_metadata']
                logger.info(f"[DEBUG] NLG 맥락 메타데이터: {nlg_context}")
            
            # 맥락이 없으면 의도 기반으로 생성
            if not nlg_context or not nlg_context:
                # 의도 기반으로 맥락 메타데이터 생성
                if extracted_info.intent == IntentType.FOOD_REQUEST:
                    nlg_context = {
                        'context_type': 'food_recommendation',
                        'intent': 'food_request'
                    }
                    # 추천 결과가 있으면 카테고리 추가
                    if recommendations:
                        categories = list(set([r.get('category', '') for r in recommendations[:3] if r.get('category')]))
                        if categories:
                            nlg_context['categories'] = categories
                    logger.info(f"[DEBUG] 의도 기반 맥락 생성: {nlg_context}")
                elif extracted_info.intent in [IntentType.GENERAL_CHAT, IntentType.CHITCHAT]:
                    nlg_context = {'context_type': 'general_chat'}
            
            # 대화 히스토리에 저장 (맥락 포함)
            conversation_manager.add_message(user_id, 'assistant', response.text)
            
            # 맥락 메타데이터도 저장 (다음 턴에서 사용)
            if nlg_context:
                conversation_manager.update_context(user_id, nlg_context)
        
        # 5단계: T맵 정보 추가 (추천 결과가 있을 때만)
        if recommendations and len(recommendations) > 0:
            recommendations = self._add_tmap_info_to_recommendations(
                recommendations,
                user_profile
            )
            logger.info(f"T맵 정보 추가 완료: {len(recommendations)}개 추천")
        
        # 6단계: 최종 추천 결과 정리 (RAG 기반 동기화)
        # Golden Path 시나리오 처리 (최우선)
        if golden_path_mode and golden_path_mode.get('is_golden'):
            # 추천 결과가 신뢰도가 낮거나 없으면 폴백 사용
            if not recommendations or len(recommendations) < 2:
                fallback_data = golden_path_mode.get('fallback_response', {})
                if 'recommendations' in fallback_data:
                    # 폴백 추천 사용
                    golden_recs = []
                    for fb_rec in fallback_data['recommendations']:
                        golden_recs.append({
                            'shop_id': f"golden_{golden_path_mode['scenario_id']}_{len(golden_recs)}",
                            'shop_name': fb_rec['shop_name'],
                            'menu_name': fb_rec['menu_name'],
                            'price': fb_rec['price'],
                            'category': fb_rec.get('category', ''),
                            'reason': fb_rec['reason'],
                            'source': 'golden_path_fallback'
                        })
                    response.recommendations = golden_recs
                    response.metadata['golden_path_used'] = True
                    response.metadata['scenario_id'] = golden_path_mode['scenario_id']
                    if 'response' in fallback_data:
                        response.text = fallback_data['response'] + "\n" + response.text
                    logger.info(f"Golden Path 폴백 사용: {golden_path_mode['scenario_id']}")
                    # Golden Path 추천도 저장
                    conversation_manager.update_recommendations(user_id, response.recommendations)
            else:
                # 기존 추천이 충분하면 그대로 사용
                response.recommendations = recommendations
                response.metadata['golden_path_enhanced'] = True
                response.metadata['scenario_id'] = golden_path_mode['scenario_id']
                # 추천 결과 저장
                conversation_manager.update_recommendations(user_id, response.recommendations)
        elif final_recommendations and len(final_recommendations) > 0:
            # RAG 기반 추천을 우선 사용 (LLM 응답과 일치시킴)
            response.recommendations = final_recommendations  # 최종 리스트 사용
            response.metadata['wide_deep_used'] = True
            response.metadata['rag_sync'] = True  # RAG 동기화 표시
            # Wide&Deep 추천 결과를 대화 상태에 저장
            conversation_manager.update_recommendations(user_id, response.recommendations)
        elif rag_candidates:
            # Wide&Deep이 없어도 RAG 후보가 있으면 그것을 사용
            fallback_recs = []
            for shop in rag_candidates[:3]:
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                if shop_menus:
                    menu = self._select_best_menu(shop_menus, extracted_info.entities.food_type)
                    fallback_recs.append({
                        'shop_id': shop.id,
                        'shop_name': shop.name,
                        'menu_name': menu.name,
                        'price': menu.price,
                        'category': shop.category,
                        'address': shop.address,
                        'source': 'rag_fallback'
                    })
            if fallback_recs:
                response.recommendations = fallback_recs
                response.metadata['rag_fallback'] = True
                # RAG fallback 추천도 저장
                conversation_manager.update_recommendations(user_id, response.recommendations)
        elif response.recommendations and len(response.recommendations) > 0:
            # 마지막 폴백: LLM 추천이 있으면 저장
            conversation_manager.update_recommendations(user_id, response.recommendations)
        
        # 메타데이터 추가
        if rag_documents:
            response.metadata['rag_used'] = True
            response.metadata['rag_documents_count'] = len(rag_documents)
        
        # 세션 데이터 수집
        response_time_ms = int((datetime.now() - interaction_start).total_seconds() * 1000)
        
        # SystemOutput 생성
        system_output = SystemOutput(
            rag_candidates=[{'shop_id': c.id, 'name': c.name} for c in rag_candidates[:20]] if rag_candidates else [],
            recommendation_scores=[{'shop_id': r['shop_id'], 'score': r.get('wide_deep_score', 0)} for r in recommendations] if recommendations else [],
            displayed_recommendations=[r['shop_id'] for r in response.recommendations] if response.recommendations else [],
            generated_response=response.text,
            response_time_ms=response_time_ms
        )
        
        # NLU 출력 정리
        nlu_output = {
            'intent': extracted_info.intent.value if extracted_info.intent else 'unknown',
            'entities': {
                'food_type': extracted_info.entities.food_type,
                'location': extracted_info.entities.location_preference,
                'budget': extracted_info.entities.budget
            },
            'confidence': extracted_info.confidence if isinstance(extracted_info.confidence, (int, float)) else 'low'
        }
        
        # Interaction 생성 및 세션에 추가
        interaction = Interaction(
            turn_id=self.current_turn_id,
            timestamp=interaction_start,
            user_input={'text': user_input},
            nlu_output=nlu_output,
            system_output=system_output
        )
        
        self.session_manager.add_interaction(session_id, interaction)
        
        # 응답에 세션 ID 추가 (프론트엔드에서 피드백 시 사용)
        response.metadata['session_id'] = session_id
        response.metadata['turn_id'] = self.current_turn_id
        
        # 데이터 수집: 상호작용 데이터
        if self.data_collector:
            interaction_data = {
                'user_input': user_input,
                'intent': extracted_info.intent.name if hasattr(extracted_info.intent, 'name') else str(extracted_info.intent),
                'response_text': response.text,
                'recommendations': final_recommendations,
                'session_id': session_id,
                'turn_id': self.current_turn_id,
                'processing_time': (datetime.now() - interaction_start).total_seconds()
            }
            self.data_collector.collect_interaction_data(user_id, interaction_data)
        
        return response
    
    def _build_search_query_from_entities(self, extracted_info: ExtractedInfo) -> str:
        """NLU 엔티티로 깔끔한 검색 쿼리 재구성"""
        query_parts = []
        entities = extracted_info.entities
        
        # 음식 타입
        if entities.food_type:
            query_parts.append(entities.food_type)
        
        # 위치
        if entities.location_preference:
            query_parts.append(entities.location_preference)
        
        # 가격
        if entities.budget:
            query_parts.append(f"{entities.budget}원 이하")
        
        # 기본 키워드 추가
        if query_parts:
            query_parts.append("맛집")
        else:
            # 엔티티가 없으면 의도 기반 기본 쿼리
            intent_to_query = {
                IntentType.FOOD_REQUEST: "맛집 추천",
                IntentType.BUDGET_INQUIRY: "가격대별 메뉴",
                IntentType.LOCATION_INQUIRY: "지역별 맛집",
                IntentType.GREETING: None,  # 인사는 검색 안 함
                IntentType.CHITCHAT: None,  # 일상 대화도 검색 안 함
                IntentType.GENERAL_CHAT: None  # 일반 대화도 검색 안 함
            }
            default_query = intent_to_query.get(extracted_info.intent, "맛집 추천")
            if default_query:
                query_parts = [default_query]
            else:
                return ""  # 검색하지 않음
        
        search_query = " ".join(query_parts)
        logger.debug(f"NLU 엔티티 → 검색 쿼리: {search_query}")
        return search_query
    
    def _perform_structured_rag_search(self, extracted_info: ExtractedInfo, user_input: str, exclude_filters: Dict = None, enriched_context: Dict = None):
        """NLU 결과 기반 구조화된 RAG 검색 (사전 필터링 강화 + Context Enrich 활용)"""
        entities = extracted_info.entities
        all_shops = list(self.knowledge.shops.values())
        
        # exclude_filters 초기화
        if exclude_filters is None:
            exclude_filters = {}
        
        # 1. 사전 필터링 (pre-filtering)
        pre_filtered_candidates = all_shops
        
        # 1-1. 위치 필터링 (가장 강력한 필터)
        location_candidates = None
        location_info = {}
        if entities.location_preference:
            location_info = normalize_location(entities.location_preference)
            if location_info.get('lat'):
                # 반경 5km로 시작, 결과 없으면 10km로 확장
                radius_km = 5.0
                results = filter_shops_by_distance(all_shops, location_info['lat'], location_info['lng'], radius_km)
                if not results:
                    radius_km = 10.0
                    results = filter_shops_by_distance(all_shops, location_info['lat'], location_info['lng'], radius_km)
                
                if results:
                    location_candidates = [res['shop'] for res in results]
                    # 거리 정보 메타데이터 저장
                    self._location_metadata = {res['shop'].id: {'distance': res['distance'], 'location_name': location_info.get('name')} for res in results}
                    logger.info(f"위치 기반 사전 필터링: {location_info.get('name')} 반경 {radius_km}km - {len(location_candidates)}개 후보")
                    pre_filtered_candidates = location_candidates
            elif location_info.get('district'):
                # 구/시 단위 텍스트 매칭
                location_results = filter_shops_by_address(all_shops, location_info['district'])
                if location_results:
                    location_candidates = [result['shop'] for result in location_results]
                    logger.info(f"구 단위 필터링: {location_info['district']} - {len(location_candidates)}개 가게")
                    pre_filtered_candidates = location_candidates
        
        # 1-2. exclude_category 필터 적용 (modify_request에서 전달됨)
        if 'exclude_category' in exclude_filters and pre_filtered_candidates:
            exclude_categories = exclude_filters['exclude_category']
            if isinstance(exclude_categories, str):
                exclude_categories = [exclude_categories]
            
            category_excluded = [
                shop for shop in pre_filtered_candidates
                if not any(exc_cat.lower() in shop.category.lower() for exc_cat in exclude_categories)
            ]
            if category_excluded:
                pre_filtered_candidates = category_excluded
                logger.info(f"카테고리 제외 필터 적용 ({exclude_categories}): {len(pre_filtered_candidates)}개 후보")
        
        # 1-2-1. Context Enrich 기반 카테고리 필터링 (추가)
        if enriched_context and enriched_context.get('category_weights'):
            weights = enriched_context['category_weights']
            
            # 페널티 카테고리가 있으면 필터링 (최근 많이 먹은 카테고리)
            if weights.get('penalize_categories'):
                # 페널티가 0.3 이하인 카테고리는 제외 (70% 이상 감점)
                heavily_penalized = [cat for cat, penalty in weights['penalize_categories'].items() if penalty <= 0.3]
                if heavily_penalized:
                    filtered = [
                        shop for shop in pre_filtered_candidates
                        if not any(pen_cat.lower() in shop.category.lower() 
                                  for pen_cat in heavily_penalized)
                    ]
                    if filtered:  # 필터링 후 결과가 있을 때만 적용
                        pre_filtered_candidates = filtered
                        logger.info(f"Context Enrich - 최근 반복 카테고리 제외 ({heavily_penalized}): {len(pre_filtered_candidates)}개")
        
        # 1-3. 카테고리(음식 종류) 필터링
        if entities.food_type and pre_filtered_candidates:
            # MODIFY_REQUEST (부정 피드백)인 경우 해당 카테고리 제외
            if extracted_info.intent == IntentType.MODIFY_REQUEST:
                category_filtered = [
                    shop for shop in pre_filtered_candidates 
                    if entities.food_type.lower() not in shop.category.lower()  # NOT IN으로 제외
                ]
                if category_filtered:
                    pre_filtered_candidates = category_filtered
                    logger.info(f"카테고리 제외 필터링 후 ('{entities.food_type}' 제외): {len(pre_filtered_candidates)}개 후보")
            else:
                # 일반 요청인 경우 해당 카테고리 포함
                category_filtered = [
                    shop for shop in pre_filtered_candidates 
                    if entities.food_type.lower() in shop.category.lower()
                ]
                if category_filtered:
                    pre_filtered_candidates = category_filtered
                    logger.info(f"카테고리 필터링 후: {len(pre_filtered_candidates)}개 후보")
        
        # 1-3. 예산 필터링
        if entities.budget and pre_filtered_candidates:
            budget_filtered = []
            for shop in pre_filtered_candidates:
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                if any(m.price <= entities.budget * 1.2 for m in shop_menus):  # 20% 여유
                    budget_filtered.append(shop)
            if budget_filtered:
                pre_filtered_candidates = budget_filtered
                logger.info(f"예산 필터링 후: {len(pre_filtered_candidates)}개 후보")
        
        # 2. RAG 의미 검색 (필터링된 후보 대상)
        semantic_query = self._build_search_query_from_entities(extracted_info)
        
        # 필터링된 후보가 너무 많으면 RAG로 줄이고, 적으면 그대로 사용
        if len(pre_filtered_candidates) > 30 and self.rag_retriever:
            # RAG 검색으로 순위 매기기
            all_rag_docs = self.rag_retriever.search(semantic_query)
            
            # 사전 필터링된 가게 ID 집합
            pre_filtered_ids = {s.id for s in pre_filtered_candidates}
            
            # RAG 결과와 사전 필터링 교집합
            final_candidates_shops = []
            for doc in all_rag_docs:
                metadata = doc.get_metadata()
                if metadata.get('type') == 'shop':
                    shop_id = metadata.get('shop_id')
                    if shop_id in pre_filtered_ids and shop_id in self.knowledge.shops:
                        final_candidates_shops.append(self.knowledge.shops[shop_id])
            
            # RAG 결과가 너무 적으면 사전 필터링 결과 사용
            if len(final_candidates_shops) < 3:
                final_candidates = pre_filtered_candidates[:10]
            else:
                final_candidates = final_candidates_shops[:10]
            
            logger.info(f"RAG 필터링: {len(pre_filtered_candidates)} -> {len(final_candidates)}개")
        else:
            # RAG 스킵하고 거리순 또는 그대로 사용
            if location_candidates:
                # 거리순 정렬 (가까운 순)
                final_candidates = sorted(pre_filtered_candidates, 
                                        key=lambda s: self._location_metadata.get(s.id, {}).get('distance', float('inf')))[:10]
            else:
                final_candidates = pre_filtered_candidates[:10]
        
        # 다양성을 위한 믹스 적용
        if location_candidates and final_candidates:
            final_candidates = self._apply_additional_filters_with_mix(final_candidates, entities, location_info)
        
        documents = self._create_rag_documents_from_shops(final_candidates)
        return documents, final_candidates
    
    def _extract_shop_candidates_from_documents(self, documents):
        """RAG 문서에서 가게 후보 추출"""
        candidates = []
        
        for doc in documents:
            metadata = doc.get_metadata()
            if metadata.get('type') == 'shop':
                shop_id = metadata.get('shop_id')
                if shop_id and shop_id in self.knowledge.shops:
                    candidates.append(self.knowledge.shops[shop_id])
        
        return candidates
    
    def _build_rag_context(self, documents):
        """문서 리스트로부터 컨텍스트 생성"""
        if not documents:
            return ""
        
        context_parts = ["다음은 관련된 정보입니다:"]
        for i, doc in enumerate(documents[:5], 1):  # 상위 5개만
            content = doc.get_content()
            if len(content) > 200:
                content = content[:200] + "..."
            context_parts.append(f"\n{i}. {content}")
        
        return "\n".join(context_parts)
    
    def _calculate_entity_match_score(self, shop, entities) -> float:
        """NLU 엔티티와 가게 정보 매칭 점수 계산"""
        score = 0.5  # 기본 점수
        
        # 음식 종류 매칭
        if entities.food_type:
            if entities.food_type.lower() in shop.category.lower():
                score += 0.3
            elif entities.food_type.lower() in shop.name.lower():
                score += 0.2
        
        # 위치 매칭
        if entities.location_preference:
            if entities.location_preference in shop.address:
                score += 0.2
        
        # 가격 매칭
        if entities.budget:
            # 가게의 평균 가격이 예산 이하인지 체크
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                avg_price = sum(m.price for m in shop_menus) / len(shop_menus)
                if avg_price <= entities.budget:
                    score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_layer1_score(self, shop, rag_rank: int, extracted_info, user_profile) -> dict:
        """Layer 1 점수 계산 (RAG + 개인화 + 엔티티 매칭)"""
        
        # RAG 점수 (순위 기반)
        rag_score = max(0, 1.0 - (rag_rank * 0.1))  # 1위: 1.0, 2위: 0.9, ...
        
        # 개인화 점수 (Wide&Deep 또는 기본 로직)
        if self.wide_deep_model:
            personalization_score = self._calculate_personalized_score(shop, extracted_info, user_profile)
        else:
            personalization_score = 0.5  # 기본값
        
        # 엔티티 매칭 점수
        entity_match_score = self._calculate_entity_match_score(shop, extracted_info.entities)
        
        # 최종 점수 = RAG(0.5) + 개인화(0.3) + 엔티티매칭(0.2)
        combined_score = (rag_score * 0.5 + 
                         personalization_score * 0.3 + 
                         entity_match_score * 0.2)
        
        return {
            'combined_score': combined_score,
            'rag_score': rag_score,
            'personalization_score': personalization_score,
            'entity_match_score': entity_match_score
        }
    
    def _get_four_funnel_candidates(self, extracted_info: ExtractedInfo, user_profile: Dict, pre_filtered_candidates=None, enriched_context=None) -> List[Dict]:
        """Layer 1: 4-Funnel을 통한 후보 생성 (사전 필터링된 후보와 병합 + Context 활용)"""
        
        # 4-Funnel로 다양성 확보 (RAG 결과와 병합)
        all_candidates = []
        
        # 1. RAG/사전 필터링된 후보를 우선 추가
        if pre_filtered_candidates and len(pre_filtered_candidates) > 0:
            for i, shop in enumerate(pre_filtered_candidates[:10]):  # 상위 10개만
                all_candidates.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'category': shop.category,
                    'address': shop.address,
                    'funnel_source': 'rag_filtered',
                    'base_score': 100 - i * 2  # RAG 우선순위
                })
            logger.info(f"RAG 후보 {len(all_candidates)}개 추가")
        
        # NLU 엔티티에서 정보 추출
        entities = extracted_info.entities
        
        # 4-Funnel 후보 생성 파라미터 준비
        user_id = user_profile.get('user_id')
        user_location = entities.location_preference if entities else None
        query = self._build_search_query_from_entities(extracted_info)
        
        # 시간대 추출
        current_time = datetime.now()
        hour = current_time.hour
        if 6 <= hour < 11:
            time_of_day = 'breakfast'
        elif 11 <= hour < 14:
            time_of_day = 'lunch'
        elif 14 <= hour < 17:
            time_of_day = 'snack'
        elif 17 <= hour < 21:
            time_of_day = 'dinner'
        else:
            time_of_day = 'late_night'
        
        # 사용자 타입 추출 (프로필 기반)
        user_type = user_profile.get('user_type', 'general')
        
        # 필터 생성 (MODIFY_REQUEST 고려)
        filters = {}
        # MODIFY_REQUEST (부정 피드백)인 경우 특별 처리
        if extracted_info.intent == IntentType.MODIFY_REQUEST:
            # 이전 추천에서 카테고리 추출
            # conversation_manager는 이미 임포트됨 (line 21)
            state = conversation_manager.get_state(user_profile.get('user_id', 'default'))
            if state.last_recommendations:
                # 이전 추천의 모든 카테고리 수집 (중복 제거)
                excluded_categories = list(set([
                    rec.get('category') for rec in state.last_recommendations[:3]
                    if rec.get('category')
                ]))
                
                if excluded_categories:
                    # 기존 추천 목록에서 제외된 카테고리를 빼고 필터링
                    filtered_recommendations = [
                        shop for shop in list(self.knowledge.shops.values())
                        if not any(exc_cat.lower() in shop.category.lower() 
                                 for exc_cat in excluded_categories)
                    ]
                    
                    if filtered_recommendations:
                        # 필터링된 목록에서 새로운 후보 생성
                        logger.info(f"modify_request 인텐트 감지 - 이전 추천 제외 필터 생성")
                        logger.info(f"제외할 카테고리: {excluded_categories}")
                        
                        # TeenPersonalizer에 부정 피드백 반영
                        for category in excluded_categories:
                            logger.info(f"TeenPersonalizer에 부정 피드백 반영: {category}")
                            # 실제 personalizer 피드백 처리는 아래에서
                            
                        # 필터링된 목록을 후보로 사용
                        logger.info(f"카테고리 제외 필터 적용 ({excluded_categories}): {len(filtered_recommendations)}개 후보")
                        
                    filters['exclude_category'] = excluded_categories
                    logger.info(f"카테고리 제외 필터링 후 ('{', '.join(excluded_categories)}' 제외): {len(filtered_recommendations)}개 후보")
            else:
                logger.info("modify_request 감지했으나 이전 추천이 없음")
        elif entities and entities.food_type:
            filters['category'] = entities.food_type
        if entities and entities.budget:
            filters['max_price'] = entities.budget
        
        # 급식카드 일일 한도 자동 적용 (페르소나 또는 기본값)
        if 'max_price' not in filters:
            # enriched_context에서 급식카드 정보 확인
            if enriched_context and 'meal_card' in enriched_context:
                daily_limit = enriched_context['meal_card'].get('daily_limit', 9500)
                filters['max_price'] = daily_limit
                logger.info(f"급식카드 일일 한도 자동 적용: {daily_limit}원")
            # user_profile에서 확인
            elif user_profile and 'meal_card_info' in user_profile:
                daily_limit = user_profile['meal_card_info'].get('daily_limit', 9500)
                filters['max_price'] = daily_limit
                logger.info(f"페르소나 급식카드 한도 적용: {daily_limit}원")
            else:
                # 기본값 설정 (18세 미만 급식카드 기본 한도)
                filters['max_price'] = 9500
                logger.info("급식카드 기본 한도 적용: 9500원")
            
        # Context에서 최근 카테고리와 사용자 컨텍스트 추출
        recent_categories = set()
        user_context = None
        
        # ConversationManager에서 최근 추천 카테고리 가져오기
        state = conversation_manager.get_state(user_id)
        if state and state.recent_recommended_categories:
            recent_categories = set(state.recent_recommended_categories)
            logger.info(f"최근 추천 카테고리 제외: {recent_categories}")
        
        if enriched_context:
            # Context Enrich에서 추가 카테고리 정보
            if 'category_weights' in enriched_context:
                weights = enriched_context['category_weights']
                if 'penalize_categories' in weights:
                    additional_categories = set(weights['penalize_categories'].keys())
                    recent_categories.update(additional_categories)
            
            # 사용자 컨텍스트 준비
            user_context = {
                'weather': enriched_context.get('weather', {}),
                'nutrition_status': enriched_context.get('nutrition_status', {}),
                'time_context': enriched_context.get('time_context', {}),
                'location': enriched_context.get('location', {})
            }
        
        # 위치 정보 보강 (페르소나 위치 정보 활용)
        if not user_location and user_profile and 'location' in user_profile:
            # 페르소나의 기본 위치 사용
            location_info = user_profile['location']
            if isinstance(location_info, dict):
                user_location = location_info.get('name', location_info.get('district', ''))
                # 위경도 정보도 컨텍스트에 추가
                if 'latitude' in location_info and 'longitude' in location_info:
                    if not user_context:
                        user_context = {}
                    user_context['user_latitude'] = location_info['latitude']
                    user_context['user_longitude'] = location_info['longitude']
                    logger.info(f"페르소나 위치 사용: {user_location} ({location_info['latitude']}, {location_info['longitude']})")
        
        # 2. 4-Funnel을 통한 추가 후보 생성 (다양성 확보)
        funnel_candidates = self.candidate_generator.generate_candidates(
            user_id=user_id,
            user_location=user_location,
            query=query,
            time_of_day=time_of_day,
            user_type=user_type,
            filters=filters,
            current_time=current_time,
            recent_categories=recent_categories,  # 최근 카테고리 전달
            user_context=user_context  # 컨텍스트 전달
        )
        
        # 기존 RAG 후보와 중복되지 않는 것만 추가
        existing_ids = {c['shop_id'] for c in all_candidates}
        for candidate in funnel_candidates[:20]:  # 4-Funnel에서 최대 20개
            if candidate['shop_id'] not in existing_ids:
                all_candidates.append(candidate)
                existing_ids.add(candidate['shop_id'])
        
        logger.info(f"4-Funnel 후보 추가 → 총 {len(all_candidates)}개 후보")
        
        # 3. 최종 후보 반환 (RAG + 4-Funnel 병합)
        return all_candidates
    
    def _get_wide_deep_recommendations_from_candidates(self, candidates, extracted_info, user_profile, enriched_context=None):
        """Layer 1 후보군에서 Wide&Deep으로 최종 랭킹"""
        
        if not candidates:
            return []
        
        # Wide&Deep 모델이 있으면 사용, 없으면 규칙 기반
        if self.wide_deep_model:
            return self._rank_with_wide_deep_model(candidates, extracted_info, user_profile, enriched_context)
        else:
            return self._rank_with_rules(candidates, extracted_info, user_profile, enriched_context)
    
    def _rank_with_wide_deep_model(self, candidates, extracted_info, user_profile, enriched_context=None):
        """Wide&Deep 모델로 랭킹"""
        # TODO: 실제 Wide&Deep 모델 추론 구현
        # 현재는 규칙 기반으로 폴백
        return self._rank_with_rules(candidates, extracted_info, user_profile, enriched_context)
    
    def _rank_with_rules(self, candidates, extracted_info, user_profile, enriched_context=None):
        """TeenPersonalizer 기반 랭킹 (11개 피처 + 실시간 학습)"""
        
        # TeenPersonalizer 사용 시도
        try:
            from src.personalization.teen_personalizer import get_personalizer
            personalizer = get_personalizer()
            
            # 컨텍스트 준비 - Context Enrich 정보 활용
            context = self._prepare_personalization_context(extracted_info, enriched_context)
            
            # TeenPersonalizer로 랭킹 (11개 피처 기반)
            ranked_results = personalizer.rank_candidates(
                candidates[:30],  # 상위 30개만 평가
                extracted_info,
                user_profile,
                context
            )
            
            # 결과 변환 (dictionary 형태로)
            recommendations = []
            for shop_data, score in ranked_results:
                # shop_data는 이미 완전한 shop 정보를 담은 dictionary
                shop_id = shop_data.get('shop_id') or shop_data.get('id')
                
                # 실제 메뉴 가격 정보 가져오기
                try:
                    from src.utils.menu_helper import get_shop_avg_price
                    avg_price = get_shop_avg_price(shop_id) if shop_id else None
                    if not avg_price:
                        avg_price = shop_data.get('price_range', 8000)
                except:
                    avg_price = shop_data.get('price_range', 8000)
                
                recommendations.append({
                    'shop_id': shop_id,
                    'shop_name': shop_data.get('shop_name') or shop_data.get('name', ''),
                    'category': shop_data.get('category', ''),
                    'address': shop_data.get('address', ''),
                    'price_range': avg_price,  # 실제 평균 가격 사용
                    'teen_score': score,  # TeenPersonalizer 점수
                    'reason': f"개인화 추천 (점수: {score:.1f})",
                    'latitude': shop_data.get('latitude'),
                    'longitude': shop_data.get('longitude')
                })
            
            # 개인화 수준 로깅
            user_id = user_profile.get('user_id', 'guest')
            level = personalizer.get_personalization_level(user_id)
            logger.info(f"TeenPersonalizer 적용 - 개인화 수준: {level}")
            
            return recommendations[:3] if recommendations else self._fallback_ranking(candidates, extracted_info, user_profile)
            
        except ImportError:
            logger.warning("TeenPersonalizer 없음, 기존 규칙 사용")
            return self._fallback_ranking(candidates, extracted_info, user_profile)
        except Exception as e:
            logger.error(f"TeenPersonalizer 오류: {e}")
            return self._fallback_ranking(candidates, extracted_info, user_profile)
    
    def _prepare_personalization_context(self, extracted_info, enriched_context=None):
        """개인화를 위한 컨텍스트 준비 - Context Enrich 정보 활용"""
        context = {
            'time': datetime.now().isoformat(),
            'hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday()
        }
        
        # Context Enrich 정보 우선 활용
        if enriched_context:
            # 시간대 정보
            if 'time_context' in enriched_context:
                context['time_context'] = enriched_context['time_context']
            
            # 날씨 정보
            if 'weather' in enriched_context:
                context['weather'] = enriched_context['weather']
            
            # 위치 정보
            if 'location' in enriched_context:
                context['location'] = enriched_context['location']
            
            # 영양 상태 정보
            if 'nutrition_status' in enriched_context:
                context['nutrition_status'] = enriched_context['nutrition_status']
        
        # 엔티티에서 추가 정보 추출 (폴백용)
        if hasattr(extracted_info, 'entities') and extracted_info.entities:
            entities = extracted_info.entities
            if hasattr(entities, 'emotion'):
                context['emotion'] = entities.emotion
            if hasattr(entities, 'group_size'):
                context['group_size'] = entities.group_size
            # weather가 없을 때만 엔티티에서 가져옴
            if 'weather' not in context and hasattr(entities, 'weather'):
                context['weather'] = entities.weather
        
        # 날씨 정보가 여전히 없으면 기본값
        if 'weather' not in context:
            context['weather'] = {'condition': 'clear', 'temp': 20}
        
        return context
    
    def _fallback_ranking(self, candidates, extracted_info, user_profile):
        """폴백: 기존 단순 규칙 기반 랭킹"""
        scores = []
        for candidate in candidates[:30]:  # 상위 30개만 평가
            # Layer 1에서 온 각 Funnel 점수들 활용
            base_score = max([
                candidate.get('collaborative_score', 0),
                candidate.get('content_score', 0),
                candidate.get('context_score', 0),
                candidate.get('base_score', 0)
            ])
            
            # 개인화 점수 추가
            personalization_bonus = 0
            
            # 선호 카테고리 보너스
            preferred_categories = user_profile.get('preferred_categories', [])
            if candidate.get('category') in preferred_categories:
                personalization_bonus += 0.2
            
            # 엔티티 매칭 보너스
            entities = extracted_info.entities
            if entities and entities.food_type:
                if entities.food_type.lower() in candidate.get('category', '').lower():
                    personalization_bonus += 0.3
            
            # 최종 점수
            final_score = base_score + personalization_bonus
            
            # shop 객체 찾기
            shop = self.knowledge.shops.get(candidate['shop_id'])
            if shop:
                scores.append((shop, candidate, final_score))
        
        # 점수순 정렬
        scores.sort(key=lambda x: x[2], reverse=True)
        
        # 상위 3개 추천
        recommendations = []
        for shop, candidate, score in scores[:3]:
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                menu = self._select_best_menu(shop_menus, extracted_info.entities.food_type if extracted_info.entities else None)
                recommendations.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'menu_name': menu.name,
                    'price': menu.price,
                    'category': shop.category,
                    'address': shop.address,
                    'wide_deep_score': float(score),
                    'funnel_source': candidate.get('funnel_source', 'unknown'),
                    'reason': self._get_recommendation_reason(shop, extracted_info)
                })
        
        return recommendations
    
    def _enhance_intent_with_context(
        self, 
        simplified_intent: str, 
        original_intent: str, 
        user_input: str, 
        conversation_context: List[Dict]
    ) -> str:
        """대화 컨텍스트를 고려하여 의도를 보정합니다."""
        
        # 부정 피드백 패턴
        negative_patterns = ['별로', '별론데', '싫어', '안좋', '다른', '말고', '아니', '그거말고', '빼고', '제외', '그닥', '안땡', '딴']
        
        # 추천 관련 키워드 (최근 추천이 있었는지 확인)
        recent_recommendation_keywords = ['추천', '맛집', '음식', '식당', '가게', '메뉴']
        
        # 최근 대화에서 추천이 있었는지 확인 (최근 2턴까지만, TTL 적용)
        has_recent_recommendation = False
        if conversation_context:
            # 최근 2턴만 확인 (사용자 + 봇 각 1턴씩 = 총 2개 메시지)
            recent_messages = conversation_context[-2:] if len(conversation_context) > 2 else conversation_context
            for msg in recent_messages:
                if isinstance(msg, dict):
                    content = msg.get('content', '') or msg.get('bot', '') or msg.get('assistant', '')
                    if any(keyword in content for keyword in recent_recommendation_keywords):
                        has_recent_recommendation = True
                        logger.info(f"[DEBUG] 최근 추천 감지: '{content[:30]}...'")
                        break
        
        # 부정 패턴이 있고 최근에 추천이 있었다면 음식추천으로 변환
        if any(pattern in user_input.lower() for pattern in negative_patterns) and has_recent_recommendation:
            logger.info(f"[DEBUG] 컨텍스트 보정: '{original_intent}' → '음식추천' (부정 피드백 + 최근 추천 감지)")
            return '음식추천'  # IntentPostProcessor가 이를 modify_request로 변환
        
        # 기존 의도 유지
        return simplified_intent
    
    def _extract_intent_and_entities(self, user_input: str, context: List[Dict], user_id: str = None) -> ExtractedInfo:
        """A.X Encoder NLU로 의도와 엔티티 추출 (맥락 고려)"""
        
        # 짧은 응답 처리기 확인
        from src.nlp.short_response_handler import get_short_response_handler
        short_handler = get_short_response_handler()
        
        # A.X Encoder NLU 우선 사용
        if self.ax_nlu:
            try:
                # NLG가 생성한 맥락 힌트 추가 (우선순위 1)
                enhanced_input = user_input
                # ConversationManager 가져오기
                from src.inference.conversation_manager import ConversationManager
                conversation_manager = ConversationManager()
                nlg_context = conversation_manager.get_last_context(user_id) if user_id and hasattr(conversation_manager, 'get_last_context') else None
                
                if nlg_context:
                    # NLG가 생성한 맥락 메타데이터 활용
                    context_type = nlg_context.get('context_type', '')
                    if context_type == 'food_recommendation':
                        # 음식 추천 맥락
                        categories = nlg_context.get('categories', [])
                        detail = nlg_context.get('detail', '')
                        if categories:
                            hint = f"[방금 {', '.join(categories)} 추천함] "
                        elif detail:
                            hint = f"[방금 {detail} 추천함] "
                        else:
                            hint = "[방금 음식 추천함] "
                        enhanced_input = hint + user_input
                        logger.info(f"[DEBUG] NLG 맥락 힌트 추가: {enhanced_input}")
                    elif context_type == 'location_based':
                        # 위치 기반 추천 맥락
                        detail = nlg_context.get('detail', '')
                        if detail:
                            hint = f"[방금 {detail} 근처 추천함] "
                            enhanced_input = hint + user_input
                            logger.info(f"[DEBUG] NLG 위치 맥락 힌트 추가: {enhanced_input}")
                
                # 폴백: 기존 방식 (NLG 맥락이 없을 때)
                elif context and 'last_intent' in context:
                    last_intent = context.get('last_intent')
                    # 음식 추천 후 피드백인 경우만 힌트 추가
                    if last_intent in ['음식추천', 'food_request', 'FOOD_REQUEST']:
                        # 추천 카테고리 정보가 있으면 포함
                        if 'last_recommendations' in context and context['last_recommendations']:
                            categories = []
                            for rec in context['last_recommendations'][:3]:
                                if 'category' in rec:
                                    categories.append(rec['category'])
                            if categories:
                                hint = f"[방금 {', '.join(set(categories))} 추천함] "
                                enhanced_input = hint + user_input
                                logger.info(f"[DEBUG] 폴백 맥락 힌트 추가: {enhanced_input}")
                
                nlu_result = self.ax_nlu.predict(enhanced_input)
                
                # 짧은 응답이면 맥락 기반 해석
                if short_handler.is_short_response(user_input):
                    interpreted_intent, confidence, metadata = short_handler.interpret(
                        user_input, context, nlu_result.intent
                    )
                    nlu_result.intent = interpreted_intent
                    nlu_result.confidence = confidence
                    
                    # 피드백 타입 추가
                    if metadata.get('feedback_type'):
                        from models.ax_encoder_nlu import Entity
                        nlu_result.entities.append(
                            Entity('FEEDBACK', metadata['feedback_type'])
                        )
                
                # 디버깅: NLU 결과 로그 출력
                logger.info(f"[DEBUG] A.X Encoder 원본 결과: intent='{nlu_result.intent}', confidence={nlu_result.confidence}")
                logger.info(f"[DEBUG] A.X Encoder 엔티티: {[(e.entity_type, e.value) for e in nlu_result.entities]}")
                
                # A.X Encoder 결과를 ExtractedInfo로 변환
                # 엔티티에서 정보 추출
                food_type = None
                location = None
                budget = None
                
                for entity in nlu_result.entities:
                    if entity.entity_type == "MENU":
                        food_type = entity.value
                    elif entity.entity_type == "LOCATION":
                        location = entity.value
                    elif entity.entity_type == "PRICE":
                        # 가격 엔티티를 예산으로 변환
                        try:
                            price_str = entity.value.replace('원', '').replace(',', '')
                            if '만' in price_str:
                                budget = int(price_str.replace('만', '')) * 10000
                            elif '천' in price_str:
                                budget = int(price_str.replace('천', '')) * 1000
                            else:
                                budget = int(price_str)
                        except:
                            pass
                
                # 의도 매핑
                intent_mapping = {
                    "음식추천": IntentType.FOOD_REQUEST,
                    "modify_request": IntentType.MODIFY_REQUEST,  # 부정 피드백 처리
                    "가격문의": IntentType.BUDGET_INQUIRY,
                    "잔액확인": IntentType.BALANCE_CHECK,
                    "쿠폰조회": IntentType.COUPON_INQUIRY,
                    "가게정보": IntentType.SHOP_INQUIRY,
                    "위치검색": IntentType.LOCATION_INQUIRY,
                    "영업시간": IntentType.TIME_INQUIRY,
                    "일반대화": IntentType.GENERAL_CHAT,
                    "감사인사": IntentType.THANKS,
                    "기타": IntentType.GENERAL_CHAT
                }
                
                mapped_intent = intent_mapping.get(nlu_result.intent, IntentType.FOOD_REQUEST)
                
                # IntentPostProcessor로 세부 의도 결정
                detailed_intent = None
                if self.intent_postprocessor:
                    simplified_intent = mapped_intent.name.lower() if hasattr(mapped_intent, 'name') else str(mapped_intent)
                    
                    # 대화 컨텍스트 기반 의도 보정
                    context_enhanced_intent = self._enhance_intent_with_context(
                        simplified_intent, nlu_result.intent, user_input, context
                    )
                    
                    detailed_intent = self.intent_postprocessor.process(
                        simplified_intent=context_enhanced_intent,
                        entities={'location': bool(location), 'food': bool(food_type), 'price': bool(budget)},
                        confidence=nlu_result.confidence,
                        text=user_input
                    )
                
                # 디버깅: 매핑 후 의도 확인
                logger.info(f"[DEBUG] 의도 매핑: '{nlu_result.intent}' → {mapped_intent}")
                
                extracted_info = ExtractedInfo(
                    raw_text=user_input,
                    intent=mapped_intent,
                    entities=ExtractedEntity(
                        food_type=food_type,
                        budget=budget,
                        location_preference=location,
                        companions=[],
                        time_preference=None,
                        menu_options=[],
                        special_requirements=[]
                    ),
                    confidence=nlu_result.confidence,
                    confidence_level=ConfidenceLevel.HIGH if nlu_result.confidence > 0.8 else 
                                   ConfidenceLevel.MEDIUM if nlu_result.confidence > 0.5 else ConfidenceLevel.LOW
                )
                # 세부 의도 추가
                if detailed_intent:
                    extracted_info.detailed_intent = detailed_intent
                
            except Exception as e:
                logger.warning(f"A.X Encoder NLU 추출 실패, 폴백 사용: {e}")
        
        # 폴백: 기존 규칙 기반 추출
        extracted_data = self._fallback_extraction(user_input)
        
        return ExtractedInfo(
            raw_text=user_input,
            intent=extracted_data['intent'],
            entities=ExtractedEntity(
                food_type=extracted_data['food_type'],
                budget=extracted_data['budget'],
                location_preference=extracted_data['location'],
                companions=[],
                time_preference=None,
                menu_options=[],
                special_requirements=[]
            ),
            confidence=0.8,
            confidence_level=ConfidenceLevel.HIGH
        )
    
    def _fallback_extraction(self, user_input: str) -> Dict:
        """폴백 추출 로직 (규칙 기반 + 향상된 패턴)"""
        import re
        
        # 음식 타입 추출 (확장된 패턴)
        food_type = None
        food_patterns = {
            '치킨': ['치킨', '통닭', '닭강정', '닭'],
            '한식': ['한식', '김치찌개', '된장찌개', '찌개', '국밥', '비빔밥', '불고기', '삼겹살'],
            '중식': ['중식', '중국', '짜장', '짬뽕', '탕수육', '마라', '양꼬치'],
            '일식': ['일식', '일본', '초밥', '스시', '라멘', '돈까스', '우동', '덮밥'],
            '양식': ['양식', '파스타', '스테이크', '리조또', '샐러드'],
            '피자': ['피자'],  # 피자 분리
            '분식': ['분식', '떡볶이', '김밥', '라면', '순대', '튀김'],
            '카페': ['카페', '커피', '디저트', '케이크', '베이커리'],
            '버거': ['버거', '햄버거', '수제버거']
        }
        
        for category, keywords in food_patterns.items():
            if any(keyword in user_input for keyword in keywords):
                food_type = category if category != '카페' else '카페/커피'
                break
        
        # 위치 추출 (user_location_manager + 추가 패턴)
        from utils.user_location import user_location_manager
        location = user_location_manager.extract_location_from_text(user_input)
        
        # 추가 위치 패턴
        if not location:
            # "XX동", "XX역", "XX구" 패턴 (제외 단어 필터링)
            # 먹고싶다, 먹고시퍼 등은 제외
            exclude_patterns = ['먹고', '이하로', '이상으로', '정도로', '으로', '하고']
            location_match = re.search(r'([가-힣]+(?:동|역|구|시))', user_input)
            if location_match:
                potential_location = location_match.group(1)
                # 제외 패턴 체크
                if not any(pattern in potential_location for pattern in exclude_patterns):
                    location = potential_location.replace('역', '').replace('동', '').replace('구', '')
        
        # 예산 추출 (향상된 패턴)
        budget = None
        # "X만원", "X만", "X천원" 패턴
        budget_match = re.search(r'(\d+)\s*만\s*(\d*)\s*원?|(\d+)\s*천\s*원?', user_input)
        if budget_match:
            if budget_match.group(1):  # X만원
                budget = int(budget_match.group(1)) * 10000
                if budget_match.group(2):  # X만Y천원
                    budget += int(budget_match.group(2)) * 1000
            elif budget_match.group(3):  # X천원
                budget = int(budget_match.group(3)) * 1000
        
        # 의도 분류 - 인사말 우선 체크
        intent = IntentType.CHITCHAT  # 기본값을 CHITCHAT으로
        
        # 인사말 패턴 체크 (최우선)
        greeting_patterns = ['안녕', '하이', 'hi', 'hello', '반가', '처음', '시작', '헬로']
        if any(pattern in user_input.lower() for pattern in greeting_patterns):
            intent = IntentType.CHITCHAT
        # 부정적 피드백 패턴 체크
        elif any(word in user_input for word in ['별로', '싫어', '안좋', '다른', '말고', '아니', '그거말고']):
            # 부정적 피드백이지만 음식 추천 의도로 처리 (다른 추천 원함)
            intent = IntentType.MODIFY_REQUEST
        # 음식 관련 패턴이 있을 때만 FOOD_REQUEST
        elif any(word in user_input for word in ['먹', '추천', '맛집', '배고', '식사', '밥', '음식', '라멘', 
                                                '치킨', '피자', '중식', '한식', '일식', '양식']):
            intent = IntentType.FOOD_REQUEST
        # 위치 또는 예산만 있는 경우도 음식 추천으로
        elif location or budget or food_type:
            intent = IntentType.FOOD_REQUEST
        elif any(word in user_input for word in ['고마워', '감사', '땡큐', '고맙', 'ㄱㅅ', 'ㄳ']):
            intent = IntentType.THANKS
        elif any(word in user_input for word in ['잘가', '바이', '종료', '끝', '그만', 'ㅂㅇ', 'ㅂㅂ', 'bye']):
            intent = IntentType.GOODBYE
        
        return {
            'food_type': food_type,
            'location': location,
            'budget': budget,
            'intent': intent
        }
    
    def _needs_recommendation(self, extracted_info: ExtractedInfo) -> bool:
        """추천이 필요한지 판단 - IntentPostProcessor의 28개 세부 의도 활용"""
        # 추천이 필요한 의도들 (확장됨)
        recommendation_intents = {
            IntentType.FOOD_REQUEST,
            IntentType.BUDGET_INQUIRY,  # 예산 문의도 추천 필요
            IntentType.LOCATION_INQUIRY,  # 위치 문의도 추천 필요
            IntentType.COUPON_INQUIRY,  # 쿠폰 문의도 추천 필요
            IntentType.MODIFY_REQUEST,  # 다른 추천 요청
        }
        
        # 기본 의도 체크
        if extracted_info.intent in recommendation_intents:
            return True
        
        # 세부 의도 체크 (IntentPostProcessor 활용)
        if hasattr(extracted_info, 'detailed_intent'):
            detailed_recommendation_intents = {
                'food_request', 'restaurant_search', 'menu_recommendation',
                'category_search', 'nearby_search', 'popular_request',
                'price_inquiry', 'discount_inquiry', 'student_discount',
                'delivery_inquiry', 'packaging_inquiry', 'budget_inquiry'
            }
            if extracted_info.detailed_intent in detailed_recommendation_intents:
                return True
        
        # 엔티티 기반 판단 (음식, 위치, 예산이 있으면 추천)
        if extracted_info.entities:
            if extracted_info.entities.food_type or \
               extracted_info.entities.location_preference or \
               extracted_info.entities.budget:
                return True
        
        # 키워드 기반 폴백
        food_keywords = ['먹', '추천', '맛집', '음식', '배고', '점심', '저녁', '아침', 
                        '치킨', '피자', '한식', '중식', '일식', '급식카드', '배달']
        if any(keyword in extracted_info.raw_text for keyword in food_keywords):
            return True
        
        return False
    
    def _get_wide_deep_recommendations(self, extracted_info: ExtractedInfo, user_profile: Dict) -> List[Dict]:
        """Wide&Deep 모델로 개인화 추천"""
        
        # 후보 가게 필터링
        candidate_shops = self._filter_shops_by_intent(extracted_info)
        
        if not candidate_shops:
            return []
        
        # Wide&Deep 점수 계산
        scores = []
        for shop in candidate_shops[:30]:  # 상위 30개만 계산 (속도)
            score = self._calculate_personalized_score(shop, extracted_info, user_profile)
            scores.append((shop, score))
        
        # 점수순 정렬
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 상위 3개 추천
        recommendations = []
        for shop, score in scores[:3]:
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                # 카테고리에 맞는 메뉴 선택
                menu = self._select_best_menu(shop_menus, extracted_info.entities.food_type)
                recommendations.append({
                    'shop_id': shop.id,
                    'shop_name': shop.name,
                    'menu_name': menu.name,
                    'price': menu.price,
                    'category': shop.category,
                    'address': shop.address,
                    'wide_deep_score': float(score),
                    'reason': self._get_recommendation_reason(shop, extracted_info)
                })
        
        return recommendations
    
    def _filter_shops_by_intent(self, extracted_info: ExtractedInfo) -> List:
        """의도에 따라 가게 필터링"""
        all_shops = list(self.knowledge.shops.values())
        filtered = []
        
        entities = extracted_info.entities
        
        for shop in all_shops:
            # 음식 타입 필터
            if entities.food_type:
                if entities.food_type.lower() not in shop.category.lower():
                    continue
            
            # 예산 필터
            if entities.budget:
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                if shop_menus:
                    avg_price = np.mean([m.price for m in shop_menus])
                    if avg_price > entities.budget * 1.5:  # 1.5배 여유
                        continue
            
            # 위치 필터
            if entities.location_preference:
                if entities.location_preference not in shop.address:
                    continue
            
            filtered.append(shop)
        
        return filtered
    
    def _calculate_personalized_score(self, shop, extracted_info: ExtractedInfo, user_profile: Dict) -> float:
        """Wide&Deep 모델로 개인화 점수 계산"""
        with torch.no_grad():
            # Wide 특성 생성 (50차원)
            wide_features = torch.zeros(50)
            
            # 카테고리 원핫 인코딩
            category_map = {
                'korean': 0, 'chinese': 1, 'japanese': 2, 'western': 3,
                'chicken': 4, 'pizza': 5, 'burger': 6, 'cafe': 7
            }
            
            for cat, idx in category_map.items():
                if cat in shop.category.lower():
                    wide_features[idx] = 1.0
            
            # 사용자 요청 특성
            if extracted_info.entities.food_type:
                food_type_idx = category_map.get(extracted_info.entities.food_type, -1)
                if food_type_idx >= 0:
                    wide_features[food_type_idx + 10] = 1.0  # 요청 카테고리 표시
            
            # 가격대
            shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
            if shop_menus:
                avg_price = np.mean([m.price for m in shop_menus])
                if avg_price < 10000:
                    wide_features[20] = 1.0  # 저가
                elif avg_price < 20000:
                    wide_features[21] = 1.0  # 중가
                else:
                    wide_features[22] = 1.0  # 고가
            
            # 착한가게 여부
            if shop.is_good_influence_shop:
                wide_features[25] = 1.0
            
            # Deep 특성
            user_id = torch.LongTensor([hash(user_profile.get('user_id', 'default')) % 10000])
            shop_id = torch.LongTensor([shop.id % 1000])
            category_id = torch.LongTensor([category_map.get(shop.category.lower(), 0)])
            
            numerical = torch.zeros(10)
            numerical[0] = 4.0  # 평점 (기본값)
            numerical[1] = user_profile.get('meal_frequency', 3.0)
            numerical[2] = 1.0 if shop.is_good_influence_shop else 0.0
            
            # 모델 예측
            score = self.wide_deep_model(
                wide_features.unsqueeze(0).to(self.device),
                user_id.to(self.device),
                shop_id.to(self.device),
                category_id.to(self.device),
                numerical.unsqueeze(0).to(self.device)
            )
            
            return score.item()
    
    def _select_best_menu(self, menus: List, food_type: Optional[str]) -> Any:
        """가장 적합한 메뉴 선택"""
        if not menus:
            return None
        
        # 음식 타입과 매칭되는 메뉴 우선
        if food_type:
            for menu in menus:
                if food_type in menu.name.lower():
                    return menu
        
        # 인기 메뉴 우선
        popular = [m for m in menus if hasattr(m, 'is_popular') and m.is_popular]
        if popular:
            return popular[0]
        
        # 가장 저렴한 메뉴
        return min(menus, key=lambda x: x.price)
    
    def _merge_recommendations(self, llm_recs: List, wide_deep_recs: List, user_intent) -> List:
        """LLM 추천과 Wide&Deep 추천 병합"""
        
        # Wide&Deep이 더 정확한 경우 우선
        if wide_deep_recs and len(wide_deep_recs) >= 3:
            return wide_deep_recs
        
        # 둘 다 있으면 병합
        merged = wide_deep_recs.copy()
        
        # LLM 추천 중 Wide&Deep에 없는 것 추가
        existing_shops = {r['shop_id'] for r in merged}
        for rec in llm_recs:
            if rec.get('shop_id') not in existing_shops:
                merged.append(rec)
                if len(merged) >= 5:
                    break
        
        return merged[:3]  # 최대 3개
    
    def _apply_additional_filters(self, shops: List, entities: ExtractedEntity) -> List:
        """위치 필터링된 가게들에 추가 필터 적용"""
        filtered = shops.copy()
        
        # 음식 타입 필터
        if entities.food_type:
            filtered = [s for s in filtered if entities.food_type.lower() in s.category.lower()]
        
        # 예산 필터
        if entities.budget:
            filtered_by_budget = []
            for shop in filtered:
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                if shop_menus:
                    # 예산 이하 메뉴가 있는지 확인
                    affordable_menus = [m for m in shop_menus if m.price <= entities.budget * 1.2]
                    if affordable_menus:
                        filtered_by_budget.append(shop)
            filtered = filtered_by_budget
        
        return filtered
    
    def _apply_additional_filters_with_mix(self, shops: List, entities: ExtractedEntity, location_info: Dict) -> List:
        """위치 필터링된 가게들에 카테고리 믹스 및 평점/거리 가중치 적용"""
        
        # 1. 거리 및 평점 기반 스코어 계산
        shops_with_scores = []
        for shop in shops:
            distance = float('inf')
            if hasattr(self, '_location_metadata') and shop.id in self._location_metadata:
                distance = self._location_metadata[shop.id]['distance']
            
            # 거리 점수 (가까울수록 높음, 5km 초과는 0점)
            distance_score = max(0, 1 - (distance / 5.0))
            
            # 평점 (없으면 3.5점 기본)
            rating = getattr(shop, 'rating', 3.5)
            
            # 최종 점수 = 거리 가중치 60% + 평점 가중치 40%
            combined_score = (distance_score * 0.6) + ((rating / 5.0) * 0.4)
            shops_with_scores.append({'shop': shop, 'score': combined_score, 'distance': distance})
        
        # 점수순으로 정렬
        shops_with_scores.sort(key=lambda x: x['score'], reverse=True)
        sorted_shops = [item['shop'] for item in shops_with_scores]
        
        # 2. 요청 카테고리와 다른 카테고리 분리
        category_matched = []
        other_shops = []
        
        food_type_lower = entities.food_type.lower() if entities.food_type else ''
        
        for shop in sorted_shops:
            # 예산 필터는 공통으로 적용
            if entities.budget:
                shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop.id]
                if not any(m.price <= entities.budget * 1.2 for m in shop_menus):
                    continue
            
            if food_type_lower and food_type_lower in shop.category.lower():
                category_matched.append(shop)
            else:
                other_shops.append(shop)
        
        # 3. 결과 조합: 요청 카테고리 2개 + 다른 카테고리 1~2개 (총 3~4개)
        final_candidates = []
        final_candidates.extend(category_matched[:2])
        
        remaining = 4 - len(final_candidates)
        final_candidates.extend(other_shops[:remaining])
        
        # 로그 출력
        if category_matched:
            logger.info(f"카테고리 매칭 {len(category_matched[:2])}개 + 다른 카테고리 {len(other_shops[:remaining])}개")
        else:
            logger.info(f"평점/거리 기반 상위 {len(final_candidates)}개 선택")
        
        return final_candidates[:4]  # 최대 4개 반환
    
    def _create_rag_documents_from_shops(self, shops: List):
        """가게 리스트를 RAG 문서 형태로 변환"""
        from rag.documents import ShopDocument
        documents = []
        
        for shop in shops:
            doc = ShopDocument({
                'id': shop.id,
                'name': shop.name,
                'category': shop.category,
                'address': shop.address,
                'rating': getattr(shop, 'rating', 4.0),
                'is_good_influence_shop': shop.is_good_influence_shop
            })
            documents.append(doc)
        
        return documents
    
    def _get_recommendation_reason(self, shop, extracted_info: ExtractedInfo) -> str:
        """추천 이유 생성 (거리 정보 포함)"""
        reasons = []
        
        # 거리 정보 추가
        if hasattr(self, '_location_metadata') and shop.id in self._location_metadata:
            distance_info = self._location_metadata[shop.id]
            distance = distance_info.get('distance')
            location_name = distance_info.get('location_name', '')
            
            if distance is not None:
                if distance < 1:
                    reasons.append(f"{location_name}에서 도보 {int(distance*1000)}m")
                elif distance < 3:
                    reasons.append(f"{location_name}에서 {distance:.1f}km (가까움)")
                else:
                    reasons.append(f"{location_name}에서 {distance:.1f}km")
        
        # 음식 타입 매칭
        if extracted_info.entities.food_type:
            if extracted_info.entities.food_type.lower() in shop.category.lower():
                reasons.append(f"✅ {extracted_info.entities.food_type} 전문")
        
        # 착한가게
        if shop.is_good_influence_shop:
            reasons.append("💚 착한가게")
        
        return " | ".join(reasons) if reasons else "인기 맛집"
    
    def record_user_feedback(self, session_id: str, turn_id: int, 
                            selected_shop_id: int, unselected_shop_ids: List[int],
                            reason: Optional[str] = None) -> bool:
        """사용자 피드백 기록
        
        Args:
            session_id: 세션 ID
            turn_id: 턴 ID
            selected_shop_id: 선택된 가게 ID
            unselected_shop_ids: 선택되지 않은 가게 ID들
            reason: 선택 이유
            
        Returns:
            성공 여부
        """
        try:
            self.session_manager.record_user_selection(
                session_id, turn_id, selected_shop_id, 
                unselected_shop_ids, reason
            )
            logger.info(f"피드백 기록 완료: session={session_id}, turn={turn_id}, selected={selected_shop_id}")
            
            # Wide&Deep 모델이 있으면 실시간 업데이트 (선택적)
            if self.wide_deep_model:
                # 간단한 온라인 학습 또는 가중치 조정
                # 여기서는 로그만 남기고 실제 구현은 별도로
                logger.info(f"Wide&Deep 모델 피드백 반영 대기: shop_id={selected_shop_id}")
            
            return True
        except Exception as e:
            logger.error(f"피드백 기록 실패: {e}")
            return False
    
    def get_training_data(self) -> List[Dict]:
        """세션 데이터에서 학습 데이터 추출"""
        return self.session_manager.get_training_data()
    
    def _get_default_user_profile(self) -> Dict:
        """기본 사용자 프로필"""
        return {
            'user_id': 'default',
            'age_group': '20s',
            'preferred_cuisines': ['korean', 'chicken'],
            'price_sensitivity': 'medium',
            'meal_frequency': 3.0
        }
    
    def _add_tmap_info_to_recommendations(self, recommendations: List[Dict], user_profile: Optional[Dict] = None) -> List[Dict]:
        """추천 결과에 T맵 정보 추가
        
        Args:
            recommendations: 추천 리스트
            user_profile: 사용자 프로필 (위치 정보 포함 가능)
            
        Returns:
            T맵 정보가 추가된 추천 리스트
        """
        from src.utils.tmap_api import TMapRouteAPI
        from src.utils.tmap_utils import TmapURLGenerator
        
        # T맵 API 초기화
        tmap_api = TMapRouteAPI()
        url_gen = TmapURLGenerator()
        
        # 사용자 위치 확인 (기본값: 부평역)
        user_lat = 37.4914
        user_lng = 126.7247
        user_location_name = "부평역"
        
        if user_profile and 'location' in user_profile:
            loc = user_profile['location']
            if isinstance(loc, dict):
                user_lat = loc.get('lat', user_lat)
                user_lng = loc.get('lng', user_lng)
                user_location_name = loc.get('name', user_location_name)
        
        # 각 추천에 T맵 정보 추가
        for rec in recommendations:
            try:
                # 가게 좌표 가져오기 (없으면 더미 좌표)
                shop_lat = rec.get('latitude', 37.4914 + (hash(rec['shop_name']) % 100) * 0.001)
                shop_lng = rec.get('longitude', 126.7247 + (hash(rec['shop_name']) % 100) * 0.001)
                
                # 경로 정보 조회 (도보)
                route_info = tmap_api.get_route_info(
                    start_lat=user_lat,
                    start_lng=user_lng,
                    end_lat=shop_lat,
                    end_lng=shop_lng,
                    route_type="pedestrian"
                )
                
                # T맵 URL 생성
                tmap_url = url_gen.generate_web_url(
                    start_lat=user_lat,
                    start_lng=user_lng,
                    end_lat=shop_lat,
                    end_lng=shop_lng,
                    start_name=user_location_name,
                    end_name=rec['shop_name']
                )
                
                # T맵 정보 추가
                rec['tmap_info'] = {
                    'distance_meters': route_info['distance'] if route_info else None,
                    'walking_time_minutes': route_info['time'] // 60 if route_info else None,
                    'distance_text': route_info['distance_text'] if route_info else "거리 정보 없음",
                    'time_text': route_info['time_text'] if route_info else "시간 정보 없음",
                    'directions_url': tmap_url
                }
                
                # 추천 이유에도 거리 정보 추가
                if route_info:
                    distance_km = route_info['distance'] / 1000
                    if distance_km < 0.5:
                        distance_desc = "도보 5분 이내"
                    elif distance_km < 1:
                        distance_desc = f"도보 {route_info['time']//60}분"
                    else:
                        distance_desc = f"{distance_km:.1f}km 거리"
                    
                    if 'reason' in rec:
                        rec['reason'] = f"{rec['reason']} | {distance_desc}"
                    else:
                        rec['reason'] = distance_desc
                        
            except Exception as e:
                logger.warning(f"T맵 정보 추가 실패 ({rec['shop_name']}): {e}")
                # 실패해도 기본값 추가
                rec['tmap_info'] = {
                    'distance_meters': None,
                    'walking_time_minutes': None,
                    'distance_text': "거리 정보 없음",
                    'time_text': "시간 정보 없음",
                    'directions_url': None
                }
        
        return recommendations
    
    def _check_navigation_context(self, user_id: str, user_input: str) -> Optional[ChatbotResponse]:
        """대화 컨텍스트에서 길찾기 응답 확인"""
        
        state = conversation_manager.get_state(user_id)
        
        # 길찾기 대기 중이고 사용자가 위치를 입력한 경우 (예: "코엑스")
        if state.waiting_for_navigation and not any(kw in user_input.lower() for kw in ['아니', '취소', 'ㄴㄴ', '됐']):
            # "응", "좋아" 같은 수락이 아니라 위치명이 입력된 경우
            if not any(kw in user_input.lower() for kw in ['응', 'ㅇㅇ', '좋아', 'ㅇㅋ', '네', '그래']):
                # 위치로 간주하고 처리
                state.user_location = user_input
                conversation_manager.set_user_location(user_id, user_input)
                navigation_status = 'accept'
            else:
                # 일반적인 길찾기 응답 확인
                navigation_status = conversation_manager.check_navigation_response(user_id, user_input)
        else:
            # 대화 관리자에서 길찾기 응답 확인
            navigation_status = conversation_manager.check_navigation_response(user_id, user_input)
        
        if navigation_status == 'accept':
            # 사용자가 길찾기를 수락한 경우
            selected_shop = conversation_manager.get_selected_shop(user_id)
            
            if selected_shop:
                # 선택된 가게 정보에서 좌표 가져오기
                shop_id = selected_shop.get('shop_id')
                shop_name = selected_shop.get('shop_name', '선택한 가게')
                
                if shop_id and shop_id in self.knowledge.shops:
                    shop = self.knowledge.shops[shop_id]
                    
                    # 좌표가 있는지 확인
                    if hasattr(shop, 'latitude') and hasattr(shop, 'longitude') and shop.latitude and shop.longitude:
                        # 사용자 위치 확인
                        state = conversation_manager.get_state(user_id)
                        
                        # user_location_manager에서 위치 확인
                        if not state.user_location:
                            user_loc = user_location_manager.get_user_location(user_id)
                            if user_loc and user_loc.get('location_name'):
                                state.user_location = user_loc.get('location_name')
                                logger.info(f"저장된 사용자 위치 사용: {state.user_location}")
                        
                        # 사용자 위치가 없으면 요청
                        if not state.user_location:
                            response = ChatbotResponse(
                                text=conversation_manager.generate_navigation_ready_message(),
                                metadata={'waiting_for_location': True, 'selected_shop': selected_shop}
                            )
                            return response
                        
                        # 사용자 위치가 있으면 T맵 URL 생성
                        from utils.location_utils import normalize_location
                        location_info = normalize_location(state.user_location)
                        
                        if location_info and 'lat' in location_info:
                            # T맵 네비게이션 응답 생성
                            navigation_response = create_tmap_navigation_response(
                                shop_name=shop_name,
                                shop_lat=shop.latitude,
                                shop_lng=shop.longitude,
                                user_location_name=state.user_location
                            )
                            
                            response = ChatbotResponse(
                                text=navigation_response['text'],
                                metadata=navigation_response.get('metadata', {})
                            )
                            
                            # Quick Reply 버튼 추가
                            if 'quick_reply_buttons' in navigation_response:
                                response.metadata['quick_reply_buttons'] = navigation_response['quick_reply_buttons']
                            
                            # 대화 상태 초기화
                            conversation_manager.clear_state(user_id)
                            
                            return response
                        else:
                            # 위치를 인식할 수 없는 경우
                            response = ChatbotResponse(
                                text=f"'{state.user_location}'를 찾을 수 없어요. 다른 위치를 알려주세요! (예: 강남역, 홍대입구)",
                                metadata={'waiting_for_location': True, 'selected_shop': selected_shop}
                            )
                            return response
                    else:
                        # 좌표가 없는 경우
                        response = ChatbotResponse(
                            text=f"아쉽게도 {shop_name}의 정확한 위치 정보가 없어서 길찾기를 제공할 수 없어요. 😢\n주소: {shop.address}"
                        )
                        conversation_manager.clear_state(user_id)
                        return response
        
        elif navigation_status == 'reject':
            # 사용자가 길찾기를 거절한 경우
            response = ChatbotResponse(
                text=conversation_manager.generate_rejection_response()
            )
            conversation_manager.clear_state(user_id)
            return response
        
        # 사용자가 위치를 입력한 경우 (waiting_for_location 상태)
        state = conversation_manager.get_state(user_id)
        
        # waiting_for_location 메타데이터를 체크
        if hasattr(state, 'selected_shop') and state.selected_shop:
            # 위치로 보이는 입력인지 확인
            from utils.location_utils import normalize_location
            location_info = normalize_location(user_input)
            
            if location_info and state.waiting_for_navigation:
                # 사용자 위치 저장
                conversation_manager.set_user_location(user_id, user_input)
                
                # T맵 URL 생성
                selected_shop = state.selected_shop
                shop_id = selected_shop.get('shop_id')
                shop_name = selected_shop.get('shop_name', '선택한 가게')
                
                if shop_id and shop_id in self.knowledge.shops:
                    shop = self.knowledge.shops[shop_id]
                    
                    if hasattr(shop, 'latitude') and hasattr(shop, 'longitude'):
                        if shop.latitude and shop.longitude and 'lat' in location_info:
                            # T맵 네비게이션 응답 생성
                            navigation_response = create_tmap_navigation_response(
                                shop_name=shop_name,
                                shop_lat=shop.latitude,
                                shop_lng=shop.longitude,
                                user_location_name=user_input
                            )
                            
                            response = ChatbotResponse(
                                text=navigation_response['text'],
                                metadata=navigation_response.get('metadata', {})
                            )
                            
                            # Quick Reply 버튼 추가
                            if 'quick_reply_buttons' in navigation_response:
                                response.metadata['quick_reply_buttons'] = navigation_response['quick_reply_buttons']
                            
                            # 대화 상태 초기화
                            conversation_manager.clear_state(user_id)
                            
                            return response
        
        return None
    
    def process_feedback(self, user_id: str, shop_id: int, feedback_type: str, metadata: Optional[Dict] = None):
        """사용자 피드백 처리 및 TeenPersonalizer 프로필 업데이트"""
        try:
            from src.personalization.teen_personalizer import get_personalizer
            personalizer = get_personalizer()
            
            # 피드백 타입 매핑
            interaction_map = {
                "click": "click",
                "view": "view",
                "order": "order",
                "like": "like",
                "dislike": "dislike",
                "detail_view": "click",
                "navigation": "click",
                "share": "like"
            }
            
            interaction_type = interaction_map.get(feedback_type, "view")
            
            # 메타데이터 보강
            if metadata is None:
                metadata = {}
            
            # shop 정보 추가
            if shop_id and shop_id in self.knowledge.shops:
                shop = self.knowledge.shops[shop_id]
                metadata["category"] = shop.category
                metadata["name"] = shop.name
                # price_range가 없을 수 있으므로 안전하게 처리
                if hasattr(shop, 'price_range'):
                    metadata["price_range"] = shop.price_range
                else:
                    # 메뉴에서 평균 가격 계산
                    shop_menus = [m for m in self.knowledge.menus.values() if m.shop_id == shop_id]
                    if shop_menus:
                        avg_price = sum(m.price for m in shop_menus) / len(shop_menus)
                        metadata["price_range"] = int(avg_price)
            
            # TeenPersonalizer 프로필 업데이트 (EMA 실시간 학습)
            personalizer.update_from_interaction(
                user_id=user_id,
                shop_id=shop_id,
                interaction_type=interaction_type,
                metadata=metadata
            )
            
            # SessionDataManager에도 기록 (UserFeedback 구조에 맞게)
            if hasattr(self, "session_manager"):
                feedback = UserFeedback(
                    selected_shop_id=shop_id if feedback_type in ['click', 'order', 'like'] else None,
                    selection_reason=feedback_type,
                    implicit_signals={
                        'type': feedback_type,
                        'timestamp': datetime.now().isoformat(),
                        'metadata': metadata
                    }
                )
                # 세션 찾기 (최근 세션 사용)
                session_id = metadata.get("session_id", f"user_{user_id}")
                
                try:
                    self.session_manager.add_feedback(session_id, feedback)
                except Exception as e:
                    # 세션 매니저 오류는 무시 (핵심 기능 아님)
                    logger.debug(f"Session manager feedback failed: {e}")
            
            # 데이터 수집: 피드백 데이터
            if self.data_collector:
                self.data_collector.collect_feedback_data(
                    user_id=user_id,
                    feedback_type=feedback_type,
                    feedback_content={'shop_id': shop_id},
                    context=metadata
                )
            
            logger.info(f"Feedback processed: user={user_id}, shop={shop_id}, type={feedback_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process feedback: {e}")
            return False
    
    def shutdown_data_collector(self):
        """데이터 수집기 정상 종료"""
        if self.data_collector:
            try:
                # 버퍼에 남은 데이터 저장
                self.data_collector._flush_all_buffers()
                # 수집기 종료
                self.data_collector.is_running = False
                logger.info("데이터 수집기 종료 완료")
            except Exception as e:
                logger.error(f"데이터 수집기 종료 실패: {e}")
