"""Specification agent that collects version-specific AUTOSAR items."""

import logging
import re
from typing import List

from pydantic import ValidationError

from autosar_langgraph.prompts import SPEC_AGENT_SYSTEM_PROMPT
from autosar_langgraph.retrieval import SpecRetriever
from autosar_langgraph.state import AutosarState, CollectedSpecItem, SpecTarget

logger = logging.getLogger(__name__)

_CONSTRAINT_PATTERN = re.compile(r"\[[^\]]*(?:constr|req)[^\]]*\][^\n]*", re.IGNORECASE)
_MANDATORY_PATTERN = re.compile(r"^[-*]\s+(.+?\(mandatory\).*)$", re.IGNORECASE | re.MULTILINE)


class SpecExtractionError(Exception):
    """Raised when specification extraction fails for one target."""


def build_collected_spec_item(target: SpecTarget, chunks: List[str]) -> CollectedSpecItem:
    """
    Build a spec item from retrieved chunks without calling an LLM.

    Args:
        target: Specification target that produced the chunks.
        chunks: Retrieved specification text. May be empty.

    Returns:
        A CollectedSpecItem. Empty input yields an explicit not-found summary.
    """
    if not chunks:
        return CollectedSpecItem(
            source_document=target.document,
            release=target.autosar_release,
            section=target.chapter_or_section,
            content_summary="No matching specification content found.",
        )

    combined = "\n".join(chunks)
    constraints = _unique(_CONSTRAINT_PATTERN.findall(combined))
    mandatory = _unique(match.strip() for match in _MANDATORY_PATTERN.findall(combined))
    related = _related_lines(combined)
    summary = _summary(chunks)
    return CollectedSpecItem(
        source_document=target.document,
        release=target.autosar_release,
        section=target.chapter_or_section,
        content_summary=summary,
        raw_excerpt=chunks[0][:500],
        constraints=constraints,
        mandatory_attributes=mandatory,
        related_requirements=related,
    )


def collect_specs_for_target(
    target: SpecTarget,
    retriever: SpecRetriever,
    llm_client: object | None = None,
) -> CollectedSpecItem:
    """
    Retrieve relevant chunks and extract a CollectedSpecItem for one SpecTarget.

    Args:
        target: The specification target produced by the Translator.
        retriever: Component that returns version-filtered chunks.
        llm_client: Optional LLM interface used for structured extraction.

    Returns:
        A CollectedSpecItem populated from the retrieved content.

    Raises:
        SpecExtractionError: When the LLM client fails after chunks were retrieved.
    """
    validated = target if isinstance(target, SpecTarget) else SpecTarget.model_validate(target)
    chunks = retriever.search(
        release=validated.autosar_release,
        document=validated.document,
        meta_model_element=validated.meta_model_element,
        keywords=validated.keywords,
    )
    if not chunks or llm_client is None or not hasattr(llm_client, "extract"):
        return build_collected_spec_item(validated, chunks)

    try:
        extracted = llm_client.extract(  # type: ignore[attr-defined]
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
    llm_client: object | None = None,
) -> AutosarState:
    """
    Fill collected_spec_items from spec_targets.

    Args:
        state: Current workflow state containing spec_targets.
        retriever: Spec chunk retriever.
        llm_client: Optional LLM client for extraction.

    Returns:
        Updated state with collected_spec_items populated.
    """
    updated = state.model_copy(deep=True)
    collected: List[CollectedSpecItem] = []
    for raw_target in _targets_from_state(state):
        try:
            target = raw_target if isinstance(raw_target, SpecTarget) else SpecTarget.model_validate(raw_target)
            collected.append(collect_specs_for_target(target, retriever, llm_client))
        except (ValidationError, SpecExtractionError) as exc:
            logger.warning("Skipping spec target: %s", exc)
            updated.errors.append(str(exc))
    updated.collected_spec_items = collected
    updated.current_node = "specs_agent"
    return updated


def _targets_from_state(state: AutosarState) -> List[SpecTarget]:
    """Prefer aggregated spec_targets, otherwise read them from elements."""
    if state.spec_targets:
        return list(state.spec_targets)
    targets: List[SpecTarget] = []
    for element in state.elements:
        targets.extend(element.spec_targets)
    return targets


def _summary(chunks: List[str]) -> str:
    """Use the first descriptive lines as a short summary."""
    lines = []
    for line in chunks[0].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("[release=") or stripped.endswith("]"):
            continue
        if stripped.startswith(("-", "*")) or stripped.lower() in {"attributes:", "constraints:", "related:"}:
            continue
        lines.append(stripped)
        if len(lines) == 2:
            break
    return " ".join(lines) if lines else "Specification chunks were retrieved."


def _related_lines(text: str) -> List[str]:
    """Collect short 'see also' or mapping sentences."""
    related = []
    for line in text.splitlines():
        lowered = line.lower()
        if "mapped to" in lowered or lowered.startswith("see also"):
            related.append(line.strip())
    return _unique(related)


def _unique(items: List[str]) -> List[str]:
    """Preserve order while dropping duplicates."""
    seen = set()
    unique: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
