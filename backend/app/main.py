import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.auth import set_refreshed_auth_cookies
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

app.include_router(api_router)


@app.middleware("http")
async def refresh_supabase_cookies(request, call_next):
    response = await call_next(request)
    set_refreshed_auth_cookies(request, response)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)
