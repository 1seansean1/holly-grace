"""Holly Grace goal hierarchy module.

Implements the seven-level goal hierarchy (L0–L4 Celestial, L5–L6 Terrestrial)
per Goal Hierarchy Formal Spec v0.1.
"""

from __future__ import annotations

from .predicates import (
    CelestialPredicateProtocol,
    CelestialState,
    L0SafetyPredicate,
    L1LegalPredicate,
    L2EthicalPredicate,
    L3PermissionsPredicate,
    L4ConstitutionalPredicate,
    PredicateResult,
    check_celestial_compliance,
    evaluate_celestial_chain,
)

__all__ = [
    "CelestialState",
    "PredicateResult",
    "CelestialPredicateProtocol",
    "L0SafetyPredicate",
    "L1LegalPredicate",
    "L2EthicalPredicate",
    "L3PermissionsPredicate",
    "L4ConstitutionalPredicate",
    "evaluate_celestial_chain",
    "check_celestial_compliance",
]
