"""FastAPI application factory."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.agent_routes import router as agent_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import ApiError

log = logging.getLogger("ripple.api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ripple Room API", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["content-type"],
        )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:12]
        request.state.correlation_id = cid
        response: Response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        log.info(
            "api_error code=%s path=%s cid=%s",
            exc.code,
            request.url.path,
            getattr(request.state, "correlation_id", "-"),
        )
        return JSONResponse(status_code=exc.status, content=exc.payload())

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "")} for e in exc.errors()[:20]]
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "VALIDATION_ERROR", "message": "Request failed validation.", "details": details}
            },
        )

    app.include_router(router)
    app.include_router(agent_router)

    static_dir = settings.static_dir
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app


app = create_app()
