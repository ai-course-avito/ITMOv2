def test_repeated_fourier_requests_are_deterministic(api_client):
    request = {
        "operation": "fourier_partial_sum",
        "contract_version": "v1",
        "parameters": {"order": 5, "x_values": [-1.0, -0.25, 0.0, 1.0]},
    }
    first = api_client.post("/api/v1/calculate", json=request).json()
    second = api_client.post("/api/v1/calculate", json=request).json()
    assert first["metadata"]["normalized_parameters"] == second["metadata"]["normalized_parameters"]
    assert first["data"] == second["data"]
    assert second["metadata"]["cache_status"] == "hit"


def test_chebyshev_values_are_finite(api_client):
    response = api_client.post(
        "/api/v1/calculate",
        json={
            "operation": "chebyshev_values",
            "contract_version": "v1",
            "parameters": {"kind": "first", "order": 4, "x_values": [-1.0, 0.0, 1.0]},
        },
    )
    assert response.status_code == 200
    assert all(value == value for value in response.json()["data"]["y"])
