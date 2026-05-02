"""LLM configuration loader — parses config/llm.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pydantic
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider (e.g. anthropic, openai)."""

    api_key: str | None = None
    base_url: str = ""
    default_model: str = ""
    parameters: dict[str, Any] = pydantic.Field(default_factory=dict)


class SceneRoute(BaseModel):
    """Routing configuration for a specific scene."""

    tier: str = "low"
    provider: str = ""
    model: str = ""
    parameters: dict[str, Any] = pydantic.Field(default_factory=dict)


class LLMConfig(BaseModel):
    """Top-level LLM configuration loaded from config/llm.json."""

    providers: dict[str, ProviderConfig] = pydantic.Field(default_factory=dict)
    scene_routing: dict[str, SceneRoute] = pydantic.Field(default_factory=dict)

    SCENES: ClassVar[frozenset] = frozenset({
        "narrative",
        "analysis",
        "brainstorm",
        "filter",
        "kg",
    })

    @classmethod
    def load(cls, path: str | Path | None = None) -> LLMConfig:
        """Load configuration from a JSON file.

        Searches in order:
        1. Explicit ``path``
        2. ``config/llm.json`` relative to cwd
        3. ``config/llm.json`` relative to the novelagent package root
        """
        if path is None:
            candidates = [
                Path.cwd() / "config" / "llm.json",
                Path(__file__).resolve().parent.parent.parent.parent
                / "config"
                / "llm.json",
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break
            else:
                # No config file found — return defaults
                return cls()

        path_obj = Path(path)
        if not path_obj.exists():
            return cls()
        with open(path_obj, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def get_scene_config(self, scene: str = "narrative") -> SceneRoute:
        """Return the route config for a scene, falling back to narrative."""
        route = self.scene_routing.get(scene)
        if route is not None:
            return route
        # Fallback to narrative scene config
        fallback = self.scene_routing.get("narrative")
        if fallback is not None:
            return fallback
        return SceneRoute(provider="", model="")

    def get_provider_config(self, provider_name: str) -> ProviderConfig | None:
        """Return the provider config by name."""
        return self.providers.get(provider_name)

    def is_configured(self) -> bool:
        """Return True if at least one provider has an API key."""
        return any(p.api_key for p in self.providers.values())
