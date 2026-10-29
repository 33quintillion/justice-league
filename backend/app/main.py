import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import account, admin, admin_sources, ai, auth, cases, dev, library, public

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("justice")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JUSTICE AI API", version="0.2.0", docs_url="/api/docs" if settings.is_dev else None,
                  openapi_url="/api/openapi.json" if settings.is_dev else None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        if not settings.is_dev:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Return readable messages without echoing submitted values (which may be sensitive).
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Please check the highlighted fields", "errors": errors})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})

    for r in (public.router, auth.router, account.router, cases.router, admin_sources.router, admin.router, library.router, ai.router):
        app.include_router(r)
    if settings.is_dev:
        app.include_router(dev.router)
    return app


app = create_app()
