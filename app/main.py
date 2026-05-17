import traceback
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
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            request.method,

