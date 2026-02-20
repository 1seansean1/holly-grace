"""Model Validation Engine for schema and semantic validation.

Provides:
- ModelValidator protocol (runtime_checkable) with validate() method
- ValidationResult dataclass: valid flag, errors list, warnings list
- ValidationError: field, message, severity
- SchemaValidationRule: JSON schema compliance
- SemanticValidationRule: business logic constraints
- ModelValidationPipeline: chains validators, short-circuits on critical errors
- validate_model() entry point per ICD spec
"""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

import jsonschema


class SeverityLevel(enum.Enum):
    """Severity levels for validation errors."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class ValidationError:
    """Validation error with field, message, and severity.

    Attributes:
        field: Field name where error occurred.
        message: Error description.
        severity: Severity level (critical, error, warning, info).
    """

    field: str
    message: str
    severity: str = SeverityLevel.ERROR.value

    def __post_init__(self) -> None:
        """Validate severity is a known level."""
        valid_levels = {level.value for level in SeverityLevel}
        if self.severity not in valid_levels:
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass(slots=True)
class ValidationResult:
    """Result of model validation.

    Attributes:
        valid: Whether validation passed.
        errors: List of ValidationError objects.
        warnings: List of warning messages.
    """

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(
        self, field: str, message: str, severity: str = SeverityLevel.ERROR.value
    ) -> None:
        """Add a validation error.

        Args:
            field: Field name where error occurred.
            message: Error description.
            severity: Severity level.
        """
        self.errors.append(ValidationError(field=field, message=message, severity=severity))
        # Mark invalid if error is not just a warning
        if severity in (SeverityLevel.CRITICAL.value, SeverityLevel.ERROR.value):
            self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message.

        Args:
            message: Warning description.
        """
        self.warnings.append(message)

    def has_critical_errors(self) -> bool:
        """Check if result has critical errors.

        Returns:
            True if any error has critical severity.
        """
        return any(
            err.severity == SeverityLevel.CRITICAL.value for err in self.errors
        )

    def critical_errors(self) -> list[ValidationError]:
        """Get all critical errors.

        Returns:
            List of critical ValidationError objects.
        """
        return [err for err in self.errors if err.severity == SeverityLevel.CRITICAL.value]

    def error_count(self) -> int:
        """Count errors by severity.

        Returns:
            Total number of errors (excluding warnings).
        """
        return len(
            [
                err
                for err in self.errors
                if err.severity in (SeverityLevel.CRITICAL.value, SeverityLevel.ERROR.value)
            ]
        )


@runtime_checkable
class ModelValidator(Protocol):
    """Protocol for model validators.

    Any class implementing validate(model: dict[str, Any]) -> ValidationResult
    satisfies this protocol.
    """

    def validate(self, model: dict[str, Any]) -> ValidationResult:
        """Validate a model.

        Args:
            model: Model data to validate.

        Returns:
            ValidationResult with valid flag and any errors/warnings.

        Raises:
            ValueError: If model is None or not a dict.
        """
        ...


class SchemaValidationRule:
    """Validates model against JSON schema.

    Attributes:
        schema: JSON schema as dict.
        name: Rule name for reporting.
    """

    __slots__ = ("schema", "name")

    def __init__(self, schema: dict[str, Any], name: str = "SchemaValidation") -> None:
        """Initialize schema validation rule.

        Args:
            schema: JSON schema to validate against.
            name: Optional rule name.

        Raises:
            ValueError: If schema is not a valid dict.
        """
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a dict")
        self.schema = schema
        self.name = name

    def validate(self, model: dict[str, Any]) -> ValidationResult:
        """Validate model against JSON schema.

        Args:
            model: Model data to validate.

        Returns:
            ValidationResult with schema validation errors.
        """
        result = ValidationResult(valid=True)

        if not isinstance(model, dict):
            result.add_error(
                "_root",
                "Model must be a dict",
                SeverityLevel.CRITICAL.value,
            )
            return result

        validator = jsonschema.Draft7Validator(self.schema)

        # Collect all validation errors
        errors = sorted(validator.iter_errors(model), key=lambda e: e.path)

        for error in errors:
            field_path = ".".join(str(p) for p in error.path) or "_root"
            result.add_error(
                field_path,
                f"Schema validation failed: {error.message}",
                SeverityLevel.ERROR.value,
            )

        return result


class SemanticValidationRule:
    """Custom semantic validation rule.

    Applies business logic constraints to a model.

    Attributes:
        validator_fn: Callable that validates a model and returns ValidationResult.
        name: Rule name for reporting.
    """

    __slots__ = ("validator_fn", "name")

    def __init__(
        self,
        validator_fn: Callable[[dict[str, Any]], ValidationResult],
        name: str = "SemanticValidation",
    ) -> None:
        """Initialize semantic validation rule.

        Args:
            validator_fn: Function that takes model dict and returns ValidationResult.
            name: Optional rule name.

        Raises:
            TypeError: If validator_fn is not callable.
        """
        if not callable(validator_fn):
            raise TypeError("validator_fn must be callable")
        self.validator_fn = validator_fn
        self.name = name

    def validate(self, model: dict[str, Any]) -> ValidationResult:
        """Validate model using semantic rules.

        Args:
            model: Model data to validate.

        Returns:
            ValidationResult from the validator function.
        """
        if not isinstance(model, dict):
            result = ValidationResult(valid=False)
            result.add_error(
                "_root",
                "Model must be a dict",
                SeverityLevel.CRITICAL.value,
            )
            return result

        return self.validator_fn(model)


class ModelValidationPipeline:
    """Chains multiple validators with optional short-circuit on critical errors.

    Attributes:
        validators: List of validators (rules or callables).
        short_circuit: If True, stop on first critical error.
    """

    __slots__ = ("validators", "short_circuit")

    def __init__(
        self,
        validators: list[Any] | None = None,
        short_circuit: bool = True,
    ) -> None:
        """Initialize validation pipeline.

        Args:
            validators: List of validator objects (SchemaValidationRule,
                SemanticValidationRule, or callables with validate method).
            short_circuit: If True, stop on first critical error.
        """
        self.validators = validators or []
        self.short_circuit = short_circuit

    def add_validator(self, validator: Any) -> ModelValidationPipeline:
        """Add a validator to the pipeline.

        Args:
            validator: Validator object with validate(model) -> ValidationResult method.

        Returns:
            Self for method chaining.

        Raises:
            TypeError: If validator doesn't have a validate method.
        """
        if not hasattr(validator, "validate") or not callable(getattr(validator, "validate")):
            raise TypeError("Validator must have a callable validate method")
        self.validators.append(validator)
        return self

    def validate(self, model: dict[str, Any]) -> ValidationResult:
        """Run all validators in pipeline.

        Args:
            model: Model data to validate.

        Returns:
            Aggregated ValidationResult from all validators.
        """
        combined_result = ValidationResult(valid=True)

        if not isinstance(model, dict):
            combined_result.add_error(
                "_root",
                "Model must be a dict",
                SeverityLevel.CRITICAL.value,
            )
            return combined_result

        for validator in self.validators:
            result = validator.validate(model)

            # Merge results
            combined_result.valid = combined_result.valid and result.valid
            combined_result.errors.extend(result.errors)
            combined_result.warnings.extend(result.warnings)

            # Short-circuit on critical errors if enabled
            if self.short_circuit and result.has_critical_errors():
                break

        return combined_result


def validate_model(
    model: dict[str, Any],
    schema: dict[str, Any] | None = None,
    semantic_validators: list[Callable[[dict[str, Any]], ValidationResult]] | None = None,
) -> ValidationResult:
    """Primary entry point for model validation.

    Validates a model against optional JSON schema and semantic rules.

    Args:
        model: Model data to validate.
        schema: Optional JSON schema for validation.
        semantic_validators: Optional list of semantic validation functions.

    Returns:
        ValidationResult with valid flag and any errors/warnings.

    Raises:
        TypeError: If semantic_validators contain non-callable items.
    """
    if not isinstance(model, dict):
        result = ValidationResult(valid=False)
        result.add_error(
            "_root",
            "Model must be a dict",
            SeverityLevel.CRITICAL.value,
        )
        return result

    pipeline = ModelValidationPipeline(short_circuit=True)

    # Add schema validation if provided
    if schema is not None:
        if not isinstance(schema, dict):
            result = ValidationResult(valid=False)
            result.add_error(
                "_root",
                "Schema must be a dict",
                SeverityLevel.CRITICAL.value,
            )
            return result
        pipeline.add_validator(SchemaValidationRule(schema, "SchemaValidation"))

    # Add semantic validators if provided
    if semantic_validators:
        for i, validator_fn in enumerate(semantic_validators):
            if not callable(validator_fn):
                raise TypeError(f"semantic_validator[{i}] must be callable")
            pipeline.add_validator(
                SemanticValidationRule(validator_fn, f"SemanticValidation_{i}")
            )

    return pipeline.validate(model)
