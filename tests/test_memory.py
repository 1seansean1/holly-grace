"""Tests for the 3-tier memory architecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.memory.short_term import format_context_window, get_recent_messages
from src.memory.long_term import COLLECTIONS


class TestShortTermMemory:
    def test_get_recent_messages_windowing(self):
        messages = [HumanMessage(content=f"msg {i}") for i in range(20)]
        state = {"messages": messages}
        recent = get_recent_messages(state, k=5)
        assert len(recent) == 5
        assert recent[0].content == "msg 15"

    def test_get_recent_messages_fewer_than_k(self):
        messages = [HumanMessage(content="only one")]
        state = {"messages": messages}
        recent = get_recent_messages(state, k=10)
        assert len(recent) == 1

    def test_format_context_window(self):
        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="hi there"),
        ]
        state = {"messages": messages}
        formatted = format_context_window(state, k=10)
        assert "[Human]:" in formatted
        assert "[AI]:" in formatted


class TestMediumTermMemory:
    @patch("src.memory.medium_term._get_redis")
    def test_store_and_get_session(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = '{"step": 1}'

        from src.memory.medium_term import store_session, get_session

        store_session("content_post", "camp_123", {"step": 1})
        mock_redis.setex.assert_called_once()

        result = get_session("content_post", "camp_123")
        assert result == {"step": 1}

    @patch("src.memory.medium_term._get_redis")
    def test_delete_session(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.delete.return_value = 1

        from src.memory.medium_term import delete_session

        assert delete_session("content_post", "camp_123") is True


class TestLongTermMemory:
    def test_collections_defined(self):
        assert len(COLLECTIONS) == 4
        assert "campaign_results" in COLLECTIONS
        assert "pricing_decisions" in COLLECTIONS
        assert "product_performance" in COLLECTIONS
        assert "agent_lessons" in COLLECTIONS
