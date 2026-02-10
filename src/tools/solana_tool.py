"""Solana mining tools — read-only queries for profitability and validator health.

Three tools:
1. solana_check_profitability — ROI calculation from RPC + env vars
2. solana_validator_health — Validator uptime / skip rate / delinquency
3. solana_mining_report — Combined report with hierarchy gate status
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
_ELECTRICITY_RATE = float(os.getenv("SOL_ELECTRICITY_RATE_KWH", "0.12"))
_DEPRECIATION = float(os.getenv("SOL_HARDWARE_DEPRECIATION_MONTHLY", "150.00"))
_VALIDATOR_IDENTITY = os.getenv("SOLANA_VALIDATOR_IDENTITY", "")
_WALLET_ADDRESS = os.getenv("SOLANA_WALLET_ADDRESS", "")

_TIMEOUT = 10.0


def _rpc_call(method: str, params: list | None = None) -> dict | None:
    """Make a Solana JSON-RPC call. Returns result or None on failure."""
    try:
        resp = httpx.post(
            _RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            timeout=_TIMEOUT,
        )
        data = resp.json()
        if "error" in data:
            logger.warning("Solana RPC error (%s): %s", method, data["error"])
            return None
        return data.get("result")
    except Exception as e:
        logger.warning("Solana RPC unavailable (%s): %s", method, e)
        return None


def _get_sol_price() -> float | None:
    """Fetch current SOL/USD price from a public API."""
    try:
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "usd"},
            timeout=_TIMEOUT,
        )
        return resp.json().get("solana", {}).get("usd")
    except Exception:
        return None


@tool
def solana_check_profitability() -> str:
    """Check Solana mining/staking profitability.

    Calculates net ROI based on:
    - Current SOL price (from CoinGecko)
    - Estimated staking APY (from epoch info)
    - Electricity cost (from env: SOL_ELECTRICITY_RATE_KWH)
    - Hardware depreciation (from env: SOL_HARDWARE_DEPRECIATION_MONTHLY)

    Returns a JSON report with profitability metrics.
    """
    now = datetime.now(timezone.utc).isoformat()
    sol_price = _get_sol_price()

    # Get epoch info for staking estimate
    epoch_info = _rpc_call("getEpochInfo")
    supply_info = _rpc_call("getSupply")

    # Estimate staking APY from epoch length (~2-3 days per epoch, ~6-7% APY)
    estimated_apy = 0.068  # Solana average staking APY
    if epoch_info:
        slot_index = epoch_info.get("slotIndex", 0)
        slots_in_epoch = epoch_info.get("slotsInEpoch", 432000)
        epoch_progress = slot_index / slots_in_epoch if slots_in_epoch else 0
    else:
        epoch_progress = 0

    total_supply = None
    circulating_supply = None
    if supply_info:
        total_supply = supply_info.get("value", {}).get("total")
        circulating_supply = supply_info.get("value", {}).get("circulating")

    # Assume 1 validator node running 24/7:
    # ~200W average power draw for a Solana validator
    watts = 200
    hours_per_month = 730
    kwh_per_month = watts * hours_per_month / 1000
    electricity_cost_monthly = kwh_per_month * _ELECTRICITY_RATE
    total_cost_monthly = electricity_cost_monthly + _DEPRECIATION

    # Staking revenue estimate (assume 1000 SOL staked)
    staked_sol = 1000  # Configurable baseline
    monthly_reward_sol = staked_sol * (estimated_apy / 12)
    monthly_revenue_usd = monthly_reward_sol * (sol_price or 0)

    net_profit_monthly = monthly_revenue_usd - total_cost_monthly
    roi_pct = (net_profit_monthly / total_cost_monthly * 100) if total_cost_monthly else 0

    result = {
        "timestamp": now,
        "sol_price_usd": sol_price,
        "estimated_staking_apy": round(estimated_apy * 100, 2),
        "epoch_progress": round(epoch_progress, 4),
        "total_supply_lamports": total_supply,
        "circulating_supply_lamports": circulating_supply,
        "costs": {
            "electricity_rate_kwh": _ELECTRICITY_RATE,
            "kwh_per_month": round(kwh_per_month, 1),
            "electricity_cost_monthly": round(electricity_cost_monthly, 2),
            "hardware_depreciation_monthly": _DEPRECIATION,
            "total_cost_monthly": round(total_cost_monthly, 2),
        },
        "revenue": {
            "staked_sol": staked_sol,
            "monthly_reward_sol": round(monthly_reward_sol, 4),
            "monthly_revenue_usd": round(monthly_revenue_usd, 2),
        },
        "profitability": {
            "net_profit_monthly_usd": round(net_profit_monthly, 2),
            "roi_percent": round(roi_pct, 2),
            "is_profitable": net_profit_monthly > 0,
        },
    }
    return json.dumps(result, indent=2)


@tool
def solana_validator_health() -> str:
    """Check Solana validator health metrics.

    Queries the Solana RPC for:
    - Validator identity and vote account status
    - Current epoch performance (credits, skip rate)
    - Cluster delinquency status
    - Recent block production stats

    Returns a JSON report with health metrics.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Get vote accounts for validator performance data
    vote_accounts = _rpc_call("getVoteAccounts")
    validator_info = None
    is_delinquent = None

    if vote_accounts and _VALIDATOR_IDENTITY:
        # Search current validators
        for v in vote_accounts.get("current", []):
            if v.get("nodePubkey") == _VALIDATOR_IDENTITY:
                validator_info = v
                is_delinquent = False
                break
        # Search delinquent validators
        if validator_info is None:
            for v in vote_accounts.get("delinquent", []):
                if v.get("nodePubkey") == _VALIDATOR_IDENTITY:
                    validator_info = v
                    is_delinquent = True
                    break

    # Get block production stats
    block_production = None
    if _VALIDATOR_IDENTITY:
        block_production = _rpc_call(
            "getBlockProduction",
            [{"identity": _VALIDATOR_IDENTITY}],
        )

    # Get cluster nodes count
    cluster_nodes = _rpc_call("getClusterNodes")
    node_count = len(cluster_nodes) if cluster_nodes else None

    # Calculate skip rate from block production
    skip_rate = None
    leader_slots = 0
    blocks_produced = 0
    if block_production and block_production.get("value", {}).get("byIdentity"):
        identity_data = block_production["value"]["byIdentity"]
        if _VALIDATOR_IDENTITY in identity_data:
            stats = identity_data[_VALIDATOR_IDENTITY]
            leader_slots = stats[0] if len(stats) > 0 else 0
            blocks_produced = stats[1] if len(stats) > 1 else 0
            if leader_slots > 0:
                skip_rate = round((leader_slots - blocks_produced) / leader_slots * 100, 2)

    # Extract validator-specific metrics
    epoch_credits = None
    activated_stake = None
    commission = None
    if validator_info:
        epoch_credits = validator_info.get("epochCredits", [])
        activated_stake = validator_info.get("activatedStake")
        commission = validator_info.get("commission")

    result = {
        "timestamp": now,
        "validator_identity": _VALIDATOR_IDENTITY or "(not configured)",
        "status": {
            "found": validator_info is not None,
            "is_delinquent": is_delinquent,
            "commission_pct": commission,
            "activated_stake_lamports": activated_stake,
        },
        "performance": {
            "leader_slots": leader_slots,
            "blocks_produced": blocks_produced,
            "skip_rate_pct": skip_rate,
            "recent_epoch_credits": epoch_credits[-3:] if epoch_credits else [],
        },
        "cluster": {
            "total_nodes": node_count,
            "current_validators": len(vote_accounts.get("current", []))
            if vote_accounts
            else None,
            "delinquent_validators": len(vote_accounts.get("delinquent", []))
            if vote_accounts
            else None,
        },
        "health_score": _compute_health_score(
            is_delinquent=is_delinquent,
            skip_rate=skip_rate,
            validator_found=validator_info is not None,
        ),
    }
    return json.dumps(result, indent=2)


def _compute_health_score(
    *,
    is_delinquent: bool | None,
    skip_rate: float | None,
    validator_found: bool,
) -> float:
    """Compute a 0.0–1.0 health score for the validator."""
    if not validator_found:
        return 0.5  # Unknown — validator not configured or not found
    if is_delinquent:
        return 0.1  # Critical — validator is delinquent
    if skip_rate is not None:
        if skip_rate > 20:
            return 0.3
        if skip_rate > 10:
            return 0.6
        if skip_rate > 5:
            return 0.8
    return 1.0  # Healthy


@tool
def solana_mining_report() -> str:
    """Generate a comprehensive Solana mining report.

    Combines:
    - Profitability analysis (from solana_check_profitability)
    - Validator health (from solana_validator_health)
    - Hierarchy gate status (L5 gate open/closed)
    - Hierarchy predicate values for Solana mining predicates (f38-f42)

    Returns a structured JSON report suitable for decision-making.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Get profitability data
    profitability = json.loads(solana_check_profitability.invoke({}))

    # Get validator health
    health = json.loads(solana_validator_health.invoke({}))

    # Get hierarchy gate status
    gate_status = None
    predicate_status = None
    try:
        from src.hierarchy.store import get_gate_status, get_predicates_by_level
        gates = get_gate_status(5)
        if gates:
            gate_status = {
                "level": 5,
                "is_open": gates[0].is_open,
                "failing_predicates": gates[0].failing_predicates,
            }
        # Get L5 predicates for Solana mining module
        l5_preds = get_predicates_by_level(5)
        solana_preds = [p for p in l5_preds if p.module_id == "solana-mining"]
        if solana_preds:
            predicate_status = [
                {
                    "index": p.index,
                    "name": p.name,
                    "current_value": p.current_value,
                    "epsilon_dmg": p.epsilon_dmg,
                    "passing": p.current_value is None
                    or p.current_value >= (1.0 - p.epsilon_dmg),
                }
                for p in solana_preds
            ]
    except Exception:
        gate_status = {"level": 5, "is_open": None, "error": "hierarchy unavailable"}

    # Compute overall recommendation
    is_profitable = profitability.get("profitability", {}).get("is_profitable", False)
    health_score = health.get("health_score", 0.5)
    gate_open = gate_status.get("is_open", True) if gate_status else True

    if not gate_open:
        recommendation = "HALT — Celestial gate closed (moral/ethical constraint violated)"
    elif not is_profitable:
        recommendation = "PAUSE — Mining currently unprofitable, review costs"
    elif health_score < 0.5:
        recommendation = "WARNING — Validator health critical, investigate immediately"
    elif health_score < 0.8:
        recommendation = "MONITOR — Validator health degraded, monitor closely"
    else:
        recommendation = "CONTINUE — Mining profitable, validator healthy, gates open"

    result = {
        "timestamp": now,
        "recommendation": recommendation,
        "profitability": profitability.get("profitability", {}),
        "validator_health": {
            "score": health_score,
            "is_delinquent": health.get("status", {}).get("is_delinquent"),
            "skip_rate_pct": health.get("performance", {}).get("skip_rate_pct"),
        },
        "hierarchy": {
            "gate": gate_status,
            "predicates": predicate_status,
        },
        "sol_price_usd": profitability.get("sol_price_usd"),
        "costs_monthly_usd": profitability.get("costs", {}).get("total_cost_monthly"),
        "revenue_monthly_usd": profitability.get("revenue", {}).get(
            "monthly_revenue_usd"
        ),
    }
    return json.dumps(result, indent=2)
