def test_math_response_exposes_v1_metadata_and_result_semantics(api_client):
    response = api_client.post(
        "/api/v1/calculate",
        json={
            "operation": "fourier_partial_sum",
            "contract_version": "v1",
            "parameters": {"order": 3, "x_values": [-1.0, 0.0, 1.0]},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v1"
    assert payload["metadata"]["result"] == {"ordering": "request_order", "finite": True}
    assert payload["metadata"]["domain"]["unit"] == "radian"


def test_invalid_content_type_has_structured_error(api_client):
    response = api_client.post("/api/v1/calculate", content="{}", headers={"content-type": "text/plain"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CONTENT_TYPE"
