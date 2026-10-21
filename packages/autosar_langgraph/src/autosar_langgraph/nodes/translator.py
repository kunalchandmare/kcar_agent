"""Translator node: Ollama maps the request into version-aware AUTOSAR elements."""

import logging
import re
from typing import Any

from autosar_langgraph.llm import StructuredLLM
from autosar_langgraph.parsing import release_hint
from autosar_langgraph.prompts import TRANSLATOR_SYSTEM_PROMPT
from autosar_langgraph.retrieval import KIND_TO_DOCUMENT, canonical_document
from autosar_langgraph.state import AutosarElement, AutosarState, SpecTarget, TranslationResult

logger = logging.getLogger(__name__)


def translator_node(state: AutosarState, llm: StructuredLLM) -> dict[str, Any]:
    """
    Produce elements and aggregated spec targets.

    Args:
        state: Current LangGraph state. Intent may already hold a release.
        llm: Structured LLM, Ollama in production.

    Returns:
        Partial state containing elements, spec_targets, and translation notes.
        On failure the element lists stay empty and the error is recorded.
    """
    errors = list(state.get("errors") or [])
    try:
        extracted = llm.extract(
            system_prompt=TRANSLATOR_SYSTEM_PROMPT,
            payload={
                "user_request": state["user_request"],
                "requested_autosar_release": state.get("requested_autosar_release"),
                "intent": state.get("intent"),
                "known_documents": sorted(set(KIND_TO_DOCUMENT.values())),
            },
            response_model=TranslationResult,
        )
        result = extracted if isinstance(extracted, TranslationResult) else TranslationResult.model_validate(extracted)
        result = normalize_translation(result, state.get("requested_autosar_release"))
    except Exception as exc:
        logger.warning("Translator LLM failed; using explicit request tokens: %s", exc)
        result = explicit_translation(
            state["user_request"],
            state.get("requested_autosar_release"),
        )
        if not result.elements:
            errors.append(f"translator_llm_failed: {exc}")

    return {
        "elements": [element.model_dump() for element in result.elements],
        "translation_summary": result.translation_summary,
        "ambiguities": result.ambiguities,
        "missing_information": result.missing_information,
        "spec_targets": [
            target.model_dump() for element in result.elements for target in element.spec_targets
        ],
        "errors": errors,
        "current_node": "autosar_translator",
    }


def normalize_translation(result: TranslationResult, release: str | None) -> TranslationResult:
    """
    Make every element carry a release and a PDF-selectable document id.

    Args:
        result: Raw translator output.
        release: Release already known from the request or intent.

    Returns:
        The same result with spec_targets filled and document ids canonical.
    """
    for element in result.elements:
        if not element.autosar_release and release:
            element.autosar_release = release
        if not element.spec_targets:
            element.spec_targets = [_target_for(element)]
        for target in element.spec_targets:
            if not target.autosar_release:
                target.autosar_release = element.autosar_release
            target.document = canonical_document(target.document, element.kind)
            if not target.meta_model_element:
                target.meta_model_element = element.kind
    return result


def _target_for(element: AutosarElement) -> SpecTarget:
    """Build the SpecTarget the spec agent uses to choose a PDF."""
    return SpecTarget(
        autosar_release=element.autosar_release,
        document=canonical_document("", element.kind),
        meta_model_element=element.kind,
        required_items=["mandatory attributes", "constraints"],
        keywords=[element.kind, element.name],
    )


_KIND_PATTERNS = (
    ("ISignal", re.compile(r"\bi-?signals?\b", re.IGNORECASE)),
    ("SystemSignal", re.compile(r"\bsignals?\b", re.IGNORECASE)),
    ("SoftwareComponent", re.compile(r"\b(?:software\s+components?|swcs?)\b", re.IGNORECASE)),
    ("Port", re.compile(r"\bports?\b", re.IGNORECASE)),
    ("DataType", re.compile(r"\b(?:application\s+)?data\s+types?\b", re.IGNORECASE)),
    ("Pdu", re.compile(r"\bpdus?\b", re.IGNORECASE)),
)
_BIT_LENGTH = re.compile(r"\b(\d+)\s*-?\s*bits?\b", re.IGNORECASE)
_NAME_AFTER = re.compile(r"\b(?:type|named|called|for)\s+([A-Za-z][\w .-]{0,48})", re.IGNORECASE)


def explicit_translation(user_request: str, requested_release: str | None) -> TranslationResult:
    """
    Build targets from release and element words the user actually wrote.

    Args:
        user_request: Natural-language request.
        requested_release: Release already known from intent, if any.

    Returns:
        A translation with spec targets, or an empty result when nothing was explicit.
    """
    release = requested_release or release_hint(user_request) or ""
    isignal = re.search(r"\bi-?signals?\b", user_request, re.IGNORECASE) is not None
    kinds = []
    for kind, pattern in _KIND_PATTERNS:
        if kind == "SystemSignal" and isignal:
            continue
        if pattern.search(user_request):
            kinds.append(kind)
    if not kinds or not release:
        return TranslationResult(
            translation_summary="Translation failed. No elements were invented.",
            missing_information=["translator output"] if not kinds else ["AUTOSAR release"],
        )

    bit_length = _BIT_LENGTH.search(user_request)
    name = _explicit_name(user_request)
    elements = []
    for kind in kinds:
        attributes = {}
        if bit_length and kind in {"SystemSignal", "ISignal", "Signal", "Pdu"}:
            attributes["length"] = int(bit_length.group(1))
        elements.append(
            AutosarElement(
                name=name,
                kind=kind,  # type: ignore[arg-type]
                autosar_release=release,
                attributes=attributes,
                notes="Built from explicit request tokens because the LLM was unavailable.",
                spec_targets=[
                    SpecTarget(
                        autosar_release=release,
                        document=canonical_document("", kind),
                        meta_model_element=kind,
                        required_items=["mandatory attributes", "constraints"],
                        keywords=[kind, name],
                    )
                ],
            )
        )
    names = ", ".join(f"{element.kind}:{element.name}" for element in elements)
    return TranslationResult(
        elements=elements,
        translation_summary=f"Translated explicit request to {names} for release {release}.",
    )


def _explicit_name(user_request: str) -> str:
    """Return a PascalCase name only when the request names one."""
    match = _NAME_AFTER.search(user_request)
    if match is None:
        return "RequestedElement"
    phrase = _BIT_LENGTH.sub("", match.group(1))
    words = [part for part in re.split(r"[\s._-]+", phrase) if part.isalpha()]
    if not words:
        return "RequestedElement"
    return "".join(word[:1].upper() + word[1:] for word in words)
