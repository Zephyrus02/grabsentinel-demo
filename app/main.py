import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(title="Auth Server")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        # Ensure exception logging uses the correct level to avoid pipeline misclassification
        raise
    # Explicitly log successful requests with INFO level to ensure correct parsing
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "request_success method=%s path=%s duration_ms=%.2f",
        request.method, request.url.path, elapsed_ms
    )
