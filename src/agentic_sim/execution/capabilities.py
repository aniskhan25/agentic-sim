from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProviderCapabilities:
    """What a backend can do, separate from how to connect to it."""

    supports_concurrency: bool
    supports_server_batching: bool
    supports_structured_output: bool
    supports_prefix_caching: bool
    max_context_tokens: int
    observable_token_usage: bool
    observable_energy: bool
