# Holly Grace

Autonomous e-commerce agent system. 31 AI agents orchestrated by Holly Grace (Opus 4.6), with a 7-level goal hierarchy, durable workflow execution, and a React console for human oversight. Manages a print-on-demand Shopify store 24/7.

## Documentation

| Document | What It Covers |
|----------|---------------|
| [Architecture](docs/ARCHITECTURE.md) | What exists and how it works — components, tables, endpoints, agents, jobs |
| [Interaction](docs/INTERACTION.md) | How Sean and Holly work together — decision rights, tiers, conversation patterns |
| [Operations](docs/OPERATIONS.md) | How to run, deploy, monitor, and fix — setup, runbooks, monitoring |
| [Decisions](docs/DECISIONS.md) | Why things are the way they are — 16 architectural decision records |
| [Radar](docs/RADAR.md) | What to work on next — improvement radar with biweekly sweep process |

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/1seansean1/ecom-agents.git
cd ecom-agents
py -3.11 -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2. Docker services (Postgres, Redis, ChromaDB, Ollama)
docker compose up -d

# 3. Environment
cp .env.example .env   # Fill in API keys

# 4. Start agents server (:8050)
set PYTHONUTF8=1
python -m uvicorn src.serve:app --host 0.0.0.0 --port 8050

# 5. Start console (:8060 backend, :3000 frontend)
cd console/backend && python -m uvicorn app.main:app --port 8060
cd console/frontend && npm install && npm run dev
```

See [Operations](docs/OPERATIONS.md) for full setup and deployment guide.

## Stack

| Layer | Technology |
|-------|------------|
| LLMs | Ollama qwen2.5:3b, GPT-4o, GPT-4o-mini, Claude Opus 4.6 |
| Framework | LangChain + LangGraph 0.6.x |
| Backend | FastAPI (agents :8050, console :8060) |
| Database | PostgreSQL 16 (44 tables), Redis 7 (5 streams), ChromaDB |
| Frontend | React 18 + Vite + Tailwind (19 pages) |
| Deploy | AWS ECS Fargate (us-east-2), ALB, ElastiCache, RDS |

## Tests

```bash
pytest tests/ -v              # All tests (1100+)
pytest tests/security/ -v     # Security tests (147)
```

## Version

See [CHANGELOG.md](CHANGELOG.md) for release history.
