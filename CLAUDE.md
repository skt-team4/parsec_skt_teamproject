# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YUM:AI is a child-focused food recommendation system featuring an AI chatbot character named "그르시" (Geursi) that helps children find suitable restaurants and food options. The system consists of a React Native mobile app, Python FastAPI backend with AI capabilities, and multiple deployment options.

## Architecture

### Frontend - React Native/Expo Mobile App
**Location**: `public_projects/ljm_skt_teamproject-main/ljm_skt_teamproject-main/`
- Built with React Native 0.79.5, Expo SDK 53, TypeScript
- File-based routing with Expo Router
- Key screens:
  - `app/chat.tsx` - Main chat interface with 그르시 (Geursi) AI assistant
  - `app/food-category.tsx` - Food category selection
  - `app/nutrition.tsx` - Nutrition information display
  - `app/food_vision.tsx` - Food image analysis using camera
  - `app/orders.tsx` - Order management
  - `app/store.tsx` - Store/restaurant details with T-Map integration
  - `app/settings.tsx` - User settings (persona, location, allergies, preferences)
  - `app/(tabs)/_layout.tsx` - Tab navigation layout (5 tabs)
  - `app/(auth)/login.tsx` - Login screen with Google OAuth integration
  - `app/(auth)/register.tsx` - User registration
  - `app/(auth)/welcome.tsx` - Welcome screen

### Backend - Python FastAPI + AI Models
**Primary Location**: `public_projects/chatbot_v0/`
- **Main Server**: `persona_api_server.py` - Persona-based API (port 8000)
- **Alternative Server**: `src/api/server.py` - Standard API (port 8080)
- Core modules:
  - `src/inference/integrated_pipeline.py` - Main AI pipeline
  - `models/ax_encoder_base/` - A.X Encoder model files
  - `src/rag/` - FAISS-based RAG system
  - `src/recommendation/` - Multi-funnel recommendation engine
  - `src/data/restaurants_real.json` - Restaurant database
  - `data/personas.json` - Youth persona profiles (민호, 명빈, 태훈)
  - `outputs/prebuilt_faiss.faiss` - Pre-built vector indexes

### Food Recognition & Nutrition Analysis Service
**Location**: `public_projects/food_korean/`
- **Food Recognition Server**: `food_korean/app_korean.py` - Korean food recognition API (port 5001)
- **Nutrition Analysis Server**: `nutrition_server.py` - Static nutrition database API (port 5002) 
- **LogMeal Integration Server**: `logmeal_nutrition_server.py` - Real-time LogMeal API integration (port 5003)
- **Nutrition History Server**: `nutrition_history_server.py` - Nutrition tracking and history API (port 5004)
- **Dashboard**: `nutrition_dashboard.html` - Web interface for viewing nutrition history

**Food Recognition Technology:**
- CLIP model (OpenAI clip-vit-base-patch32) for text-image matching
- Supports 30+ Korean foods and 15+ international foods
- Uses CLIP's zero-shot learning for food recognition without specific training
- Korean foods: 떡볶이, 김치, 불고기, 비빔밥, 삼겹살, 김밥, 잡채, etc.

**Real-time Nutrition Analysis (LogMeal Integration):**
- Direct LogMeal API integration for image-based nutrition analysis
- Real-time analysis based on actual food portions in images
- Returns different nutrition values for different images of the same food
- Comprehensive nutritional information including:
  - Calories (displayed as integers)
  - Macronutrients: protein, carbohydrates, fat (displayed to 1 decimal place)
  - Micronutrients: fiber, sodium, sugar (displayed to 1 decimal place)
  - Nutrition score (A-E grade)
  - Daily intake reference percentages

**Nutrition History Tracking:**
- Automatic saving of all nutrition analyses
- Web dashboard with statistics and visualizations
- Filtering by meal type (breakfast, lunch, dinner)
- Pagination support for large datasets
- Delete functionality for individual records

### Database
**Location**: `database/`
- Schema: `database/yumai_final_fixed.sql` (PostgreSQL schema)
- Note: chatbot_v0 uses SQLite internally, PostgreSQL is optional
- Includes users, shops, sessions, interactions, recommendations tables

## Common Development Commands

### Frontend Development
```bash
cd public_projects/ljm_skt_teamproject-main/ljm_skt_teamproject-main

# Install dependencies
npm install

# Start development server (web on port 19000)
npm run web       # Always uses port 19000
# Or use platform-specific scripts:
start-web.bat     # Windows
./start-web.sh    # Mac/Linux

# Platform-specific runs
npm run android    # Android emulator/device
npm run ios       # iOS simulator

# Code quality
npm run lint      # ESLint check
```

### Backend Development
```bash
cd public_projects/chatbot_v0

# Install dependencies
pip install -r requirements.txt

# Run persona-based API server (recommended)
python persona_api_server.py
# Server runs at http://localhost:8080

# Alternative: Standard API server
python src/api/server.py
# Server runs at http://localhost:8000

# Interactive chat mode for testing
python main.py --mode chat

# Run tests
python test_basic.py
python test_api.py
python test_chatbot.py
python test_performance.py
```

### Food Recognition & Nutrition Service
```bash
cd public_projects/food_korean

# Install dependencies
pip install fastapi uvicorn pillow torch transformers flask flask-cors requests

# Start all nutrition services (Windows)
start_nutrition_services.bat

# Start all nutrition services (Mac/Linux)
chmod +x start_nutrition_services.sh
./start_nutrition_services.sh

# Or run services individually:

# Terminal 1: Korean food recognition API
cd food_korean
python app_korean.py
# Server runs at http://localhost:5001

# Terminal 2: LogMeal nutrition integration
python logmeal_nutrition_server.py
# Server runs at http://localhost:5003

# Terminal 3: Nutrition history tracking
python nutrition_history_server.py
# Server runs at http://localhost:5004

# Access the nutrition dashboard
# Open browser to http://localhost:5004

# Test food recognition API
curl -X POST http://localhost:5001/analyze \
  -F "file=@image.jpg"

# Test LogMeal nutrition API
curl -X POST http://localhost:5003/analyze-nutrition \
  -F "file=@food.jpg"

# List supported foods
curl http://localhost:5001/foods
```

### Docker Operations
```bash
# Build and run main composition
docker-compose up --build

# Specific configurations
docker-compose -f docker-compose-yumai.yml up
docker-compose -f docker-compose-simple.yml up
```

## API Endpoints

### Persona API Server (Port 8080) - Primary
- `GET /` - Service information
- `GET /health` - Health check with model loading status
- `POST /chat` - Main chat endpoint with persona support
  - Request: `{message, user_id, persona_id, metadata?, weather?}`
  - Response: `{response, recommendations, intent, confidence, persona_info}`
- `GET /personas` - Available personas list
- `GET /users/{user_id}/profile` - User profile
- `GET /users/{user_id}/history` - Chat history

### Standard API Server (Port 8000) - Alternative
- Same endpoints as above plus:
- `GET /docs` - Swagger API documentation
- `GET /metrics` - Performance metrics
- `POST /v1/chat/completions` - OpenAI-compatible endpoint

### Food Recognition API (Port 5001)
- `GET /` - HTML interface (if korean.html exists)
- `POST /analyze` - Analyze food image
  - Request: multipart/form-data with image file
  - Response: `{status, predictions[], food_item, confidence}`
- `GET /health` - API health check with model status
- `GET /foods` - List supported foods
  - Response: `{korean_foods[], other_foods[], total}`

### Nutrition Analysis API (Port 5002) - Static Database
- `GET /nutrition/{food_name}` - Get nutritional information from static database
  - Request: food name in URL (e.g., /nutrition/떡볶이)
  - Response: Static nutrition data with calories, macronutrients, vitamins, minerals
- `GET /health` - Health check endpoint

### LogMeal Nutrition API (Port 5003) - Real-time Analysis
- `POST /analyze-nutrition` - Analyze nutrition from food image
  - Request: multipart/form-data with image file
  - Response: Real-time nutrition data based on actual food portions
    - `status`: success/error
    - `foodNames`: detected food items
    - `nutritional_info`: comprehensive nutrition data
    - `nutri_score`: nutrition grade (A-E)
- `GET /health` - Health check with LogMeal API status

### Nutrition History API (Port 5004) - Tracking & Dashboard
- `POST /api/save-nutrition` - Save nutrition analysis record
  - Request: JSON with foodName, mealType, calories, nutritionInfo, nutriScore
  - Response: `{status, recordId, message}`
- `GET /api/get-history` - Retrieve nutrition history
  - Query params: userId, limit, offset, dateFrom, dateTo, mealType
  - Response: paginated records with nutrition details
- `GET /api/get-statistics` - Get nutrition statistics
  - Response: total records, average calories, meal distribution, nutri score distribution
- `DELETE /api/delete-record/{record_id}` - Delete specific record
- `GET /` - Serve nutrition dashboard HTML interface

## External Services Configuration

### Google OAuth
- Client ID: Set in `.env` file (EXPO_PUBLIC_GOOGLE_CLIENT_ID)
- Redirect URIs: `http://localhost:19000`, `http://localhost:19000/redirect`
- Configuration: `config/auth.config.ts`
- Service: `services/googleAuthService.ts`
- Required: Set up Authorized redirect URIs in Google Cloud Console

### OpenWeatherMap API
- API Key: `72cade2afd8d0b233391812e15fda078` (hardcoded)
- Used for real-time weather data based on user location

### T-Map API
- API Key: `F1YRiyhnpe2JhzqhlotAu8LF56DUKeQD9cA4Uxxb` (in tmapService.js)
- Services: Address search, reverse geocoding, POI search
- Note: Korean addresses only, no international support

## Testing

### Backend Test Suite
```bash
cd public_projects/chatbot_v0

# Test with personas
python main.py --mode chat
# Select: 1 (민호, 17세), 2 (명빈, 14세), 3 (태훈, 12세)

# API endpoint tests
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "내 이름이 뭐야?", "user_id": "test", "persona_id": "min_ho"}'
```

### Frontend Testing
```bash
cd public_projects/ljm_skt_teamproject-main/ljm_skt_teamproject-main

# Lint checks
npm run lint

# Start Expo and test on device/emulator
npx expo start
```

## Key Data Flows

1. **Chat Flow with Persona Context**: 
   User input → Frontend collects settings (location, weather, allergies, preferences) → API `/chat` with metadata → Persona context loading → AI model inference with full context → Response generation → Frontend display

2. **Settings Impact on AI**:
   Settings page → AsyncStorage save → Next chat request includes: location data, weather info, selected allergies, preferred categories → Backend creates system prompt with all context → AI generates contextual response

3. **Persona Management**:
   Settings page persona selection → Warning about conversation reset → Clear chat history → Update persona_id → New conversation with fresh context

## Important Configuration

### Environment Variables
```bash
# Frontend (.env)
EXPO_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here
EXPO_PUBLIC_GOOGLE_CLIENT_SECRET=your_google_client_secret_here
EXPO_PUBLIC_API_URL=http://localhost:8000

# Backend
PYTHONPATH=.
API_HOST=0.0.0.0
API_PORT=8080  # or 8000 for standard server
LOG_LEVEL=info
DEVICE=cuda    # or 'cpu' for CPU-only
```

### Key File Paths
- User profiles: `outputs/user_profiles/`
- Session logs: `outputs/yumai_chatbot.log`
- FAISS indexes: `outputs/prebuilt_faiss.faiss`
- Persona data: `data/personas.json`
- Restaurant data: `src/data/restaurants_real.json`
- Google Auth Config: `config/auth.config.ts`
- Google Auth Service: `services/googleAuthService.ts`

## Migration Notes

When migrating from `chat_bot` to `chatbot_v0`:
1. Use `persona_api_server.py` (port 8080) instead of standard server
2. Frontend should call `http://localhost:8080/chat`
3. Include persona_id in requests for persona-based responses
4. No PostgreSQL required - uses SQLite internally
5. See `MIGRATION_TO_CHATBOT_V0.md` for detailed steps

## Key Features

- **그르시 (Geursi) Character**: AI chatbot character providing friendly food recommendations
- **Google OAuth Login**: Secure authentication with Google accounts
- **Persona System**: Three youth personas with different characteristics
  - 김민호 (17세): Low balance, seafood restrictions
  - 김명빈 (14세): Multiple allergies, needs quiet places
  - 강태훈 (12세): Prefers convenience stores, simple foods
- **Context-Aware AI**: Uses location, weather, allergies, and preferences
- **Meal Card System**: Tracks balance and spending for student users
- **Real-time Weather**: OpenWeatherMap integration for location-based weather
- **Address Services**: T-Map API for Korean address search and validation
- **Food Vision**: Camera integration for food image analysis
- **Learning Data Collection**: Automatic data collection for model improvement

## Service Information

- **Service Name**: YUM:AI
- **AI Character**: 그르시 (Geursi)
- **Target Users**: Children and youth
- **Primary Function**: Food recommendation with dietary considerations