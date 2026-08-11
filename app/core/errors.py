# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The error envelope described in docs/api.md.

Every failure leaves through `{"error": {"code", "message", "detail"}}`. The
code is stable and machine readable, the message is written for the operator
who is looking at a substation hypervisor and needs to know what to do next.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """A failure with an operator facing message and a stable code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


class AuthenticationRequired(ApiError):
    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(
            "authentication_required", message, status.HTTP_401_UNAUTHORIZED
        )


class PermissionDenied(ApiError):
    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            "permission_denied", message, status.HTTP_403_FORBIDDEN, detail
        )


def _envelope(
    code: str, message: str, detail: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


_STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "authentication_required",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "precondition_failed",
    status.HTTP_503_SERVICE_UNAVAILABLE: "unavailable",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "invalid_request",
                "The request body or parameters are not valid.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )
