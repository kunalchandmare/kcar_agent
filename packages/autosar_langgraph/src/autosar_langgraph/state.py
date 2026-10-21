"""Typed state shared by the phase-1 LangGraph nodes."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

ElementKind = Literal[
    "SoftwareComponent",
    "Port",
    "Interface",
    "DataElement",
    "Signal",
    "SystemSignal",
    "ISignal",
    "Pdu",
    "Runnable",
    "DataType",
    "System",
    "ECU",
    "CommunicationCluster",
    "Other",
]


class SpecTarget(BaseModel):
    """Target that tells the Spec Agent exactly what to retrieve."""

    autosar_release: str
    document: str
    chapter_or_section: Optional[str] = None
    meta_model_element: str
    required_items: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class AutosarElement(BaseModel):
    """Version-aware AUTOSAR element produced by the Translator."""

    name: str
    kind: ElementKind
    autosar_release: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    references: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    notes: Optional[str] = None
    spec_targets: List[SpecTarget] = Field(default_factory=list)


class CollectedSpecItem(BaseModel):
    """Structured specification content returned by the Spec Agent."""

    source_document: str
    release: str
    section: Optional[str] = None
    content_summary: str
    raw_excerpt: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    mandatory_attributes: List[str] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)


class IntentResult(BaseModel):
    """Light structure extracted from the user request before translation."""

    request_type: str
    entities: List[str] = Field(default_factory=list)
    autosar_release: Optional[str] = None
    notes: str = ""


class TranslationResult(BaseModel):
    """Structured translator output written into workflow state."""

    elements: List[AutosarElement] = Field(default_factory=list)
    translation_summary: str = ""
    ambiguities: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


class AutosarState(TypedDict):
    """LangGraph state for phase 1. Later phases will add planner and generator fields."""

    user_request: str
    requested_autosar_release: Optional[str]
    intent: Optional[Dict[str, Any]]
    elements: List[Dict[str, Any]]
    translation_summary: str
    ambiguities: List[str]
    missing_information: List[str]
    spec_targets: List[Dict[str, Any]]
    collected_spec_items: List[Dict[str, Any]]
    current_node: str
    errors: List[str]
    messages: List[Dict[str, str]]
