"""Application exception hierarchy."""


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str = "", detail: str | None = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    pass


class ValidationError(AppError):
    """Raised when input data fails validation."""

    pass


class ConfigurationError(AppError):
    """Raised when configuration is invalid or missing required values."""

    pass


class AuthenticationError(AppError):
    """Raised when authentication credentials are missing or invalid."""

    pass


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks permission for an action."""

    pass


class BackendUnavailableError(AppError):
    """Raised when an external service or image-generation backend is unreachable."""

    def __init__(
        self,
        message: str = "",
        detail: str | None = None,
        backend: str = "",
        retries_attempted: int = 0,
    ) -> None:
        self.backend = backend
        self.retries_attempted = retries_attempted
        super().__init__(message, detail)


class ComplianceError(AppError):
    """Raised when content fails legal or brand compliance checks."""

    def __init__(
        self,
        message: str = "",
        detail: str | None = None,
        error_count: int = 0,
        violations: list | None = None,
    ) -> None:
        self.error_count = error_count
        self.violations = violations or []
        super().__init__(message, detail)


class StorageError(AppError):
    """Raised when a file-storage operation fails."""

    pass


class JobError(AppError):
    """Raised when a background job encounters an unrecoverable error."""

    pass
