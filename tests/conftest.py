"""Shared test fixtures for ecom-agents."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.llm.config import LLMSettings, ModelID
from src.llm.router import LLMRouter
from src.state import AgentState


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpss_test_fake")
    monkeypatch.setenv("SHOPIFY_SHOP_URL", "test-store.myshopify.com")
    monkeypatch.setenv("SHOPIFY_API_VERSION", "2025-01")
    monkeypatch.setenv("PRINTFUL_API_KEY", "test_fake")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test_fake")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "12345")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11435")
    monkeypatch.setenv("DATABASE_URL", "postgresql://ecom:ecom_dev_password@localhost:5434/ecom_agents")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6381/0")
    monkeypatch.setenv("CHROMA_URL", "http://localhost:8100")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")


@pytest.fixture
def llm_settings():
    """Test LLM settings."""
    return LLMSettings(
        openai_api_key="sk-test-fake",
        anthropic_api_key="sk-ant-test-fake",
        ollama_base_url="http://localhost:11435",
    )


@pytest.fixture
def router(llm_settings):
    """Test LLM router."""
    return LLMRouter(llm_settings)


@pytest.fixture
def sample_state() -> AgentState:
    """A minimal valid AgentState for testing."""
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="Check for new orders")],
        "task_type": "",
        "task_complexity": "",
        "current_agent": "",
        "route_to": "",
        "trigger_source": "test",
        "trigger_payload": {"task": "Check for new orders"},
        "should_spawn_sub_agents": False,
        "sub_agents_spawned": [],
        "memory_context": "",
        "sales_result": {},
        "operations_result": {},
        "revenue_result": {},
        "sub_agent_results": {},
        "error": "",
        "retry_count": 0,
    }


@pytest.fixture
def mock_llm_response():
    """Helper to create a mock LLM response."""

    def _make(content: str):
        mock = MagicMock()
        mock.content = content
        return mock

    return _make
