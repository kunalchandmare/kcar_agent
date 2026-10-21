"""LLM client protocol and a deterministic client for offline runs."""

from typing import Any, Protocol

from pydantic import BaseModel

from autosar_langgraph.nodes.specs import build_collected_spec_item
from autosar_langgraph.nodes.translator import translate_request
from autosar_langgraph.state import CollectedSpecItem, SpecTarget, TranslationResult


class StructuredLLM(Protocol):
    """Client that returns a Pydantic model instead of free text."""

    def extract(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Extract a response_model instance from payload."""
        ...


class RuleBasedLLM:
    """Offline stand-in that applies the same rules as the workflow nodes."""

    def extract(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[BaseModel],
    ) -> BaseModel:
        """
        Build a structured result without a network call.

        Args:
            system_prompt: Unused. Kept so the signature matches a real client.
            payload: Translator or spec-agent input.
            response_model: TranslationResult or CollectedSpecItem.

        Returns:
            An instance of response_model.

        Raises:
            TypeError: When response_model is not supported.
        """
        del system_prompt
        if response_model is TranslationResult:
            return translate_request(
                str(payload.get("user_request", "")),
                payload.get("requested_autosar_release"),
            )
        if response_model is CollectedSpecItem:
            target = SpecTarget.model_validate(payload["target"])
            chunks = list(payload.get("chunks") or [])
            return build_collected_spec_item(target, chunks)
        raise TypeError(f"Unsupported response model: {response_model.__name__}")
