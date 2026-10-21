"""Translate a natural-language request into version-aware AUTOSAR elements."""

import logging
from typing import List, Optional

from autosar_langgraph.parsing import (
    detect_element_kinds,
    extract_bit_length,
    extract_release,
    infer_element_name,
)
from autosar_langgraph.prompts import TRANSLATOR_SYSTEM_PROMPT
from autosar_langgraph.state import AutosarElement, AutosarState, SpecTarget, TranslationResult

logger = logging.getLogger(__name__)

_REQUIRED_ITEMS = {
    "SystemSignal": ["mandatory attributes", "constraints", "related ISignal mapping rules"],
    "ISignal": ["mandatory attributes", "constraints", "SystemSignal reference rules"],
    "SoftwareComponent": ["mandatory attributes", "ports", "constraints"],
    "Port": ["mandatory attributes", "direction", "interface reference rules"],
    "DataType": ["mandatory attributes", "constraints", "category rules"],
    "Interface": ["mandatory attributes", "data elements", "constraints"],
    "Pdu": ["mandatory attributes", "constraints", "signal mapping rules"],
    "Runnable": ["mandatory attributes", "constraints", "data access points"],
}


def translate_request(user_request: str, requested_release: Optional[str]) -> TranslationResult:
    """
    Map a request to AUTOSAR elements without calling an LLM.

    Args:
        user_request: Natural-language request.
        requested_release: Release supplied by the caller, if any.

    Returns:
        A translation result with elements and spec targets.
    """
    release = requested_release or extract_release(user_request)
    detected = detect_element_kinds(user_request)
    missing: List[str] = []
    ambiguities: List[str] = []
    if release is None:
        missing.append("AUTOSAR release")
        release = ""
    if not detected:
        missing.append("AUTOSAR element kind")
        ambiguities.append("No AUTOSAR element kind was recognized in the request.")

    bit_length = extract_bit_length(user_request)
    elements: List[AutosarElement] = []
    for kind, document in detected:
        name = _name_for_kind(kind, user_request)
        attributes = _attributes_for(kind, user_request, bit_length)
        if kind in {"SystemSignal", "ISignal", "Signal"} and bit_length is None:
            missing.append(f"bit length for {name}")
        elements.append(
            AutosarElement(
                name=name,
                kind=kind,  # type: ignore[arg-type]
                autosar_release=release,
                attributes=attributes,
                confidence=0.7,
                notes="Rule-based translation. Confirm with an LLM before generating artifacts.",
                spec_targets=[
                    SpecTarget(
                        autosar_release=release,
                        document=document,
                        chapter_or_section=kind if kind != "DataType" else "ApplicationDataType",
                        meta_model_element=kind,
                        required_items=list(_REQUIRED_ITEMS.get(kind, ["mandatory attributes", "constraints"])),
                        keywords=_keywords(kind, name),
                    )
                ],
            )
        )

    if len(elements) > 1:
        ambiguities.append("Request mentions more than one AUTOSAR element; each was emitted separately.")

    names = ", ".join(f"{element.kind}:{element.name}" for element in elements) or "none"
    summary = f"Translated request to {names} for release {release or 'unspecified'}."
    return TranslationResult(
        elements=elements,
        translation_summary=summary,
        ambiguities=_unique(ambiguities),
        missing_information=_unique(missing),
    )


def translator_node(state: AutosarState, llm_client: object | None = None) -> AutosarState:
    """
    Produce elements and aggregated spec targets from the user request.

    Args:
        state: Current workflow state. Intent may already hold a release.
        llm_client: Optional client with an extract method. Rule-based translation
            is used when the client is missing or fails.

    Returns:
        A new state containing elements, spec_targets, and translation notes.
    """
    updated = state.model_copy(deep=True)
    release = state.requested_autosar_release
    result = _translate_with_client(state.user_request, release, llm_client, updated.errors)
    updated.elements = result.elements
    updated.translation_summary = result.translation_summary
    updated.ambiguities = result.ambiguities
    updated.missing_information = result.missing_information
    updated.spec_targets = [target for element in result.elements for target in element.spec_targets]
    updated.current_node = "autosar_translator"
    return updated


def _translate_with_client(
    user_request: str,
    release: Optional[str],
    llm_client: object | None,
    errors: List[str],
) -> TranslationResult:
    """Try structured LLM extraction, then fall back to the rule-based translator."""
    if llm_client is None or not hasattr(llm_client, "extract"):
        return translate_request(user_request, release)
    try:
        extracted = llm_client.extract(  # type: ignore[attr-defined]
            system_prompt=TRANSLATOR_SYSTEM_PROMPT,
            payload={"user_request": user_request, "requested_autosar_release": release},
            response_model=TranslationResult,
        )
    except Exception as exc:
        logger.warning("Translator LLM failed; using rule-based translation: %s", exc)
        errors.append(f"translator_llm_failed: {exc}")
        return translate_request(user_request, release)
    if isinstance(extracted, TranslationResult):
        return extracted
    return TranslationResult.model_validate(extracted)


def _name_for_kind(kind: str, user_request: str) -> str:
    """Choose an element name, with a kind-specific fallback."""
    fallback = {
        "SoftwareComponent": "RequestedSoftwareComponent",
        "Port": "RequestedPort",
        "DataType": "RequestedDataType",
        "ISignal": "RequestedISignal",
        "SystemSignal": "RequestedSystemSignal",
    }.get(kind, "RequestedElement")
    return infer_element_name(user_request, fallback)


def _attributes_for(kind: str, user_request: str, bit_length: Optional[int]) -> dict:
    """Collect attributes that are explicit in the request."""
    attributes: dict = {}
    if bit_length is not None and kind in {"SystemSignal", "ISignal", "Signal", "Pdu"}:
        attributes["length"] = bit_length
    if kind == "Port" and "required" in user_request.lower():
        attributes["direction"] = "required"
    return attributes


def _keywords(kind: str, name: str) -> List[str]:
    """Build retrieval keywords from the kind and the element name."""
    split_name = []
    current = []
    for character in name:
        if character.isupper() and current:
            split_name.append("".join(current))
            current = [character]
        else:
            current.append(character)
    if current:
        split_name.append("".join(current))
    return [kind, name, *split_name]


def _unique(items: List[str]) -> List[str]:
    """Preserve order while dropping duplicate strings."""
    seen = set()
    unique: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
