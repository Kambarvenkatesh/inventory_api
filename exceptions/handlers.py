import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger("inventory_api")


class AppException(Exception):
    status_code = 500
    error = "InternalError"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ProductNotFoundError(AppException):
    status_code, error = 404, "ProductNotFound"


class DuplicateProductCodeError(AppException):
    status_code, error = 409, "DuplicateProductCode"


class InsufficientStockError(AppException):
    status_code, error = 400, "InsufficientStock"


class InvalidRequestError(AppException):
    status_code, error = 400, "InvalidRequest"


class DatabaseOperationError(AppException):
    status_code, error = 500, "DatabaseError"


def _body(error: str, message: str, details=None):
    body = {"error": error, "message": message}
    if details is not None:
        body["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exc(_: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.error, exc.message))

    @app.exception_handler(RequestValidationError)
    async def validation_exc(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"] if p not in ("body",)),
             "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422,
                            content=_body("ValidationError", "Request validation failed", details))

    @app.exception_handler(OperationalError)
    async def db_conn_exc(_: Request, exc: OperationalError):
        logger.error("Database connection failure: %s", exc)
        return JSONResponse(status_code=503,
                            content=_body("DatabaseUnavailable", "Database connection failure"))

    @app.exception_handler(SQLAlchemyError)
    async def db_exc(_: Request, exc: SQLAlchemyError):
        logger.error("Database error: %s", exc)
        return JSONResponse(status_code=500,
                            content=_body("DatabaseError", "A database error occurred"))
