"""API Cost Tracking MCP server — read-only LLM spend observability.

Stdio MCP server that exposes 3 tools:
- anthropic_usage: Anthropic model-level spend from local cost tracker
- openai_usage: OpenAI model-level spend from local cost tracker
- combined_cost_summary: Merged cost view across all providers with totals

Reads from src.llm.cost_config in-memory tracking (get_workflow_costs,
get_total_cost_by_workflow, get_cost_summary, MODEL_COSTS).
Falls back gracefully if the module is not importable (e.g. running standalone).

Runs as: python -m src.mcp.servers.api_costs
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _load_cost_config():
    """Lazily import the cost_config module. Returns None if not available."""
    try:
        from src.llm import cost_config
        return cost_config
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _anthropic_usage(args: dict) -> str:
    """Return Anthropic model-level spend from local cost tracking."""
    try:
        cc = _load_cost_config()
        if cc is None:
            return json.dumps({
                "error": "Cost tracking unavailable — src.llm.cost_config not importable",
                "hint": "Run this MCP server within the ecom-agents environment",
            })

        workflow_id = args.get("workflow_id")
        limit = int(args.get("limit", 100))

        # Anthropic model IDs
        anthropic_models = {
            mid for mid, mc in cc.MODEL_COSTS.items()
            if "claude" in mid.lower()
        }

        # Get all tracked entries
        all_entries = cc.get_workflow_costs(workflow_id=workflow_id, limit=limit)

        # Filter to Anthropic only
        anthropic_entries = [e for e in all_entries if e["model_id"] in anthropic_models]

        # Aggregate per-model
        model_totals: dict[str, dict] = {}
        for e in anthropic_entries:
            mid = e["model_id"]
            if mid not in model_totals:
                model_totals[mid] = {
                    "model_id": mid,
                    "display_name": cc.MODEL_COSTS[mid].display_name if mid in cc.MODEL_COSTS else mid,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_calls": 0,
                }
            model_totals[mid]["total_input_tokens"] += e["input_tokens"]
            model_totals[mid]["total_output_tokens"] += e["output_tokens"]
            model_totals[mid]["total_cost_usd"] += e["cost_usd"]
            model_totals[mid]["total_calls"] += e["calls"]

        # Round costs
        for mt in model_totals.values():
            mt["total_cost_usd"] = round(mt["total_cost_usd"], 6)

        grand_total = round(sum(mt["total_cost_usd"] for mt in model_totals.values()), 6)

        result = {
            "provider": "anthropic",
            "models": sorted(model_totals.values(), key=lambda x: x["total_cost_usd"], reverse=True),
            "grand_total_usd": grand_total,
            "entries_scanned": len(anthropic_entries),
            "filter_workflow": workflow_id,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"anthropic_usage failed: {str(e)}"})


def _openai_usage(args: dict) -> str:
    """Return OpenAI model-level spend from local cost tracking."""
    try:
        cc = _load_cost_config()
        if cc is None:
            return json.dumps({
                "error": "Cost tracking unavailable — src.llm.cost_config not importable",
                "hint": "Run this MCP server within the ecom-agents environment",
            })

        workflow_id = args.get("workflow_id")
        limit = int(args.get("limit", 100))

        # OpenAI model IDs
        openai_models = {
            mid for mid, mc in cc.MODEL_COSTS.items()
            if "gpt" in mid.lower()
        }

        # Get all tracked entries
        all_entries = cc.get_workflow_costs(workflow_id=workflow_id, limit=limit)

        # Filter to OpenAI only
        openai_entries = [e for e in all_entries if e["model_id"] in openai_models]

        # Aggregate per-model
        model_totals: dict[str, dict] = {}
        for e in openai_entries:
            mid = e["model_id"]
            if mid not in model_totals:
                model_totals[mid] = {
                    "model_id": mid,
                    "display_name": cc.MODEL_COSTS[mid].display_name if mid in cc.MODEL_COSTS else mid,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_calls": 0,
                }
            model_totals[mid]["total_input_tokens"] += e["input_tokens"]
            model_totals[mid]["total_output_tokens"] += e["output_tokens"]
            model_totals[mid]["total_cost_usd"] += e["cost_usd"]
            model_totals[mid]["total_calls"] += e["calls"]

        # Round costs
        for mt in model_totals.values():
            mt["total_cost_usd"] = round(mt["total_cost_usd"], 6)

        grand_total = round(sum(mt["total_cost_usd"] for mt in model_totals.values()), 6)

        result = {
            "provider": "openai",
            "models": sorted(model_totals.values(), key=lambda x: x["total_cost_usd"], reverse=True),
            "grand_total_usd": grand_total,
            "entries_scanned": len(openai_entries),
            "filter_workflow": workflow_id,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"openai_usage failed: {str(e)}"})


def _combined_cost_summary(args: dict) -> str:
    """Merge all providers into a single cost view with totals."""
    try:
        cc = _load_cost_config()
        if cc is None:
            return json.dumps({
                "error": "Cost tracking unavailable — src.llm.cost_config not importable",
                "hint": "Run this MCP server within the ecom-agents environment",
            })

        workflow_id = args.get("workflow_id")
        limit = int(args.get("limit", 200))

        # Get all tracked entries
        all_entries = cc.get_workflow_costs(workflow_id=workflow_id, limit=limit)

        # Classify by provider
        provider_map: dict[str, str] = {}
        for mid in cc.MODEL_COSTS:
            if "claude" in mid.lower():
                provider_map[mid] = "anthropic"
            elif "gpt" in mid.lower():
                provider_map[mid] = "openai"
            elif cc.MODEL_COSTS[mid].is_local:
                provider_map[mid] = "local"
            else:
                provider_map[mid] = "other"

        # Aggregate per-provider and per-model
        by_provider: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        for e in all_entries:
            mid = e["model_id"]
            provider = provider_map.get(mid, "unknown")

            # Provider totals
            if provider not in by_provider:
                by_provider[provider] = {
                    "provider": provider,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_calls": 0,
                }
            by_provider[provider]["total_input_tokens"] += e["input_tokens"]
            by_provider[provider]["total_output_tokens"] += e["output_tokens"]
            by_provider[provider]["total_cost_usd"] += e["cost_usd"]
            by_provider[provider]["total_calls"] += e["calls"]

            # Model totals
            if mid not in by_model:
                by_model[mid] = {
                    "model_id": mid,
                    "provider": provider,
                    "display_name": cc.MODEL_COSTS[mid].display_name if mid in cc.MODEL_COSTS else mid,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_calls": 0,
                }
            by_model[mid]["total_input_tokens"] += e["input_tokens"]
            by_model[mid]["total_output_tokens"] += e["output_tokens"]
            by_model[mid]["total_cost_usd"] += e["cost_usd"]
            by_model[mid]["total_calls"] += e["calls"]

        # Round costs
        for p in by_provider.values():
            p["total_cost_usd"] = round(p["total_cost_usd"], 6)
        for m in by_model.values():
            m["total_cost_usd"] = round(m["total_cost_usd"], 6)

        grand_total = round(sum(p["total_cost_usd"] for p in by_provider.values()), 6)

        # Per-workflow breakdown
        workflow_totals = cc.get_total_cost_by_workflow()

        # Model pricing reference
        pricing_ref = cc.get_cost_summary()

        result = {
            "grand_total_usd": grand_total,
            "by_provider": sorted(by_provider.values(), key=lambda x: x["total_cost_usd"], reverse=True),
            "by_model": sorted(by_model.values(), key=lambda x: x["total_cost_usd"], reverse=True),
            "by_workflow": workflow_totals,
            "entries_scanned": len(all_entries),
            "filter_workflow": workflow_id,
            "pricing_reference": pricing_ref,
        }
        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": f"combined_cost_summary failed: {str(e)}"})


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "anthropic_usage",
        "description": "Get Anthropic (Claude) model-level spend from local cost tracking. Shows per-model token counts, costs, and call counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Filter by workflow ID (optional — omit for all workflows)"},
                "limit": {"type": "integer", "description": "Max entries to scan (default: 100)"},
            },
        },
    },
    {
        "name": "openai_usage",
        "description": "Get OpenAI (GPT) model-level spend from local cost tracking. Shows per-model token counts, costs, and call counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Filter by workflow ID (optional — omit for all workflows)"},
                "limit": {"type": "integer", "description": "Max entries to scan (default: 100)"},
            },
        },
    },
    {
        "name": "combined_cost_summary",
        "description": "Combined cost view across all providers (Anthropic, OpenAI, local). Shows totals by provider, by model, and by workflow.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string", "description": "Filter by workflow ID (optional — omit for all workflows)"},
                "limit": {"type": "integer", "description": "Max entries to scan (default: 200)"},
            },
        },
    },
]

_TOOL_DISPATCH = {
    "anthropic_usage": _anthropic_usage,
    "openai_usage": _openai_usage,
    "combined_cost_summary": _combined_cost_summary,
}


def _write(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


def _result(req_id: Any, result: dict[str, Any]) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications (no id) — ignore
        if req_id is None:
            continue

        if method == "initialize":
            requested = (params or {}).get("protocolVersion") or "2025-11-25"
            _result(req_id, {
                "protocolVersion": requested,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "api-costs", "version": "1.0.0"},
            })
            continue

        if method == "ping":
            _result(req_id, {})
            continue

        if method == "tools/list":
            _result(req_id, {"tools": _TOOLS})
            continue

        if method == "tools/call":
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments") or {}
            handler = _TOOL_DISPATCH.get(name)
            if not handler:
                _error(req_id, -32601, f"Unknown tool: {name}")
                continue
            try:
                text = handler(arguments if isinstance(arguments, dict) else {})
            except Exception as e:
                text = json.dumps({"error": str(e)})
            _result(req_id, {"content": [{"type": "text", "text": text}]})
            continue

        _error(req_id, -32601, f"Unknown method: {method}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
