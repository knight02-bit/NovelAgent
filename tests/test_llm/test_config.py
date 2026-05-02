"""Tests for LLM config loader."""

import json
from pathlib import Path

import pytest

from novelagent.llm import LLMConfig


class TestLLMConfigLoad:
    """Config file loading and fallback behaviour."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "llm.json"
        cfg_path.write_text(json.dumps({
            "providers": {
                "test_provider": {
                    "api_key": "sk-test",
                    "base_url": "https://test.api.com",
                    "default_model": "test-model",
                    "parameters": {"temperature": 0.5},
                }
            },
            "scene_routing": {
                "narrative": {
                    "tier": "high",
                    "provider": "test_provider",
                    "model": "test-model",
                    "parameters": {"max_tokens": 512},
                }
            },
        }))

        config = LLMConfig.load(str(cfg_path))
        assert config.is_configured() is True
        assert "test_provider" in config.providers
        assert config.providers["test_provider"].api_key == "sk-test"

    def test_load_nonexistent_returns_defaults(self) -> None:
        config = LLMConfig.load("/nonexistent/path/llm.json")
        assert config.providers == {}
        assert config.is_configured() is False

    def test_empty_config_is_not_configured(self) -> None:
        config = LLMConfig()
        assert config.is_configured() is False


class TestSceneRouting:
    """Scene-based route resolution."""

    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(
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
                    "tier": "high",
                    "provider": "provider_a",
                    "model": "model-a",
                    "parameters": {"max_tokens": 4096},
                },
                "kg": {
                    "tier": "low",
                    "provider": "provider_b",
                    "model": "model-b",
                    "parameters": {"max_tokens": 512},
                },
            },
        )

    def test_get_scene_config(self, config: LLMConfig) -> None:
        route = config.get_scene_config("narrative")
        assert route.provider == "provider_a"
        assert route.model == "model-a"
        assert route.parameters["max_tokens"] == 4096

    def test_get_kg_scene(self, config: LLMConfig) -> None:
        route = config.get_scene_config("kg")
        assert route.provider == "provider_b"
        assert route.model == "model-b"

    def test_unknown_scene_falls_back_to_narrative(
        self, config: LLMConfig
    ) -> None:
        route = config.get_scene_config("unknown_scene")
        # Falls back to narrative
        assert route.provider == "provider_a"

    def test_unknown_scene_with_no_narrative_fallback(self) -> None:
        config = LLMConfig(scene_routing={"kg": {"tier": "low", "provider": "p", "model": "m"}})
        route = config.get_scene_config("unknown_scene")
        assert route.provider == ""  # no fallback available

    def test_get_provider_config(self, config: LLMConfig) -> None:
        pc = config.get_provider_config("provider_a")
        assert pc is not None
        assert pc.api_key == "key-a"

    def test_get_nonexistent_provider(self, config: LLMConfig) -> None:
        assert config.get_provider_config("nonexistent") is None

    def test_scenes_constant(self) -> None:
        assert "narrative" in LLMConfig.SCENES
        assert "analysis" in LLMConfig.SCENES
        assert "brainstorm" in LLMConfig.SCENES
        assert "filter" in LLMConfig.SCENES
        assert "kg" in LLMConfig.SCENES
        assert len(LLMConfig.SCENES) == 5
