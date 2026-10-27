"""HTTP boundary and same-origin static UI; no input or model output is logged."""
import asyncio
import json
import logging
from pathlib import Path
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.errors import ReviewError
from app.review import ReviewService

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'
audit = logging.getLogger('review.audit')
audit.setLevel(logging.INFO)
audit.propagate = False
if not audit.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    audit.addHandler(handler)


def create_app(*, service=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    reviewer = service or ReviewService(Settings.from_env())
    app.state.review_service = reviewer
    app.mount('/static', StaticFiles(directory=STATIC_DIR, check_dir=False), name='static')

    @app.get('/')
    async def index():
        path = STATIC_DIR / 'index.html'
        if not path.is_file():
            return JSONResponse({'detail': 'UI files are not ready.'}, status_code=404)
        return FileResponse(path, headers={'Cache-Control': 'no-store'})

    @app.post('/api/reviews')
    async def review(request: Request):
        request_id = str(uuid4())
        started = time.monotonic()
        status = 500
        try:
            media_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
            if media_type != 'application/json':
                raise ReviewError('UNSUPPORTED_MEDIA_TYPE')
            try:
                body = json.loads(await request.body())
            except (ValueError, UnicodeError, RecursionError):
                raise ReviewError('INVALID_JSON') from None
            if not isinstance(body, dict) or set(body) != {'diff'} or not isinstance(body['diff'], str):
                raise ReviewError('INVALID_REQUEST')
            result = await reviewer.review(body['diff'])
            status = 200
            return JSONResponse({'request_id': request_id, **result}, headers={'Cache-Control': 'no-store'})
        except ReviewError as error:
            status = error.status
            return JSONResponse({'request_id': request_id, 'error': {'code': error.code, 'message': error.message}},
                                status_code=status, headers={'Cache-Control': 'no-store'})
        except asyncio.CancelledError:
            status = 499
            raise
        except Exception:
            error = ReviewError('INTERNAL_ERROR')
            status = error.status
            return JSONResponse({'request_id': request_id, 'error': {'code': error.code, 'message': error.message}},
                                status_code=status, headers={'Cache-Control': 'no-store'})
        finally:
            audit.info(json.dumps({'request_id': request_id,
                                   'duration_ms': round((time.monotonic()-started)*1000, 3),
                                   'status': status}))

    return app


app = create_app()
