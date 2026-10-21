"""Typed state shared by the AUTOSAR workflow nodes."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

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


class TranslationResult(BaseModel):
    """Structured translator output written into workflow state."""

    elements: List[AutosarElement] = Field(default_factory=list)
    translation_summary: str = ""
    ambiguities: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


class AutosarState(BaseModel):
    """Workflow state passed between intent, translator, and spec nodes."""

    user_request: str
    requested_autosar_release: Optional[str] = None
    intent: Optional[Dict[str, Any]] = None
    elements: List[AutosarElement] = Field(default_factory=list)
    translation_summary: str = ""
    ambiguities: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    spec_targets: List[SpecTarget] = Field(default_factory=list)
    collected_spec_items: Optional[List[CollectedSpecItem]] = None
    current_node: str = "start"
    errors: List[str] = Field(default_factory=list)
    messages: List[Dict[str, str]] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready copy of the state."""
        return self.model_dump()
