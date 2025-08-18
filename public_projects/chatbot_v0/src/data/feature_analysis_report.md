# 나비얌 챗봇 초기 학습을 위한 Feature 분석 및 활용 방안

## 📊 Sample Data 구조 개요

**총 30개 시트**, 각각 다른 도메인의 데이터를 포함:
- 가게 정보 (shop, shop_menu, shop_menu_category)
- 메뉴 및 옵션 (shop_menu_option, shop_menu_option_category)
- 브랜드 및 제품 (brand, products)
- 쿠폰 및 할인 (coop_coupon, coupon_*)
- 리뷰 및 사용자 (review, user, userfavorite)
- 기프트카드 및 포인트 (giftcard_*, point_transaction)

---

## 🎯 챗봇 학습에 활용 가능한 핵심 Feature들

### 1. **가게 정보 (shop 시트)** ⭐⭐⭐⭐⭐
**활용도: 최고** - 추천 시스템의 핵심

#### 핵심 Feature들:
- **`shopName`**: 가게 이름 → 직접 추천 멘션
- **`category`**: 음식 카테고리 (한식, 카페/디저트 등) → 사용자 의도 매칭
- **`addressName`**: 위치 정보 → 근처 가게 추천
- **`openHour/closeHour`**: 영업시간 → 시간대별 추천
- **`message`**: 사장님 메시지 → 개성있는 추천 멘트
- **`isGoodInfluenceShop`**: 착한가게 여부 → 나비얌 핵심 컨셉
- **`breakStartHour/breakEndHour`**: 브레이크타임 → 실시간 영업상태
- **`contact`**: 연락처 → 주문 안내

#### 학습 활용 예시:
```python
# 대화 생성 예시
"치킨 먹고 싶어" → "치킨카페 김밥순대가 어때요? 착한가게로 선정된 곳이에요!"
"지금 열린 곳 있어?" → "커피플래닛은 오전 7시부터 자정까지 운영해요!"
```

### 2. **메뉴 정보 (shop_menu 시트)** ⭐⭐⭐⭐⭐
**활용도: 최고** - 구체적 추천의 핵심

#### 핵심 Feature들:
- **`name`**: 메뉴명 → 구체적 메뉴 추천
- **`price`**: 가격 → 예산별 추천
- **`description`**: 메뉴 설명 → 상세한 추천 멘트
- **`is_best`**: 베스트 메뉴 → 우선 추천
- **`is_sold_out`**: 품절 여부 → 실시간 정보 제공
- **`discount_value`**: 할인 정보 → 혜택 안내

#### 학습 활용 예시:
```python
"만원으로 뭐 먹을까?" → "치킨마요덮밥 8900원 어때요? 베스트 메뉴예요!"
"할인되는 거 있어?" → "지금 치킨버거가 1000원 할인 중이에요!"
```

### 3. **메뉴 카테고리 (shop_menu_category)** ⭐⭐⭐⭐
**활용도: 높음** - 메뉴 분류 및 추천 로직

#### 핵심 Feature들:
- **`name`**: 카테고리명 → 메뉴 그룹핑
- **`priority`**: 우선순위 → 추천 순서 결정

### 4. **리뷰 데이터 (review 시트)** ⭐⭐⭐⭐
**활용도: 높음** - 사용자 피드백 기반 추천

#### 예상 Feature들:
- 리뷰 내용 → 맛 평가, 분위기 설명
- 평점 → 품질 지표
- 사용자 ID → 개인화 정보

### 5. **사용자 선호도 (userfavorite)** ⭐⭐⭐⭐
**활용도: 높음** - 개인화 추천

#### 예상 Feature들:
- 즐겨찾기한 가게/메뉴 → 개인 취향 파악
- 선호 카테고리 → 맞춤 추천

### 6. **쿠폰 정보 (coupon_*)** ⭐⭐⭐
**활용도: 중간** - 혜택 안내

#### 활용 방안:
- 현재 사용 가능한 쿠폰 → 할인 혜택 안내
- 쿠폰 조건 → 주문 가이드

---

## 🚀 챗봇 학습 데이터 생성 전략

### 1. **기본 추천 대화 패턴**
```python
# Feature 조합 예시
shop_data = {
    "name": "치킨카페 김밥순대", 
    "category": "한식", 
    "isGoodInfluenceShop": True,
    "message": "신선한 치킨카페를 한 번 드셔보세요~"
}

menu_data = {
    "name": "치킨마요덮밥", 
    "price": 8900, 
    "is_best": True
}

# 생성할 대화
"한식 먹고 싶어" → "치킨카페 김밥순대 어때요? 착한가게로 선정된 곳이고, 베스트 메뉴인 치킨마요덮밥 8900원 추천드려요! 사장님이 '신선한 치킨카페를 한 번 드셔보세요~'라고 하시네요 😊"
```

### 2. **상황별 대화 시나리오**

#### A. 예산 기반 추천
```python
사용자: "5천원으로 뭐 먹을까?"
나비얌: "5천원 예산이라면 [price <= 5000인 메뉴들] 중에서 [shop.message 활용한 개성있는 추천]"
```

#### B. 시간 기반 추천
```python
사용자: "지금 열린 곳 있어?"
나비얌: "[현재시간 >= openHour && 현재시간 <= closeHour] 조건으로 필터링한 가게 추천"
```

#### C. 착한가게 특화 추천
```python
사용자: "착한가게 추천해줘"
나비얌: "[isGoodInfluenceShop = True] 가게들을 우선 추천하며 사회적 가치 언급"
```

### 3. **Feature 기반 대화 증강**

#### 활용할 Feature 조합:
1. **기본 정보**: shopName + category + addressName
2. **메뉴 정보**: menu.name + price + is_best
3. **특성 정보**: isGoodInfluenceShop + message
4. **실시간 정보**: openHour + is_sold_out
5. **혜택 정보**: discount_value + 쿠폰 정보

---

## 📋 추천하는 초기 학습 Feature 우선순위

### 🥇 **1순위 (필수 Feature)**
- `shop.shopName` - 가게명
- `shop.category` - 음식 카테고리  
- `shop_menu.name` - 메뉴명
- `shop_menu.price` - 가격
- `shop.isGoodInfluenceShop` - 착한가게 여부

### 🥈 **2순위 (중요 Feature)**  
- `shop.message` - 사장님 메시지
- `shop_menu.is_best` - 베스트 메뉴
- `shop.openHour/closeHour` - 영업시간
- `shop_menu.description` - 메뉴 설명
- `shop.addressName` - 위치정보

### 🥉 **3순위 (보조 Feature)**
- `shop_menu.discount_value` - 할인정보
- `shop_menu.is_sold_out` - 품절상태
- `review` 데이터 - 리뷰 정보
- `userfavorite` 데이터 - 선호도
- `coupon` 데이터 - 쿠폰 혜택

---

## 🎯 구체적인 데이터 생성 방향

### 1. **템플릿 기반 대화 생성**
```python
템플릿: "[category] 먹고 싶어" 
→ "{shopName}에서 {menu_name} {price}원 어때요? {special_feature}"

special_feature 조건:
- isGoodInfluenceShop = True → "착한가게예요!"
- is_best = True → "베스트 메뉴예요!"  
- discount_value > 0 → "{discount_value}원 할인 중이에요!"
```

### 2. **상황별 시나리오 확장**
- 시간대별: 아침/점심/저녁/야식
- 예산별: 5천원/1만원/1만5천원/2만원 이상
- 동반자별: 혼자/친구/가족/연인
- 특성별: 착한가게/일반가게/브랜드점

### 3. **아동 친화적 톤 적용**
- 밝고 친근한 표현
- 이모티콘 활용 😊🍽️✨  
- 간단하고 이해하기 쉬운 설명
- 격려와 응원의 메시지

---

## 📈 예상 학습 데이터 볼륨

현재 sample_data 기준:
- **가게**: ~10개 → 100-200개 대화 시나리오
- **메뉴**: ~10개 → 200-400개 메뉴 추천 대화  
- **카테고리**: ~5개 → 100-150개 카테고리별 대화
- **상황조합**: 시간×예산×특성 → 500-1000개 상황별 대화

**총 예상 초기 학습 데이터: 1000-2000개 대화 쌍**

이 정도면 LoRA 학습을 위한 최소 데이터셋(50-200개)을 크게 상회하여, 충분한 초기 학습이 가능할 것으로 예상됩니다.