from statistics import quantiles
from time import perf_counter


def test_typical_api_latency_budget(api_client):
    request = {
        "operation": "fourier_partial_sum",
        "contract_version": "v1",
        "parameters": {"order": 10, "x_values": [-1.0, 0.0, 1.0]},
    }
    durations = []
    for _ in range(20):
        started = perf_counter()
        response = api_client.post("/api/v1/calculate", json=request)
        durations.append((perf_counter() - started) * 1000)
        assert response.status_code == 200
    p95 = quantiles(durations, n=20, method="inclusive")[18]
    assert p95 < 250
