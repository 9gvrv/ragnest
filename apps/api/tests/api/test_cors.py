from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import create_app


async def _preflight(origin: str):
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )


async def test_preflight_allows_the_configured_web_origin(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://ragnest.vercel.app")

    response = await _preflight("https://ragnest.vercel.app")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ragnest.vercel.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]


async def test_preflight_rejects_other_origins(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://ragnest.vercel.app")

    response = await _preflight("https://evil.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_no_cors_headers_when_allowlist_is_empty(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "")

    response = await _preflight("https://ragnest.vercel.app")

    assert "access-control-allow-origin" not in response.headers
