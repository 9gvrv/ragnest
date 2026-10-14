from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import create_app


async def test_health_reports_connected(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


async def test_health_reports_503_when_database_fails():
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("database is down")

    app = create_app()

    async def broken_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health")

    assert resp.status_code == 503
    assert resp.json() == {"status": "error", "database": "unreachable"}
