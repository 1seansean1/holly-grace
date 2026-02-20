"""Holly Grace Sandbox — SIL-3 isolated code execution per Behavior Spec §2.

This package implements the sandbox layer of Holly Grace, providing secure,
isolated code execution in containerized environments with namespace-based
isolation, seccomp filtering, and cgroup resource limits.

Modules:
- container: Minimal Alpine-based container image builder
- executor: Code executor with gRPC service (future)
- isolation: Namespace, seccomp, and cgroup enforcement (future)
- protocol: gRPC protocol definitions (future)
"""

from holly.sandbox.container import (
    ContainerConfig,
    ContainerImage,
    ContainerState,
    IsolationLayer,
    MinimalContainerImage,
    create_minimal_container,
)

__all__ = [
    "ContainerConfig",
    "ContainerImage",
    "ContainerState",
    "IsolationLayer",
    "MinimalContainerImage",
    "create_minimal_container",
]
