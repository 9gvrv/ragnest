async def test_app_boots_and_serves_openapi(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert "openapi" in resp.json()
