import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.routes import router as api_router

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5500")

app = FastAPI(title="HoneyChain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router)