import io
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from app.ml_model import ModelUnavailableError, predict
import os

from dotenv import load_dotenv
from app.routing.routes import router as api_router

load_dotenv()

DEFAULT_FRONTEND_URL = "https://honeychain-icix.onrender.com"
LOCAL_FRONTEND_URLS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def get_frontend_origins() -> list[str]:
    env_list = os.getenv("FRONTEND_URLS")
    if env_list:
        return [origin.strip().rstrip("/") for origin in env_list.split(",") if origin.strip()]

    origins: list[str] = []
    for url in [DEFAULT_FRONTEND_URL, *LOCAL_FRONTEND_URLS]:
        if url not in origins:
            origins.append(url)

    return origins


FRONTEND_URLS = get_frontend_origins()
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="HoneyChain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
class ObjectDetection(BaseModel):
    label: str = Field(description="Detected object class: Queen, Worker, Drone, or Varroa")
    confidence: float = Field(ge=0, le=1)
    box: list[float] = Field(description="Bounding box [x1, y1, x2, y2] in source-image pixels")


class BeeImagePrediction(BaseModel):
    prediction: Literal["Healthy", "Infected"]
    bee_status: Literal["Healthy", "Infected"]
    varroa_detected: bool
    detections: list[ObjectDetection]
    counts: dict[str, int]
    thresholds: dict[str, float]


@app.post("/predict", response_model=BeeImagePrediction, tags=["image classification"])
async def predict_image(file: UploadFile = File(...)):
    image_bytes = await file.read(2 * 1024 * 1024 + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Choose a JPG or PNG image")
    if len(image_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Images must be 2 MB or smaller")

    try:
        with Image.open(io.BytesIO(image_bytes)) as uploaded_image:
            if uploaded_image.format not in {"JPEG", "PNG"}:
                raise HTTPException(status_code=400, detail="Only JPG and PNG images are supported")
            image = uploaded_image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=400, detail="Upload a valid JPG or PNG image") from error

    try:
        return predict(image)
    except ModelUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Bee image assessment failed") from error
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)
