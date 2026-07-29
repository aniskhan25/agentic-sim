from __future__ import annotations

import os
import time
from typing import Any

from agentic_sim.execution.capabilities import ProviderCapabilities
from agentic_sim.execution.openai_compatible_backend import (
    OpenAICompatibleExecutionBackend,
    Transport,
    _first_choice_text,
    _json_object,
)
from agentic_sim.models import PlatformManifest


class SelfHostedExecutionBackend(OpenAICompatibleExecutionBackend):
    """OpenAI-compatible client for a self-hosted model server (e.g. vLLM on
    LUMI/Roihu) -- item 19's prerequisite for the real two-system HPC study.
    Shares all request/response/repair/role-policy/receipt logic with
    AittaExecutionBackend via OpenAICompatibleExecutionBackend; differs only
    in what's genuinely different about a self-hosted deployment:

    - no required API key (most self-hosted vLLM servers run without auth;
      `_send`'s base-class header logic already omits Authorization when
      `api_key` is empty, so this needs no override at all);
    - env vars are generically named (SELF_HOSTED_*, not AITTA_*);
    - `enable_prefix_caching` and `max_context_tokens` are caller-supplied,
      since a deployed `vllm serve` invocation's real flags aren't
      discoverable over the OpenAI-compatible API itself;
    - an optional `platform_manifest` (see models/platform_manifest.py,
      ADR 0005) can be attached so every produced receipt carries
      `manifest_mode`, marking the run as primary evidence rather than a
      portability observation -- left unset (None) by default, never
      invented.
    """

    name = "self_hosted"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 3,
        max_json_repair_attempts: int = 1,
        max_concurrency: int = 1,
        temperature: float = 0.2,
        top_p: float = 0.95,
        max_completion_tokens: int | None = None,
        max_context_tokens: int | None = None,
        enable_prefix_caching: bool = False,
        transport: Transport | None = None,
        platform_manifest: PlatformManifest | None = None,
    ) -> None:
        resolved_api_key = api_key or os.environ.get("SELF_HOSTED_API_KEY", "")
        resolved_base_url = base_url or os.environ.get("SELF_HOSTED_BASE_URL", "")
        resolved_model_name = model_name or os.environ.get("SELF_HOSTED_MODEL", "")
        resolved_timeout = float(
            timeout_seconds
            if timeout_seconds is not None
            else os.environ.get("SELF_HOSTED_REQUEST_TIMEOUT", 120)
        )
        resolved_max_completion_tokens = int(
            max_completion_tokens or os.environ.get("SELF_HOSTED_MAX_COMPLETION_TOKENS", 256)
        )

        if not resolved_base_url:
            raise ValueError("SELF_HOSTED_BASE_URL is required for the self-hosted backend")
        if not resolved_model_name:
            raise ValueError("SELF_HOSTED_MODEL is required for the self-hosted backend")
        # api_key is deliberately NOT required -- most self-hosted vLLM
        # deployments run with no --api-key at all.

        self.enable_prefix_caching = enable_prefix_caching
        self.max_context_tokens = (
            int(max_context_tokens) if max_context_tokens is not None else resolved_max_completion_tokens
        )

        super().__init__(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model_name=resolved_model_name,
            timeout_seconds=resolved_timeout,
            max_retries=max_retries,
            max_json_repair_attempts=max_json_repair_attempts,
            max_concurrency=max_concurrency,
            temperature=temperature,
            top_p=top_p,
            max_completion_tokens=resolved_max_completion_tokens,
            transport=transport,
            platform_manifest=platform_manifest,
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_concurrency=self.max_concurrency > 1,
            supports_server_batching=False,
            supports_structured_output=True,
            supports_prefix_caching=self.enable_prefix_caching,
            max_context_tokens=self.max_context_tokens,
            observable_token_usage=True,
            observable_energy=False,
        )


def check_self_hosted_connection(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int = 0,
    transport: Transport | None = None,
) -> dict[str, Any]:
    backend = SelfHostedExecutionBackend(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        temperature=0,
        max_completion_tokens=64,
        transport=transport,
    )
    payload = {
        "model": backend.model_name,
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": 'Return exactly {"ok": true}.'},
        ],
        "temperature": 0,
        "max_completion_tokens": 64,
        "response_format": {"type": "json_object"},
        "n": 1,
    }
    started = time.perf_counter()
    response, _ = backend._send(payload)
    latency_seconds = round(time.perf_counter() - started, 3)
    content = _first_choice_text(response)
    parsed = _json_object(content)
    return {
        "ok": parsed.get("ok") is True,
        "base_url": backend.base_url,
        "model": backend.model_name,
        "latency_seconds": latency_seconds,
        "usage": response.get("usage"),
    }
