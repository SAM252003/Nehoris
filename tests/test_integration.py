from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_docs_page_is_available():
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "Swagger UI" in resp.text or "swagger-ui" in resp.text.lower()
