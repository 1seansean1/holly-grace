"""Model registry, cost table, and task complexity routing."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class TaskComplexity(str, Enum):
    """Task complexity levels that drive model selection."""

    TRIVIAL = "trivial"  # Simple classification, tagging
    SIMPLE = "simple"  # Single-step operations, lookups
    MODERATE = "moderate"  # Content generation, multi-step ops
    COMPLEX = "complex"  # Strategic analysis, campaign planning


class ModelID(str, Enum):
    """Registered model identifiers."""

    OLLAMA_QWEN = "ollama_qwen"
    GPT4O_MINI = "gpt4o_mini"
    GPT4O = "gpt4o"
    CLAUDE_OPUS = "claude_opus"


class ModelSpec(BaseModel):
    """Specification for a registered model."""

    model_id: ModelID
    provider: str  # "ollama", "openai", "anthropic"
    model_name: str  # Provider-specific model name
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_tokens: int = 4096
    temperature: float = 0.0


# Model registry — single source of truth for all model configs
MODEL_REGISTRY: dict[ModelID, ModelSpec] = {
    ModelID.OLLAMA_QWEN: ModelSpec(
        model_id=ModelID.OLLAMA_QWEN,
        provider="ollama",
        model_name="qwen2.5:3b",
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        max_tokens=2048,
        temperature=0.0,
    ),
    ModelID.GPT4O_MINI: ModelSpec(
        model_id=ModelID.GPT4O_MINI,
        provider="openai",
        model_name="gpt-4o-mini",
        cost_per_1k_input=0.15,
        cost_per_1k_output=0.60,
        max_tokens=4096,
        temperature=0.0,
    ),
    ModelID.GPT4O: ModelSpec(
        model_id=ModelID.GPT4O,
        provider="openai",
        model_name="gpt-4o",
        cost_per_1k_input=2.50,
        cost_per_1k_output=10.00,
        max_tokens=4096,
        temperature=0.7,
    ),
    ModelID.CLAUDE_OPUS: ModelSpec(
        model_id=ModelID.CLAUDE_OPUS,
        provider="anthropic",
        model_name="claude-opus-4-6",
        cost_per_1k_input=15.00,
        cost_per_1k_output=75.00,
        max_tokens=4096,
        temperature=0.0,
    ),
}

# Complexity → primary model mapping (cost-optimized)
COMPLEXITY_MODEL_MAP: dict[TaskComplexity, ModelID] = {
    TaskComplexity.TRIVIAL: ModelID.OLLAMA_QWEN,
    TaskComplexity.SIMPLE: ModelID.GPT4O_MINI,
    TaskComplexity.MODERATE: ModelID.GPT4O,
    TaskComplexity.COMPLEX: ModelID.CLAUDE_OPUS,
}

# Fallback chains per model (ordered by preference)
FALLBACK_CHAINS: dict[ModelID, list[ModelID]] = {
    ModelID.OLLAMA_QWEN: [ModelID.GPT4O_MINI, ModelID.GPT4O],
    ModelID.GPT4O_MINI: [ModelID.GPT4O, ModelID.OLLAMA_QWEN],
    ModelID.GPT4O: [ModelID.GPT4O_MINI, ModelID.CLAUDE_OPUS],
    ModelID.CLAUDE_OPUS: [ModelID.GPT4O, ModelID.GPT4O_MINI],
}


class LLMSettings(BaseSettings):
    """Environment-driven LLM settings."""

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11435"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}
