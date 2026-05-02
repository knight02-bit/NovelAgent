"""LLM Provider abstraction with scene-based routing and API dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from novelagent.llm.config import LLMConfig


class LLMError(Exception):
    """Raised when an LLM API call fails."""


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""

    text: str = ""
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
    })


class LLMProvider:
    """Single-model LLM provider with scene-based routing.

    For v0, uses one configured model (the ``narrative`` scene's route).
    Scene routing is preserved for future multi-model support.
    """

    def __init__(
        self,
        config_path: str | None = None,
        config: LLMConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or LLMConfig.load(config_path)
        self._http_client = http_client

    # ── Public API ───────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        scene: str = "narrative",
        **override_params: Any,
    ) -> LLMResponse:
        """Send a prompt to the LLM and return the response.

        The scene determines which provider and model to use.
        Extra ``**override_params`` are merged into the request parameters.
        """
        scene_config = self.config.get_scene_config(scene)
        provider_name = scene_config.provider
        provider_cfg = self.config.get_provider_config(provider_name)

        if not provider_cfg or not provider_cfg.base_url:
            raise LLMError(
                f"No provider configuration for scene '{scene}' "
                f"(resolved provider: '{provider_name}')"
            )

        params = {**scene_config.parameters, **override_params}
        model = scene_config.model or provider_cfg.default_model

        if "api_key" in params:
            api_key = params.pop("api_key")
        else:
            api_key = provider_cfg.api_key or ""

        try:
            text, usage = await self._call_api(
                provider_name=provider_name,
                base_url=provider_cfg.base_url,
                api_key=api_key,
                model=model,
                prompt=prompt,
                params=params,
            )
        except httpx.HTTPStatusError as e:
            raise LLMError(
                f"LLM API error ({e.response.status_code}): {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise LLMError(f"LLM request failed: {e}") from e

        return LLMResponse(
            text=text,
            model=model,
            provider=provider_name,
            usage=usage,
        )

    # ── API Dispatch ─────────────────────────────────────────────────────

    async def _call_api(
        self,
        provider_name: str,
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, int]]:
        """Dispatch to the correct API format based on provider name."""
        client = self._http_client or httpx.AsyncClient(timeout=120.0)
        owned_client = self._http_client is None

        try:
            if provider_name == "anthropic":
                return await self._call_anthropic(
                    client, base_url, api_key, model, prompt, params
                )
            return await self._call_openai_compatible(
                client, base_url, api_key, model, prompt, params
            )
        finally:
            if owned_client:
                await client.aclose()

    @staticmethod
    async def _call_anthropic(
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, int]]:
        """Call the Anthropic Messages API."""
        url = f"{base_url.rstrip('/')}/v1/messages"
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": params.pop("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
        }
        if params:
            body["temperature"] = params.pop("temperature", 0.7)
        body.update(params)

        resp = await client.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }

    @staticmethod
    async def _call_openai_compatible(
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, int]]:
        """Call an OpenAI-compatible chat completions API."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if params:
            body["temperature"] = params.pop("temperature", 0.7)
            body["max_tokens"] = params.pop("max_tokens", 1024)
        body.update(params)

        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        text = ""
        choices = data.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the internally-owned HTTP client if one was created."""
        if self._http_client is not None:
            await self._http_client.aclose()
