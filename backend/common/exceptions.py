from __future__ import annotations


class ScholarOSError(RuntimeError):
    """Base exception for expected ScholarOS service failures."""


class ExternalServiceError(ScholarOSError):
    """Raised when an external source or LLM provider fails."""


class RepositoryLoadError(ScholarOSError):
    """Raised when a code repository cannot be loaded."""
