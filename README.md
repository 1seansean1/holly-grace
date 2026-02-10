# Holly Grace

Autonomous agent orchestration platform. Multi-agent system with LangGraph, 4 LLM providers, real-time dashboard, and integrated multi-model chat.

## Architecture

```
holly-grace/
├── src/              # Agent system (LangGraph, tools, APS, guardrails)
├── console/          # Dashboard
│   ├── frontend/     # React + Tailwind (Vite)
│   ├── backend/      # FastAPI proxy + auth
│   └── aws/          # Terraform (ECS, RDS, ElastiCache, CloudFront)
├── chat-ui/          # Multi-model chat server (OpenAI, Anthropic, Google, Grok)
├── docker/           # Docker build contexts
├── tests/            # 818+ tests
├── docker-compose.yml
├── pyproject.toml
└── VERSION
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/1seansean1/holly-grace.git
cd holly-grace

# 2. Python environment
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. Docker services
docker compose up -d

# 4. Start agent system (port 8050)
PYTHONUTF8=1 python -m uvicorn src.serve:app --host 0.0.0.0 --port 8050 --reload

# 5. Start chat server (port 8072)
cd chat-ui && py -3.11 server.py

# 6. Start dashboard (port 5173)
cd console/frontend && npm install && npm run dev
```

## Services

| Port  | Service               |
|-------|-----------------------|
| 5173  | Dashboard (Vite dev)  |
| 8050  | Agent system (LangServe) |
| 8060  | Dashboard backend     |
| 8072  | Chat server           |
| 5434  | PostgreSQL            |
| 6381  | Redis                 |
| 8100  | ChromaDB              |
| 11435 | Ollama (GPU)          |

## Tests

```bash
# All agent tests
pytest tests/ -v

# Chat frontend integration tests (requires chat server running)
pytest tests/test_chat_frontend.py -v

# Security tests only
pytest tests/security/ -v
```

## Deploy

```bash
cd console/aws
./deploy.sh all    # Build + push + deploy + frontend
```

## Version

See [CHANGELOG.md](CHANGELOG.md) for release history. Uses [SemVer](https://semver.org/).
