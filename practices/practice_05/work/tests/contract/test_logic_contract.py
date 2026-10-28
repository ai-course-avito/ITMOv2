from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_contract_success_metadata_and_fourier_interval():
    response = client.post(
        "/api/v1/calculate",
        json={
            "operation": "fourier_partial_sum",
            "contract_version": "v1",
            "parameters": {"order": 3, "interval": [-1, 1], "sample_count": 5},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["contract_version"] == "v1"
    assert set(payload["metadata"]) >= {"normalized_parameters", "domain", "tolerance", "duration_ms", "cache_status"}
    assert len(payload["data"]["x"]) == len(payload["data"]["y"]) == 5


def test_unknown_target_and_extra_fields_are_rejected():
    response = client.post(
        "/api/v1/calculate",
        json={
            "operation": "interpolation_comparison",
            "contract_version": "v1",
            "parameters": {"target": "eval(x)", "node_count": 4, "evaluation_grid": [0], "extra": 1},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_malformed_json_is_structured():
    response = client.post("/api/v1/calculate", content=b"not-json", headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_JSON"
