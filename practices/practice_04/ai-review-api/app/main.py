from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.llm import LLMClient, get_llm_client

MAX_DIFF_BYTES = 100000
LLM_TIMEOUT_SECONDS = 10

app = FastAPI(title="ai-review-api")


class ReviewRequest(BaseModel):
    diff: str

    @field_validator("diff")
    @classmethod
    def diff_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("diff must not be blank")
        return value


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/review")
def review(body: ReviewRequest, llm: LLMClient = Depends(get_llm_client)):
    if len(body.diff.encode("utf-8")) > MAX_DIFF_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "error": "diff_too_large",
                "detail": f"diff is larger than {MAX_DIFF_BYTES} bytes",
                "max_bytes": MAX_DIFF_BYTES,
            },
        )
    # shutdown(wait=False): иначе зависший вызов LLM держал бы ответ дольше таймаута
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(llm.review, body.diff).result(timeout=LLM_TIMEOUT_SECONDS)
    except Exception:
        return JSONResponse(
            status_code=502,
            content={"error": "llm_unavailable", "detail": "LLM is unavailable or timed out"},
        )
    finally:
        executor.shutdown(wait=False)
