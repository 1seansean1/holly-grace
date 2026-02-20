"""Integration tests for Phase D → Phase E transition chain.

Tests the complete flow of:
- Building the phase chain
- Validating chain structure
- Verifying D→E readiness
- Full transition workflow
"""

from __future__ import annotations

import pytest

from holly.safety.phase_transition import (
    GoalChainValidator,
    PhaseGoal,
    PhaseGoalChain,
    PhaseTransitionVerifier,
    build_phase_d_e_chain,
)


class TestPhaseDBoundary:
    """Integration tests for Phase D boundary."""

    def test_phase_d_complete_workflow(self) -> None:
        """Test complete Phase D satisfaction workflow."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        # Initially all Phase D goals unsatisfied
        all_met, unsatisfied = verifier.check_d_goals_met()
        assert not all_met
        assert len(unsatisfied) == 4

        # Satisfy D.G1
        verifier.mark_goal_satisfied("D.G1")
        all_met, unsatisfied = verifier.check_d_goals_met()
        assert not all_met
        assert len(unsatisfied) == 3

        # Satisfy remaining Phase D goals
        for goal_id in ["D.G2", "D.G3", "D.G4"]:
            verifier.mark_goal_satisfied(goal_id)

        # Now all Phase D goals satisfied
        all_met, unsatisfied = verifier.check_d_goals_met()
        assert all_met
        assert len(unsatisfied) == 0

    def test_phase_d_gates_all_postconditions(self) -> None:
        """Test that Phase D gates provide all required postconditions."""
        chain = build_phase_d_e_chain()

        # Collect all Phase D postconditions
        d_postconditions = set()
        for goal in chain.goals_by_phase("D"):
            d_postconditions.update(goal.postconditions)

        # These should include key outputs
        expected_outputs = {
            "redaction_deployed",
            "guardrails_deployed",
            "governance_deployed",
            "secret_scanner_deployed",
            "egress_deployed",
            "icd_coverage_100",
            "safety_argument_complete",
            "gate_passed",
            "sil2_verified",
            "phase_d_complete",
        }

        # All expected outputs should be in postconditions
        assert expected_outputs.issubset(d_postconditions)


class TestPhaseEPrerequisites:
    """Integration tests for Phase E prerequisites."""

    def test_phase_e_prereqs_match_d_outputs(self) -> None:
        """Test that Phase E preconditions match Phase D postconditions."""
        chain = build_phase_d_e_chain()

        # Collect Phase D postconditions
        d_postconditions = set()
        for goal in chain.goals_by_phase("D"):
            d_postconditions.update(goal.postconditions)

        # Check Phase E preconditions
        for e_goal in chain.goals_by_phase("E"):
            for precond in e_goal.preconditions:
                # Each precondition should be satisfied by D
                assert precond in d_postconditions or any(
                    precond in other_goal.postconditions
                    for other_goal in chain.goals_by_phase("E")
                )

    def test_phase_e_deployment_ready_preconditions(self) -> None:
        """Test that E.G1 preconditions are met by D.G4."""
        chain = build_phase_d_e_chain()

        e_g1 = chain.get_goal("E.G1")
        d_g4 = chain.get_goal("D.G4")

        assert e_g1 is not None
        assert d_g4 is not None

        # E.G1 should depend on D.G4 postconditions
        e_g1_pres = set(e_g1.preconditions)
        d_g4_posts = set(d_g4.postconditions)

        # All E.G1 preconditions should come from D.G4 or prior D goals
        for precond in e_g1_pres:
            is_available = precond in d_g4_posts or any(
                precond in goal.postconditions
                for goal in chain.goals_by_phase("D")
            )
            assert is_available, f"E.G1 precondition {precond} not available from Phase D"


class TestTransitionReadiness:
    """Integration tests for transition readiness verification."""

    def test_transition_blocked_until_d_complete(self) -> None:
        """Test that transition is blocked until Phase D is complete."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        # Transition should be blocked initially
        report = verifier.verify_transition()
        assert not report.ready
        assert len(report.blockers) > 0

        # Add D.G1
        verifier.mark_goal_satisfied("D.G1")
        report = verifier.verify_transition()
        assert not report.ready

        # Add D.G2, D.G3, D.G4
        for goal_id in ["D.G2", "D.G3", "D.G4"]:
            verifier.mark_goal_satisfied(goal_id)

        # Now should be NOT ready (still need E.G1)
        report = verifier.verify_transition()
        assert not report.ready

        # Mark E.G1 as satisfied
        verifier.mark_goal_satisfied("E.G1")

        # Now should be ready
        report = verifier.verify_transition()
        assert report.ready
        assert len(report.blockers) == 0

    def test_transition_report_completion_tracking(self) -> None:
        """Test that transition report tracks completion."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        # Partial completion
        verifier.mark_goal_satisfied("D.G1")
        verifier.mark_goal_satisfied("D.G2")
        report = verifier.verify_transition()

        total_goals = len(chain.goals_by_phase("D")) + len(
            chain.goals_by_phase("E")
        )
        assert report.completion_percentage == 2 / total_goals

    def test_transition_report_blocker_detail(self) -> None:
        """Test that transition report details blockers."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        report = verifier.verify_transition()
        assert not report.ready

        # Should have detailed blockers
        assert any("Phase D" in b for b in report.blockers)

    def test_sil_level_in_report(self) -> None:
        """Test that transition report includes SIL level info."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        # Mark some Phase D goals as satisfied
        verifier.mark_goal_satisfied("D.G1")
        verifier.mark_goal_satisfied("D.G2")

        report = verifier.verify_transition()
        assert report.sil_min >= 2  # Should be at least SIL-2


class TestGoalChainConsistency:
    """Integration tests for goal chain consistency."""

    def test_no_cycles_in_phase_chain(self) -> None:
        """Test that the Phase D→E chain has no cycles."""
        chain = build_phase_d_e_chain()
        validator = GoalChainValidator(chain)

        is_valid, errors = validator.validate()
        assert is_valid, f"Chain has errors: {errors}"

        # Specifically check for cycles
        cycle_errors = [e for e in errors if "Cycle" in e]
        assert len(cycle_errors) == 0

    def test_all_goals_in_chain(self) -> None:
        """Test that all goals are reachable in the chain."""
        chain = build_phase_d_e_chain()
        validator = GoalChainValidator(chain)

        is_valid, errors = validator.validate()
        assert is_valid, f"Chain has errors: {errors}"

        # Check no orphaned goals
        orphan_errors = [e for e in errors if "Orphaned" in e]
        assert len(orphan_errors) == 0

    def test_sil_levels_consistent_across_boundary(self) -> None:
        """Test that SIL levels are consistent across phase boundary."""
        chain = build_phase_d_e_chain()

        d_goals = chain.goals_by_phase("D")
        e_goals = chain.goals_by_phase("E")

        # All should be SIL-2 or higher
        for goal in d_goals + e_goals:
            assert goal.sil_level >= 2


class TestCriticalPathTracing:
    """Integration tests for critical path tracing through goals."""

    def test_d_g1_to_d_g4_path(self) -> None:
        """Test the critical path D.G1 → D.G2 → D.G3 → D.G4."""
        chain = build_phase_d_e_chain()

        # Trace from D.G1
        current = "D.G1"
        visited = []

        while current:
            visited.append(current)
            if current not in chain.transitions:
                break
            current = chain.transitions[current]

        # Should traverse Phase D goals
        phase_d_visited = [g for g in visited if g.startswith("D")]
        assert len(phase_d_visited) >= 4

    def test_phase_boundary_crossing(self) -> None:
        """Test transition from Phase D to Phase E."""
        chain = build_phase_d_e_chain()

        # Find the transition from Phase D to Phase E
        d_to_e_transitions = []
        for from_id, to_id in chain.transitions.items():
            from_goal = chain.get_goal(from_id)
            to_goal = chain.get_goal(to_id)

            if from_goal and to_goal:
                if from_goal.phase == "D" and to_goal.phase == "E":
                    d_to_e_transitions.append((from_id, to_id))

        # Should have at least one D→E transition
        assert len(d_to_e_transitions) > 0


class TestFullTransitionScenario:
    """End-to-end test of complete D→E transition."""

    def test_complete_phase_d_to_e_transition(self) -> None:
        """Test complete workflow from Phase D start to E readiness."""
        # Build chain
        chain = build_phase_d_e_chain()

        # Validate structure
        validator = GoalChainValidator(chain)
        is_valid, errors = validator.validate()
        assert is_valid, f"Chain validation failed: {errors}"

        # Create verifier
        verifier = PhaseTransitionVerifier(chain)

        # Phase 1: Verify D is not complete
        all_met, unsatisfied = verifier.check_d_goals_met()
        assert not all_met

        # Phase 2: Satisfy all Phase D goals in sequence
        d_goals = chain.goals_by_phase("D")
        for goal in d_goals:
            verifier.mark_goal_satisfied(goal.goal_id)

        # Phase 3: Verify D is complete
        all_met, unsatisfied = verifier.check_d_goals_met()
        assert all_met

        # Phase 4: Check E prerequisites
        e_ready, missing = verifier.check_e_prerequisites()
        assert not e_ready  # E.G1 not yet satisfied

        # Phase 5: Mark E.G1 satisfied
        verifier.mark_goal_satisfied("E.G1")
        e_ready, missing = verifier.check_e_prerequisites()
        assert e_ready

        # Phase 6: Get final transition report
        report = verifier.verify_transition()
        assert report.ready
        assert report.phase_from == "D"
        assert report.phase_to == "E"
        assert len(report.blockers) == 0

    def test_transition_progression_metrics(self) -> None:
        """Test metrics throughout transition progression."""
        chain = build_phase_d_e_chain()
        verifier = PhaseTransitionVerifier(chain)

        total_d_goals = len(chain.goals_by_phase("D"))
        total_e_goals = len(chain.goals_by_phase("E"))

        # Check at each stage
        reports_by_stage = []

        for i, goal in enumerate(chain.goals_by_phase("D")):
            verifier.mark_goal_satisfied(goal.goal_id)
            report = verifier.verify_transition()
            reports_by_stage.append(report)

            # Completion should increase monotonically
            total_goals = total_d_goals + total_e_goals
            expected_pct = (i + 1) / total_goals
            assert report.completion_percentage >= (i / total_goals)

        # Add E.G1
        verifier.mark_goal_satisfied("E.G1")
        final_report = verifier.verify_transition()
        assert final_report.ready
