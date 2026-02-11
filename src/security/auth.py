"""Bearer token authentication and role-based authorization.

Auth contract (from security plan):
- Transport: Authorization: Bearer <token> header (HTTP), ?token= query param (WS)
- Format: JWT with exp claim
- Roles: admin (full CRUD + triggers), operator (read + trigger jobs), viewer (read-only)
- Public: only GET /health
- Rejection: 401 missing/malformed/expired, 403 insufficient role
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# JWT configuration
_DEV_DEFAULT = "holly-grace-dev-secret-change-in-production"
_SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", _DEV_DEFAULT)
_ALGORITHM = "HS256"
_DEFAULT_EXPIRE_SECONDS = 3600  # 1 hour

# Fail startup in production if AUTH_SECRET_KEY is not set
if _SECRET_KEY == _DEV_DEFAULT and os.environ.get("TESTING") != "1":
    logger.warning(
        "AUTH_SECRET_KEY is using the default development value. "
        "Set AUTH_SECRET_KEY env var in production!"
    )

# Role hierarchy: admin > operator > viewer > webhook (webhook is special-purpose)
ROLES = ("viewer", "operator", "admin")

# Webhook role is separate from the main hierarchy — it's a service identity,
# not a user role. Webhook-triggered agent runs use this role.
WEBHOOK_ROLE = "webhook"

# All valid roles including webhook
ALL_ROLES = (*ROLES, WEBHOOK_ROLE)

# Single source of truth for unauthenticated access
# Webhook endpoints are public (signature-verified, not JWT-verified)
PUBLIC_ALLOWLIST: set[tuple[str, str]] = {("GET", "/"), ("GET", "/health")}

# Webhook endpoint prefixes — matched by prefix, not exact path.
# These bypass JWT auth but MUST verify provider-specific signatures.
WEBHOOK_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/webhooks/shopify",
    "/webhooks/stripe",
    "/webhooks/printful",
)

# Methods handled by CORS middleware before auth
SKIP_METHODS: set[str] = {"OPTIONS"}

# Write methods that require operator or admin
WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Endpoints requiring admin role (config changes, dangerous operations)
ADMIN_ONLY_PATHS: set[str] = {
    "/agents",                          # POST (create)
    "/agents/{agent_id}",               # PUT, DELETE
    "/agents/{agent_id}/rollback",      # POST
    "/aps/switch/{channel_id}/{theta_id}",  # POST
    "/morphogenetic/goals",             # POST (create)
    "/morphogenetic/goals/{goal_id}",   # PUT, DELETE
    "/morphogenetic/goals/reset",       # POST
    "/morphogenetic/cascade/config",    # PUT
    "/morphogenetic/cascade/config/reset",  # POST
    "/system/import",                   # POST
    "/workflows",                       # POST (create)
    "/workflows/{workflow_id}",         # PUT, DELETE
    "/workflows/{workflow_id}/rollback",  # POST
    # MCP registry
    "/mcp/servers",                     # POST
    "/mcp/servers/{server_id}",         # PATCH, DELETE
    "/mcp/servers/{server_id}/sync",    # POST
    "/mcp/tools/{tool_id}",             # PATCH
}

# Endpoints that operator can trigger
OPERATOR_PATHS: set[str] = {
    "/scheduler/trigger/{job_id}",      # POST
    "/aps/evaluate",                    # POST
    "/agents/efficacy/compute",         # POST
    "/morphogenetic/evaluate",          # POST
    "/eval/run",                        # POST
    "/workflows/{workflow_id}/compile", # POST
    "/workflows/{workflow_id}/activate",  # POST
    "/approvals/{approval_id}/approve", # POST
    "/approvals/{approval_id}/reject",  # POST
    "/scheduler/dlq/{dlq_id}/retry",    # POST
    "/agent/invoke",                    # POST (LangServe)
    "/agent/batch",                     # POST (LangServe)
    "/agent/stream",                    # POST (LangServe)
    "/agent/stream_log",               # POST (LangServe)
}


@dataclass
class TokenMetadata:
    """Metadata about a created token, returned by create_token."""
    token: str
    role: str
    subject: str
    expires_at: float  # Unix timestamp


def create_token(
    role: str = "viewer",
    subject: str = "user",
    expires_in: int = _DEFAULT_EXPIRE_SECONDS,
    secret_key: str | None = None,
) -> TokenMetadata:
    """Create a signed JWT token.

    Args:
        role: One of 'viewer', 'operator', 'admin'
        subject: Token subject (user identifier)
        expires_in: Seconds until expiry
        secret_key: Override secret key (for testing)

    Returns:
        TokenMetadata with token string and expiry info
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {ROLES}")

    key = secret_key or _SECRET_KEY
    now = time.time()
    expires_at = now + expires_in

    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now),
        "exp": int(expires_at),
    }

    token = jwt.encode(payload, key, algorithm=_ALGORITHM)
    return TokenMetadata(
        token=token,
        role=role,
        subject=subject,
        expires_at=expires_at,
    )


def verify_token(token: str, secret_key: str | None = None) -> dict:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token string
        secret_key: Override secret key (for testing)

    Returns:
        Decoded payload dict with 'sub', 'role', 'iat', 'exp'

    Raises:
        ValueError: If token is invalid, expired, or malformed
    """
    key = secret_key or _SECRET_KEY
    try:
        payload = jwt.decode(token, key, algorithms=[_ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e

    if "role" not in payload:
        raise ValueError("Token missing required 'role' claim")
    if payload["role"] not in ROLES:
        raise ValueError(f"Invalid role in token: {payload['role']}")

    return payload


def _role_level(role: str) -> int:
    """Get numeric level for role comparison."""
    try:
        return ROLES.index(role)
    except ValueError:
        return -1


def check_authorization(role: str, method: str, path_template: str) -> Optional[str]:
    """Check if a role is authorized for a method+path.

    Returns None if authorized, or an error message if not.
    """
    # Webhook role has restricted access — only specific agent invocations
    if role == WEBHOOK_ROLE:
        return _check_webhook_authorization(method, path_template)

    # GET/HEAD requests: viewer and above can access
    if method in ("GET", "HEAD"):
        return None  # All authenticated users can read

    # Write operations
    if method in WRITE_METHODS:
        # Admin-only paths require admin
        if path_template in ADMIN_ONLY_PATHS:
            if _role_level(role) < _role_level("admin"):
                return f"Admin role required for {method} {path_template}"
            return None

        # Operator paths require operator or above
        if path_template in OPERATOR_PATHS:
            if _role_level(role) < _role_level("operator"):
                return f"Operator role required for {method} {path_template}"
            return None

        # Default for unlisted write paths: require operator
        if _role_level(role) < _role_level("operator"):
            return f"Operator role required for {method} {path_template}"

    return None


# Paths that webhook role is allowed to invoke
WEBHOOK_ALLOWED_PATHS: set[str] = {
    "/agent/invoke",    # Trigger agent via LangServe
    "/agent/batch",     # Batch agent invocation
}


def _check_webhook_authorization(method: str, path_template: str) -> Optional[str]:
    """Check authorization for webhook-triggered requests.

    Webhooks have very restricted access — they can only trigger agent
    invocations on specific whitelisted paths.
    """
    if method == "POST" and path_template in WEBHOOK_ALLOWED_PATHS:
        return None
    return f"Webhook role not authorized for {method} {path_template}"


def is_webhook_path(path: str) -> bool:
    """Check if a request path is a webhook endpoint (public, signature-verified)."""
    return any(path.startswith(prefix) for prefix in WEBHOOK_PUBLIC_PREFIXES)


def extract_bearer_token(authorization: str | None) -> str | None:
    """Extract token from Authorization header value.

    Expected format: 'Bearer <token>'
    Returns None if header is missing or malformed.
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return None
    return parts[1].strip() if parts[1].strip() else None
