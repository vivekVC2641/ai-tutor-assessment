import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request

from app.config import settings
from app.logging_config import setup_logging
from app.request_context import set_trace_id
from rag.vector_store import FaissVectorStore
from routes.api import router as api_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-request-id") or f"req_{uuid4().hex[:12]}"
    set_trace_id(trace_id)
    response = await call_next(request)
    response.headers["x-request-id"] = trace_id
    logger.info(
        "Handled request method=%s path=%s status=%s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict:
    store = FaissVectorStore()
    return {
        "app_name": settings.app_name,
        "provider": settings.provider,
        "index_ready": store.index_exists(),
    }
