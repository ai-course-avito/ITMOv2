from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from math import pi, sin
import time

app = FastAPI(title="SpecKit Demo Backend")


def _perf_meta(start: float) -> dict:
    return {
        "compute_ms": (time.perf_counter() - start) * 1000.0,
        "payload_bytes": 0,
    }


@app.get("/api/health")
def health():
    return {"data": {"ok": True, "ts": int(time.time() * 1000)}, "meta": {}}


@app.get("/api/signals")
def signals():
    return {"data": ["square", "sawtooth", "triangle", "step", "sin", "cos"], "meta": {}}


@app.get("/api/fourier/series")
def fourier_series(
    signal: str = Query("square"),
    N: int = Query(10, ge=1, le=512),
    grid_n: int = Query(512, ge=64, le=4096),
):
    if signal != "square":
        raise HTTPException(status_code=400, detail={"code": "400_BAD_COMBO", "message": "Only 'square' supported in demo"})

    start = time.perf_counter()
    xs = [(-pi) + (2 * pi) * i / grid_n for i in range(grid_n + 1)]

    def sN(x: float) -> float:
        # s_N(x) = (4/π) * sum_{k=0}^{N-1} sin((2k+1)x)/(2k+1)
        s = 0.0
        for k in range(N):
            n = 2 * k + 1
            s += sin(n * x) / n
        return (4.0 / pi) * s

    ys = [sN(x) for x in xs]
    meta = {"flags": {"stable_method": "analytic", "cache_hit": False}, "perf": _perf_meta(start)}
    return {"data": {"x": xs, "sN": ys}, "meta": meta}
