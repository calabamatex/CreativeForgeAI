"""Tests for the application exception hierarchy."""
import pytest

from src.exceptions import (
    AppError,
    NotFoundError,
    ValidationError,
    ConfigurationError,
    AuthenticationError,
    AuthorizationError,
    BackendUnavailableError,
    ComplianceError,
    StorageError,
    JobError,
)


class TestExceptionHierarchy:
    """Verify all exceptions inherit from AppError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            NotFoundError,
            ValidationError,
            ConfigurationError,
            AuthenticationError,
            AuthorizationError,
            BackendUnavailableError,
            ComplianceError,
            StorageError,
            JobError,
        ],
    )
    def test_inherits_from_app_error(self, exc_class):
        assert issubclass(exc_class, AppError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            NotFoundError,
            ValidationError,
            ConfigurationError,
            AuthenticationError,
            AuthorizationError,
            BackendUnavailableError,
            ComplianceError,
            StorageError,
            JobError,
        ],
    )
    def test_inherits_from_exception(self, exc_class):
        assert issubclass(exc_class, Exception)


class TestAppError:
    """Test base AppError behaviour."""

    def test_default_message(self):
        err = AppError()
        assert err.message == ""
        assert err.detail is None

    def test_custom_message_and_detail(self):
        err = AppError(message="something broke", detail="extra info")
        assert err.message == "something broke"
        assert err.detail == "extra info"
        assert str(err) == "something broke"

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise AppError("test")


class TestComplianceError:
    """Test ComplianceError carries structured fields."""

    def test_default_fields(self):
        err = ComplianceError(message="blocked")
        assert err.error_count == 0
        assert err.violations == []
        assert err.message == "blocked"

    def test_with_violations(self):
        violations = [{"field": "headline", "issue": "prohibited word"}]
        err = ComplianceError(
            message="2 errors",
            error_count=2,
            violations=violations,
        )
        assert err.error_count == 2
        assert len(err.violations) == 1
        assert err.violations[0]["field"] == "headline"

    def test_with_detail(self):
        err = ComplianceError(
            message="blocked",
            detail="Full report here",
            error_count=1,
        )
        assert err.detail == "Full report here"


class TestBackendUnavailableError:
    """Test BackendUnavailableError carries backend info."""

    def test_default_fields(self):
        err = BackendUnavailableError(message="timeout")
        assert err.backend == ""
        assert err.retries_attempted == 0

    def test_with_backend_info(self):
        err = BackendUnavailableError(
            message="API unreachable",
            backend="openai",
            retries_attempted=3,
        )
        assert err.backend == "openai"
        assert err.retries_attempted == 3
        assert str(err) == "API unreachable"


class TestConfigurationError:
    """Test ConfigurationError exists and works."""

    def test_basic(self):
        err = ConfigurationError(message="Missing API key", detail="OPENAI_API_KEY")
        assert err.message == "Missing API key"
        assert err.detail == "OPENAI_API_KEY"
        assert isinstance(err, AppError)
