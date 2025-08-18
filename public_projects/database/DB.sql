CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin"; 
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml_features;
CREATE SCHEMA IF NOT EXISTS chatbot;
CREATE SCHEMA IF NOT EXISTS nutrition;

CREATE TABLE chatbot.shops (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shop_name VARCHAR(30) NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN (
        '한식', '중식', '일식', '양식', '치킨', '피자', '패스트푸드',
        '분식', '카페/디저트', '도시락/죽', '프랜차이즈', '기타음식', '편의점'
    )),
    address_name VARCHAR(50),
    latitude DECIMAL(8, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,

    is_good_influence_shop BOOLEAN DEFAULT FALSE,
    is_food_card_shop CHAR(1) NOT NULL DEFAULT 'U' CHECK (is_food_card_shop IN ('Y', 'N', 'P', 'U')),
    -- Y: 사용가능, N: 사용불가, P: 부분사용가능, U: 미확인
    contact VARCHAR(20), 

    business_hours JSONB,  
    current_status VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN' 
        CHECK (current_status IN ('OPEN', 'CLOSED', 'BREAK_TIME', 'UNKNOWN')),  -- [COMPUTED] 실시간 계산
    
    popularity_score DECIMAL(4,3) DEFAULT 0.000 CHECK (popularity_score >= 0 AND popularity_score <= 1),  
    quality_score DECIMAL(4,3) DEFAULT 0.000 CHECK (quality_score >= 0 AND quality_score <= 1),
    recommendation_count INT DEFAULT 0 CHECK (recommendation_count >= 0),  

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,  
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    data_from VARCHAR(50) DEFAULT 'manual', -- 데이터 출처: 'manual', 'crawled', 'api', 'user_generated'
    
    CONSTRAINT shops_location_check CHECK (
        latitude >= -90 AND latitude <= 90 AND
        longitude >= -180 AND longitude <= 180
    )
);

CREATE INDEX idx_shops_category ON chatbot.shops(category);  -- 카테고리별 필터링
CREATE INDEX idx_shops_good_influence ON chatbot.shops(is_good_influence_shop) WHERE is_good_influence_shop = TRUE;  -- 착한가게만
CREATE INDEX idx_shops_food_card ON chatbot.shops(is_food_card_shop) WHERE is_food_card_shop != 'N';  -- 급식카드 가능
CREATE INDEX idx_shops_location ON chatbot.shops(latitude, longitude);  -- 거리 기반 검색용
CREATE INDEX idx_shops_popularity ON chatbot.shops(popularity_score DESC);  -- 인기순 정렬
CREATE INDEX idx_shops_status ON chatbot.shops(current_status) WHERE current_status = 'OPEN';  -- 영업중인 가게만
CREATE INDEX idx_shops_name_gin ON chatbot.shops USING gin(shop_name gin_trgm_ops);  -- 가게명 검색

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_shops_updated_at BEFORE UPDATE ON chatbot.shops
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION get_shop_hours(shop_id INT, day_name TEXT DEFAULT NULL)
  RETURNS TABLE(open_hour TIME, close_hour TIME) AS $$
  BEGIN
      RETURN QUERY
      SELECT
          (business_hours->COALESCE(day_name, to_char(NOW(), 'day'))->>'open')::TIME,
          (business_hours->COALESCE(day_name, to_char(NOW(), 'day'))->>'close')::TIME
      FROM chatbot.shops
      WHERE id = shop_id;
  END;
  $$ LANGUAGE plpgsql;

CREATE TABLE chatbot.menus (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shop_id INT NOT NULL REFERENCES chatbot.shops(id) ON DELETE CASCADE,
    
    menu_name VARCHAR(50) NOT NULL,
    price INT NOT NULL CHECK (price >= 0),
    menu_description TEXT,
    category VARCHAR(30) CHECK (category IN (
        '메인메뉴', '세트메뉴', '사이드메뉴', '음료', '디저트', '기타'
    )),
    options JSONB, 

    is_available BOOLEAN NOT NULL DEFAULT TRUE, -- 판매 가능 여부
    is_best BOOLEAN DEFAULT FALSE,
    
    dietary_info VARCHAR(200),
    recommendation_frequency INT DEFAULT 0 CHECK (recommendation_frequency >= 0),  -- [CHATBOT_GENERATED] 추천 횟수
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT shop_menu_unique UNIQUE (shop_id, menu_name)
);

CREATE INDEX idx_menus_shop ON chatbot.menus(shop_id);
CREATE INDEX idx_menus_price ON chatbot.menus(price);
CREATE INDEX idx_menus_available ON chatbot.menus(is_available) WHERE is_available = TRUE;
CREATE INDEX idx_menus_best ON chatbot.menus(is_best) WHERE is_best = TRUE;
CREATE INDEX idx_menus_shop_price ON chatbot.menus(shop_id, price);

CREATE TRIGGER update_menus_updated_at BEFORE UPDATE ON chatbot.menus
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE chatbot.users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_user_id VARCHAR(200) NOT NULL UNIQUE, 
    platform VARCHAR(50) NOT NULL DEFAULT 'web' CHECK (platform IN (
        'web', 'mobile_app', 'kakao', 'line', 'facebook', 'test'
    )), 

    user_name VARCHAR(30), 
    nickname VARCHAR(30),
    email VARCHAR(100) UNIQUE, 
    phone_number VARCHAR(20), 
    birthday DATE,  
    current_address TEXT,
    preferred_location VARCHAR(50), 

    user_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (user_status IN (
        'ACTIVE', 'INACTIVE', 'SUSPENDED', 'DELETED'
    )),

    -- 개인정보 동의
    --terms_agreed_at TIMESTAMP WITH TIME ZONE,
    --privacy_agreed_at TIMESTAMP WITH TIME ZONE,
    --marketing_agreed_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE INDEX idx_users_external_id ON chatbot.users(external_user_id);
CREATE INDEX idx_users_platform ON chatbot.users(platform);
CREATE INDEX idx_users_status ON chatbot.users(user_status) WHERE user_status = 'ACTIVE';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON chatbot.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE chatbot.foodcard_users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id) ON DELETE CASCADE,

    card_number VARCHAR(30) UNIQUE,
    card_type VARCHAR(30) NOT NULL CHECK (card_type IN (
        '아동급식카드', '청소년급식카드', '취약계층지원카드', '기타'
    )),
    card_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (card_status IN (
        'ACTIVE', 'INACTIVE', 'SUSPENDED', 'EXPIRED', 'LOST'
    )),
    balance INT NOT NULL DEFAULT 0 CHECK (balance >= 0),  
    target_age_group VARCHAR(20) NOT NULL CHECK (target_age_group IN (
        '초등학생', '중학생', '고등학생', '대학생', '청년', '기타'
    )),
    
    balance_alert_threshold INT DEFAULT 5000, 
    balance_alert_sent BOOLEAN DEFAULT FALSE, 

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP WITH TIME ZONE, 
    -- 1:1 관계
    CONSTRAINT foodcard_users_unique_user UNIQUE (user_id)
);

CREATE INDEX idx_foodcard_status ON chatbot.foodcard_users(card_status) WHERE card_status = 'ACTIVE';  
CREATE INDEX idx_foodcard_balance ON chatbot.foodcard_users(balance) WHERE balance < 5000;

CREATE TRIGGER update_foodcard_users_updated_at BEFORE UPDATE ON chatbot.foodcard_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TYPE price_range_type AS ENUM (
    'BUDGET',    -- 5,000원 미만
    'ECONOMY',   -- 5,000-10,000원
    'MEDIUM',    -- 10,000-15,000원  
    'PREMIUM',   -- 15,000-20,000원
    'LUXURY'     -- 20,000원 이상
);
CREATE TABLE chatbot.user_profiles (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id) ON DELETE CASCADE,

    -- 설정 화면 (필터링 기준; 개인별 DEFAULT)
    min_rating_threshold DECIMAL(2,1) DEFAULT 3.0 
    CHECK (min_rating_threshold >= 0.0 AND min_rating_threshold <= 5.0),
    
    preferred_price_min INT NOT NULL DEFAULT 0 
        CHECK (preferred_price_min >= 0),
    preferred_price_max INT NOT NULL DEFAULT 15000
        CHECK (preferred_price_max >= preferred_price_min),
    price_range_preset price_range_type NOT NULL DEFAULT 'MEDIUM',    
    max_walking_minutes INT DEFAULT 10 
    CHECK (max_walking_minutes > 0 AND max_walking_minutes <= 60),

    preferred_categories TEXT[] DEFAULT '{}',  -- [CHATBOT_LEARNED] 선호 음식 카테고리 ['한식', '중식']
    average_budget INT,                    -- [CHATBOT_COMPUTED] 평균 예산 (원)
    favorite_shops INT[] DEFAULT '{}',     -- [USER_BEHAVIOR] 즐겨찾는 가게 ID 배열
    conversation_style VARCHAR(20) DEFAULT 'friendly' CHECK (conversation_style IN (
        'friendly', 'formal', 'casual', 'brief'
    )),           
    -- 학습된 패턴들
    taste_preferences JSONB DEFAULT '{}',      -- [CHATBOT_LEARNED] 맛 선호도 {"매운맛": 0.8, "단맛": 0.3}
    companion_patterns TEXT[] DEFAULT '{}',    -- [CHATBOT_LEARNED] 동반자 패턴 ['혼자', '친구', '가족']
    location_preferences TEXT[] DEFAULT '{}',  -- [CHATBOT_LEARNED] 위치 선호도 ['건국대', '강남']
    
    -- 개인화 관련 설정
    good_influence_preference DECIMAL(3,2) DEFAULT 0.50 CHECK (
        good_influence_preference >= 0 AND good_influence_preference <= 1
    ),                                        -- [USER_BEHAVIOR] 착한가게 선호도 (0.0~1.0)
    interaction_count INT DEFAULT 0,      -- [SYSTEM] 총 상호작용 횟수
    data_completeness DECIMAL(3,2) DEFAULT 0.00 CHECK (
        data_completeness >= 0 AND data_completeness <= 1
    ),                                        -- [SYSTEM] 데이터 완성도 (0.0~1.0)
    
    recent_orders JSONB DEFAULT '[]', 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_profiles_unique_user UNIQUE (user_id)
);

CREATE INDEX idx_user_profiles_user ON chatbot.user_profiles(user_id);
CREATE INDEX idx_user_profiles_categories ON chatbot.user_profiles USING GIN(preferred_categories);
CREATE INDEX idx_user_profiles_favorites ON chatbot.user_profiles USING GIN(favorite_shops);
CREATE INDEX idx_user_profiles_completeness ON chatbot.user_profiles(data_completeness DESC)
    WHERE data_completeness > 0.5;
CREATE INDEX idx_taste_preferences_gin ON chatbot.user_profiles USING GIN (taste_preferences);
CREATE INDEX idx_recent_orders_gin ON chatbot.user_profiles USING GIN (recent_orders);

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON chatbot.user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION clean_invalid_shop_references()
  RETURNS void AS $$
  BEGIN
      UPDATE chatbot.user_profiles
      SET favorite_shops = (
          SELECT array_agg(shop_id)
          FROM unnest(favorite_shops) as shop_id
          WHERE shop_id IN (SELECT id FROM chatbot.shops)
      );
  END;
  $$ LANGUAGE plpgsql;

CREATE INDEX idx_user_profiles_search_filters ON chatbot.user_profiles(min_rating_threshold, preferred_price_min, preferred_price_max, max_walking_minutes);

CREATE OR REPLACE FUNCTION get_user_price_range(user_id_param INT)
RETURNS TABLE(min_price INT, max_price INT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        up.preferred_price_min,
        up.preferred_price_max
    FROM chatbot.user_profiles up
    WHERE up.user_id = user_id_param;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION filter_shops_by_user_preferences(
    user_id_param INT,
    user_lat DECIMAL(8,6), 
    user_lng DECIMAL(9,6)
)
RETURNS TABLE(shop_id INT, distance_minutes INT) AS $$
DECLARE
    max_minutes INT;
    min_rating DECIMAL(2,1);
    min_price INT;
    max_price INT;
BEGIN
    SELECT up.max_walking_minutes, up.min_rating_threshold, 
           up.preferred_price_min, up.preferred_price_max
    INTO max_minutes, min_rating, min_price, max_price
    FROM chatbot.user_profiles up 
    WHERE up.user_id = user_id_param;
    
    RETURN QUERY
    SELECT s.id, 15 as estimated_minutes 
    FROM chatbot.shops s
    WHERE s.quality_score >= min_rating;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE chatbot.coupons (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    coupon_name VARCHAR(50) NOT NULL,
    coupon_code VARCHAR(50) NOT NULL,
    coupon_description TEXT,
    coupon_type VARCHAR(30) NOT NULL CHECK (coupon_type IN (
        'FIXED_AMOUNT', 'PERCENTAGE', 'FREEBIE', 'BOGO'
    )),
    
    discount_amount INT CHECK (discount_amount > 0),
    discount_rate DECIMAL(3,2) CHECK (discount_rate > 0 AND discount_rate <= 1),    
    max_discount_amount INT, 

    -- 사용 조건
    min_order_amount INT DEFAULT 0,
    usage_type VARCHAR(30) NOT NULL CHECK (usage_type IN (
        'ALL', 'SHOP', 'CATEGORY', 'FOODCARD', 'NEW_USER', 'LOYALTY'
    )),
    
    -- 적용 대상
    target_categories TEXT[], -- ARRAY['한식', '중식']
    applicable_shop_ids INT[], -- ARRAY[1, 2, 3]
    target_user_types TEXT[], -- ARRAY['foodcard', 'new', 'vip']

    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE NOT NULL,

    -- 발급 제한
    max_issue_count INT, -- NULL이면 무제한
    max_use_per_user INT DEFAULT 1,
    total_issued INT DEFAULT 0,
    total_used INT DEFAULT 0,

    -- 상태 관리
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority_score DECIMAL(3,2) DEFAULT 0.50 CHECK (priority_score >= 0 AND priority_score <= 1),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    -- 할인 정보가 둘 중 하나는 존재하도록
    CONSTRAINT coupons_discount_check CHECK (
        (discount_amount IS NOT NULL AND discount_rate IS NULL) OR
        (discount_amount IS NULL AND discount_rate IS NOT NULL)
    ),
    CONSTRAINT coupons_valid_period CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

CREATE INDEX idx_coupons_type ON chatbot.coupons(usage_type);
CREATE INDEX idx_coupons_active ON chatbot.coupons(is_active, valid_from, valid_until);
CREATE INDEX idx_coupons_categories ON chatbot.coupons USING GIN(target_categories);
CREATE INDEX idx_coupons_shops ON chatbot.coupons USING GIN(applicable_shop_ids);
CREATE INDEX idx_coupons_code ON chatbot.coupons(coupon_code);


CREATE TABLE chatbot.user_wallet (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id) ON DELETE CASCADE,
    coupon_id INT NOT NULL REFERENCES chatbot.coupons(id) ON DELETE CASCADE,
    
    -- 쿠폰 상태
    coupon_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (coupon_status IN (
        'ACTIVE', 'USED', 'EXPIRED', 'CANCELLED'
    )),

    -- 발급 정보
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    issued_by VARCHAR(100) DEFAULT 'SYSTEM',
    acquisition_source VARCHAR(50) NOT NULL CHECK (acquisition_source IN (
        'WELCOME_BONUS', 'LOYALTY_REWARD', 'EMERGENCY_ASSIST', 
        'PROMOTION', 'ADMIN_GRANT', 'REFERRAL'
    )),
    acquisition_context JSONB,
    expires_at TIMESTAMP WITH TIME ZONE,
    expiry_notified_at TIMESTAMP WITH TIME ZONE,
    expiry_notification_count INT DEFAULT 0,

    usage_probability DECIMAL(4,3) DEFAULT 0.500 CHECK (usage_probability >= 0 AND usage_probability <= 1),
    recommended_usage_date DATE,

    CONSTRAINT user_coupon_unique_active UNIQUE (user_id, coupon_id, coupon_status) 
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_user_coupon_user_status ON chatbot.user_wallet(user_id, coupon_status);
CREATE INDEX idx_user_coupon_expires ON chatbot.user_wallet(expires_at) WHERE coupon_status = 'ACTIVE';
CREATE INDEX idx_user_coupon_usage_prob ON chatbot.user_wallet(usage_probability DESC) WHERE coupon_status = 'ACTIVE';

CREATE TYPE order_stat AS ENUM ('confirmed', 'preparing', 'prepared', 'picked', 'canceled');
-- 주문완료, 조리중/준비중, 조리/준비완료, 픽업/배송 완료

CREATE TABLE chatbot.orders (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id),
    shop_id INT NOT NULL REFERENCES chatbot.shops(id),
    menu_id INT NOT NULL REFERENCES chatbot.menus(id),

    order_status order_stat,   
    order_time TIMESTAMP WITH TIME ZONE, -- 쿠폰 사용 시간 동일
    quantity INT,  
    price INT,  
    discount_applied INT
);
CREATE INDEX idx_orders_userid ON chatbot.orders(user_id);

-- 주문 없이 쿠폰 사용이 기록되는 걸 방지
CREATE TABLE chatbot.orders_coupons (
    order_id INT NOT NULL REFERENCES chatbot.orders(id) ON DELETE CASCADE,
    user_wallet_id INT NOT NULL REFERENCES chatbot.user_wallet(id) ON DELETE CASCADE,
    applied_discount INT NOT NULL, 
    PRIMARY KEY (order_id, user_wallet_id)
);

CREATE TABLE chatbot.reviews (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id),
    shop_id INT NOT NULL REFERENCES chatbot.shops(id) ON DELETE CASCADE,
    order_id INT NOT NULL REFERENCES chatbot.orders(id) ON DELETE CASCADE,
    
    rating DECIMAL(2,1) NOT NULL,
    comment TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,   
    
    sentiment VARCHAR(20), 
    quality_score DECIMAL(3,2), 
    helpful_count INT DEFAULT 0,
    CONSTRAINT unique_user_order_review UNIQUE (user_id, order_id)
);
CREATE INDEX idx_reviews_order_rating ON chatbot.reviews(order_id, rating);
CREATE INDEX idx_reviews_user ON chatbot.reviews(user_id);

CREATE TABLE chatbot.conversation_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INT REFERENCES chatbot.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_turns INT DEFAULT 0,
    session_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE chatbot.conversation_messages (
    id BIGSERIAL NOT NULL,
    session_id UUID NOT NULL REFERENCES chatbot.conversation_sessions(session_id) ON DELETE CASCADE,
    conversation_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    turn_number INT NOT NULL DEFAULT 1,
    input_text VARCHAR(1000) NOT NULL, -- input token: 312
    response_text VARCHAR(700) NOT NULL, --response token: 200
	
    extracted_intent VARCHAR(50) CHECK (extracted_intent IN (
        'FOOD_REQUEST', 'BUDGET_INQUIRY', 'COUPON_INQUIRY', 
        'LOCATION_INQUIRY', 'TIME_INQUIRY', 'GENERAL_CHAT',
        'MENU_OPTION', 'EMERGENCY_FOOD', 'GROUP_DINING', 
        'BALANCE_CHECK', 'BALANCE_CHARGE', 'UNKNOWN'
    )),  -- [AI_COMPUTED] NLU가 추출한 의도
    intent_confidence DECIMAL(4,3) CHECK (intent_confidence >= 0 AND intent_confidence <= 1),  -- [AI_COMPUTED] 의도 신뢰도
    emotion INT,  -- 감정별 카테고리 매핑 (약 6종류)
    
    extracted_entities JSONB,  
    previous_intent VARCHAR(50), 
    user_strategy VARCHAR(20) CHECK (user_strategy IN ('onboarding_mode', 'data_building_mode', 'normal_mode', 'urgent_mode')),
    
    processing_time_ms INT,  -- [SYSTEM] 전체 처리 시간
    nlu_time_ms INT,        -- [SYSTEM] NLU 처리 시간
    rag_time_ms INT,        -- [SYSTEM] RAG 검색 시간
    response_time_ms INT,   -- [SYSTEM] 응답 생성 시간
    
    -- 품질 지표
    response_quality_score DECIMAL(4,3) CHECK (response_quality_score >= 0 AND response_quality_score <= 1),      -- [AI_COMPUTED] 응답 품질
    user_satisfaction_inferred DECIMAL(4,3) CHECK (user_satisfaction_inferred >= 0 AND user_satisfaction_inferred <= 1),  -- [AI_COMPUTED] 추론된 만족도
    conversation_coherence DECIMAL(4,3) CHECK (conversation_coherence >= 0 AND conversation_coherence <= 1),      -- [AI_COMPUTED] 대화 일관성
    
    -- 추천 결과
    recommended_shop_ids INT[],           -- [CHATBOT_GENERATED] 추천된 가게 ID 리스트
    selected_shop_id INT REFERENCES chatbot.shops(id),  -- [USER_ACTION] 사용자가 선택한 가게
    applied_coupon_ids TEXT[],             -- [CHATBOT_GENERATED] 적용된 쿠폰 ID
    
    -- 제약조건
    PRIMARY KEY (id, conversation_time),
    CHECK (turn_number > 0),
    CHECK (processing_time_ms >= 0),
    CHECK (nlu_time_ms >= 0),
    CHECK (rag_time_ms >= 0),
    CHECK (response_time_ms >= 0),
    CHECK (emotion >= 1 AND emotion <= 6)  -- 감정 카테고리 범위 제한
) PARTITION BY RANGE (conversation_time);

CREATE INDEX idx_sessions_user_created ON chatbot.conversation_sessions(user_id, created_at DESC);
CREATE INDEX idx_sessions_user_activity ON chatbot.conversation_sessions(user_id, last_activity DESC);
CREATE INDEX idx_sessions_status ON chatbot.conversation_sessions(session_status);

CREATE INDEX idx_messages_comprehensive ON chatbot.conversation_messages(
    session_id, 
    conversation_time DESC, 
    turn_number, 
    extracted_intent
);
CREATE INDEX idx_entities_gin ON chatbot.conversation_messages USING GIN (extracted_entities);

CREATE OR REPLACE FUNCTION update_user_preferences_from_conversation(
    user_id_param INT,
    entities_json JSONB
) RETURNS VOID AS $$
BEGIN
    UPDATE chatbot.user_profiles 
    SET 
        preferred_price_max = COALESCE(
            (entities_json->>'budget')::INT, 
            preferred_price_max
        ),
        max_walking_minutes = COALESCE(
            CASE 
                WHEN entities_json->>'time_preference' = '가까운' THEN 5
                WHEN entities_json->>'time_preference' = '근처' THEN 10
                ELSE max_walking_minutes
            END,
            max_walking_minutes
        )
    WHERE user_id = user_id_param;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE chatbot.conversation_messages_2024_08 PARTITION OF chatbot.conversation_messages
  FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE chatbot.conversation_messages_2024_09 PARTITION OF chatbot.conversation_messages
  FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');

CREATE OR REPLACE FUNCTION create_monthly_partition(target_date DATE)
RETURNS void AS $$
DECLARE
    start_date DATE := date_trunc('month', target_date);
    end_date DATE := start_date + INTERVAL '1 month';
    partition_name TEXT := 'conversation_messages_' || to_char(start_date, 'YYYY_MM');
BEGIN
    EXECUTE format('CREATE TABLE IF NOT EXISTS chatbot.%I PARTITION OF chatbot.conversation_messages
                   FOR VALUES FROM (%L) TO (%L)', 
                   partition_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;


CREATE MATERIALIZED VIEW chatbot.mv_conversation_analysis AS
SELECT 
    -- 기본 대화 정보
    m.id as message_id,
    s.user_id,
    m.input_text as message_text,
    m.extracted_intent as intent,
    m.extracted_entities as entities,
    m.intent_confidence as confidence_score,
    m.conversation_time as timestamp,
    
    -- 사용자 정보 JOIN
    u.user_name as username,
    u.external_user_id,
    u.platform,
    u.preferred_location,
    u.user_status,
    
    -- 개인화 정보 JOIN  
    up.preferred_categories,
    up.taste_preferences as dietary_restrictions,
    up.average_budget,
    up.conversation_style,
    up.companion_patterns,
    up.location_preferences,
    up.good_influence_preference,
    up.data_completeness,
    
    -- 세션 정보
    s.session_id,
    m.turn_number,
    m.user_strategy,
    m.emotion,
    m.previous_intent,
    
    -- 성능 및 품질 메트릭
    m.processing_time_ms,
    m.nlu_time_ms,
    m.response_quality_score,
    m.user_satisfaction_inferred,
    
    -- 추천 결과
    m.recommended_shop_ids,
    m.selected_shop_id,
    m.applied_coupon_ids

FROM chatbot.conversation_messages m
JOIN chatbot.conversation_sessions s ON m.session_id = s.session_id
JOIN chatbot.users u ON s.user_id = u.id
LEFT JOIN chatbot.user_profiles up ON s.user_id = up.user_id
WHERE m.conversation_time >= NOW() - INTERVAL '7 days'
ORDER BY m.conversation_time DESC;

-- Materialized View 자동 리프레시 (1시간마다)
CREATE OR REPLACE FUNCTION refresh_mv_conversation_analysis()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW chatbot.mv_conversation_analysis;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION auto_delete_old_conversations()
RETURNS void AS $$
BEGIN
    -- 오래된 메시지 먼저 삭제 (CASCADE로 연관 데이터도 삭제됨)
    DELETE FROM chatbot.conversation_messages
    WHERE conversation_time < NOW() - INTERVAL '6 months';
    
    -- 메시지가 없는 세션들 정리
    DELETE FROM chatbot.conversation_sessions s
    WHERE NOT EXISTS (
        SELECT 1 FROM chatbot.conversation_messages m 
        WHERE m.session_id = s.session_id
    );
END;
$$ LANGUAGE plpgsql;

-- 유저별 금지 재료(텍스트형, 슬림)
CREATE TABLE chatbot.user_allergy (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES chatbot.users(id) ON DELETE CASCADE,
  ingredient TEXT NOT NULL,                           -- 예: 'peanut', 'milk', 'shrimp'
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, lower(ingredient))
);
CREATE INDEX idx_allergy
  ON chatbot.user_allergy(user_id, lower(ingredient));


CREATE TABLE ml_features.nlu_features (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.shops(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- NLU 핵심 결과
    nlu_intent VARCHAR(50),  -- food_request, budget_inquiry 등
    nlu_confidence DECIMAL(4,3),
    
    -- 추출된 특징들
    food_category_mentioned VARCHAR(100),        -- "치킨", "한식", "일식" 등
    budget_mentioned INT,                        -- 예산 금액
    location_mentioned VARCHAR(100),             -- "근처", "강남" 등
    companions_mentioned JSONB,                   -- ["친구", "가족"] 등
    time_preference VARCHAR(50),                 -- "지금", "저녁" 등
    menu_options JSONB,                           -- ["맵게", "곱배기"] 등
    special_requirements JSONB,                   -- 특별 요구사항
    
    -- 처리 메타데이터
    processing_time_ms INT,
    model_version VARCHAR(20)
);

CREATE INDEX idx_nlu_user_timestamp ON ml_features.nlu_features(user_id, created_at);
CREATE INDEX idx_intent ON ml_features.nlu_features(nlu_intent);
CREATE INDEX idx_food_category ON ml_features.nlu_features(food_category_mentioned);

CREATE TYPE interaction AS ENUM ('text_input', 'selection', 'feedback', 'coupon_use');
CREATE TABLE ml_features.user_interactions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id),
    session_id UUID REFERENCES chatbot.conversation_sessions(session_id) ON DELETE CASCADE,
    time_stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- [CHATBOT_GENERATED] 상호작용 세부사항
    interaction_type interaction,
    
    -- [CHATBOT_GENERATED] 학습 데이터 추출 결과
    food_preference_extracted VARCHAR(100),      
    budget_pattern_extracted INT, 
    companion_pattern_extracted JSONB, 
    location_preference_extracted VARCHAR(100), 
    
    -- [DERIVED] 추천 관련 데이터 (shops 테이블과 연결)
    recommendation_provided BOOLEAN DEFAULT FALSE,
    recommendation_count INT DEFAULT 0,
    recommendations JSONB,                        -- 추천된 shop_id들과 점수
    
    -- [CHATBOT_GENERATED] 사용자 상태
    user_strategy VARCHAR(30),
    conversation_turn INT
);
CREATE INDEX idx_interaction_timestamp ON ml_features.user_interactions(user_id, time_stamp);
CREATE INDEX idx_session ON ml_features.user_interactions(session_id);

CREATE TABLE analytics.recommendations_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id), 
    shop_id INT NOT NULL REFERENCES chatbot.shops(id),
    session_id UUID REFERENCES chatbot.conversation_sessions(session_id) ON DELETE CASCADE,
    time_stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 추천 입력 조건
    request_food_type VARCHAR(100),              -- NLU에서 추출한 음식 종류
    request_budget INT,                          -- NLU에서 추출한 예산
    request_location VARCHAR(100),               -- NLU에서 추출한 위치 선호
    
    -- [DERIVED] 추천 결과 (shops 테이블의 shop_id 참조)
    recommendations JSONB NOT NULL,               -- [{shop_id, score, reason}] 배열
    recommendation_count INT NOT NULL,
    top_recommendation_shop_id INT,              -- shops.id 참조
    
    -- 사용자 선택 (나중에 업데이트)
    user_selection JSONB,                         -- 사용자가 선택한 가게 정보
    selection_timestamp TIMESTAMP NULL,
    
    -- 추천 시스템 메타데이터
    recommendation_method VARCHAR(50),           -- "wide_deep", "rag", "hybrid"
    confidence_score DECIMAL(4,3),
    wide_score DECIMAL(4,3),                    -- Wide 모델 점수
    deep_score DECIMAL(4,3),                    -- Deep 모델 점수
    rag_score DECIMAL(4,3)                     -- RAG 검색 점수
);

CREATE INDEX idx_recommendation_timestamp ON analytics.recommendations_log(user_id, time_stamp);
CREATE INDEX idx_session_rmd ON analytics.recommendations_log(session_id);
CREATE INDEX idx_shop_rmd ON analytics.recommendations_log(top_recommendation_shop_id);


CREATE TABLE analytics.user_feedback (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    
    session_id UUID REFERENCES chatbot.conversation_sessions(session_id) ON DELETE CASCADE,
    related_recommendation_id BIGINT NOT NULL REFERENCES analytics.recommendations_log(id),
    user_id INT NOT NULL REFERENCES chatbot.users(id),  
    time_stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 피드백 기본 정보
    feedback_type VARCHAR(30) NOT NULL,          -- "selection", "rating", "text", "implicit"
    feedback_target_type VARCHAR(30) NOT NULL,
    feedback_target_id VARCHAR(30) NOT NULL,         
    feedback_content JSONB,                       -- 피드백 내용 (점수, 텍스트, 선택 등)
    context JSONB,                                -- 피드백이 발생한 상황 정보

    -- [DERIVED] 피드백 분석 결과
    sentiment VARCHAR(20),                       -- "positive", "negative", "neutral"
    satisfaction_score DECIMAL(3,2),            -- 0.00 ~ 1.00
    feedback_quality DECIMAL(3,2)              -- 피드백 품질 점수
);
CREATE INDEX idx_feedback_user_timestamp ON analytics.user_feedback(user_id, time_stamp);
CREATE INDEX idx_feedback_type ON analytics.user_feedback(feedback_type);
CREATE INDEX idx_recommendation ON analytics.user_feedback(related_recommendation_id);


CREATE TABLE nutrition.foods (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(50) NOT NULL,
    ingredients TEXT[], 
    brand VARCHAR(100),
    source VARCHAR(50) NOT NULL,              -- 예: 'USDA', 'KFDA', 'Manual'
    source_food_id VARCHAR(100),              -- 외부 DB 식별자
    nutrients JSONB NOT NULL,                  -- { "kcal": 250, "protein_g": 8.5, ... }
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 메뉴 ↔ 영양소 매핑
CREATE TABLE nutrition.menu_nutrition_map (
    menu_id INT NOT NULL REFERENCES chatbot.menus(id) ON DELETE CASCADE,
    food_id INT NOT NULL REFERENCES nutrition.foods(id),
    portion_g DECIMAL(6,2) NOT NULL,          -- 기준 분량
    multiplier DECIMAL(6,3) DEFAULT 1.000,    -- 분량 조정 비율
    confidence DECIMAL(4,3) CHECK (confidence >= 0 AND confidence <= 1),
    valid_from DATE DEFAULT CURRENT_DATE,
    valid_to DATE,
    PRIMARY KEY (menu_id, food_id, valid_from)
);
CREATE INDEX idx_menu_nutrition_valid 
    ON nutrition.menu_nutrition_map(menu_id, valid_from, valid_to);

CREATE TABLE analytics.user_meals (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES chatbot.users(id) ON DELETE CASCADE,
    taken_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) NOT NULL CHECK (source IN ('order','photo','manual')),
    menu_id INT REFERENCES chatbot.menus(id),
    food_name VARCHAR(200),                   -- 분류 결과 (메뉴 이름)
    portion_estimate_g DECIMAL(6,2),           -- 추정 중량
    classifier_label VARCHAR(200),             -- 이미지 분류 결과 레이블
    mapping_confidence DECIMAL(4,3),           -- 매핑 신뢰도
    nutrition_snapshot JSONB NOT NULL,         -- { "kcal": ..., "protein_g": ..., ... }
    nutrition_source_version INT,              -- nutrition.foods.version
    image_id UUID                              -- 이미지 파일 식별자 (optional)
);

CREATE INDEX idx_user_meals_user_time 
    ON analytics.user_meals(user_id, taken_at DESC);

CREATE TABLE IF NOT EXISTS analytics.daily_intake_summary (
  user_id INT NOT NULL,
  intake_date DATE NOT NULL,
  totals JSONB NOT NULL,
  PRIMARY KEY (user_id, intake_date)
);

-- 2) 초기도입: 전기간 백필 (idempotent; 여러 번 돌려도 안전)
INSERT INTO analytics.daily_intake_summary (user_id, intake_date, totals)
SELECT
  user_id,
  d AS intake_date,
  jsonb_object_agg(key, sum_val) AS totals
FROM (
  SELECT
    m.user_id,
    DATE(m.taken_at) AS d,
    ns.key,
    SUM((ns.value)::NUMERIC) AS sum_val
  FROM analytics.user_meals m
  CROSS JOIN LATERAL jsonb_each_text(m.nutrition_snapshot) AS ns(key, value)
  GROUP BY m.user_id, DATE(m.taken_at), ns.key
) x
GROUP BY user_id, d
ON CONFLICT (user_id, intake_date)
DO UPDATE SET totals = EXCLUDED.totals;

-- 3) 당일 증분 업서트 (원하면 주석 처리 가능)
INSERT INTO analytics.daily_intake_summary (user_id, intake_date, totals)
SELECT
  user_id,
  d AS intake_date,
  jsonb_object_agg(key, sum_val) AS totals
FROM (
  SELECT
    m.user_id,
    DATE(m.taken_at) AS d,
    ns.key,
    SUM((ns.value)::NUMERIC) AS sum_val
  FROM analytics.user_meals m
  CROSS JOIN LATERAL jsonb_each_text(m.nutrition_snapshot) AS ns(key, value)
  WHERE m.taken_at >= CURRENT_DATE
    AND m.taken_at <  CURRENT_DATE + INTERVAL '1 day'
  GROUP BY m.user_id, DATE(m.taken_at), ns.key
) x
GROUP BY user_id, d
ON CONFLICT (user_id, intake_date)
DO UPDATE SET totals = EXCLUDED.totals;
