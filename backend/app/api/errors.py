"""One error format for the whole API: {"error": {"code": "...", "message": "..."}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.disputes.classifier import ClassifierNotAvailable
from app.seed import SyntheticDataMissing
from app.state_machine import IllegalTransition, InvalidDeliveryCode
from app.trust.service import FeaturesMissing

logger = logging.getLogger("safeorder.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ModelUnavailable(RuntimeError):
    pass


def _body(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for item in exc.errors()[:5]:
        where = ".".join(str(p) for p in item["loc"] if p != "body")
        parts.append(f"{where}: {item['msg']}" if where else item["msg"])
    return "; ".join(parts) or "invalid request"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _body(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _body(422, "VALIDATION_ERROR", _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return _body(exc.status_code, code, str(exc.detail))

    @app.exception_handler(LookupError)
    async def not_found(_: Request, exc: LookupError) -> JSONResponse:
        return _body(404, "NOT_FOUND", str(exc.args[0]) if exc.args else "not found")

    @app.exception_handler(IllegalTransition)
    async def illegal(_: Request, exc: IllegalTransition) -> JSONResponse:
        return _body(409, "ILLEGAL_STATE", str(exc))

    @app.exception_handler(InvalidDeliveryCode)
    async def bad_code(_: Request, exc: InvalidDeliveryCode) -> JSONResponse:
        return _body(400, "INVALID_CODE", "the delivery code is wrong")

    @app.exception_handler(ClassifierNotAvailable)
    async def no_classifier(_: Request, exc: ClassifierNotAvailable) -> JSONResponse:
        return _body(503, "CLASSIFIER_UNAVAILABLE", str(exc))

    @app.exception_handler(ModelUnavailable)
    async def no_model(_: Request, exc: ModelUnavailable) -> JSONResponse:
        return _body(503, "MODEL_UNAVAILABLE", str(exc))

    @app.exception_handler(FeaturesMissing)
    async def no_features(_: Request, exc: FeaturesMissing) -> JSONResponse:
        return _body(409, "NO_TRUST_FEATURES", str(exc))

    @app.exception_handler(SyntheticDataMissing)
    async def no_data(_: Request, exc: SyntheticDataMissing) -> JSONResponse:
        return _body(409, "DATA_MISSING", str(exc))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return _body(500, "INTERNAL_ERROR", "something went wrong")
