"""Tests for revenue generation seed objectives (Phase 5).

Verifies:
- seed_revenue_objectives() submits 9 tasks to the autonomy queue
- Idempotency via Redis flag (REVENUE_SEED_FLAG)
- Task content and priorities are correct
- Flag is set after successful seeding
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


class TestRevenueObjectives(unittest.TestCase):
    """Test the REVENUE_OBJECTIVES constant."""

    def test_objective_count(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        self.assertEqual(len(REVENUE_OBJECTIVES), 9)

    def test_all_have_required_fields(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        for i, obj in enumerate(REVENUE_OBJECTIVES):
            self.assertIn("objective", obj, f"Objective {i} missing 'objective'")
            self.assertIn("priority", obj, f"Objective {i} missing 'priority'")
            self.assertIn("type", obj, f"Objective {i} missing 'type'")

    def test_type_distribution(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        types = [obj["type"] for obj in REVENUE_OBJECTIVES]
        self.assertEqual(types.count("revenue_research"), 8)
        self.assertEqual(types.count("revenue_synthesis"), 1)

    def test_priorities(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        priorities = [obj["priority"] for obj in REVENUE_OBJECTIVES]
        # The Studio is high priority
        self.assertIn("high", priorities)
        # Synthesis is low priority (waits for others)
        self.assertEqual(REVENUE_OBJECTIVES[-1]["priority"], "low")
        # Most are normal
        self.assertEqual(priorities.count("normal"), 7)

    def test_studio_is_high_priority(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        studio = [o for o in REVENUE_OBJECTIVES if "THE STUDIO" in o["objective"]]
        self.assertEqual(len(studio), 1)
        self.assertEqual(studio[0]["priority"], "high")

    def test_synthesis_is_last(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        last = REVENUE_OBJECTIVES[-1]
        self.assertEqual(last["type"], "revenue_synthesis")
        self.assertIn("REVENUE SYNTHESIS", last["objective"])

    def test_all_research_mention_store_findings(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        for obj in REVENUE_OBJECTIVES:
            if obj["type"] == "revenue_research":
                self.assertIn("revenue_research", obj["objective"],
                              f"Research objective should mention storing as 'revenue_research'")

    def test_objective_content_not_empty(self):
        from src.holly.autonomy import REVENUE_OBJECTIVES
        for i, obj in enumerate(REVENUE_OBJECTIVES):
            self.assertGreater(len(obj["objective"]), 100,
                               f"Objective {i} seems too short")


class TestSeedRevenueObjectives(unittest.TestCase):
    """Test the seed_revenue_objectives() function."""

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_seeds_9_objectives_when_flag_not_set(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives, REVENUE_OBJECTIVES

        r = MagicMock()
        r.exists.return_value = 0  # Flag not set
        mock_redis.return_value = r

        seed_revenue_objectives()

        self.assertEqual(mock_submit.call_count, len(REVENUE_OBJECTIVES))

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_skips_when_flag_already_set(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives

        r = MagicMock()
        r.exists.return_value = 1  # Flag already set
        mock_redis.return_value = r

        seed_revenue_objectives()

        mock_submit.assert_not_called()

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_sets_flag_after_seeding(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives, REVENUE_SEED_FLAG

        r = MagicMock()
        r.exists.return_value = 0
        mock_redis.return_value = r

        seed_revenue_objectives()

        # Check flag was set
        r.set.assert_called_once()
        flag_key = r.set.call_args[0][0]
        self.assertEqual(flag_key, REVENUE_SEED_FLAG)

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_passes_correct_priorities(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives

        r = MagicMock()
        r.exists.return_value = 0
        mock_redis.return_value = r

        seed_revenue_objectives()

        # Check that high-priority Studio task was submitted correctly
        calls = mock_submit.call_args_list
        high_calls = [c for c in calls if c.kwargs.get("priority") == "high"
                      or (len(c.args) > 1 and c.args[1] == "high")]
        # At least 1 high priority call (The Studio)
        high_kw = [c for c in calls if c[1].get("priority") == "high"]
        self.assertGreaterEqual(len(high_kw), 1)

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_passes_correct_task_types(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives

        r = MagicMock()
        r.exists.return_value = 0
        mock_redis.return_value = r

        seed_revenue_objectives()

        # Check task types
        types = [c[1].get("task_type") for c in mock_submit.call_args_list]
        self.assertEqual(types.count("revenue_research"), 8)
        self.assertEqual(types.count("revenue_synthesis"), 1)

    @patch("src.holly.autonomy._get_redis")
    @patch("src.holly.autonomy.submit_task")
    def test_skips_on_redis_unavailable(self, mock_submit, mock_redis):
        from src.holly.autonomy import seed_revenue_objectives

        mock_redis.side_effect = Exception("Redis connection refused")

        seed_revenue_objectives()

        mock_submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
