"""Tests for LLM Provider API dispatch with mocked HTTP."""

import httpx
import pytest

from novelagent.llm import LLMConfig, LLMError, LLMProvider, LLMResponse


def _make_anthropic_response(text: str = "Hello from Claude") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )


def _make_openai_response(text: str = "Hello from GPT") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


@pytest.fixture
def anthropic_config() -> LLMConfig:
    return LLMConfig(
        providers={
            "anthropic": {
                "api_key": "sk-ant-test",
                "base_url": "https://api.anthropic.com",
                "default_model": "claude-sonnet-4-6",
                "parameters": {"temperature": 0.8, "max_tokens": 4096},
            }
        },
        scene_routing={
            "narrative": {
                "tier": "high",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "parameters": {"temperature": 0.8, "max_tokens": 1024},
            }
        },
    )


@pytest.fixture
def openai_config() -> LLMConfig:
    return LLMConfig(
        providers={
            "openai": {
                "api_key": "sk-openai-test",
                "base_url": "https://api.openai.com/v1",
                "default_model": "gpt-4o",
                "parameters": {"temperature": 0.7},
            }
        },
        scene_routing={
            "narrative": {
                "tier": "high",
                "provider": "openai",
                "model": "gpt-4o",
                "parameters": {"temperature": 0.7, "max_tokens": 512},
            }
        },
    )


@pytest.fixture
def no_key_config() -> LLMConfig:
    """Config with empty API key — tests graceful failure."""
    return LLMConfig(
        providers={
            "anthropic": {
                "api_key": "",
                "base_url": "https://api.anthropic.com",
                "default_model": "claude-sonnet-4-6",
                "parameters": {},
            }
        },
        scene_routing={
            "narrative": {
                "tier": "high",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "parameters": {},
            }
        },
    )


@pytest.fixture
def no_provider_config() -> LLMConfig:
    """Config referencing a non-existent provider."""
    return LLMConfig(
        providers={},
        scene_routing={
            "narrative": {
                "tier": "high",
                "provider": "nonexistent",
                "model": "nonexistent",
                "parameters": {},
            }
        },
    )


class TestAnthropicAPI:
    """Anthropic Messages API calls."""

    async def test_generate_success(self, anthropic_config: LLMConfig) -> None:
        transport = httpx.MockTransport(lambda req: _make_anthropic_response())
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=anthropic_config, http_client=client)
        result = await provider.generate("Hello", scene="narrative")

        assert isinstance(result, LLMResponse)
        assert result.text == "Hello from Claude"
        assert result.model == "claude-sonnet-4-6"
        assert result.provider == "anthropic"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 5

    async def test_generate_sends_correct_headers(self, anthropic_config: LLMConfig) -> None:
        sent_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent_headers.update(dict(request.headers))
            return _make_anthropic_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=anthropic_config, http_client=client)
        await provider.generate("Hello")

        assert sent_headers.get("x-api-key") == "sk-ant-test"
        assert sent_headers.get("anthropic-version") == "2023-06-01"

    async def test_generate_sends_correct_body(self, anthropic_config: LLMConfig) -> None:
        sent_body = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json
            sent_body.update(json.loads(request.content))
            return _make_anthropic_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=anthropic_config, http_client=client)
        await provider.generate("Test prompt")

        assert sent_body["model"] == "claude-sonnet-4-6"
        assert sent_body["max_tokens"] == 1024
        assert sent_body["messages"] == [{"role": "user", "content": "Test prompt"}]

    async def test_override_params(self, anthropic_config: LLMConfig) -> None:
        sent_body = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json
            sent_body.update(json.loads(request.content))
            return _make_anthropic_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=anthropic_config, http_client=client)
        await provider.generate("Hello", scene="narrative", temperature=0.5, max_tokens=2048)

        assert sent_body["temperature"] == 0.5
        assert sent_body["max_tokens"] == 2048


class TestOpenAIAPI:
    """OpenAI-compatible chat completions API calls."""

    async def test_generate_success(self, openai_config: LLMConfig) -> None:
        transport = httpx.MockTransport(lambda req: _make_openai_response())
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=openai_config, http_client=client)
        result = await provider.generate("Hello", scene="narrative")

        assert result.text == "Hello from GPT"
        assert result.model == "gpt-4o"
        assert result.provider == "openai"

    async def test_generate_sends_auth_header(self, openai_config: LLMConfig) -> None:
        sent_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent_headers.update(dict(request.headers))
            return _make_openai_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=openai_config, http_client=client)
        await provider.generate("Hello")

        assert sent_headers.get("authorization") == "Bearer sk-openai-test"

    async def test_generate_sends_correct_body(self, openai_config: LLMConfig) -> None:
        sent_body = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json
            sent_body.update(json.loads(request.content))
            return _make_openai_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)

        provider = LLMProvider(config=openai_config, http_client=client)
        await provider.generate("Test prompt")

        assert sent_body["model"] == "gpt-4o"
        assert sent_body["messages"] == [{"role": "user", "content": "Test prompt"}]


class TestErrorHandling:
    """LLM API error handling."""

    async def test_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = LLMConfig(
            providers={"test": {"api_key": "bad", "base_url": "https://test.api.com", "default_model": "m"}},
            scene_routing={"narrative": {"tier": "low", "provider": "test", "model": "m"}},
        )

        provider = LLMProvider(config=config, http_client=client)
        with pytest.raises(LLMError, match="LLM API error"):
            await provider.generate("Hello")

    async def test_network_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.RequestError("Connection refused")

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = LLMConfig(
            providers={"test": {"api_key": "key", "base_url": "https://test.api.com", "default_model": "m"}},
            scene_routing={"narrative": {"tier": "low", "provider": "test", "model": "m"}},
        )

        provider = LLMProvider(config=config, http_client=client)
        with pytest.raises(LLMError, match="LLM request failed"):
            await provider.generate("Hello")

    async def test_no_provider_config(self) -> None:
        config = LLMConfig(
            providers={},
            scene_routing={"narrative": {"tier": "low", "provider": "nonexistent", "model": "m"}},
        )
        provider = LLMProvider(config=config)
        with pytest.raises(LLMError, match="No provider configuration"):
            await provider.generate("Hello")


class TestSceneSelection:
    """Scene routing in the provider."""

    async def test_routes_to_correct_endpoint(self) -> None:
        """Different scenes use different provider configs."""
        call_log = []

        config = LLMConfig(
            providers={
                "provider_a": {
                    "api_key": "key-a",
                    "base_url": "https://a.example.com",
                    "default_model": "model-a",
                    "parameters": {},
                },
                "provider_b": {
                    "api_key": "key-b",
                    "base_url": "https://b.example.com",
                    "default_model": "model-b",
                    "parameters": {},
                },
            },
            scene_routing={
                "narrative": {
                    "tier": "high", "provider": "provider_a", "model": "model-a", "parameters": {},
                },
                "kg": {
                    "tier": "low", "provider": "provider_b", "model": "model-b", "parameters": {},
                },
            },
        )

        def handler(request: httpx.Request) -> httpx.Response:
            call_log.append(str(request.url))
            return _make_openai_response()

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        provider = LLMProvider(config=config, http_client=client)

        await provider.generate("Hello", scene="narrative")
        assert any("a.example.com" in str(c) for c in call_log)


class TestProviderLifecycle:
    """Provider lifecycle management."""

    async def test_close_with_owned_client(self) -> None:
        """Provider with no injected client creates and cleans up its own."""
        config = LLMConfig(
            providers={"t": {"api_key": "k", "base_url": "https://test.api.com", "default_model": "m"}},
            scene_routing={"narrative": {"tier": "low", "provider": "t", "model": "m"}},
        )
        provider = LLMProvider(config=config)
        # close should not raise even if no client was used
        await provider.close()
