import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routing.routes import router as api_router

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="HoneyChain API", version="0.1.0")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)