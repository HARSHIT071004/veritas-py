import time
import json
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("clearlens.http")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        request_id = f"req_{int(start * 1000000)}"

        try:
            response = await call_next(request)
            duration_ms = int((time.time() - start) * 1000)

            if response.status_code >= 400:
                logger.warning(
                    f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                    extra={"request_id": request_id, "duration_ms": duration_ms}
                )
            return response

        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(
                f"{request.method} {request.url.path} -> 500 ({duration_ms}ms): {str(exc)}",
                extra={"request_id": request_id, "duration_ms": duration_ms},
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Internal server error",
                    "request_id": request_id
                }
            )


class RequestValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length", "0")
            if content_length.isdigit() and int(content_length) > 10_000_000:
                return JSONResponse(
                    status_code=413,
                    content={"success": False, "error": "Request too large (max 10MB)"}
                )
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    if body:
                        json.loads(body)
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "error": "Invalid JSON in request body"}
                    )
        return await call_next(request)
