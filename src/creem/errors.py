"""Exception hierarchy for the Creem SDK.

Every failure raised by the SDK derives from :class:`CreemError`. API
failures raise a subclass of :class:`CreemAPIError` carrying the HTTP
status, the API's ``trace_id`` (include it in support requests), and the
human-readable messages from the response body.
"""

from __future__ import annotations


class CreemError(Exception):
    """Base class for all errors raised by the SDK."""


class CreemConfigurationError(CreemError):
    """The client was constructed without a usable API key."""


class CreemAPIError(CreemError):
    """An API request failed with a non-2xx status.

    Attributes:
        status: The HTTP status code.
        trace_id: The request identifier for debugging (may be absent when
            the response body was not the standard error envelope).
        error: The short error category from the API.
        messages: Human-readable error messages, one per problem found.
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        trace_id: str | None = None,
        error: str | None = None,
        messages: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.trace_id = trace_id
        self.error = error
        self.messages = messages or []

    @property
    def detail(self) -> str:
        """The human-readable error summary."""
        return str(self.args[0])

    def __str__(self) -> str:
        base = self.detail
        if self.trace_id:
            base = f"{base} (trace_id: {self.trace_id})"
        return base


class CreemValidationError(CreemAPIError):
    """400: invalid parameters, malformed JSON, or a duplicate resource."""


class CreemAuthError(CreemAPIError):
    """401/403: missing, invalid, or unauthorized API key."""


class CreemNotFoundError(CreemAPIError):
    """404: the requested resource does not exist."""


class CreemRateLimitError(CreemAPIError):
    """429: the rate limit was exceeded."""


class CreemServerError(CreemAPIError):
    """5xx: the Creem API failed to process the request."""
