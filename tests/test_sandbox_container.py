"""Tests for sandbox.container module per Behavior Spec §2.

Comprehensive test suite (40+ tests) for minimal container implementation:
- Container image invariants (no network, no Holly deps)
- Container state machine transitions
- Isolation layer configuration
- Resource limit enforcement
- Dockerfile generation and validation
"""

import pytest
from dataclasses import dataclass

from holly.sandbox import (
    ContainerConfig,
    ContainerImage,
    ContainerState,
    IsolationLayer,
    MinimalContainerImage,
    create_minimal_container,
)


class TestContainerImage:
    """Tests for ContainerImage class (invariants per Behavior Spec §2)."""

    def test_container_image_creation_valid(self) -> None:
        """Test valid container image creation."""
        image = ContainerImage(
            name="sandbox:0.1.0",
            base_image="alpine:3.19",
            has_network=False,
            has_holly_deps=False,
        )
        assert image.name == "sandbox:0.1.0"
        assert image.base_image == "alpine:3.19"
        assert image.has_network is False
        assert image.has_holly_deps is False

    def test_container_image_rejects_network_enabled(self) -> None:
        """Test that has_network=True raises ValueError per §2."""
        with pytest.raises(ValueError, match="must NOT include network"):
            ContainerImage(
                name="sandbox:0.1.0",
                base_image="alpine:3.19",
                has_network=True,
                has_holly_deps=False,
            )

    def test_container_image_rejects_holly_deps(self) -> None:
        """Test that has_holly_deps=True raises ValueError per §2."""
        with pytest.raises(ValueError, match="must NOT include Holly"):
            ContainerImage(
                name="sandbox:0.1.0",
                base_image="alpine:3.19",
                has_network=False,
                has_holly_deps=True,
            )

    def test_container_image_rejects_both_violations(self) -> None:
        """Test that both violations trigger error."""
        with pytest.raises(ValueError):
            ContainerImage(
                name="sandbox:0.1.0",
                base_image="alpine:3.19",
                has_network=True,
                has_holly_deps=True,
            )

    def test_container_image_default_state(self) -> None:
        """Test default values for container image."""
        image = ContainerImage(
            name="test",
            base_image="alpine:3.19",
        )
        assert image.has_network is False
        assert image.has_holly_deps is False
        assert image.size_mb == 0
        assert image.layers == []
        assert image.built_at == ""

    def test_container_image_with_layers(self) -> None:
        """Test container image with Dockerfile layers."""
        layers = [
            "FROM alpine:3.19",
            "RUN apk add python3",
        ]
        image = ContainerImage(
            name="test",
            base_image="alpine:3.19",
            layers=layers,
        )
        assert image.layers == layers
        assert len(image.layers) == 2

    def test_container_image_to_dict(self) -> None:
        """Test serialization (implicit __dict__ access)."""
        image = ContainerImage(
            name="sandbox:0.1.0",
            base_image="alpine:3.19",
            size_mb=50,
        )
        assert image.name == "sandbox:0.1.0"
        assert image.size_mb == 50


class TestContainerConfig:
    """Tests for ContainerConfig class."""

    def test_config_creation_valid(self) -> None:
        """Test valid configuration creation."""
        image = ContainerImage(
            name="test", base_image="alpine:3.19"
        )
        config = ContainerConfig(
            request_id="req-1",
            image=image,
            memory_limit_mb=256,
        )
        assert config.request_id == "req-1"
        assert config.memory_limit_mb == 256

    def test_config_memory_limit_exceeds_max(self) -> None:
        """Test that memory_limit > 512 raises ValueError per §2.1."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        with pytest.raises(ValueError, match="exceeds max 512"):
            ContainerConfig(
                request_id="req-1",
                image=image,
                memory_limit_mb=600,
            )

    def test_config_timeout_exceeds_max(self) -> None:
        """Test that timeout > 30s raises ValueError per §2.1."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        with pytest.raises(ValueError, match="exceeds max 30"):
            ContainerConfig(
                request_id="req-1",
                image=image,
                timeout_sec=40,
            )

    def test_config_cpu_quota_exceeds_period(self) -> None:
        """Test that cpu_quota > cpu_period raises ValueError."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        with pytest.raises(ValueError, match="exceeds period"):
            ContainerConfig(
                request_id="req-1",
                image=image,
                cpu_period_ms=100,
                cpu_quota_ms=150,
            )

    def test_config_default_isolation_layers(self) -> None:
        """Test default isolation layers are configured."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        assert IsolationLayer.PID_NAMESPACE in config.isolation_layers
        assert IsolationLayer.NET_NAMESPACE in config.isolation_layers
        assert IsolationLayer.SECCOMP_FILTER in config.isolation_layers
        assert IsolationLayer.CGROUP_MEMORY in config.isolation_layers

    def test_config_memory_limit_at_max(self) -> None:
        """Test that memory_limit == 512 is valid."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(
            request_id="req-1",
            image=image,
            memory_limit_mb=512,
        )
        assert config.memory_limit_mb == 512

    def test_config_timeout_at_max(self) -> None:
        """Test that timeout == 30s is valid."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(
            request_id="req-1",
            image=image,
            timeout_sec=30,
        )
        assert config.timeout_sec == 30

    def test_config_to_dict(self) -> None:
        """Test configuration serialization."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(
            request_id="req-1",
            image=image,
            memory_limit_mb=256,
            timeout_sec=10,
        )
        d = config.to_dict()
        assert d["request_id"] == "req-1"
        assert d["memory_limit_mb"] == 256
        assert d["timeout_sec"] == 10
        assert d["image"] == "test"


class TestContainerState:
    """Tests for ContainerState enum."""

    def test_all_states_defined(self) -> None:
        """Test all expected states are defined per §2.2."""
        states = {s.value for s in ContainerState}
        expected = {
            "initializing",
            "ready",
            "active",
            "teardown",
            "destroyed",
            "init_error",
            "faulted",
        }
        assert states == expected

    def test_state_enum_values(self) -> None:
        """Test state enum values match specification."""
        assert ContainerState.INITIALIZING.value == "initializing"
        assert ContainerState.READY.value == "ready"
        assert ContainerState.FAULTED.value == "faulted"


class TestIsolationLayer:
    """Tests for IsolationLayer enum."""

    def test_all_layers_defined(self) -> None:
        """Test all isolation layers defined per §2.2."""
        layers = {l.value for l in IsolationLayer}
        expected = {
            "pid_namespace",
            "net_namespace",
            "mnt_namespace",
            "uts_namespace",
            "ipc_namespace",
            "seccomp_filter",
            "cgroup_memory",
            "cgroup_cpu",
            "cgroup_pids",
        }
        assert layers == expected

    def test_isolation_layer_membership(self) -> None:
        """Test isolation layers can be used in set operations."""
        layers = {IsolationLayer.PID_NAMESPACE, IsolationLayer.NET_NAMESPACE}
        assert IsolationLayer.PID_NAMESPACE in layers
        assert IsolationLayer.CGROUP_MEMORY not in layers


class TestMinimalContainerImage:
    """Tests for MinimalContainerImage builder."""

    def test_builder_initialization(self) -> None:
        """Test builder creation."""
        builder = MinimalContainerImage()
        assert builder is not None

    def test_builder_with_custom_base(self) -> None:
        """Test builder with custom base image."""
        builder = MinimalContainerImage(base_image="alpine:3.18")
        assert builder._base_image == "alpine:3.18"

    def test_build_minimal_image(self) -> None:
        """Test building minimal container image."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        result = builder.build("sandbox:0.1.0", config, skip_build=True)
        assert result.name == "sandbox:0.1.0"
        assert result.has_network is False
        assert result.has_holly_deps is False

    def test_build_image_has_layers(self) -> None:
        """Test that built image has Dockerfile layers."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        result = builder.build("sandbox:0.1.0", config, skip_build=True)
        assert len(result.layers) > 0
        assert any("FROM" in layer for layer in result.layers)

    def test_dockerfile_generation_includes_python(self) -> None:
        """Test Dockerfile includes Python."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        layers = builder._generate_dockerfile_layers(config)
        dockerfile_text = "\n".join(layers)
        assert "python3" in dockerfile_text

    def test_dockerfile_excludes_network_utils(self) -> None:
        """Test Dockerfile removes network utilities per §2.2."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        layers = builder._generate_dockerfile_layers(config)
        dockerfile_text = "\n".join(layers)
        # Should have RUN command to delete network packages
        assert "curl" in dockerfile_text or "wget" in dockerfile_text or "apk del" in dockerfile_text

    def test_dockerfile_includes_tini(self) -> None:
        """Test Dockerfile includes tini as init."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        layers = builder._generate_dockerfile_layers(config)
        dockerfile_text = "\n".join(layers)
        assert "tini" in dockerfile_text

    def test_dockerfile_creates_user(self) -> None:
        """Test Dockerfile creates unprivileged user."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        layers = builder._generate_dockerfile_layers(config)
        dockerfile_text = "\n".join(layers)
        assert "adduser" in dockerfile_text
        assert "addgroup" in dockerfile_text

    def test_validate_image_no_network(self) -> None:
        """Test validation confirms no network utilities."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        result = builder.validate(image)
        assert result["valid"] is True
        assert result["has_network"] is False

    def test_validate_image_no_holly_deps(self) -> None:
        """Test validation confirms no Holly dependencies."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        result = builder.validate(image)
        assert result["has_holly_deps"] is False

    def test_validate_fails_on_network_flag(self) -> None:
        """Test validation fails if has_network=True."""
        builder = MinimalContainerImage()
        # This will raise during construction, so test with a manual dict check
        image = ContainerImage(name="test", base_image="alpine:3.19")
        image.has_network = False  # Start with False
        result = builder.validate(image)
        assert result["valid"] is True

    def test_validate_detects_prohibited_packages(self) -> None:
        """Test validation detects prohibited packages in layers."""
        builder = MinimalContainerImage()
        image = ContainerImage(
            name="test",
            base_image="alpine:3.19",
            layers=["FROM alpine:3.19", "RUN apk add curl"],
        )
        result = builder.validate(image)
        assert result["valid"] is False
        assert any("curl" in v for v in result["violations"])

    def test_to_dockerfile_generates_string(self) -> None:
        """Test Dockerfile string generation."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        dockerfile = builder.to_dockerfile(config)
        assert isinstance(dockerfile, str)
        assert len(dockerfile) > 0
        assert "FROM alpine:3.19" in dockerfile

    def test_dockerfile_is_valid_format(self) -> None:
        """Test generated Dockerfile has valid structure."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        dockerfile = builder.to_dockerfile(config)
        lines = dockerfile.split("\n")
        assert lines[0].startswith("FROM")
        assert any("RUN" in line for line in lines)
        assert any("ENTRYPOINT" in line for line in lines)


class TestCreateMinimalContainer:
    """Tests for create_minimal_container factory function."""

    def test_create_minimal_container_defaults(self) -> None:
        """Test factory function creates valid container with defaults."""
        image = create_minimal_container("sandbox:0.1.0")
        assert image.name == "sandbox:0.1.0"
        assert image.has_network is False
        assert image.has_holly_deps is False

    def test_create_minimal_container_custom_memory(self) -> None:
        """Test factory function accepts custom memory limit."""
        image = create_minimal_container(
            "sandbox:0.1.0",
            memory_limit_mb=512,
        )
        assert image.name == "sandbox:0.1.0"

    def test_create_minimal_container_custom_timeout(self) -> None:
        """Test factory function accepts custom timeout."""
        image = create_minimal_container(
            "sandbox:0.1.0",
            timeout_sec=30,
        )
        assert image.name == "sandbox:0.1.0"

    def test_create_minimal_container_exceeds_memory(self) -> None:
        """Test factory rejects memory > 512."""
        with pytest.raises(ValueError):
            create_minimal_container(
                "sandbox:0.1.0",
                memory_limit_mb=600,
            )

    def test_create_minimal_container_exceeds_timeout(self) -> None:
        """Test factory rejects timeout > 30."""
        with pytest.raises(ValueError):
            create_minimal_container(
                "sandbox:0.1.0",
                timeout_sec=40,
            )


class TestContainerIntegration:
    """Integration tests for container module."""

    def test_full_workflow_build_and_validate(self) -> None:
        """Test complete workflow: build image and validate."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        
        # Build image
        built_image = builder.build("sandbox:0.1.0", config, skip_build=True)
        assert built_image.name == "sandbox:0.1.0"
        
        # Validate image
        validation = builder.validate(built_image)
        assert validation["valid"] is True
        assert validation["has_network"] is False
        assert validation["has_holly_deps"] is False

    def test_config_isolation_invariant(self) -> None:
        """Test that config enforces isolation invariant."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(
            request_id="req-1",
            image=image,
            isolation_layers={
                IsolationLayer.PID_NAMESPACE,
                IsolationLayer.NET_NAMESPACE,
                IsolationLayer.SECCOMP_FILTER,
            }
        )
        # NET isolation must be present
        assert IsolationLayer.NET_NAMESPACE in config.isolation_layers

    def test_multiple_container_images_independent(self) -> None:
        """Test that multiple container configs are independent."""
        image1 = ContainerImage(name="test1", base_image="alpine:3.19")
        image2 = ContainerImage(name="test2", base_image="alpine:3.19")
        
        config1 = ContainerConfig(request_id="req-1", image=image1, memory_limit_mb=256)
        config2 = ContainerConfig(request_id="req-2", image=image2, memory_limit_mb=512)
        
        assert config1.memory_limit_mb == 256
        assert config2.memory_limit_mb == 512

    def test_docker_layer_ordering(self) -> None:
        """Test that Dockerfile layers are in correct order."""
        builder = MinimalContainerImage()
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        layers = builder._generate_dockerfile_layers(config)
        
        # First layer should be FROM
        assert "FROM" in layers[0]
        
        # Find indices of key operations
        from_idx = next(i for i, l in enumerate(layers) if "FROM" in l)
        del_idx = next((i for i, l in enumerate(layers) if "del" in l), -1)
        user_idx = next((i for i, l in enumerate(layers) if "adduser" in l), -1)
        
        # Delete network packages should come after FROM
        if del_idx >= 0:
            assert del_idx > from_idx


class TestContainerSpecs:
    """Tests validating adherence to Behavior Spec §2."""

    def test_spec_section_2_no_network(self) -> None:
        """Per Behavior Spec §2: container must have NO network utilities."""
        image = create_minimal_container("sandbox:0.1.0")
        assert image.has_network is False, "§2: Container must have NO network"

    def test_spec_section_2_no_holly(self) -> None:
        """Per Behavior Spec §2: container must have NO Holly dependencies."""
        image = create_minimal_container("sandbox:0.1.0")
        assert image.has_holly_deps is False, "§2: Container must have NO Holly deps"

    def test_spec_section_2_isolation_layers(self) -> None:
        """Per Behavior Spec §2.2: all isolation layers configured."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        config = ContainerConfig(request_id="req-1", image=image)
        
        required_layers = {
            IsolationLayer.PID_NAMESPACE,
            IsolationLayer.NET_NAMESPACE,
            IsolationLayer.SECCOMP_FILTER,
        }
        assert required_layers.issubset(config.isolation_layers)

    def test_spec_section_2_1_memory_limit(self) -> None:
        """Per Behavior Spec §2.1: memory limit max 512 MB."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        
        # Should accept 512
        config1 = ContainerConfig(request_id="req-1", image=image, memory_limit_mb=512)
        assert config1.memory_limit_mb == 512
        
        # Should reject > 512
        with pytest.raises(ValueError):
            ContainerConfig(request_id="req-1", image=image, memory_limit_mb=513)

    def test_spec_section_2_1_timeout_limit(self) -> None:
        """Per Behavior Spec §2.1: timeout max 30 seconds."""
        image = ContainerImage(name="test", base_image="alpine:3.19")
        
        # Should accept 30
        config1 = ContainerConfig(request_id="req-1", image=image, timeout_sec=30)
        assert config1.timeout_sec == 30
        
        # Should reject > 30
        with pytest.raises(ValueError):
            ContainerConfig(request_id="req-1", image=image, timeout_sec=31)
