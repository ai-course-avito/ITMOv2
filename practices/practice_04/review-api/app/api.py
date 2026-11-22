from fastapi import FastAPI, HTTPException

from app.dependencies import review_service

app = FastAPI()


@app.post("/api/reviews")
def create_review(payload: dict) -> dict[str, str]:
    if "diff" not in payload or not isinstance(payload["diff"], str):
        raise HTTPException(status_code=422, detail="invalid diff")
    diff = payload["diff"]
    if not diff.strip():
        raise HTTPException(status_code=422, detail="invalid diff")
    if len(diff) > 20000:
        raise HTTPException(status_code=413, detail="diff too large")
    return review_service.review(diff)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
