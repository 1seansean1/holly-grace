"""LLM router: maps task complexity to LangChain ChatModel instances."""

from __future__ import annotations

import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.llm.config import (
    MODEL_REGISTRY,
    LLMSettings,
    ModelID,
    ModelSpec,
    TaskComplexity,
    COMPLEXITY_MODEL_MAP,
)

logger = logging.getLogger(__name__)


class LLMRouter:
    """Creates and caches LangChain ChatModel instances by ModelID."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self._settings = settings or LLMSettings()
        self._cache: dict[ModelID, BaseChatModel] = {}

    def get_model(self, model_id: ModelID) -> BaseChatModel:
        """Get or create a ChatModel for the given model ID."""
        if model_id in self._cache:
            return self._cache[model_id]

        spec = MODEL_REGISTRY[model_id]
        model = self._create_model(spec)
        self._cache[model_id] = model
        return model

    def get_model_for_complexity(self, complexity: TaskComplexity) -> BaseChatModel:
        """Get the primary model for a given task complexity."""
        model_id = COMPLEXITY_MODEL_MAP[complexity]
        return self.get_model(model_id)

    def _create_model(self, spec: ModelSpec) -> BaseChatModel:
        """Instantiate a LangChain ChatModel from a ModelSpec."""
        if spec.provider == "ollama":
            return ChatOllama(
                model=spec.model_name,
                base_url=self._settings.ollama_base_url,
                temperature=spec.temperature,
                num_predict=spec.max_tokens,
            )
        elif spec.provider == "openai":
            return ChatOpenAI(
                model=spec.model_name,
                api_key=self._settings.openai_api_key,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
            )
        elif spec.provider == "anthropic":
            return ChatAnthropic(
                model=spec.model_name,
                api_key=self._settings.anthropic_api_key,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
            )
        else:
            raise ValueError(f"Unknown provider: {spec.provider}")
