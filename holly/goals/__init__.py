"""Holly Grace goal hierarchy module.

Implements the seven-level goal hierarchy (L0–L4 Celestial, L5–L6 Terrestrial)
per Goal Hierarchy Formal Spec v0.1, with T0–T3 task classification and
Assembly Index computation per Assembly Theory.
"""

from __future__ import annotations

from .assembly_index import (
    AssemblyIndexResult,
    AssemblyStep,
    GoalDecomposer,
    classify_complexity,
    compute_assembly_index,
)
from .classification import (
    ClassificationResult,
    TaskClassification,
    TaskClassifier,
    TaskLevel,
)
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
    # Celestial predicates (L0–L4)
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
    # Task classification (T0–T3)
    "TaskLevel",
    "TaskClassification",
    "ClassificationResult",
    "TaskClassifier",
    # Assembly Index (Assembly Theory)
    "AssemblyStep",
    "AssemblyIndexResult",
    "compute_assembly_index",
    "classify_complexity",
    "GoalDecomposer",
]
