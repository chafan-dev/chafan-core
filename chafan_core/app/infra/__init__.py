"""Infrastructure helpers (request context, cache utilities, external clients)."""

# Import RequestContext lazily-safe: no app.crud at module import time.
from chafan_core.app.infra.request_context import RequestContext

__all__ = ["RequestContext"]
