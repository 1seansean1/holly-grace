"""Integration tests for Model Validation Engine.

Test classes:
- TestRealWorldSchemas: validation against real-world JSON schemas
- TestComplexValidationChains: multi-step validation pipelines
- TestErrorAggregation: error collection across validators
- TestValidatorInteroperability: validators work together correctly
"""
from __future__ import annotations

import pytest

from holly.validation.model_validator import (
    ModelValidationPipeline,
    SchemaValidationRule,
    SemanticValidationRule,
    SeverityLevel,
    ValidationResult,
    validate_model,
)


class TestRealWorldSchemas:
    """Integration tests with realistic schemas."""

    def test_api_request_schema(self) -> None:
        """Test validation of API request-like schema."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "minimum": 1},
                "name": {"type": "string", "minLength": 1},
                "email": {"type": "string"},
                "age": {"type": "integer", "minimum": 0, "maximum": 150},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id", "name", "email"],
        }

        # Valid request
        valid_request = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "tags": ["admin", "user"],
        }
        result = validate_model(valid_request, schema=schema)
        assert result.valid is True

        # Invalid request (missing required field)
        invalid_request = {"id": 1, "name": "Jane"}
        result = validate_model(invalid_request, schema=schema)
        assert result.valid is False

    def test_configuration_schema(self) -> None:
        """Test validation of configuration-like schema."""
        schema = {
            "type": "object",
            "properties": {
                "database": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "credentials": {
                            "type": "object",
                            "properties": {
                                "username": {"type": "string"},
                                "password": {"type": "string"},
                            },
                            "required": ["username", "password"],
                        },
                    },
                    "required": ["host", "port"],
                },
                "features": {
                    "type": "object",
                    "properties": {
                        "caching": {"type": "boolean"},
                        "logging": {"type": "boolean"},
                    },
                },
            },
            "required": ["database"],
        }

        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "secret"},
            },
            "features": {"caching": True, "logging": True},
        }

        result = validate_model(config, schema=schema)
        assert result.valid is True

    def test_contract_schema(self) -> None:
        """Test validation of business contract schema."""
        schema = {
            "type": "object",
            "properties": {
                "contractId": {"type": "string", "pattern": "^CT-[0-9]{6}$"},
                "parties": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"enum": ["buyer", "seller", "intermediary"]},
                        },
                        "required": ["name", "role"],
                    },
                    "minItems": 2,
                },
                "amount": {"type": "number", "minimum": 0},
                "startDate": {"type": "string", "format": "date"},
                "endDate": {"type": "string", "format": "date"},
            },
            "required": ["contractId", "parties", "amount"],
        }

        contract = {
            "contractId": "CT-123456",
            "parties": [
                {"name": "Company A", "role": "buyer"},
                {"name": "Company B", "role": "seller"},
            ],
            "amount": 50000.00,
            "startDate": "2026-01-01",
            "endDate": "2027-01-01",
        }

        result = validate_model(contract, schema=schema)
        assert result.valid is True


class TestComplexValidationChains:
    """Test multi-step validation pipelines."""

    def test_user_validation_chain(self) -> None:
        """Test complete user validation pipeline."""
        schema = {
            "type": "object",
            "properties": {
                "username": {"type": "string", "minLength": 3},
                "email": {"type": "string"},
                "password": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["username", "email", "password"],
        }

        def validate_username_format(model: dict) -> ValidationResult:
            """Username must be alphanumeric."""
            result = ValidationResult(valid=True)
            username = model.get("username", "")
            if username and not username.replace("_", "").isalnum():
                result.add_error("username", "Must be alphanumeric with underscores")
            return result

        def validate_email_format(model: dict) -> ValidationResult:
            """Email must contain @."""
            result = ValidationResult(valid=True)
            email = model.get("email", "")
            if email and "@" not in email:
                result.add_error("email", "Invalid email format")
            return result

        def validate_password_strength(model: dict) -> ValidationResult:
            """Password must be at least 8 characters."""
            result = ValidationResult(valid=True)
            password = model.get("password", "")
            if password and len(password) < 8:
                result.add_error("password", "Password must be at least 8 characters")
            return result

        def validate_age_range(model: dict) -> ValidationResult:
            """Age must be between 18 and 120 if provided."""
            result = ValidationResult(valid=True)
            age = model.get("age")
            if age is not None and (age < 18 or age > 120):
                result.add_error("age", "Age must be between 18 and 120")
            return result

        pipeline = ModelValidationPipeline()
        pipeline.add_validator(SchemaValidationRule(schema))
        pipeline.add_validator(SemanticValidationRule(validate_username_format))
        pipeline.add_validator(SemanticValidationRule(validate_email_format))
        pipeline.add_validator(SemanticValidationRule(validate_password_strength))
        pipeline.add_validator(SemanticValidationRule(validate_age_range))

        # Valid user
        user = {
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecurePass123",
            "age": 30,
        }
        result = pipeline.validate(user)
        assert result.valid is True

        # Invalid user (weak password)
        user_weak_pass = {
            "username": "john_doe",
            "email": "john@example.com",
            "password": "weak",
            "age": 30,
        }
        result = pipeline.validate(user_weak_pass)
        assert result.valid is False
        assert any("at least 8" in e.message for e in result.errors)

    def test_order_validation_chain(self) -> None:
        """Test order validation with multiple business rules."""
        schema = {
            "type": "object",
            "properties": {
                "orderId": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "productId": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "price": {"type": "number"},
                        },
                        "required": ["productId", "quantity", "price"],
                    },
                },
                "totalAmount": {"type": "number"},
                "status": {"enum": ["pending", "confirmed", "shipped", "delivered"]},
            },
            "required": ["orderId", "items"],
        }

        def validate_items_not_empty(model: dict) -> ValidationResult:
            """Order must have at least one item."""
            result = ValidationResult(valid=True)
            items = model.get("items", [])
            if not items:
                result.add_error("items", "Order must have at least one item")
            return result

        def validate_quantities(model: dict) -> ValidationResult:
            """All quantities must be positive."""
            result = ValidationResult(valid=True)
            for i, item in enumerate(model.get("items", [])):
                if item.get("quantity", 0) <= 0:
                    result.add_error(f"items[{i}].quantity", "Quantity must be positive")
            return result

        def validate_prices(model: dict) -> ValidationResult:
            """All prices must be positive."""
            result = ValidationResult(valid=True)
            for i, item in enumerate(model.get("items", [])):
                if item.get("price", 0) <= 0:
                    result.add_error(f"items[{i}].price", "Price must be positive")
            return result

        pipeline = (
            ModelValidationPipeline()
            .add_validator(SchemaValidationRule(schema))
            .add_validator(SemanticValidationRule(validate_items_not_empty))
            .add_validator(SemanticValidationRule(validate_quantities))
            .add_validator(SemanticValidationRule(validate_prices))
        )

        # Valid order
        order = {
            "orderId": "ORD-123",
            "items": [
                {"productId": "P1", "quantity": 2, "price": 29.99},
                {"productId": "P2", "quantity": 1, "price": 49.99},
            ],
            "totalAmount": 109.97,
            "status": "pending",
        }
        result = pipeline.validate(order)
        assert result.valid is True

        # Invalid order (negative quantity)
        invalid_order = {
            "orderId": "ORD-124",
            "items": [{"productId": "P1", "quantity": -1, "price": 29.99}],
        }
        result = pipeline.validate(invalid_order)
        assert result.valid is False


class TestErrorAggregation:
    """Test error collection across multiple validators."""

    def test_multiple_schema_violations(self) -> None:
        """Test detecting multiple schema violations."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["name", "age", "email"],
        }

        model = {"name": 123, "age": "thirty"}
        result = validate_model(model, schema=schema)

        assert result.valid is False
        assert len(result.errors) > 0

    def test_mixed_schema_and_semantic_errors(self) -> None:
        """Test error aggregation from schema and semantic validators."""
        schema = {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["username", "password"],
        }

        def check_username(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            username = model.get("username", "")
            if len(username) < 3:
                result.add_error("username", "Too short")
            if " " in username:
                result.add_error("username", "Contains spaces")
            return result

        pipeline = (
            ModelValidationPipeline(short_circuit=False)
            .add_validator(SchemaValidationRule(schema))
            .add_validator(SemanticValidationRule(check_username))
        )

        model = {"username": "ab cd"}
        result = pipeline.validate(model)

        assert result.valid is False
        error_messages = [e.message for e in result.errors]
        assert len(error_messages) >= 2

    def test_error_severity_levels(self) -> None:
        """Test error collection with various severity levels."""
        def check_model(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            result.add_error(
                "critical_field", "Critical issue", severity=SeverityLevel.CRITICAL.value
            )
            result.add_error("error_field", "Error issue", severity=SeverityLevel.ERROR.value)
            result.add_error("warning_field", "Warning issue", severity=SeverityLevel.WARNING.value)
            return result

        pipeline = ModelValidationPipeline().add_validator(SemanticValidationRule(check_model))
        result = pipeline.validate({})

        critical = [e for e in result.errors if e.severity == SeverityLevel.CRITICAL.value]
        errors = [e for e in result.errors if e.severity == SeverityLevel.ERROR.value]
        warnings = [e for e in result.errors if e.severity == SeverityLevel.WARNING.value]

        assert len(critical) == 1
        assert len(errors) == 1
        assert len(warnings) == 1


class TestValidatorInteroperability:
    """Test validators working together correctly."""

    def test_protocol_compatibility(self) -> None:
        """Test that all validators implement the protocol."""
        schema = {"type": "object"}
        schema_rule = SchemaValidationRule(schema)

        def validator_fn(model: dict) -> ValidationResult:
            return ValidationResult(valid=True)

        semantic_rule = SemanticValidationRule(validator_fn)
        pipeline = ModelValidationPipeline()

        # All should have validate method
        assert hasattr(schema_rule, "validate")
        assert hasattr(semantic_rule, "validate")
        assert hasattr(pipeline, "validate")

        assert callable(schema_rule.validate)
        assert callable(semantic_rule.validate)
        assert callable(pipeline.validate)

    def test_custom_validator_integration(self) -> None:
        """Test custom validator class with protocol."""

        class CustomValidator:
            """Custom validator implementing the protocol."""

            def validate(self, model: dict) -> ValidationResult:
                """Custom validation logic."""
                result = ValidationResult(valid=True)
                if not model.get("custom_field"):
                    result.add_error("custom_field", "Required")
                return result

        pipeline = ModelValidationPipeline()
        custom = CustomValidator()
        pipeline.add_validator(custom)

        result = pipeline.validate({})
        assert result.valid is False

        result = pipeline.validate({"custom_field": "value"})
        assert result.valid is True

    def test_pipeline_order_matters(self) -> None:
        """Test that validator order can affect pipeline behavior."""
        call_order = []

        def validator1(model: dict) -> ValidationResult:
            call_order.append(1)
            return ValidationResult(valid=True)

        def validator2(model: dict) -> ValidationResult:
            call_order.append(2)
            return ValidationResult(valid=True)

        def validator3(model: dict) -> ValidationResult:
            call_order.append(3)
            return ValidationResult(valid=True)

        pipeline = (
            ModelValidationPipeline()
            .add_validator(SemanticValidationRule(validator1))
            .add_validator(SemanticValidationRule(validator2))
            .add_validator(SemanticValidationRule(validator3))
        )

        pipeline.validate({})
        assert call_order == [1, 2, 3]

    def test_validate_model_function_composition(self) -> None:
        """Test validate_model function with multiple validators."""
        schema = {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
        }

        def check_positive(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.get("value", 0) <= 0:
                result.add_error("value", "Must be positive")
            return result

        def check_even(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.get("value", 0) % 2 != 0:
                result.add_error("value", "Must be even")
            return result

        result = validate_model(
            {"value": 4}, schema=schema, semantic_validators=[check_positive, check_even]
        )
        assert result.valid is True

        result = validate_model(
            {"value": 3}, schema=schema, semantic_validators=[check_positive, check_even]
        )
        assert result.valid is False

    def test_empty_validator_pipeline(self) -> None:
        """Test pipeline with no validators always passes."""
        pipeline = ModelValidationPipeline()
        result = pipeline.validate({})
        assert result.valid is True

        result = pipeline.validate({"any": "data"})
        assert result.valid is True

    def test_default_validate_model_behavior(self) -> None:
        """Test validate_model with no schema or validators."""
        result = validate_model({})
        assert result.valid is True

        result = validate_model({"any": "data"})
        assert result.valid is True

    def test_chained_semantic_validators_dependencies(self) -> None:
        """Test semantic validators that depend on each other."""
        def check_base_fields(model: dict) -> ValidationResult:
            """Ensure base fields exist."""
            result = ValidationResult(valid=True)
            if "id" not in model:
                result.add_error("id", "Required")
            if "status" not in model:
                result.add_error("status", "Required")
            return result

        def check_status_transitions(model: dict) -> ValidationResult:
            """Check status-specific logic."""
            result = ValidationResult(valid=True)
            status = model.get("status")
            if status == "archived" and model.get("id") is None:
                result.add_error("status", "Cannot archive without id")
            return result

        result = validate_model(
            {"id": 1, "status": "active"},
            semantic_validators=[check_base_fields, check_status_transitions],
        )
        assert result.valid is True
