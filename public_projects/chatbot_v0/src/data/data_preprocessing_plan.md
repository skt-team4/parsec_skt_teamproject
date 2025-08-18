# 나비얌 챗봇 초기 학습용 데이터 선별 및 전처리 계획

## 📊 Sample Data 실제 현황 분석

### 데이터 규모
- **shop**: 11개 가게
- **shop_menu**: 11개 메뉴
- **shop_menu_category**: 11개 카테고리
- **review**: 11개 리뷰
- **user**: 11개 사용자 (개인정보 마스킹됨)

---

## 🎯 사용할 데이터 vs 버릴 데이터

### ✅ **사용할 데이터 (우선순위별)**

#### 🥇 **1순위: 핵심 추천 데이터**
```python
# shop 테이블에서 사용할 컬럼
shop_columns_to_use = [
    'id',                    # 가게 ID (메뉴와 연결)
    'shopName',             # 가게명 (추천 멘션용)
    'category',             # 음식 카테고리 (한식, 카페/디저트)
    'addressName',          # 위치 정보 (근처 추천용)
    'openHour',             # 영업 시작 시간
    'closeHour',            # 영업 종료 시간
    'message',              # 사장님 메시지 (개성있는 추천용)
    'isGoodInfluenceShop',  # 착한가게 여부 (나비얌 핵심)
    'breakStartHour',       # 브레이크타임 시작
    'breakEndHour',         # 브레이크타임 종료
]
```

```python
# shop_menu 테이블에서 사용할 컬럼
menu_columns_to_use = [
    'id',              # 메뉴 ID
    'shop_id',         # 가게 ID (가게와 연결)
    'name',            # 메뉴명 (구체적 추천용)
    'price',           # 가격 (예산별 추천용)
    'description',     # 메뉴 설명 (상세 추천용)
    'is_best',         # 베스트 메뉴 (우선 추천용)
    'is_sold_out',     # 품절 여부 (실시간 정보)
    'discount_value',  # 할인 정보 (혜택 안내용)
]
```

#### 🥈 **2순위: 보조 정보 데이터**
```python
# review 테이블에서 사용할 컬럼
review_columns_to_use = [
    'store_id',        # 가게 ID (가게와 연결)
    'comment',         # 리뷰 내용 (맛 평가, 분위기)
    # 'user_id' 제외 (개인정보)
]
```

#### 🥉 **3순위: 카테고리 정보**
```python
# shop_menu_category 테이블에서 사용할 컬럼
category_columns_to_use = [
    'id',          # 카테고리 ID
    'name',        # 카테고리명 (메뉴 분류용)
    'shop_id',     # 가게 ID (가게와 연결)
]
```

### ❌ **버릴 데이터**

#### **개인정보 관련**
- `user` 테이블의 모든 개인정보 (name, phone, email 등)
- `managerId`, `user_id` 등 개인 식별 정보

#### **시스템 메타데이터**
- `createdAt`, `updatedAt` (챗봇 학습에 불필요)
- `deleted_at`, `priority` (시스템 관리용)
- `addressPoint` (바이너리 좌표 데이터)

#### **비즈니스 로직 데이터**
- `ordinaryShare`, `ordinaryDiscount` (할인 로직)
- `kt_idx`, `brn`, `place_id` (외부 연동 ID)
- `nursery_info_id` (어린이집 연동)

#### **불완전하거나 빈 데이터**
- `thumbnail`, `img` (이미지는 텍스트 학습에 불필요)
- `contact` (대부분 빈 값)
- `deviceToken` (기술적 정보)

---

## 🔧 전처리 계획

### 1. **데이터 정제 (Data Cleaning)**

#### A. **가게 정보 전처리**
```python
def preprocess_shop_data(shop_data):
    processed = {}
    
    # 가게명 정제
    processed['name'] = shop_data['shopName'].strip()
    
    # 카테고리 표준화
    category_mapping = {
        '한식': '한식',
        '카페/디저트': '카페',
        '중식': '중식',
        '일식': '일식',
        '양식': '양식'
    }
    processed['category'] = category_mapping.get(shop_data['category'], '기타')
    
    # 영업시간 파싱
    processed['open_time'] = parse_time(shop_data['openHour'])
    processed['close_time'] = parse_time(shop_data['closeHour'])
    
    # 사장님 메시지 정제 (불필요한 문자 제거)
    message = shop_data['message'] or ""
    processed['message'] = clean_message(message)
    
    # 착한가게 boolean 변환
    processed['is_good_shop'] = bool(shop_data['isGoodInfluenceShop'])
    
    return processed
```

#### B. **메뉴 정보 전처리**
```python
def preprocess_menu_data(menu_data):
    processed = {}
    
    # 메뉴명 정제
    processed['name'] = menu_data['name'].strip()
    
    # 가격 정수 변환 및 검증
    price = menu_data['price']
    processed['price'] = int(price) if price and price > 0 else None
    
    # 설명 정제
    description = menu_data['description'] or ""
    processed['description'] = clean_description(description)
    
    # Boolean 플래그들
    processed['is_best'] = bool(menu_data['is_best'])
    processed['is_sold_out'] = bool(menu_data['is_sold_out'])
    
    # 할인 정보
    discount = menu_data['discount_value']
    processed['discount'] = int(discount) if discount and discount > 0 else 0
    
    return processed
```

#### C. **리뷰 정보 전처리**
```python
def preprocess_review_data(review_data):
    processed = {}
    
    # 리뷰 내용 정제
    comment = review_data['comment'] or ""
    
    # 불필요한 문자 제거
    comment = re.sub(r'[^\w\s가-힣.,!?]', '', comment)
    
    # 너무 짧거나 긴 리뷰 필터링
    if 5 <= len(comment) <= 200:
        processed['comment'] = comment.strip()
        
        # 감정 분석 (간단한 키워드 기반)
        processed['sentiment'] = analyze_sentiment(comment)
        return processed
    
    return None  # 부적절한 리뷰는 제외
```

### 2. **데이터 검증 (Data Validation)**

#### A. **필수 필드 검증**
```python
def validate_shop_data(shop):
    required_fields = ['name', 'category']
    return all(shop.get(field) for field in required_fields)

def validate_menu_data(menu):
    required_fields = ['name', 'price']
    return all(menu.get(field) for field in required_fields)
```

#### B. **데이터 품질 필터링**
```python
def filter_high_quality_data(data):
    filtered = []
    
    for item in data:
        # 가격 범위 검증 (너무 비싸거나 싼 메뉴 제외)
        if item['price'] and 1000 <= item['price'] <= 50000:
            # 메뉴명 길이 검증
            if 2 <= len(item['name']) <= 30:
                # 설명 품질 검증
                if item['description'] and len(item['description']) >= 5:
                    filtered.append(item)
    
    return filtered
```

### 3. **데이터 증강 (Data Augmentation)**

#### A. **가게-메뉴 조합 생성**
```python
def create_shop_menu_combinations(shops, menus):
    combinations = []
    
    for shop in shops:
        shop_menus = [m for m in menus if m['shop_id'] == shop['id']]
        
        for menu in shop_menus:
            combination = {
                'shop_name': shop['name'],
                'shop_category': shop['category'],
                'menu_name': menu['name'],
                'menu_price': menu['price'],
                'is_good_shop': shop['is_good_shop'],
                'is_best_menu': menu['is_best'],
                'shop_message': shop['message']
            }
            combinations.append(combination)
    
    return combinations
```

#### B. **상황별 시나리오 생성**
```python
def generate_scenario_data(combinations):
    scenarios = []
    
    for combo in combinations:
        # 예산별 시나리오
        budget_scenarios = create_budget_scenarios(combo)
        
        # 카테고리별 시나리오
        category_scenarios = create_category_scenarios(combo)
        
        # 특성별 시나리오 (착한가게, 베스트메뉴)
        feature_scenarios = create_feature_scenarios(combo)
        
        scenarios.extend(budget_scenarios + category_scenarios + feature_scenarios)
    
    return scenarios
```

### 4. **최종 데이터셋 구조**

#### A. **학습용 대화 쌍 형태**
```python
training_conversation = {
    "user_input": "치킨 먹고 싶어",
    "bot_response": "치킨카페 김밥순대에서 특선치킨카레 12500원 어때요? 착한가게로 선정된 곳이고, 사장님이 '신선한 치킨카페를 한 번 드셔보세요~'라고 하시네요! 😊",
    "metadata": {
        "shop_id": 20,
        "menu_id": 32,
        "category": "한식",
        "price_range": "10000-15000",
        "is_good_shop": True,
        "scenario_type": "category_request"
    }
}
```

---

## 📊 예상 전처리 결과

### 입력 데이터
- 가게 11개 × 메뉴 11개 = 기본 121개 조합

### 전처리 후 예상 데이터
- **유효한 가게-메뉴 조합**: ~80개 (품질 필터링 후)
- **시나리오 확장**: 80개 × 10가지 상황 = **800개 대화 쌍**
- **변형 생성**: 800개 × 2-3가지 변형 = **1600-2400개 대화 쌍**

### 품질 기준
- 메뉴 가격: 1,000원 ~ 50,000원
- 메뉴명 길이: 2자 ~ 30자
- 설명 최소 길이: 5자 이상
- 리뷰 길이: 5자 ~ 200자

---

## 🚀 구현 순서

### 1단계: 데이터 추출 및 정제
```bash
python scripts/extract_sample_data.py
```

### 2단계: 데이터 검증 및 필터링
```bash
python scripts/validate_and_filter.py
```

### 3단계: 대화 데이터 생성
```bash
python scripts/generate_conversations.py
```

### 4단계: 최종 데이터셋 검증
```bash
python scripts/validate_dataset.py
```

이렇게 전처리하면 **고품질의 나비얌 특화 학습 데이터**를 확보할 수 있을 것입니다!