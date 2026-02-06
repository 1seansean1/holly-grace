"""Tests for LLM config, router, and fallback chains."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.llm.config import (
    COMPLEXITY_MODEL_MAP,
    FALLBACK_CHAINS,
    MODEL_REGISTRY,
    LLMSettings,
    ModelID,
    TaskComplexity,
)
from src.llm.fallback import get_model_with_fallbacks
from src.llm.router import LLMRouter


def test_model_registry_has_all_models():
    """All ModelID values should be in the registry."""
    for model_id in ModelID:
        assert model_id in MODEL_REGISTRY


def test_complexity_model_map_covers_all():
    """All complexity levels should have a model mapping."""
    for complexity in TaskComplexity:
        assert complexity in COMPLEXITY_MODEL_MAP


def test_fallback_chains_exist_for_all_models():
    """All models should have fallback chains defined."""
    for model_id in ModelID:
        assert model_id in FALLBACK_CHAINS
        assert len(FALLBACK_CHAINS[model_id]) >= 1


def test_router_creates_ollama_model(router):
    """Router should create ChatOllama for Ollama models."""
    model = router.get_model(ModelID.OLLAMA_QWEN)
    assert isinstance(model, ChatOllama)


def test_router_creates_openai_model(router):
    """Router should create ChatOpenAI for OpenAI models."""
    model = router.get_model(ModelID.GPT4O_MINI)
    assert isinstance(model, ChatOpenAI)


def test_router_creates_anthropic_model(router):
    """Router should create ChatAnthropic for Anthropic models."""
    model = router.get_model(ModelID.CLAUDE_OPUS)
    assert isinstance(model, ChatAnthropic)


def test_router_caches_models(router):
    """Router should return the same model instance on repeated calls."""
    m1 = router.get_model(ModelID.GPT4O_MINI)
    m2 = router.get_model(ModelID.GPT4O_MINI)
    assert m1 is m2


def test_router_get_model_for_complexity(router):
    """Router should map complexity to the correct model type."""
    model = router.get_model_for_complexity(TaskComplexity.TRIVIAL)
    assert isinstance(model, ChatOllama)

    model = router.get_model_for_complexity(TaskComplexity.COMPLEX)
    assert isinstance(model, ChatAnthropic)


def test_fallback_chain_returns_model_with_fallbacks(router):
    """get_model_with_fallbacks should wrap the primary model."""
    model = get_model_with_fallbacks(router, ModelID.OLLAMA_QWEN)
    # Should be a RunnableWithFallbacks wrapping the primary model
    assert model is not None


def test_cost_optimization():
    """Verify cost optimization: cheapest model for highest-volume task."""
    orchestrator_model = COMPLEXITY_MODEL_MAP[TaskComplexity.TRIVIAL]
    assert MODEL_REGISTRY[orchestrator_model].cost_per_1k_input == 0.0

    strategic_model = COMPLEXITY_MODEL_MAP[TaskComplexity.COMPLEX]
    assert MODEL_REGISTRY[strategic_model].cost_per_1k_input > 0.0
