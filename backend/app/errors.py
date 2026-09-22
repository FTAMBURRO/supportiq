"""API errors rendered as a consistent JSON envelope.

Lives at package level (not under ``app.api``) because the service layer
raises these and the API layer renders them: putting them under ``api``
would make services import HTTP code.
"""

from __future__ import annotations


class ApiError(Exception):
    """Base class for errors with an HTTP representation."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None,
                 status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class BadRequestError(ApiError):
    """The request cannot be understood: malformed JSON, bad types,
    unknown fields, values outside the allowed vocabulary."""

    status_code = 400
    code = "BAD_REQUEST"


class NotFoundError(ApiError):
    """The addressed resource does not exist."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(ApiError):
    """The request conflicts with the current state of the resource."""

    status_code = 409
    code = "CONFLICT"


class ValidationError(ApiError):
    """Well-formed request that fails a business validation: missing or
    blank fields, references that do not exist or are inactive."""

    status_code = 422
    code = "VALIDATION_ERROR"
