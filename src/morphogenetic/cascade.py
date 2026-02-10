"""APS Cascade Engine: 4-tier structured morphogenetic search.

When epsilon-trigger fires, the cascade escalates through tiers ordered
by substrate modification cost (cheapest first):

Tier 0: Parameter tuning (adjust theta within existing configs)
Tier 1: Goal/partition retargeting (switch goal spec, reroute tasks)
Tier 2: Boundary expansion (add tools, modify prompts) — needs approval
Tier 3: Scale reorganization (add/remove agents) — needs approval

Each tier answers a diagnostic question before escalating:
- T0: "Can I reach the basin with better parameters?"
- T1: "Am I targeting the right basin?"
- T2: "Do I need capabilities I don't have?"
- T3: "Is my scale structure correct?"
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.morphogenetic.assembly import (
    CachedCompetency,
    classify_competency,
    compute_assembly_index,
    generate_competency_id,
    generate_context_fingerprint,
    increment_reuse,
    lookup_competency,
    store_competency,
)
from src.morphogenetic.goals import GoalSpec
from src.morphogenetic.trigger import TriggerResult

logger = logging.getLogger(__name__)

# Cascade limits — defaults, overridable via cascade_config table
_MAX_TIER0_ATTEMPTS_DEFAULT = 3
_MAX_TIER1_ATTEMPTS_DEFAULT = 2
_CASCADE_TIMEOUT_SECONDS_DEFAULT = 60


def _get_cascade_config() -> dict:
    """Load cascade parameters from DB cascade_config."""
    try:
        from src.aps.store import get_cascade_config
        return get_cascade_config()
    except Exception:
        return {
            "max_tier0_attempts": _MAX_TIER0_ATTEMPTS_DEFAULT,
            "max_tier1_attempts": _MAX_TIER1_ATTEMPTS_DEFAULT,
            "cascade_timeout_seconds": _CASCADE_TIMEOUT_SECONDS_DEFAULT,
            "tier0_enabled": True, "tier1_enabled": True,
            "tier2_enabled": True, "tier3_enabled": True,
            "tier2_auto_approve": False, "tier3_auto_approve": False,
        }


class CascadeResult:
    """Result of a cascade execution."""

    def __init__(self, goal_id: str, channel_id: str):
        self.goal_id = goal_id
        self.channel_id = channel_id
        self.cascade_id = f"casc_{uuid.uuid4().hex[:12]}"
        self.tier_attempted = 0
        self.tier_succeeded: int | None = None
        self.outcome = "pending"  # success/failure/escalated/approval_pending
        self.adaptation: dict[str, Any] = {}
        self.competency_id: str | None = None
        self.diagnostics: list[dict] = []

    def to_dict(self) -> dict:
        return {
            "cascade_id": self.cascade_id,
            "goal_id": self.goal_id,
            "channel_id": self.channel_id,
            "tier_attempted": self.tier_attempted,
            "tier_succeeded": self.tier_succeeded,
            "outcome": self.outcome,
            "adaptation": self.adaptation,
            "competency_id": self.competency_id,
            "diagnostics": self.diagnostics,
        }


class MorphogeneticCascade:
    """Executes the 4-tier APS cascade for a triggered goal."""

    def execute(
        self,
        trigger: TriggerResult,
        goal: GoalSpec,
        metrics: dict[str, Any],
    ) -> CascadeResult:
        """Execute the morphogenetic cascade for a triggered goal.

        Tries each tier in order, caching on success, escalating on failure.
        """
        result = CascadeResult(trigger.goal_id, trigger.channel_id)
        start_tier = trigger.recommended_tier

        # Check hierarchy gate — if a higher-level constraint is violated,
        # do not escalate the cascade (Tier 2+ can change things that matter)
        try:
            from src.hierarchy.engine import evaluate_gate
            from src.hierarchy.store import get_all_predicates
            preds = get_all_predicates()
            if preds:
                gate = evaluate_gate(preds)
                # Gate level 5 must be open for profit/readiness cascades
                gate5 = gate.get(5)
                if gate5 and not gate5.is_open:
                    logger.warning(
                        "Hierarchy gate closed at L5 (failing: %s), blocking cascade for %s",
                        gate5.failing_predicates, trigger.goal_id,
                    )
                    result.outcome = "gate_blocked"
                    result.diagnostics.append({
                        "tier": -1,
                        "question": "Is the hierarchy gate open?",
                        "answer": f"NO — L5 gate closed, failing predicates: {gate5.failing_predicates}",
                    })
                    self._log_event(result, trigger)
                    return result
        except Exception:
            logger.debug("Hierarchy gate check unavailable, proceeding with cascade")

        # First check assembly cache for a known solution
        ctx_fp = generate_context_fingerprint(trigger.channel_id, metrics)
        cached = lookup_competency(trigger.channel_id, ctx_fp)
        if cached:
            logger.info(
                "Assembly cache hit: competency=%s type=%s reuse=%d",
                cached.competency_id, cached.competency_type, cached.reuse_count,
            )
            # Apply cached competency
            success = self._apply_cached(cached, trigger.channel_id)
            increment_reuse(cached.competency_id, success)
            if success:
                result.outcome = "cache_hit"
                result.competency_id = cached.competency_id
                result.adaptation = cached.adaptation
                result.tier_succeeded = cached.tier
                self._log_event(result, trigger)
                return result

        # Load cascade config (tier enable flags, limits)
        cfg = _get_cascade_config()
        tier_enabled = {
            0: cfg.get("tier0_enabled", True),
            1: cfg.get("tier1_enabled", True),
            2: cfg.get("tier2_enabled", True),
            3: cfg.get("tier3_enabled", True),
        }

        # Execute cascade starting from recommended tier
        for tier in range(start_tier, 4):
            if not tier_enabled.get(tier, True):
                logger.info("Tier %d disabled by config, skipping", tier)
                continue

            result.tier_attempted = tier
            diagnostic = self._diagnostic_question(tier, trigger, metrics)
            result.diagnostics.append(diagnostic)

            if tier == 0:
                success = self._tier0_parameter_tune(trigger, metrics, result)
            elif tier == 1:
                success = self._tier1_goal_retarget(trigger, goal, metrics, result)
            elif tier == 2:
                success = self._tier2_boundary_expand(trigger, goal, metrics, result, cfg)
            elif tier == 3:
                success = self._tier3_scale_reorganize(trigger, goal, metrics, result, cfg)
            else:
                success = False

            if success:
                result.tier_succeeded = tier
                result.outcome = "success"
                # Cache the successful adaptation
                self._cache_success(result, trigger, metrics)
                self._log_event(result, trigger)
                return result

            logger.info(
                "Tier %d failed for goal=%s channel=%s, escalating...",
                tier, trigger.goal_id, trigger.channel_id,
            )

        # All tiers exhausted
        result.outcome = "failure"
        self._log_event(result, trigger)
        return result

    # ------------------------------------------------------------------
    # Diagnostic questions (structured reasoning before escalation)
    # ------------------------------------------------------------------

    def _diagnostic_question(
        self, tier: int, trigger: TriggerResult, metrics: dict
    ) -> dict:
        """Generate diagnostic question for a tier."""
        questions = {
            0: "Can I reach the basin with better parameters?",
            1: "Am I targeting the right basin? Is my G^1 well-specified?",
            2: "Do I need capabilities I don't have?",
            3: "Is my scale structure correct for this problem?",
        }
        return {
            "tier": tier,
            "question": questions.get(tier, "Unknown tier"),
            "channel_id": trigger.channel_id,
            "p_fail": trigger.p_fail,
            "p_fail_ucb": trigger.p_fail_ucb,
            "epsilon_g": trigger.epsilon_g,
        }

    # ------------------------------------------------------------------
    # Tier 0: Parameter tuning
    # ------------------------------------------------------------------

    def _tier0_parameter_tune(
        self, trigger: TriggerResult, metrics: dict, result: CascadeResult
    ) -> bool:
        """Tier 0: adjust theta within existing configuration space.

        Delegates to the existing APS controller escalation logic.
        This is the cheapest tier — no structural modification.
        """
        try:
            from src.aps.theta import get_active_theta, get_theta_by_channel_and_level, set_active_theta

            current = get_active_theta(trigger.channel_id)
            current_level = current.level if hasattr(current, "level") else 0

            # Try escalating one level
            target_level = min(current_level + 1, 2)
            if target_level == current_level:
                return False  # Already at max level

            target_theta = get_theta_by_channel_and_level(trigger.channel_id, target_level)
            if target_theta is None:
                return False

            set_active_theta(trigger.channel_id, target_theta.theta_id)

            result.adaptation = {
                "type": "theta_switch",
                "from_theta": current.theta_id,
                "to_theta": target_theta.theta_id,
                "from_level": current_level,
                "to_level": target_level,
                "direction": "escalated",
                "model_changed": getattr(current, "model_id", "") != getattr(target_theta, "model_id", ""),
            }

            logger.info(
                "Tier 0 success: %s → %s (level %d → %d)",
                current.theta_id, target_theta.theta_id, current_level, target_level,
            )
            return True

        except Exception as e:
            logger.warning("Tier 0 failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Tier 1: Goal/partition retargeting
    # ------------------------------------------------------------------

    def _tier1_goal_retarget(
        self, trigger: TriggerResult, goal: GoalSpec, metrics: dict, result: CascadeResult
    ) -> bool:
        """Tier 1: change which basin is targeted / repartition.

        Options:
        - Switch partition from fine to coarse (or vice versa)
        - Adjust the goal's observation window
        """
        try:
            from src.aps.partitions import get_active_partition, set_active_partition

            current_partition = get_active_partition(trigger.channel_id)
            if current_partition is None:
                return False

            current_granularity = getattr(current_partition, "granularity", "fine")

            # If currently fine, try coarse (simpler classification = fewer errors)
            # If currently coarse, try fine (more precise routing)
            if current_granularity == "fine":
                target_granularity = "coarse"
            else:
                target_granularity = "fine"

            # Look for the alternate partition
            from src.aps.partitions import _PARTITIONS
            target_key = f"{trigger.channel_id}_{target_granularity}"
            if target_key not in _PARTITIONS:
                return False

            set_active_partition(trigger.channel_id, target_key)

            result.adaptation = {
                "type": "partition_switch",
                "from_partition": f"{trigger.channel_id}_{current_granularity}",
                "to_partition": target_key,
                "from_granularity": current_granularity,
                "to_granularity": target_granularity,
            }

            logger.info(
                "Tier 1 success: partition %s → %s",
                current_granularity, target_granularity,
            )
            return True

        except Exception as e:
            logger.warning("Tier 1 failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Tier 2: Boundary expansion (requires approval)
    # ------------------------------------------------------------------

    def _tier2_boundary_expand(
        self, trigger: TriggerResult, goal: GoalSpec, metrics: dict,
        result: CascadeResult, cfg: dict | None = None,
    ) -> bool:
        """Tier 2: expand the agent's sensing/acting interface.

        Requires human approval unless auto-approve is enabled in cascade config.
        """
        try:
            # Propose boundary expansion based on the failing channel
            proposal = self._generate_tier2_proposal(trigger, goal, metrics)

            # Check if auto-approve is enabled
            if cfg and cfg.get("tier2_auto_approve", False):
                result.adaptation = {
                    "type": "boundary_expansion_auto_approved",
                    "proposal": proposal,
                }
                logger.info("Tier 2: auto-approved for %s", trigger.channel_id)
                return True

            from src.aps.store import approval_create

            approval_id = approval_create(
                action_type="morphogenetic_tier2",
                agent_id=trigger.channel_id,
                tool_name="cascade_boundary_expand",
                parameters={
                    "cascade_id": result.cascade_id,
                    "goal_id": trigger.goal_id,
                    "channel_id": trigger.channel_id,
                    "proposal": proposal,
                    "trigger": {
                        "p_fail": trigger.p_fail,
                        "ucb": trigger.p_fail_ucb,
                        "epsilon_g": trigger.epsilon_g,
                    },
                },
                risk_level="high",
            )

            # Also create a Tower ticket for the Control Tower inbox
            tower_ticket_id = self._create_tower_ticket(
                result, trigger, goal, proposal,
                ticket_type="morphogenetic_tier2",
                risk_level="high",
            )

            result.adaptation = {
                "type": "boundary_expansion_proposed",
                "approval_id": approval_id,
                "tower_ticket_id": tower_ticket_id,
                "proposal": proposal,
            }
            result.outcome = "approval_pending"

            logger.info(
                "Tier 2: approval requested (approval=%s, tower_ticket=%s) for %s",
                approval_id, tower_ticket_id, trigger.channel_id,
            )
            return False  # Cascade pauses until approval

        except Exception as e:
            logger.warning("Tier 2 failed: %s", e)
            return False

    def _generate_tier2_proposal(
        self, trigger: TriggerResult, goal: GoalSpec, metrics: dict
    ) -> dict:
        """Generate a concrete proposal for boundary expansion."""
        proposals = []

        # Suggest tool additions based on channel type
        channel_tool_suggestions = {
            "K1": ["expanded_routing_model"],
            "K2": ["additional_content_templates"],
            "K3": ["order_validation_tool", "inventory_forecasting"],
            "K4": ["advanced_analytics", "price_optimization"],
            "K7": ["retry_with_different_provider"],
        }

        suggestions = channel_tool_suggestions.get(trigger.channel_id, [])
        if suggestions:
            proposals.append({
                "action": "add_tools",
                "tools": suggestions,
                "rationale": f"Channel {trigger.channel_id} failing at p_fail={trigger.p_fail:.3f}",
            })

        # Suggest prompt enrichment
        proposals.append({
            "action": "enrich_prompt",
            "rationale": f"Add domain knowledge to reduce errors on {goal.display_name}",
        })

        return {"proposals": proposals}

    # ------------------------------------------------------------------
    # Tier 3: Scale reorganization (requires approval)
    # ------------------------------------------------------------------

    def _tier3_scale_reorganize(
        self, trigger: TriggerResult, goal: GoalSpec, metrics: dict,
        result: CascadeResult, cfg: dict | None = None,
    ) -> bool:
        """Tier 3: reorganize the agent's scale structure.

        This is the most expensive tier — it may add/remove agents
        or restructure the graph topology. Requires approval unless auto-approve enabled.
        """
        try:
            proposal = {
                "action": "scale_reorganization",
                "rationale": (
                    f"All lower tiers exhausted for {goal.display_name}. "
                    f"Channel {trigger.channel_id} at p_fail={trigger.p_fail:.3f} "
                    f"(epsilon={trigger.epsilon_g:.3f}). "
                    "Consider adding specialized sub-agent or restructuring routing."
                ),
                "suggestions": [
                    f"Add specialized sub-agent for {trigger.channel_id} failure cases",
                    "Restructure routing to separate failing task subtypes",
                    "Add new compositional level for complex multi-step tasks",
                ],
            }

            # Check if auto-approve is enabled
            if cfg and cfg.get("tier3_auto_approve", False):
                result.adaptation = {
                    "type": "scale_reorganization_auto_approved",
                    "proposal": proposal,
                }
                logger.info("Tier 3: auto-approved for %s", trigger.channel_id)
                return True

            from src.aps.store import approval_create

            approval_id = approval_create(
                action_type="morphogenetic_tier3",
                agent_id=trigger.channel_id,
                tool_name="cascade_scale_reorganize",
                parameters={
                    "cascade_id": result.cascade_id,
                    "goal_id": trigger.goal_id,
                    "channel_id": trigger.channel_id,
                    "proposal": proposal,
                    "trigger": {
                        "p_fail": trigger.p_fail,
                        "ucb": trigger.p_fail_ucb,
                        "epsilon_g": trigger.epsilon_g,
                    },
                },
                risk_level="high",
            )

            # Also create a Tower ticket for the Control Tower inbox
            tower_ticket_id = self._create_tower_ticket(
                result, trigger, goal, proposal,
                ticket_type="morphogenetic_tier3",
                risk_level="high",
            )

            result.adaptation = {
                "type": "scale_reorganization_proposed",
                "approval_id": approval_id,
                "tower_ticket_id": tower_ticket_id,
                "proposal": proposal,
            }
            result.outcome = "approval_pending"

            logger.info(
                "Tier 3: approval requested (approval=%s, tower_ticket=%s) for %s",
                approval_id, tower_ticket_id, trigger.channel_id,
            )
            return False

        except Exception as e:
            logger.warning("Tier 3 failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Assembly caching
    # ------------------------------------------------------------------

    def _apply_cached(self, cached: CachedCompetency, channel_id: str) -> bool:
        """Apply a cached competency."""
        try:
            adaptation = cached.adaptation
            if adaptation.get("type") == "theta_switch":
                from src.aps.theta import set_active_theta
                set_active_theta(channel_id, adaptation["to_theta"])
                return True

            if adaptation.get("type") == "partition_switch":
                from src.aps.partitions import set_active_partition
                set_active_partition(channel_id, adaptation["to_partition"])
                return True

            logger.info("Cached competency type %s not auto-applicable", adaptation.get("type"))
            return False

        except Exception as e:
            logger.warning("Failed to apply cached competency: %s", e)
            return False

    def _cache_success(
        self, result: CascadeResult, trigger: TriggerResult, metrics: dict
    ) -> None:
        """Cache a successful cascade adaptation as a reusable competency."""
        tier = result.tier_succeeded
        if tier is None:
            return

        comp_type = classify_competency(tier, result.adaptation)
        comp_id = generate_competency_id(
            trigger.channel_id, trigger.goal_id, result.adaptation
        )
        ai = compute_assembly_index(result.adaptation, tier)
        ctx_fp = generate_context_fingerprint(trigger.channel_id, metrics)

        comp = CachedCompetency(
            competency_id=comp_id,
            tier=tier,
            competency_type=comp_type,
            channel_id=trigger.channel_id,
            goal_id=trigger.goal_id,
            adaptation=result.adaptation,
            context_fingerprint=ctx_fp,
            assembly_index=ai,
        )

        store_competency(comp)
        result.competency_id = comp_id

        logger.info(
            "Cached competency: id=%s type=%s tier=%d AI=%.1f",
            comp_id, comp_type, tier, ai,
        )

    def _create_tower_ticket(
        self,
        result: CascadeResult,
        trigger: TriggerResult,
        goal: GoalSpec,
        proposal: dict,
        *,
        ticket_type: str = "morphogenetic",
        risk_level: str = "high",
    ) -> int | None:
        """Create a Tower ticket for cascade approvals.

        This puts the cascade proposal into the Control Tower inbox
        alongside tool-call tickets, giving operators a unified view.
        """
        try:
            from src.tower.store import create_ticket

            return create_ticket(
                run_id=result.cascade_id,  # Use cascade_id as pseudo-run
                ticket_type=ticket_type,
                risk_level=risk_level,
                proposed_action=proposal,
                context_pack={
                    "tldr": f"Cascade {ticket_type.split('_')[-1]}: {goal.display_name}",
                    "why_stopped": (
                        f"Channel {trigger.channel_id} failing at p_fail={trigger.p_fail:.3f} "
                        f"(threshold ε={trigger.epsilon_g:.3f}). "
                        f"Cascade reached {ticket_type} needing approval."
                    ),
                    "impact": f"Will modify agent boundary/structure for {trigger.channel_id}",
                    "risk_flags": [
                        f"p_fail:{trigger.p_fail:.3f}",
                        f"goal:{trigger.goal_id}",
                        f"channel:{trigger.channel_id}",
                    ],
                    "options": {"approve": True, "reject": True},
                },
            )
        except Exception as e:
            logger.warning("Failed to create Tower ticket for cascade: %s", e)
            return None

    def _log_event(self, result: CascadeResult, trigger: TriggerResult) -> None:
        """Log cascade event to database."""
        from src.aps.store import store_cascade_event

        store_cascade_event({
            "cascade_id": result.cascade_id,
            "goal_id": trigger.goal_id,
            "channel_id": trigger.channel_id,
            "trigger_p_fail": trigger.p_fail,
            "trigger_ucb": trigger.p_fail_ucb,
            "trigger_epsilon": trigger.epsilon_g,
            "tier_attempted": result.tier_attempted,
            "tier_succeeded": result.tier_succeeded,
            "diagnostic": result.diagnostics,
            "adaptation": result.adaptation,
            "competency_id": result.competency_id,
            "outcome": result.outcome,
        })

        # Publish to message bus (fire-and-forget)
        from src.bus import STREAM_SYSTEM_HEALTH, publish
        publish(STREAM_SYSTEM_HEALTH, "cascade.completed", {
            "cascade_id": result.cascade_id,
            "goal_id": trigger.goal_id,
            "channel_id": trigger.channel_id,
            "outcome": result.outcome,
            "tier_succeeded": result.tier_succeeded,
        }, source="morphogenetic.cascade")


# Module-level singleton
_cascade = MorphogeneticCascade()


def get_cascade() -> MorphogeneticCascade:
    return _cascade
