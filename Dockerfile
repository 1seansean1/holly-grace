FROM python:3.11-slim AS base

WORKDIR /app

# Install system deps: libpq (psycopg), nginx, node (frontend build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 nginx curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# ── Stage 1: Build frontend ─────────────────────────────────────────────
COPY console/frontend/package.json console/frontend/package-lock.json* /app/console/frontend/
RUN cd /app/console/frontend && npm ci --ignore-scripts

COPY console/frontend/ /app/console/frontend/
RUN cd /app/console/frontend && npm run build

# ── Stage 2: Install Python deps ────────────────────────────────────────
# Agents API
COPY pyproject.toml .
COPY src/ src/
COPY tests/golden/ tests/golden/
RUN pip install --no-cache-dir .

# Console backend (most deps already installed by agents)
COPY console/backend/pyproject.toml /app/console/backend/
COPY console/backend/app/ /app/console/backend/app/
RUN pip install --no-cache-dir /app/console/backend

# ── Stage 3: Configure nginx ────────────────────────────────────────────
COPY deploy/nginx-production.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Copy built frontend to nginx serving dir (replace default welcome page)
RUN rm -rf /usr/share/nginx/html/* && cp -r /app/console/frontend/dist/* /usr/share/nginx/html/

# ── Entrypoint ───────────────────────────────────────────────────────────
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUTF8=1
EXPOSE 80 8050

CMD ["/app/entrypoint.sh"]
