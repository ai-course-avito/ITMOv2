from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.models import RequestEnvelope
from app.services.calculator import CalculationError, calculate, error_response


router = APIRouter(prefix="/api/v1")


@router.post("/calculate")
async def calculate_route(request: Request) -> JSONResponse:
    try:
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
            error = CalculationError("INVALID_CONTENT_TYPE", "content-type", "request must use JSON", "Content-Type must be application/json", 400)
            return JSONResponse(error_response(error).model_dump(mode="json"), status_code=400)
        body = await request.json()
        if not isinstance(body, dict):
            raise CalculationError("MALFORMED_JSON", "body", "request body must be a JSON object", "send a JSON object")
        try:
            envelope = RequestEnvelope.model_validate(body)
        except Exception as exc:
            raise CalculationError("VALIDATION_ERROR", "body", str(exc), "send the documented request envelope") from exc
        response = calculate(envelope.operation, envelope.contract_version, envelope.parameters)
        return JSONResponse(response.model_dump(mode="json"))
    except ValueError as exc:
        error = CalculationError("MALFORMED_JSON", "body", "request body is not valid JSON", "send valid JSON")
        return JSONResponse(error_response(error).model_dump(mode="json"), status_code=400)
    except CalculationError as exc:
        return JSONResponse(error_response(exc).model_dump(mode="json"), status_code=exc.status_code)
