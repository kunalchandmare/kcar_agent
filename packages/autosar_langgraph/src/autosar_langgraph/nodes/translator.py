"""Translator node: Ollama maps the request into version-aware AUTOSAR elements."""

import logging
from typing import Any

from autosar_langgraph.llm import StructuredLLM
from autosar_langgraph.prompts import TRANSLATOR_SYSTEM_PROMPT
from autosar_langgraph.state import AutosarState, TranslationResult

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
            },
            response_model=TranslationResult,
        )
        result = extracted if isinstance(extracted, TranslationResult) else TranslationResult.model_validate(extracted)
    except Exception as exc:
        logger.warning("Translator LLM failed: %s", exc)
        errors.append(f"translator_llm_failed: {exc}")
        result = TranslationResult(
            translation_summary="Translation failed. No elements were invented.",
            missing_information=["translator output"],
        )

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
