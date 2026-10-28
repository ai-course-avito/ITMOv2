from statistics import median
from time import perf_counter

from fastapi.testclient import TestClient

from app.main import app


def test_typical_fourier_latency():
    client = TestClient(app)
    durations = []
    body = {
        "operation": "fourier_partial_sum",
        "contract_version": "v1",
        "parameters": {"order": 20, "interval": [-3.14, 3.14], "sample_count": 200},
    }
    for _ in range(20):
        started = perf_counter()
        response = client.post("/api/v1/calculate", json=body)
        durations.append((perf_counter() - started) * 1000)
        assert response.status_code == 200
    assert median(durations) < 80
    assert sorted(durations)[int(len(durations) * 0.95) - 1] < 250
