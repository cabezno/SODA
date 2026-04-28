"""Pydantic schemas for the Master Contract (Arquitecto v2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DataType(BaseModel):
    """Shared data type used across modules."""

    name: str = Field(..., description="Unique name in PascalCase")
    kind: Literal["primitive", "object", "enum", "union", "list"]
    fields: Optional[dict[str, str]] = Field(
        None, description="For objects: {field_name: type}"
    )
    values: Optional[list[str]] = Field(
        None, description="For enums: allowed values"
    )
    item_type: Optional[str] = Field(
        None, description="For lists: type of items"
    )
    description: str = Field(..., min_length=10)
    used_by_modules: list[str] = Field(default_factory=list)


class InterfaceMethod(BaseModel):
    """Public method exposed by a module."""

    name: str = Field(..., description="Method name in snake_case")
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Map of {param_name: type}",
    )
    returns: str = Field(..., description="Return type")
    raises: list[str] = Field(
        default_factory=list, description="Exception types that may be raised"
    )
    description: str = Field(..., min_length=10)
    example_usage: str = Field(..., description="Usage example")
    is_async: bool = False


class Interface(BaseModel):
    """Public interface of a module."""

    name: str
    description: str
    methods: list[InterfaceMethod] = Field(..., min_length=1)
    events_emitted: list[str] = Field(default_factory=list)
    events_consumed: list[str] = Field(default_factory=list)


class Module(BaseModel):
    """System module."""

    id: str = Field(..., description="Unique ID in snake_case")
    name: str = Field(..., description="Descriptive name")
    purpose: str = Field(..., min_length=20)
    # Physical files inherited from topology.json (set by Gemini, carried through unchanged)
    archivos_principales: list[str] = Field(
        default_factory=list,
        description="Physical file paths owned by this module (inherited from topology)",
    )
    interfaces: list[Interface] = Field(..., min_length=1)
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of other modules this depends on",
    )
    data_types_used: list[str] = Field(default_factory=list)
    extension_points: list[str] = Field(default_factory=list)
    goal_ids: list[str] = Field(
        ...,
        min_length=1,
        description="IDs of objective-tree nodes this module implements",
    )
    layer: Literal["domain", "application", "infrastructure", "presentation"]

    @field_validator("id")
    @classmethod
    def validate_snake_case(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("Module ID must be snake_case alphanumeric")
        if v != v.lower():
            raise ValueError("Module ID must be lowercase")
        return v


class EventChannel(BaseModel):
    """System event channel."""

    name: str = Field(
        ..., description="Name in dotted format, e.g. 'user.created'"
    )
    payload_schema: str = Field(
        ..., description="DataType name defining the payload"
    )
    publishers: list[str] = Field(
        default_factory=list, description="Module IDs that publish"
    )
    subscribers: list[str] = Field(
        default_factory=list, description="Module IDs that consume"
    )
    description: str
    is_reserved: bool = Field(
        False, description="True if reserved for future extension"
    )

    @field_validator("name")
    @classmethod
    def validate_dotted(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(
                'Event name must use dotted notation, e.g. "user.created"'
            )
        return v


class ExtensionPoint(BaseModel):
    """Extension point for future evolution."""

    id: str
    type: Literal[
        "middleware_slot",
        "event_channel",
        "metadata_field",
        "plugin",
        "hook",
        "filter",
    ]
    location: str = Field(..., description="Where this point applies")
    contract: str = Field(
        ..., description="What an implementer must fulfill"
    )
    description: str
    example_use_case: str


class ErrorType(BaseModel):
    """Standardized error type."""

    name: str = Field(
        ..., description="Name in PascalCase, e.g. 'UserNotFoundError'"
    )
    code: str = Field(
        ..., description="Code in UPPER_SNAKE_CASE, e.g. 'AUTH_USER_NOT_FOUND'"
    )
    message_template: str = Field(
        ..., description="Message template, may contain {placeholders}"
    )
    recoverable: bool
    retry_strategy: Optional[str] = Field(
        None, description="Retry strategy if applicable"
    )
    http_status: Optional[int] = Field(None, ge=400, le=599)
    raised_by_modules: list[str] = Field(default_factory=list)


class ArchitecturalDecision(BaseModel):
    """Architectural decision with justification."""

    id: str
    title: str
    context: str = Field(..., description="Situation that led to this decision")
    decision: str = Field(..., description="What was decided")
    consequences: list[str] = Field(
        ..., description="Positive and negative implications"
    )
    alternatives_considered: list[str] = Field(default_factory=list)


class Constant(BaseModel):
    """System constant."""

    name: str = Field(..., description="UPPER_SNAKE_CASE")
    value: str
    type: str
    description: str
    used_in_modules: list[str] = Field(default_factory=list)


class MasterContract(BaseModel):
    """Complete Master Contract for a project."""

    project_id: str
    project_name: str
    version: str = Field("1.0.0", description="Contract semver")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    complexity_level: Literal["simple", "medium", "complex"]
    model_used: str

    # System components
    modules: list[Module] = Field(..., min_length=1)
    data_types: list[DataType] = Field(default_factory=list)
    event_channels: list[EventChannel] = Field(default_factory=list)
    extension_points: list[ExtensionPoint] = Field(..., min_length=3)
    error_types: list[ErrorType] = Field(..., min_length=3)
    constants: list[Constant] = Field(default_factory=list)

    # Decisions and documentation
    architectural_decisions: list[ArchitecturalDecision] = Field(
        default_factory=list
    )
    assumptions: list[str] = Field(default_factory=list)

    # Metadata
    metadata: dict = Field(default_factory=dict)
