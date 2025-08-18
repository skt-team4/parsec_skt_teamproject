from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io
import torch
from transformers import CLIPProcessor, CLIPModel
import logging
import os
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Korean Food Recognition API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)

# CLIP 모델 사용 (텍스트-이미지 매칭)
model = None
processor = None

# 한국 음식 리스트 (CLIP이 인식할 텍스트)
KOREAN_FOODS = [
    "떡볶이 tteokbokki spicy rice cake",
    "김치 kimchi fermented cabbage",
    "불고기 bulgogi marinated beef",
    "비빔밥 bibimbap mixed rice bowl",
    "삼겹살 samgyeopsal pork belly",
    "김밥 kimbap rice roll",
    "잡채 japchae glass noodles",
    "된장찌개 doenjang jjigae soybean paste stew",
    "김치찌개 kimchi jjigae kimchi stew",
    "순두부찌개 sundubu soft tofu stew",
    "갈비 galbi short ribs",
    "냉면 naengmyeon cold noodles",
    "삼계탕 samgyetang ginseng chicken soup",
    "파전 pajeon green onion pancake",
    "호떡 hotteok sweet pancake",
    "붕어빵 bungeoppang fish-shaped pastry",
    "김치볶음밥 kimchi fried rice",
    "제육볶음 jeyuk bokkeum spicy pork",
    "닭갈비 dak galbi spicy chicken",
    "순대 sundae blood sausage",
    "떡국 tteokguk rice cake soup",
    "칼국수 kalguksu knife-cut noodles",
    "팥빙수 patbingsu shaved ice dessert",
    "전 jeon korean pancake",
    "족발 jokbal pig's feet",
    "보쌈 bossam boiled pork",
    "치킨 korean fried chicken",
    "라면 ramyeon instant noodles",
    "만두 mandu dumplings",
    "계란찜 gyeran jjim steamed egg"
]

# 기타 인기 음식 추가
OTHER_FOODS = [
    "피자 pizza",
    "햄버거 hamburger",
    "파스타 pasta spaghetti",
    "초밥 sushi",
    "스테이크 steak",
    "샐러드 salad",
    "샌드위치 sandwich",
    "케이크 cake",
    "아이스크림 ice cream",
    "커피 coffee",
    "빵 bread",
    "도넛 donut",
    "초콜릿 chocolate",
    "과일 fruit",
    "야채 vegetables"
]

ALL_FOODS = KOREAN_FOODS + OTHER_FOODS

def load_model():
    global model, processor
    try:
        # CLIP 모델 사용 (다국어 지원)
        model_name = "openai/clip-vit-base-patch32"
        logger.info(f"Loading CLIP model: {model_name}")
        
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        
        logger.info("CLIP model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        return False

@app.on_event("startup")
async def startup_event():
    success = load_model()
    if not success:
        logger.warning("Running without model - will use mock predictions")

@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지 - HTML 인터페이스 제공"""
    try:
        return FileResponse("korean.html")
    except:
        # korean.html이 없으면 기본 HTML 반환
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Korean Food Recognition API</title>
        </head>
        <body>
            <h1>Korean Food Recognition API</h1>
            <p>API is running on port 5001</p>
            <p>Visit <a href="/docs">/docs</a> for API documentation</p>
        </body>
        </html>
        """)

@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        if model is None or processor is None:
            # Mock data for testing
            return JSONResponse(content={
                "status": "success",
                "predictions": [
                    {"label": "떡볶이", "score": 85.0},
                    {"label": "김치볶음밥", "score": 10.0},
                    {"label": "제육볶음", "score": 5.0}
                ],
                "food_item": "떡볶이",
                "confidence": 85.0
            })
        
        # CLIP 모델로 이미지-텍스트 매칭
        inputs = processor(
            text=ALL_FOODS,
            images=image,
            return_tensors="pt",
            padding=True
        )
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
        
        # 상위 5개 결과 추출
        top_k = 5
        top_probs, top_indices = torch.topk(probs[0], k=min(top_k, len(ALL_FOODS)))
        
        predictions = []
        for i in range(len(top_indices)):
            idx = top_indices[i].item()
            food_text = ALL_FOODS[idx]
            
            # 한글 이름만 추출 (첫 단어)
            korean_name = food_text.split()[0]
            
            # 퍼센트로 변환
            confidence_percent = float(top_probs[i].item()) * 100
            
            predictions.append({
                "label": korean_name,
                "score": confidence_percent
            })
        
        # 가장 높은 확률의 음식
        top_food = predictions[0] if predictions else {"label": "알 수 없음", "score": 0}
        
        return JSONResponse(content={
            "status": "success",
            "predictions": predictions,
            "food_item": top_food["label"],
            "confidence": top_food["score"]
        })
        
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    model_status = "loaded" if model is not None else "not_loaded"
    return {
        "status": "healthy",
        "model_status": model_status,
        "supported_foods": len(ALL_FOODS)
    }

@app.get("/foods")
async def list_foods():
    """지원하는 음식 목록 반환"""
    korean = [food.split()[0] for food in KOREAN_FOODS]
    other = [food.split()[0] for food in OTHER_FOODS]
    return {
        "korean_foods": korean,
        "other_foods": other,
        "total": len(ALL_FOODS)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)