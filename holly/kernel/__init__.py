"""L1 Kernel — invariant enforcement at every boundary crossing.

Public API:
    - k1_validate           — standalone K1 schema validation gate
    - k1_gate               — Gate-compatible K1 factory for KernelContext
    - k2_check_permissions  — standalone K2 RBAC permission check
    - k2_gate               — Gate-compatible K2 factory for KernelContext
    - k8_evaluate           — standalone K8 eval gate
    - SchemaRegistry        — ICD JSON Schema resolution singleton
    - ICDSchemaRegistry     — ICD Pydantic model resolution with TTL cache
    - PredicateRegistry     — K8 predicate resolution singleton
    - PermissionRegistry    — K2 role-to-permission mapping singleton
    - ValidationError       — raised on schema violation
    - SchemaNotFoundError   — raised when schema_id is unknown
    - PayloadTooLargeError  — raised on oversized payload
    - PredicateNotFoundError — raised when predicate_id is unknown
    - EvalGateFailure       — raised when output violates K8 predicate
    - EvalError             — raised when predicate evaluation fails
    - ICDValidationError    — raised on Pydantic model validation failure
    - ICDModelAlreadyRegisteredError — raised on duplicate ICD model registration
    - KernelError           — base exception for blanket catch
    - JWTError              — raised on missing/malformed JWT claims
    - ExpiredTokenError     — raised when JWT exp is in the past
    - RevokedTokenError     — raised when JWT jti is revoked
    - PermissionDeniedError — raised when required permissions are not granted
    - RoleNotFoundError     — raised when role is not in PermissionRegistry
    - RevocationCacheError  — raised when revocation cache is unavailable
"""

from __future__ import annotations

from holly.kernel.exceptions import (
    EvalError,
    EvalGateFailure,
    ExpiredTokenError,
    JWTError,
    KernelError,
    PayloadTooLargeError,
    PermissionDeniedError,
    PredicateAlreadyRegisteredError,
    PredicateNotFoundError,
    RevocationCacheError,
    RevokedTokenError,
    RoleNotFoundError,
    SchemaNotFoundError,
    SchemaParseError,
    ValidationError,
)
from holly.kernel.icd_schema_registry import (
    ICDModelAlreadyRegisteredError,
    ICDSchemaRegistry,
    ICDValidationError,
)
from holly.kernel.k1 import k1_gate, k1_validate
from holly.kernel.k2 import k2_check_permissions, k2_gate
from holly.kernel.k8 import k8_evaluate
from holly.kernel.permission_registry import PermissionRegistry
from holly.kernel.predicate_registry import PredicateRegistry
from holly.kernel.schema_registry import SchemaRegistry

__all__ = [
    "EvalError",
    "EvalGateFailure",
    "ExpiredTokenError",
    "ICDModelAlreadyRegisteredError",
    "ICDSchemaRegistry",
    "ICDValidationError",
    "JWTError",
    "KernelError",
    "PayloadTooLargeError",
    "PermissionDeniedError",
    "PermissionRegistry",
    "PredicateAlreadyRegisteredError",
    "PredicateNotFoundError",
    "PredicateRegistry",
    "RevocationCacheError",
    "RevokedTokenError",
    "RoleNotFoundError",
    "SchemaNotFoundError",
    "SchemaParseError",
    "SchemaRegistry",
    "ValidationError",
    "k1_gate",
    "k1_validate",
    "k2_check_permissions",
    "k2_gate",
    "k8_evaluate",
]
