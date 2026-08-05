from fastapi.testclient import TestClient

from dollartl import __version__
from dollartl.api.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
