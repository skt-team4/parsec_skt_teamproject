# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NabiYam (나비얌) is a child-focused food recommendation system featuring an AI chatbot that helps children find suitable restaurants and food options. The system consists of a React Native mobile app, Python FastAPI backend with AI capabilities, and multiple deployment options.

## Architecture

### Frontend - React Native/Expo Mobile App
**Location**: `public_projects/ljm_skt_teamproject-main/ljm_skt_teamproject-main/`
- Built with React Native 0.79.5, Expo SDK 53, TypeScript
- File-based routing with Expo Router
- Key screens:
  - `app/chat.tsx` - Main chat interface with AI assistant
  - `app/food-category.tsx` - Food category selection
  - `app/nutrition.tsx` - Nutrition information display
  - `app/food_vision.tsx` - Food image analysis using camera
  - `app/orders.tsx` - Order management
  - `app/store.tsx` - Store/restaurant details with T-Map integration
  - `app/settings.tsx` - User settings (persona, location, allergies, preferences)
  - `app/(tabs)/_layout.tsx` - Tab navigation layout (5 tabs)

### Backend - Python FastAPI + AI Models
**Primary Location**: `public_projects/chatbot_v0/`
- **Main Server**: `persona_api_server.py` - Persona-based API (port 8080)
- **Alternative Server**: `src/api/server.py` - Standard API (port 8000)
- Core modules:
  - `src/inference/integrated_pipeline.py` - Main AI pipeline
  - `models/ax_encoder_base/` - A.X Encoder model files
  - `src/rag/` - FAISS-based RAG system
  - `src/recommendation/` - Multi-funnel recommendation engine
  - `src/data/restaurants_real.json` - Restaurant database
  - `data/personas.json` - Youth persona profiles (민호, 명빈, 태훈)
  - `outputs/prebuilt_faiss.faiss` - Pre-built vector indexes

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
npx expo start --port 19000 --web

# Platform-specific runs
npm run android    # Android emulator/device
npm run ios       # iOS simulator
npm run web       # Web browser

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

### Docker Operations
```bash
# Build and run main composition
docker-compose up --build

# Specific configurations
docker-compose -f docker-compose-naviyam.yml up
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

## External Services Configuration

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
# Backend
PYTHONPATH=.
API_HOST=0.0.0.0
API_PORT=8080  # or 8000 for standard server
LOG_LEVEL=info
DEVICE=cuda    # or 'cpu' for CPU-only
```

### Key File Paths
- User profiles: `outputs/user_profiles/`
- Session logs: `outputs/naviyam_chatbot.log`
- FAISS indexes: `outputs/prebuilt_faiss.faiss`
- Persona data: `data/personas.json`
- Restaurant data: `src/data/restaurants_real.json`

## Migration Notes

When migrating from `chat_bot` to `chatbot_v0`:
1. Use `persona_api_server.py` (port 8080) instead of standard server
2. Frontend should call `http://localhost:8080/chat`
3. Include persona_id in requests for persona-based responses
4. No PostgreSQL required - uses SQLite internally
5. See `MIGRATION_TO_CHATBOT_V0.md` for detailed steps

## Key Features

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