"""Spec agent node: retrieve release-filtered chunks, then ask Ollama to extract them."""

import logging
import re
from typing import Any

from pydantic import ValidationError

from autosar_langgraph.llm import StructuredLLM
from autosar_langgraph.prompts import SPEC_AGENT_SYSTEM_PROMPT
from autosar_langgraph.retrieval import SpecRetriever
from autosar_langgraph.state import AutosarState, CollectedSpecItem, SpecTarget

logger = logging.getLogger(__name__)

_CONSTRAINT_PATTERN = re.compile(r"\[[^\]]*(?:constr|req)[^\]]*\][^\n]*", re.IGNORECASE)
_MANDATORY_PATTERN = re.compile(r"^[-*]\s+(.+?\(mandatory\).*)$", re.IGNORECASE | re.MULTILINE)


class SpecExtractionError(Exception):
    """Raised when specification extraction fails for one target."""


def empty_spec_item(target: SpecTarget, summary: str) -> CollectedSpecItem:
    """
    Build an explicit not-found item. The model is not asked to guess.

    Args:
        target: Specification target that produced no usable chunks.
        summary: Reason shown to the caller.

    Returns:
        A CollectedSpecItem with empty constraint lists.
    """
    return CollectedSpecItem(
        source_document=target.document,
        release=target.autosar_release,
        section=target.chapter_or_section,
        content_summary=summary,
    )


def collect_specs_for_target(
    target: SpecTarget,
    retriever: SpecRetriever,
    llm: StructuredLLM,
) -> CollectedSpecItem:
    """
    Retrieve chunks for one target and extract a CollectedSpecItem with the LLM.

    Args:
        target: Specification target produced by the Translator.
        retriever: Component that returns version-filtered chunks.
        llm: Structured LLM. Called only when chunks exist.

    Returns:
        A CollectedSpecItem populated from the retrieved content.

    Raises:
        SpecExtractionError: When the LLM fails after chunks were retrieved.
    """
    validated = target if isinstance(target, SpecTarget) else SpecTarget.model_validate(target)
    chunks = retriever.search(
        release=validated.autosar_release,
        document=validated.document,
        meta_model_element=validated.meta_model_element,
        keywords=validated.keywords,
    )
    if not chunks:
        return empty_spec_item(validated, "No matching specification content found.")

    try:
        extracted = llm.extract(
            system_prompt=SPEC_AGENT_SYSTEM_PROMPT,
            payload={
                "target": validated.model_dump(),
                "chunks": chunks,
                "required_items": validated.required_items,
            },
            response_model=CollectedSpecItem,
        )
    except Exception as exc:
        logger.warning("Spec extraction failed for %s: %s", validated.meta_model_element, exc)
        raise SpecExtractionError(str(exc)) from exc
    if isinstance(extracted, CollectedSpecItem):
        return extracted
    return CollectedSpecItem.model_validate(extracted)


def specs_agent_node(
    state: AutosarState,
    retriever: SpecRetriever,
    llm: StructuredLLM,
) -> dict[str, Any]:
    """
    Fill collected_spec_items from spec_targets.

    Args:
        state: Current LangGraph state containing spec_targets.
        retriever: Spec chunk retriever.
        llm: Structured LLM, Ollama in production.

    Returns:
        Partial state with collected_spec_items and current_node.
    """
    collected: list[dict[str, Any]] = []
    errors = list(state.get("errors") or [])
    for raw_target in _targets_from_state(state):
        try:
            target = raw_target if isinstance(raw_target, SpecTarget) else SpecTarget.model_validate(raw_target)
            item = collect_specs_for_target(target, retriever, llm)
            collected.append(item.model_dump())
        except (ValidationError, SpecExtractionError) as exc:
            logger.warning("Skipping spec target: %s", exc)
            errors.append(str(exc))
    return {
        "collected_spec_items": collected,
        "errors": errors,
        "current_node": "specs_agent",
    }


def _targets_from_state(state: AutosarState) -> list[Any]:
    """Prefer aggregated spec_targets, otherwise read them from elements."""
    if state.get("spec_targets"):
        return list(state["spec_targets"])
    targets: list[Any] = []
    for element in state.get("elements") or []:
        targets.extend(element.get("spec_targets") or [])
    return targets


def chunk_constraints(chunks: list[str]) -> list[str]:
    """
    Read constraint lines from retrieved chunks. Test helper and prompt context.

    Args:
        chunks: Retrieved specification text.

    Returns:
        Unique constraint lines, in order.
    """
    found = _CONSTRAINT_PATTERN.findall("\n".join(chunks))
    return list(dict.fromkeys(found))


def chunk_mandatory_attributes(chunks: list[str]) -> list[str]:
    """
    Read lines marked mandatory in retrieved chunks.

    Args:
        chunks: Retrieved specification text.

    Returns:
        Unique mandatory attribute lines, in order.
    """
    found = [match.strip() for match in _MANDATORY_PATTERN.findall("\n".join(chunks))]
    return list(dict.fromkeys(found))
