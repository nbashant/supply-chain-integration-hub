class DomainError(Exception):
    """Base class for errors safe to expose through the API."""


class DomainValidationError(DomainError):
    """A requested change violates a business rule."""


class ResourceNotFoundError(DomainError):
    """A requested domain resource does not exist."""


class ResourceConflictError(DomainError):
    """A requested change conflicts with existing state."""


class ResourceUnavailableError(DomainError):
    """A required local dependency is temporarily unavailable."""


class TransientImportError(Exception):
    """A background import failure that is safe to retry."""


class PermanentImportError(Exception):
    """A background import failure that requires investigation or correction."""
