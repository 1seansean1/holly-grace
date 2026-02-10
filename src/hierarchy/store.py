"""CRUD operations for goal hierarchy tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    FeasibilityResult,
    GateStatus,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyOrchestrator,
    HierarchyPredicate,
    TerrestrialModule,
)

logger = logging.getLogger(__name__)


def _get_conn():
    """Reuse the APS connection helper."""
    from src.aps.store import _get_conn as aps_conn
    return aps_conn()


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def upsert_predicate(p: HierarchyPredicate) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_predicates
            (index, name, level, block, pass_condition, variance, epsilon_dmg,
             agent_id, module_id, current_value, last_observed)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (index) DO UPDATE SET
                name=EXCLUDED.name, level=EXCLUDED.level, block=EXCLUDED.block,
                pass_condition=EXCLUDED.pass_condition, variance=EXCLUDED.variance,
                epsilon_dmg=EXCLUDED.epsilon_dmg, agent_id=EXCLUDED.agent_id,
                module_id=EXCLUDED.module_id, current_value=EXCLUDED.current_value,
                last_observed=EXCLUDED.last_observed""",
            (p.index, p.name, p.level, p.block, p.pass_condition, p.variance,
             p.epsilon_dmg, p.agent_id, p.module_id, p.current_value, p.last_observed),
        )


def get_predicate(index: int) -> HierarchyPredicate | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hierarchy_predicates WHERE index = %s", (index,)
        ).fetchone()
    if not row:
        return None
    return _row_to_predicate(row)


def get_all_predicates() -> list[HierarchyPredicate]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_predicates ORDER BY index"
        ).fetchall()
    return [_row_to_predicate(r) for r in rows]


def get_predicates_by_level(level: int) -> list[HierarchyPredicate]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_predicates WHERE level = %s ORDER BY index",
            (level,),
        ).fetchall()
    return [_row_to_predicate(r) for r in rows]


def get_predicates_by_block(block: str) -> list[HierarchyPredicate]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_predicates WHERE block = %s ORDER BY index",
            (block,),
        ).fetchall()
    return [_row_to_predicate(r) for r in rows]


def update_predicate_observation(index: int, value: float, source: str = "manual",
                                  metadata: dict | None = None) -> None:
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE hierarchy_predicates SET current_value=%s, last_observed=%s WHERE index=%s",
            (value, now, index),
        )
        conn.execute(
            """INSERT INTO hierarchy_observations (predicate_index, value, source, metadata, created_at)
            VALUES (%s,%s,%s,%s,%s)""",
            (index, value, source, json.dumps(metadata or {}), now),
        )


def _row_to_predicate(row) -> HierarchyPredicate:
    return HierarchyPredicate(
        index=row[0], name=row[1], level=row[2], block=row[3],
        pass_condition=row[4], variance=row[5], epsilon_dmg=row[6],
        agent_id=row[7], module_id=row[8], current_value=row[9],
        last_observed=row[10],
    )


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def upsert_block(b: HierarchyBlock) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_blocks
            (block_id, name, level, predicate_indices, rank, module_id)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (block_id) DO UPDATE SET
                name=EXCLUDED.name, level=EXCLUDED.level,
                predicate_indices=EXCLUDED.predicate_indices,
                rank=EXCLUDED.rank, module_id=EXCLUDED.module_id""",
            (b.block_id, b.name, b.level, b.predicate_indices, b.rank, b.module_id),
        )


def get_all_blocks() -> list[HierarchyBlock]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_blocks ORDER BY level, block_id"
        ).fetchall()
    return [HierarchyBlock(
        block_id=r[0], name=r[1], level=r[2],
        predicate_indices=list(r[3]), rank=r[4], module_id=r[5],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Coupling Axes
# ---------------------------------------------------------------------------

def upsert_coupling_axis(a: CouplingAxis) -> None:
    with _get_conn() as conn:
        # Check if exists
        existing = conn.execute(
            "SELECT id FROM hierarchy_coupling_axes WHERE source_idx=%s AND target_idx=%s",
            (a.source_predicate, a.target_predicate),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE hierarchy_coupling_axes
                SET rho=%s, axis_type=%s, channel_id=%s
                WHERE source_idx=%s AND target_idx=%s""",
                (a.rho, a.axis_type, a.channel_id,
                 a.source_predicate, a.target_predicate),
            )
        else:
            conn.execute(
                """INSERT INTO hierarchy_coupling_axes
                (source_idx, target_idx, rho, axis_type, channel_id)
                VALUES (%s,%s,%s,%s,%s)""",
                (a.source_predicate, a.target_predicate, a.rho,
                 a.axis_type, a.channel_id),
            )


def get_all_coupling_axes() -> list[CouplingAxis]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT source_idx, target_idx, rho, axis_type, channel_id "
            "FROM hierarchy_coupling_axes ORDER BY source_idx, target_idx"
        ).fetchall()
    return [CouplingAxis(
        source_predicate=r[0], target_predicate=r[1], rho=r[2],
        axis_type=r[3], channel_id=r[4],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def upsert_agent(a: HierarchyAgent) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_agents
            (agent_id, name, predicates, rank, capacity, sigma_max, layer)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                name=EXCLUDED.name, predicates=EXCLUDED.predicates,
                rank=EXCLUDED.rank, capacity=EXCLUDED.capacity,
                sigma_max=EXCLUDED.sigma_max, layer=EXCLUDED.layer""",
            (a.agent_id, a.name, a.predicates, a.rank, a.capacity,
             a.sigma_max, a.layer),
        )


def get_all_agents() -> list[HierarchyAgent]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_agents ORDER BY agent_id"
        ).fetchall()
    return [HierarchyAgent(
        agent_id=r[0], name=r[1], predicates=list(r[2]), rank=r[3],
        capacity=r[4], sigma_max=r[5], layer=r[6],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------

def upsert_orchestrator(o: HierarchyOrchestrator) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_orchestrators
            (orchestrator_id, name, rank, governed_agents, role)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (orchestrator_id) DO UPDATE SET
                name=EXCLUDED.name, rank=EXCLUDED.rank,
                governed_agents=EXCLUDED.governed_agents, role=EXCLUDED.role""",
            (o.orchestrator_id, o.name, o.rank, o.governed_agents, o.role),
        )


def get_all_orchestrators() -> list[HierarchyOrchestrator]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_orchestrators ORDER BY orchestrator_id"
        ).fetchall()
    return [HierarchyOrchestrator(
        orchestrator_id=r[0], name=r[1], rank=r[2],
        governed_agents=list(r[3]), role=r[4],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Terrestrial Modules
# ---------------------------------------------------------------------------

def upsert_module(m: TerrestrialModule) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO terrestrial_modules
            (module_id, name, level, status, predicate_indices, agent_id, upward_channels)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (module_id) DO UPDATE SET
                name=EXCLUDED.name, level=EXCLUDED.level, status=EXCLUDED.status,
                predicate_indices=EXCLUDED.predicate_indices,
                agent_id=EXCLUDED.agent_id, upward_channels=EXCLUDED.upward_channels""",
            (m.module_id, m.name, m.level, m.status, m.predicate_indices,
             m.agent_id, m.upward_channels),
        )


def get_module(module_id: str) -> TerrestrialModule | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM terrestrial_modules WHERE module_id = %s", (module_id,)
        ).fetchone()
    if not row:
        return None
    return TerrestrialModule(
        module_id=row[0], name=row[1], level=row[2], status=row[3],
        predicate_indices=list(row[4]), agent_id=row[5],
        upward_channels=list(row[6]),
    )


def list_modules() -> list[TerrestrialModule]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM terrestrial_modules ORDER BY level, module_id"
        ).fetchall()
    return [TerrestrialModule(
        module_id=r[0], name=r[1], level=r[2], status=r[3],
        predicate_indices=list(r[4]), agent_id=r[5],
        upward_channels=list(r[6]),
    ) for r in rows]


def delete_module(module_id: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE terrestrial_modules SET status='Inactive' WHERE module_id=%s",
            (module_id,),
        )


# ---------------------------------------------------------------------------
# Eigenvalues
# ---------------------------------------------------------------------------

def upsert_eigenvalue(e: Eigenvalue) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_eigenvalues
            (index, value, dominant_predicates, interpretation, layer)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (index) DO UPDATE SET
                value=EXCLUDED.value, dominant_predicates=EXCLUDED.dominant_predicates,
                interpretation=EXCLUDED.interpretation, layer=EXCLUDED.layer""",
            (e.index, e.value, e.dominant_predicates, e.interpretation, e.layer),
        )


def get_all_eigenvalues() -> list[Eigenvalue]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_eigenvalues ORDER BY index"
        ).fetchall()
    return [Eigenvalue(
        index=r[0], value=r[1], dominant_predicates=list(r[2]),
        interpretation=r[3], layer=r[4],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Feasibility Log
# ---------------------------------------------------------------------------

def log_feasibility(result: FeasibilityResult) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_feasibility_log
            (rank_coverage, coupling_coverage, epsilon_check, overall, details)
            VALUES (%s,%s,%s,%s,%s)""",
            (result.rank_coverage, result.coupling_coverage, result.epsilon_check,
             result.overall, json.dumps(result.details)),
        )


def get_latest_feasibility() -> FeasibilityResult | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM hierarchy_feasibility_log ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return FeasibilityResult(
        timestamp=row[1], rank_coverage=row[2], coupling_coverage=row[3],
        epsilon_check=row[4], overall=row[5],
        details=row[6] if isinstance(row[6], dict) else json.loads(row[6]),
    )


# ---------------------------------------------------------------------------
# Gate Status
# ---------------------------------------------------------------------------

def update_gate_status(gs: GateStatus) -> None:
    now = datetime.now(timezone.utc)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO hierarchy_gate_status (level, is_open, failing_predicates, updated_at)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (level) DO UPDATE SET
                is_open=EXCLUDED.is_open, failing_predicates=EXCLUDED.failing_predicates,
                updated_at=EXCLUDED.updated_at""",
            (gs.level, gs.is_open, gs.failing_predicates, now),
        )


def get_gate_status(level: int | None = None) -> list[GateStatus]:
    with _get_conn() as conn:
        if level is not None:
            rows = conn.execute(
                "SELECT * FROM hierarchy_gate_status WHERE level=%s", (level,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hierarchy_gate_status ORDER BY level"
            ).fetchall()
    return [GateStatus(
        level=r[0], is_open=r[1], failing_predicates=list(r[2]),
        timestamp=r[3],
    ) for r in rows]


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def get_observations(predicate_index: int, limit: int = 50) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM hierarchy_observations WHERE predicate_index=%s "
            "ORDER BY created_at DESC LIMIT %s",
            (predicate_index, limit),
        ).fetchall()
    return [
        {"id": r[0], "predicate_index": r[1], "value": r[2], "source": r[3],
         "metadata": r[4] if isinstance(r[4], dict) else json.loads(r[4]),
         "created_at": r[5].isoformat() if r[5] else None}
        for r in rows
    ]
