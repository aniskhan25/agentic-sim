"""Provider-neutral dispatch failure categories (target_architecture.md's
Architectural Rule 9: "Provider errors are normalized. Timeouts, capacity
failures, malformed responses, cancellation, and unsupported capabilities
have provider-neutral categories.").

Honest scope note: only ProviderTimeoutError (raised for a bare
TimeoutError) and the generic ProviderError catch-all are actually produced
by classification logic today (see sync_provider_adapter.py). The other
subtypes are defined for taxonomy completeness and for a future backend or
adapter to raise directly -- nothing in today's four backends triggers them:
Aitta's own malformed-response handling already falls back to a stub
proposal internally rather than raising, so it never reaches this layer as
an exception; ProviderCancelledError is reserved for a future adapter whose
cancel() can actually interrupt in-flight work.
"""

from __future__ import annotations


class ProviderError(Exception):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderCapacityError(ProviderError):
    pass


class ProviderCancelledError(ProviderError):
    pass


class ProviderUnsupportedCapabilityError(ProviderError):
    pass


class ProviderMalformedResponseError(ProviderError):
    pass
