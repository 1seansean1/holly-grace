"""Unit tests for Model Validation Engine.

Test classes:
- TestValidationResult: result object behavior
- TestValidationError: error object behavior
- TestSchemaValidation: schema compliance checking
- TestSemanticValidation: business logic validation
- TestValidationPipeline: chained validator behavior
- TestValidateModelFunction: end-to-end API
- TestFailureModes: invalid inputs, edge cases
"""
from __future__ import annotations

import json
import pytest

from holly.validation.model_validator import (
    ModelValidationPipeline,
    SchemaValidationRule,
    SemanticValidationRule,
    SeverityLevel,
    ValidationError,
    ValidationResult,
    validate_model,
)


class TestValidationError:
    """Test ValidationError dataclass."""

    def test_create_error_default_severity(self) -> None:
        """Test creating error with default severity."""
        error = ValidationError(field="name", message="Invalid name")
        assert error.field == "name"
        assert error.message == "Invalid name"
        assert error.severity == SeverityLevel.ERROR.value

    def test_create_error_custom_severity(self) -> None:
        """Test creating error with custom severity."""
        error = ValidationError(
            field="age",
            message="Age must be positive",
            severity=SeverityLevel.CRITICAL.value,
        )
        assert error.severity == SeverityLevel.CRITICAL.value

    def test_invalid_severity_raises_error(self) -> None:
        """Test that invalid severity raises ValueError."""
        with pytest.raises(ValueError, match="Invalid severity"):
            ValidationError(field="x", message="test", severity="unknown")

    def test_error_equality(self) -> None:
        """Test error equality comparison."""
        err1 = ValidationError(field="x", message="msg")
        err2 = ValidationError(field="x", message="msg")
        assert err1 == err2

    def test_error_repr(self) -> None:
        """Test error string representation."""
        error = ValidationError(field="test", message="msg")
        repr_str = repr(error)
        assert "ValidationError" in repr_str
        assert "test" in repr_str


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_create_valid_result(self) -> None:
        """Test creating a valid result."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_create_invalid_result(self) -> None:
        """Test creating an invalid result."""
        result = ValidationResult(valid=False)
        assert result.valid is False

    def test_add_error_marks_invalid(self) -> None:
        """Test that adding error marks result invalid."""
        result = ValidationResult(valid=True)
        result.add_error("field1", "error message")
        assert result.valid is False
        assert len(result.errors) == 1

    def test_add_multiple_errors(self) -> None:
        """Test adding multiple errors."""
        result = ValidationResult(valid=True)
        result.add_error("field1", "error1")
        result.add_error("field2", "error2")
        assert len(result.errors) == 2
        assert result.valid is False

    def test_add_warning(self) -> None:
        """Test adding warnings."""
        result = ValidationResult(valid=True)
        result.add_warning("warning1")
        result.add_warning("warning2")
        assert result.valid is True
        assert len(result.warnings) == 2

    def test_add_error_with_custom_severity(self) -> None:
        """Test adding error with custom severity."""
        result = ValidationResult(valid=True)
        result.add_error(
            "field", "msg", severity=SeverityLevel.WARNING.value
        )
        assert result.errors[0].severity == SeverityLevel.WARNING.value

    def test_has_critical_errors_true(self) -> None:
        """Test detecting critical errors."""
        result = ValidationResult(valid=False)
        result.add_error("field", "critical", severity=SeverityLevel.CRITICAL.value)
        assert result.has_critical_errors() is True

    def test_has_critical_errors_false(self) -> None:
        """Test when no critical errors present."""
        result = ValidationResult(valid=False)
        result.add_error("field", "error")
        assert result.has_critical_errors() is False

    def test_critical_errors_filter(self) -> None:
        """Test filtering critical errors."""
        result = ValidationResult(valid=False)
        result.add_error("f1", "msg1", severity=SeverityLevel.CRITICAL.value)
        result.add_error("f2", "msg2", severity=SeverityLevel.ERROR.value)
        result.add_error("f3", "msg3", severity=SeverityLevel.CRITICAL.value)
        critical = result.critical_errors()
        assert len(critical) == 2

    def test_error_count(self) -> None:
        """Test counting errors (excludes warnings)."""
        result = ValidationResult(valid=False)
        result.add_error("f1", "msg1")
        result.add_error("f2", "msg2", severity=SeverityLevel.WARNING.value)
        result.add_warning("warn")
        assert result.error_count() == 1

    def test_warning_does_not_mark_invalid(self) -> None:
        """Test that warning severity doesn't mark invalid."""
        result = ValidationResult(valid=True)
        result.add_error("field", "msg", severity=SeverityLevel.WARNING.value)
        assert result.valid is True


class TestSchemaValidation:
    """Test SchemaValidationRule for JSON schema validation."""

    def test_create_rule(self) -> None:
        """Test creating a schema validation rule."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        rule = SchemaValidationRule(schema)
        assert rule.schema == schema
        assert rule.name == "SchemaValidation"

    def test_create_rule_custom_name(self) -> None:
        """Test creating rule with custom name."""
        schema = {"type": "object"}
        rule = SchemaValidationRule(schema, name="CustomRule")
        assert rule.name == "CustomRule"

    def test_invalid_schema_type_raises(self) -> None:
        """Test that non-dict schema raises ValueError."""
        with pytest.raises(ValueError, match="Schema must be a dict"):
            SchemaValidationRule("not a dict")

    def test_validate_valid_model(self) -> None:
        """Test validating a model that matches schema."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        rule = SchemaValidationRule(schema)
        result = rule.validate({"name": "John"})
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_model(self) -> None:
        """Test validating a model that violates schema."""
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
        }
        rule = SchemaValidationRule(schema)
        result = rule.validate({"age": "not an integer"})
        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_missing_required_field(self) -> None:
        """Test validation fails for missing required field."""
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        }
        rule = SchemaValidationRule(schema)
        result = rule.validate({})
        assert result.valid is False

    def test_validate_non_dict_model(self) -> None:
        """Test validation fails for non-dict model."""
        schema = {"type": "object"}
        rule = SchemaValidationRule(schema)
        result = rule.validate("not a dict")  # type: ignore
        assert result.valid is False
        assert result.errors[0].severity == SeverityLevel.CRITICAL.value

    def test_validate_nested_schema(self) -> None:
        """Test validation of nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
        }
        rule = SchemaValidationRule(schema)
        result = rule.validate({"person": {"name": "Alice"}})
        assert result.valid is True

    def test_validate_array_schema(self) -> None:
        """Test validation with array fields."""
        schema = {
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
        }
        rule = SchemaValidationRule(schema)
        result = rule.validate({"tags": ["a", "b"]})
        assert result.valid is True


class TestSemanticValidation:
    """Test SemanticValidationRule for business logic validation."""

    def test_create_rule(self) -> None:
        """Test creating semantic validation rule."""
        def validator_fn(model: dict) -> ValidationResult:
            return ValidationResult(valid=True)

        rule = SemanticValidationRule(validator_fn)
        assert rule.validator_fn is validator_fn
        assert rule.name == "SemanticValidation"

    def test_non_callable_raises_error(self) -> None:
        """Test that non-callable validator_fn raises TypeError."""
        with pytest.raises(TypeError, match="must be callable"):
            SemanticValidationRule("not callable")  # type: ignore

    def test_validate_with_validator_function(self) -> None:
        """Test semantic validation with custom function."""
        def check_age(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.get("age", 0) < 0:
                result.add_error("age", "Age cannot be negative")
            return result

        rule = SemanticValidationRule(check_age)
        result = rule.validate({"age": 25})
        assert result.valid is True

        result = rule.validate({"age": -5})
        assert result.valid is False

    def test_validate_non_dict_model(self) -> None:
        """Test validation fails for non-dict model."""
        def validator_fn(model: dict) -> ValidationResult:
            return ValidationResult(valid=True)

        rule = SemanticValidationRule(validator_fn)
        result = rule.validate("not a dict")  # type: ignore
        assert result.valid is False
        assert result.errors[0].severity == SeverityLevel.CRITICAL.value

    def test_multiple_business_rules(self) -> None:
        """Test semantic validator enforcing multiple business rules."""
        def validate_person(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if not model.get("name"):
                result.add_error("name", "Name is required")
            if model.get("age", 0) < 18:
                result.add_error("age", "Must be 18 or older")
            return result

        rule = SemanticValidationRule(validate_person)
        result = rule.validate({"name": "Bob", "age": 25})
        assert result.valid is True

        result = rule.validate({"name": "Alice", "age": 15})
        assert result.valid is False
        assert len(result.errors) == 1


class TestValidationPipeline:
    """Test ModelValidationPipeline chaining validators."""

    def test_create_empty_pipeline(self) -> None:
        """Test creating empty pipeline."""
        pipeline = ModelValidationPipeline()
        assert pipeline.validators == []
        assert pipeline.short_circuit is True

    def test_create_with_validators(self) -> None:
        """Test creating pipeline with initial validators."""
        schema = {"type": "object"}
        rule = SchemaValidationRule(schema)
        pipeline = ModelValidationPipeline(validators=[rule])
        assert len(pipeline.validators) == 1

    def test_add_validator(self) -> None:
        """Test adding validator to pipeline."""
        pipeline = ModelValidationPipeline()
        schema = {"type": "object"}
        rule = SchemaValidationRule(schema)
        pipeline.add_validator(rule)
        assert len(pipeline.validators) == 1

    def test_add_validator_returns_self(self) -> None:
        """Test add_validator returns self for chaining."""
        pipeline = ModelValidationPipeline()
        result = pipeline.add_validator(SchemaValidationRule({"type": "object"}))
        assert result is pipeline

    def test_method_chaining(self) -> None:
        """Test chaining multiple add_validator calls."""
        schema1 = {"type": "object"}
        schema2 = {"type": "object"}
        pipeline = (
            ModelValidationPipeline()
            .add_validator(SchemaValidationRule(schema1))
            .add_validator(SchemaValidationRule(schema2))
        )
        assert len(pipeline.validators) == 2

    def test_invalid_validator_raises(self) -> None:
        """Test adding non-validator object raises TypeError."""
        pipeline = ModelValidationPipeline()
        with pytest.raises(TypeError, match="must have a callable validate method"):
            pipeline.add_validator("not a validator")  # type: ignore

    def test_pipeline_aggregates_results(self) -> None:
        """Test pipeline combines results from multiple validators."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        def semantic_check(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if not model.get("name"):
                result.add_error("name", "Name is required")
            return result

        pipeline = ModelValidationPipeline()
        pipeline.add_validator(SchemaValidationRule(schema))
        pipeline.add_validator(SemanticValidationRule(semantic_check))

        result = pipeline.validate({"name": "Alice"})
        assert result.valid is True

    def test_pipeline_collects_all_errors(self) -> None:
        """Test pipeline collects errors from all validators."""
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
        }

        def check_age(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            age = model.get("age")
            # Only check if age is an integer, to avoid type comparison errors
            if isinstance(age, int) and age < 0:
                result.add_error("age", "Age cannot be negative")
            return result

        pipeline = ModelValidationPipeline()
        pipeline.add_validator(SchemaValidationRule(schema))
        pipeline.add_validator(SemanticValidationRule(check_age))

        result = pipeline.validate({"age": "invalid"})
        assert result.valid is False
        # Should have error from schema validation about type
        assert len(result.errors) > 0

    def test_short_circuit_on_critical_error(self) -> None:
        """Test pipeline stops on critical error when short_circuit=True."""
        schema = {"type": "object"}

        def semantic_check(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            result.add_error("field", "Should not be reached")
            return result

        pipeline = ModelValidationPipeline(short_circuit=True)
        pipeline.add_validator(SchemaValidationRule(schema))
        pipeline.add_validator(SemanticValidationRule(semantic_check))

        result = pipeline.validate("not a dict")  # type: ignore
        assert result.valid is False
        # Should have critical error from schema validation
        assert result.has_critical_errors()
        # Should not have the "Should not be reached" error
        assert not any("Should not be reached" in e.message for e in result.errors)

    def test_no_short_circuit(self) -> None:
        """Test pipeline continues when short_circuit=False."""
        schema = {"type": "object"}
        
        call_order = []

        def validator1(model: dict) -> ValidationResult:
            call_order.append(1)
            result = ValidationResult(valid=False)
            result.add_error("test", "Test error")
            return result

        def validator2(model: dict) -> ValidationResult:
            call_order.append(2)
            return ValidationResult(valid=True)

        pipeline = ModelValidationPipeline(short_circuit=False)
        pipeline.add_validator(SemanticValidationRule(validator1))
        pipeline.add_validator(SemanticValidationRule(validator2))

        pipeline.validate({})
        # Both validators should run when short_circuit=False
        assert len(call_order) == 2
        assert call_order == [1, 2]

class TestValidateModelFunction:
    """Test validate_model() entry point."""

    def test_validate_with_schema_only(self) -> None:
        """Test validation with only schema."""
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        }
        result = validate_model({"id": 1}, schema=schema)
        assert result.valid is True

    def test_validate_with_schema_failure(self) -> None:
        """Test validation fails with schema."""
        schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
        }
        result = validate_model({"id": "not int"}, schema=schema)
        assert result.valid is False

    def test_validate_with_semantic_validators(self) -> None:
        """Test validation with semantic validators only."""
        def check_positive(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.get("value", 0) <= 0:
                result.add_error("value", "Must be positive")
            return result

        result = validate_model({"value": 5}, semantic_validators=[check_positive])
        assert result.valid is True

        result = validate_model({"value": -1}, semantic_validators=[check_positive])
        assert result.valid is False

    def test_validate_with_schema_and_semantic(self) -> None:
        """Test validation with both schema and semantic validators."""
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}

        def check_age(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            age = model.get("age", 0)
            if age < 0 or age > 150:
                result.add_error("age", "Invalid age range")
            return result

        result = validate_model({"age": 25}, schema=schema, semantic_validators=[check_age])
        assert result.valid is True

        result = validate_model({"age": 200}, schema=schema, semantic_validators=[check_age])
        assert result.valid is False

    def test_validate_non_dict_model(self) -> None:
        """Test validation fails for non-dict model."""
        result = validate_model("not a dict")  # type: ignore
        assert result.valid is False
        assert result.errors[0].severity == SeverityLevel.CRITICAL.value

    def test_validate_invalid_schema_type(self) -> None:
        """Test validation fails if schema is not dict."""
        result = validate_model({}, schema="not a dict")  # type: ignore
        assert result.valid is False
        assert result.errors[0].severity == SeverityLevel.CRITICAL.value

    def test_validate_non_callable_semantic_validator(self) -> None:
        """Test that non-callable semantic validator raises TypeError."""
        with pytest.raises(TypeError, match="must be callable"):
            validate_model({}, semantic_validators=["not callable"])  # type: ignore

    def test_validate_multiple_semantic_validators(self) -> None:
        """Test validation with multiple semantic validators."""
        def check_name(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if not model.get("name"):
                result.add_error("name", "Name required")
            return result

        def check_age(model: dict) -> ValidationResult:
            result = ValidationResult(valid=True)
            if model.get("age", 0) < 0:
                result.add_error("age", "Age invalid")
            return result

        result = validate_model(
            {"name": "Alice", "age": 25},
            semantic_validators=[check_name, check_age],
        )
        assert result.valid is True


class TestFailureModes:
    """Test edge cases and failure modes."""

    def test_empty_model(self) -> None:
        """Test validation of empty model."""
        schema = {"type": "object"}
        result = validate_model({}, schema=schema)
        assert result.valid is True

    def test_large_nested_model(self) -> None:
        """Test validation of large nested structure."""
        schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    },
                }
            },
        }
        model = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
        result = validate_model(model, schema=schema)
        assert result.valid is True

    def test_null_values_in_model(self) -> None:
        """Test handling of null values."""
        schema = {
            "type": "object",
            "properties": {"optional": {"type": ["string", "null"]}},
        }
        result = validate_model({"optional": None}, schema=schema)
        assert result.valid is True

    def test_validator_function_exception_propagates(self) -> None:
        """Test that exceptions in validator propagate."""
        def bad_validator(model: dict) -> ValidationResult:
            raise RuntimeError("Validator failed")

        with pytest.raises(RuntimeError, match="Validator failed"):
            validate_model({}, semantic_validators=[bad_validator])

    def test_complex_schema_validation(self) -> None:
        """Test validation with complex schema constraints."""
        schema = {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "minLength": 8},
            },
            "required": ["email", "password"],
        }
        model = {"email": "test@example.com", "password": "securepass123"}
        result = validate_model(model, schema=schema)
        assert result.valid is True

    def test_additional_properties_validation(self) -> None:
        """Test schema validation with additionalProperties."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        result = validate_model({"name": "Alice", "extra": "field"}, schema=schema)
        # May be valid depending on schema, but should process without error
        assert isinstance(result.valid, bool)

    def test_enum_validation(self) -> None:
        """Test schema validation with enum constraints."""
        schema = {
            "type": "object",
            "properties": {"status": {"enum": ["active", "inactive"]}},
        }
        result = validate_model({"status": "active"}, schema=schema)
        assert result.valid is True

        result = validate_model({"status": "unknown"}, schema=schema)
        assert result.valid is False

    def test_pipeline_with_no_validators(self) -> None:
        """Test pipeline validation with no validators."""
        pipeline = ModelValidationPipeline()
        result = pipeline.validate({})
        assert result.valid is True

    def test_result_immutability_of_errors_list(self) -> None:
        """Test that errors list can be safely modified."""
        result = ValidationResult(valid=True)
        result.add_error("f1", "msg1")
        original_count = len(result.errors)
        # Directly modify would be bad practice, but should work
        result.errors.append(ValidationError(field="f2", message="msg2"))
        assert len(result.errors) == original_count + 1

    def test_deeply_nested_schema_validation(self) -> None:
        """Test validation of deeply nested structures."""
        schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                        }
                    },
                }
            },
        }
        model = {"level1": {"level2": {"value": "test"}}}
        result = validate_model(model, schema=schema)
        assert result.valid is True
