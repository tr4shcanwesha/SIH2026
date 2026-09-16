from app.main import get_frontend_origins
from app.auth.auth import get_cookie_security


def test_get_frontend_origins_includes_prod_and_local(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("FRONTEND_URLS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    origins = get_frontend_origins()

    assert "https://honeychain-icix.onrender.com" in origins
    assert "http://localhost:8000" in origins
    assert "http://127.0.0.1:8000" in origins


def test_get_frontend_origins_respects_env_list(monkeypatch):
    monkeypatch.setenv("FRONTEND_URLS", "https://prod.example.com, http://localhost:3000")
    monkeypatch.delenv("FRONTEND_URL", raising=False)

    origins = get_frontend_origins()

    assert origins == ["https://prod.example.com", "http://localhost:3000"]


def test_get_cookie_security_depends_on_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert get_cookie_security() is False

    monkeypatch.setenv("APP_ENV", "production")
    assert get_cookie_security() is True
