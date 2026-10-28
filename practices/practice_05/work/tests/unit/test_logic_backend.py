import math

import numpy as np
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def request(operation, parameters):
    response = client.post(
        "/api/v1/calculate",
        json={"operation": operation, "contract_version": "v1", "parameters": parameters},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_fourier_n1_and_order_are_preserved():
    payload = request("fourier_partial_sum", {"order": 1, "x_values": [1.0, 0.0, -1.0]})
    assert payload["data"]["x"] == [1.0, 0.0, -1.0]
    assert np.allclose(payload["data"]["y"], [4 / math.pi * math.sin(x) for x in [1.0, 0.0, -1.0]])


def test_chebyshev_values_and_nodes():
    values = request("chebyshev_values", {"kind": "first", "order": 2, "x_values": [-1.0, 0.0, 1.0]})
    assert np.allclose(values["data"]["y"], [1.0, -1.0, 1.0])
    nodes = request("chebyshev_nodes", {"kind": "roots", "count": 8, "interval": [-1.0, 1.0]})
    result = nodes["data"]["nodes"]
    assert len(result) == 8
    assert result == sorted(result)
    assert all(-1 <= value <= 1 for value in result)


def test_interpolation_returns_both_strategies():
    payload = request(
        "interpolation_comparison",
        {"target": "cosine", "interval": [-1.0, 1.0], "node_count": 8, "evaluation_grid": [-1.0, 0.0, 1.0]},
    )
    assert set(payload["data"]["results"]) == {"chebyshev", "uniform"}
    for result in payload["data"]["results"].values():
        assert len(result["approximation"]) == 3
        assert result["max_absolute_error"] == max(abs(value) for value in result["pointwise_error"])


def test_invalid_payload_has_structured_error():
    response = client.post(
        "/api/v1/calculate",
        json={"operation": "fourier_partial_sum", "contract_version": "v1", "parameters": {"order": 0, "x_values": [0]}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_identical_request_exposes_cache_hit():
    body = {"operation": "fourier_partial_sum", "contract_version": "v1", "parameters": {"order": 2, "x_values": [0.25]}}
    first = client.post("/api/v1/calculate", json=body).json()
    second = client.post("/api/v1/calculate", json=body).json()
    assert first["data"] == second["data"]
    assert second["metadata"]["cache_status"] == "hit"
