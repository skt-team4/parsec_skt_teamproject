"""
나비얌 데이터 로더
전처리된 데이터를 로드하여 챗봇용 구조로 변환
"""

import json
import pandas as pd
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from datetime import datetime

from src.data.data_structure import (
    NaviyamShop, NaviyamMenu, NaviyamCoupon,
    NaviyamKnowledge, TrainingData, IntentType, ExtractedEntity
)

logger = logging.getLogger(__name__)


class DataLoader:
    """나비얌 데이터 로더"""

    def __init__(self, data_config=None, debug: bool = False):
        """
        Args:
            data_config: DataConfig 객체
            debug: 디버그 모드 여부
        """
        if data_config:
            self.data_path = Path(data_config.data_path)
            self.output_path = Path(data_config.output_path)
            self.cache_dir = Path(data_config.cache_dir)
            self.max_conversations = data_config.max_conversations
            self.save_processed = data_config.save_processed
        else:
            # 기본값 설정
            self.data_path = Path('data')
            self.output_path = Path('outputs')
            self.cache_dir = Path('cache')
            self.max_conversations = 100
            self.save_processed = False
        
        self.debug = debug

        self.knowledge = NaviyamKnowledge()

        # 디렉토리 생성
        self.output_path.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        # 실제 데이터 사용 (FAISS와 동일)
        self.real_data_path = Path(__file__).parent / 'restaurants_real.json'

    def load_knowledge(self) -> NaviyamKnowledge:
        """지식베이스 로드 (별칭)"""
        return self.load_all_data()
    
    def load_all_data(self) -> NaviyamKnowledge:
        """모든 나비얌 데이터 로드"""
        try:
            logger.info("나비얌 데이터 로딩 시작 (restaurants_real.json 사용)...")
            
            # FAISS와 동일한 데이터 소스 사용
            if self.real_data_path.exists():
                with open(self.real_data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 가게 데이터 로드
                for shop_data in data.get('shops', []):
                    shop = NaviyamShop(
                        id=shop_data['id'],
                        name=shop_data['name'],
                        category=shop_data['category'],
                        address=shop_data['address'],
                        is_good_influence_shop=shop_data.get('is_good_influence_shop', False),
                        is_food_card_shop='Y' if shop_data.get('is_food_card_shop', False) else 'N',
                        open_hour=shop_data.get('open_hour', '10:00'),
                        close_hour=shop_data.get('close_hour', '22:00'),
                        owner_message=shop_data.get('owner_message', ''),
                        latitude=shop_data.get('latitude'),
                        longitude=shop_data.get('longitude')
                    )
                    # 정수 키만 저장 (중복 방지)
                    self.knowledge.shops[shop.id] = shop
                
                # 메뉴 데이터 로드
                for menu_data in data.get('menus', []):
                    menu = NaviyamMenu(
                        id=menu_data['id'],
                        shop_id=menu_data['shop_id'],
                        name=menu_data['name'],
                        price=menu_data['price'],
                        category=menu_data.get('category', '기타'),
                        is_popular=menu_data.get('is_popular', False)
                    )
                    self.knowledge.menus[menu.id] = menu
                
                logger.info(f"실제 데이터 로드 완료: {len(self.knowledge.shops)}개 가게, {len(self.knowledge.menus)}개 메뉴")

            # 데이터 후처리
            self._post_process_data()

            # 캐시 저장
            if self.save_processed:
                self._save_to_cache(cache_file)

            logger.info(f"데이터 로딩 완료: "
                        f"가게 {len(self.knowledge.shops)}개, "
                        f"메뉴 {len(self.knowledge.menus)}개, "
                        f"쿠폰 {len(self.knowledge.coupons)}개")

            return self.knowledge

        except Exception as e:
            logger.error(f"데이터 로딩 실패: {e}")
            raise

    def _load_menu_shop_mapping(self):
        """1순위: 메뉴-가게 연결 테이블 로드"""
        file_path = self.data_path / self.file_mapping['shops']
        if not file_path.exists():
            logger.warning(f"메뉴-가게 매핑 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"메뉴-가게 매핑 데이터 로드: {len(df)}개 행")

            # 가게 정보 처리
            shop_groups = df.groupby(['shop_id', 'shop_name', 'category', 'is_good_influence_shop'])

            for (shop_id, shop_name, category, is_good_shop), group in shop_groups:
                shop = NaviyamShop(
                    id=int(shop_id),
                    name=str(shop_name),
                    category=str(category),
                    is_good_influence_shop=bool(is_good_shop),
                    is_food_card_shop="unknown",  # 기본값
                    address="",  # 나중에 업데이트
                    open_hour="",
                    close_hour=""
                )
                self.knowledge.shops[shop.id] = shop

            # 메뉴 정보 처리
            for _, row in df.iterrows():
                menu = NaviyamMenu(
                    id=int(row['menu_id']) if pd.notna(row.get('menu_id')) else hash(row['menu_name']),
                    shop_id=int(row['shop_id']),
                    name=str(row['menu_name']),
                    price=int(row['price']) if pd.notna(row['price']) else 0,
                    category=str(row.get('menu_category', '기타'))
                )
                self.knowledge.menus[menu.id] = menu

        except Exception as e:
            logger.error(f"메뉴-가게 매핑 로드 실패: {e}")

    def _load_popular_menus(self):
        """2순위: 인기 메뉴 순위 로드"""
        file_path = self.data_path / self.file_mapping['popular_menus']
        if not file_path.exists():
            logger.warning(f"인기 메뉴 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"인기 메뉴 데이터 로드: {len(df)}개")

            # 인기 메뉴 표시 업데이트
            for _, row in df.iterrows():
                menu_name = str(row['menu_name'])
                order_count = int(row.get('order_count', 0))

                # 메뉴 이름으로 찾아서 인기도 표시
                for menu in self.knowledge.menus.values():
                    if menu.name == menu_name:
                        menu.is_popular = order_count >= 3  # 3번 이상 주문시 인기 메뉴
                        break

        except Exception as e:
            logger.error(f"인기 메뉴 로드 실패: {e}")

    def _load_reviews(self):
        """3순위: 리뷰 데이터 로드 (자연어 톤 학습용)"""
        file_path = self.data_path / self.file_mapping['reviews']
        if not file_path.exists():
            logger.warning(f"리뷰 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"리뷰 데이터 로드: {len(df)}개")

            for _, row in df.iterrows():
                review_data = {
                    'comment': str(row['cleaned_comment']),
                    'sentiment': str(row.get('sentiment', 'neutral')),
                    'keywords': row.get('food_keywords', '').split(',') if pd.notna(row.get('food_keywords')) else [],
                    'tone': str(row.get('tone', 'friendly'))
                }
                self.knowledge.reviews.append(review_data)

        except Exception as e:
            logger.error(f"리뷰 데이터 로드 실패: {e}")

    def _load_price_categories(self):
        """4순위: 가격대별 메뉴 분류 로드"""
        file_path = self.data_path / self.file_mapping['price_categories']
        if not file_path.exists():
            logger.warning(f"가격 카테고리 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"가격 카테고리 데이터 로드: {len(df)}개")

            # 가격대별 인기 조합 생성
            for _, row in df.iterrows():
                combination = {
                    'price_range': str(row['price_range']),  # budget, mid, premium
                    'category': str(row['category']),
                    'avg_price': int(row['avg_price']) if pd.notna(row['avg_price']) else 0,
                    'menu_list': str(row.get('representative_menus', '')).split(','),
                    'recommendation_reason': f"{row['price_range']} 가격대 {row['category']} 추천"
                }
                self.knowledge.popular_combinations.append(combination)

        except Exception as e:
            logger.error(f"가격 카테고리 로드 실패: {e}")

    def _load_operation_info(self):
        """9순위: 가게 운영정보 로드"""
        file_path = self.data_path / self.file_mapping['operation_info']
        if not file_path.exists():
            logger.warning(f"운영정보 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"가게 운영정보 로드: {len(df)}개")

            for _, row in df.iterrows():
                shop_id = int(row['shop_id'])
                if shop_id in self.knowledge.shops:
                    shop = self.knowledge.shops[shop_id]
                    shop.open_hour = str(row.get('open_hour', ''))
                    shop.close_hour = str(row.get('close_hour', ''))
                    shop.break_start_hour = str(row.get('break_start_hour', '')) if pd.notna(
                        row.get('break_start_hour')) else None
                    shop.break_end_hour = str(row.get('break_end_hour', '')) if pd.notna(
                        row.get('break_end_hour')) else None
                    shop.current_status = str(row.get('current_status', 'UNKNOWN'))
                    shop.owner_message = str(row.get('owner_message', '')) if pd.notna(
                        row.get('owner_message')) else None
                    shop.address = str(row.get('address', ''))
                    shop.ordinary_discount = bool(row.get('ordinary_discount', False))

        except Exception as e:
            logger.error(f"운영정보 로드 실패: {e}")

    def _load_coupons(self):
        """쿠폰 정보 로드"""
        file_path = self.data_path / self.file_mapping['coupons']
        if not file_path.exists():
            logger.warning(f"쿠폰 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"쿠폰 데이터 로드: {len(df)}개")

            for _, row in df.iterrows():
                coupon = NaviyamCoupon(
                    id=str(row['coupon_id']),
                    name=str(row['coupon_name']),
                    description=str(row['description']),
                    amount=int(row['discount_amount']) if pd.notna(row['discount_amount']) else 0,
                    min_amount=int(row['min_amount']) if pd.notna(row.get('min_amount')) else None,
                    usage_type=str(row.get('usage_type', 'ALL')),
                    target=str(row.get('target', 'ALL')).split(','),
                    applicable_shops=[]  # 나중에 매핑에서 채움
                )
                self.knowledge.coupons[coupon.id] = coupon

        except Exception as e:
            logger.error(f"쿠폰 데이터 로드 실패: {e}")

    def _load_menu_options(self):
        """메뉴 옵션 로드"""
        file_path = self.data_path / self.file_mapping['menu_options']
        if not file_path.exists():
            logger.warning(f"메뉴 옵션 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"메뉴 옵션 데이터 로드: {len(df)}개")

            # 메뉴별 옵션 그룹화
            option_groups = df.groupby('menu_id')

            for menu_id, group in option_groups:
                if menu_id in self.knowledge.menus:
                    options = []
                    for _, option_row in group.iterrows():
                        option = {
                            'name': str(option_row['option_name']),
                            'additional_price': int(option_row.get('additional_price', 0)) if pd.notna(
                                option_row.get('additional_price')) else 0,
                            'category': str(option_row.get('option_category', '기타'))
                        }
                        options.append(option)
                    self.knowledge.menus[menu_id].options = options

        except Exception as e:
            logger.error(f"메뉴 옵션 로드 실패: {e}")

    def _load_user_patterns(self):
        """사용자 패턴 데이터 로드"""
        file_path = self.data_path / self.file_mapping['user_patterns']
        if not file_path.exists():
            logger.warning(f"사용자 패턴 파일 없음: {file_path}")
            return

        try:
            df = pd.read_csv(file_path)
            logger.info(f"사용자 패턴 데이터 로드: {len(df)}개")

            # 사용자 클러스터 정보를 popular_combinations에 추가
            for _, row in df.iterrows():
                pattern = {
                    'cluster_type': str(row.get('cluster_type', 'general')),
                    'preferred_categories': str(row.get('preferred_categories', '')).split(','),
                    'avg_budget': int(row.get('avg_budget', 7000)) if pd.notna(row.get('avg_budget')) else 7000,
                    'common_orders': str(row.get('common_orders', '')).split(','),
                    'recommendation_reason': f"{row.get('cluster_type', 'general')} 유형 사용자 패턴"
                }
                self.knowledge.popular_combinations.append(pattern)

        except Exception as e:
            logger.error(f"사용자 패턴 로드 실패: {e}")

    def _post_process_data(self):
        """데이터 후처리 및 검증"""
        # 착한가게 우선 정렬
        good_shops = [shop for shop in self.knowledge.shops.values() if shop.is_good_influence_shop]
        logger.info(f"착한가게 수: {len(good_shops)}")

        # 메뉴-가게 연결 검증
        orphan_menus = [menu for menu in self.knowledge.menus.values()
                        if menu.shop_id not in self.knowledge.shops]
        if orphan_menus:
            logger.warning(f"연결되지 않은 메뉴 {len(orphan_menus)}개 발견")

        # 가격 0인 메뉴 처리
        zero_price_menus = [menu for menu in self.knowledge.menus.values() if menu.price == 0]
        logger.info(f"가격 정보 없는 메뉴: {len(zero_price_menus)}개")

    def _load_from_cache(self, cache_file: Path) -> NaviyamKnowledge:
        """캐시에서 데이터 로드"""
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # JSON을 NaviyamKnowledge로 변환
        knowledge = NaviyamKnowledge()

        # shops 복원
        for shop_id, shop_data in data.get('shops', {}).items():
            shop = NaviyamShop(**shop_data)
            knowledge.shops[int(shop_id)] = shop

        # menus 복원
        for menu_id, menu_data in data.get('menus', {}).items():
            menu = NaviyamMenu(**menu_data)
            knowledge.menus[int(menu_id)] = menu

        # coupons 복원
        for coupon_id, coupon_data in data.get('coupons', {}).items():
            coupon = NaviyamCoupon(**coupon_data)
            knowledge.coupons[coupon_id] = coupon

        knowledge.reviews = data.get('reviews', [])
        knowledge.popular_combinations = data.get('popular_combinations', [])

        logger.info("캐시에서 데이터 로드 완료")
        return knowledge

    def _save_to_cache(self, cache_file: Path):
        """데이터를 캐시에 저장"""
        knowledge_dict = {
            'shops': {str(k): v.__dict__ for k, v in self.knowledge.shops.items()},
            'menus': {str(k): v.__dict__ for k, v in self.knowledge.menus.items()},
            'coupons': {str(k): v.__dict__ for k, v in self.knowledge.coupons.items()},
            'reviews': self.knowledge.reviews,
            'popular_combinations': self.knowledge.popular_combinations
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_dict, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"데이터 캐시 저장: {cache_file}")

    def get_training_conversations(self) -> List[TrainingData]:
        """학습용 대화 데이터 생성"""
        training_data = []
        max_items = self.max_conversations if not self.debug else 10  # 디버그시 10개만

        # 리뷰 기반 대화 생성
        review_count = 0
        for review in self.knowledge.reviews:
            if review_count >= max_items // 2:
                break
            if review['comment']:
                # 긍정 리뷰 → 추천 응답 학습 데이터
                if review['sentiment'] == 'positive':
                    training_item = TrainingData(
                        input_text=f"이 가게 어때요?",
                        target_intent=IntentType.GENERAL_CHAT,
                        target_entities=ExtractedEntity(),
                        expected_response=f"좋아요! 다른 분도 '{review['comment'][:50]}...'라고 하셨어요"
                    )
                    training_data.append(training_item)
                    review_count += 1

        # 인기 메뉴 기반 대화 생성
        popular_menus = [menu for menu in self.knowledge.menus.values() if menu.is_popular]
        menu_count = 0
        for menu in popular_menus:
            if menu_count >= max_items // 2:
                break
            training_item = TrainingData(
                input_text=f"{menu.name} 추천해줘",
                target_intent=IntentType.FOOD_REQUEST,
                target_entities=ExtractedEntity(food_type=menu.name),
                expected_response=f"{menu.name}는 인기 메뉴예요! {menu.price}원에 드실 수 있어요"
            )
            training_data.append(training_item)
            menu_count += 1

        logger.info(f"학습용 대화 데이터 생성: {len(training_data)}개")
        return training_data


# 편의 함수들 (config 버전)
def load_naviyam_data(data_config, debug: bool = False) -> NaviyamKnowledge:
    """나비얌 데이터 로드 (간편 함수)"""
    loader = NaviyamDataLoader(data_config, debug)
    return loader.load_all_data()


def generate_training_data(data_config, debug: bool = False) -> List[TrainingData]:
    """학습 데이터 생성 (간편 함수)"""
    loader = NaviyamDataLoader(data_config, debug)
    loader.load_all_data()
    return loader.get_training_conversations()