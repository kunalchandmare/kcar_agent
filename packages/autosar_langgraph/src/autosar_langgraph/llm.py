"""Ollama-backed structured LLM used by every phase-1 node."""

import json
import os
from typing import Any, Protocol

from pydantic import BaseModel

DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


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


class OllamaError(RuntimeError):
    """Raised when the Ollama server cannot complete a structured call."""


class OllamaStructuredLLM:
    """LangChain ChatOllama wrapper. The model must be pulled in Ollama already."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
        self.temperature = temperature
        self._chat = _build_chat(self.model, self.base_url, temperature)

    def extract(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[BaseModel],
    ) -> BaseModel:
        """
        Ask Ollama for one structured object.

        Args:
            system_prompt: Role instructions for this node.
            payload: JSON-serialisable input for the node.
            response_model: Pydantic class the model must fill.

        Returns:
            An instance of response_model.

        Raises:
            OllamaError: When Ollama is unreachable or the payload is not the expected model.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            structured = self._chat.with_structured_output(response_model)
            result = structured.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=json.dumps(payload, indent=2)),
                ]
            )
        except Exception as exc:
            raise OllamaError(
                f"Ollama call failed for model {self.model} at {self.base_url}: {exc}"
            ) from exc
        if isinstance(result, response_model):
            return result
        if result is None:
            raise OllamaError(f"Ollama returned no structured {response_model.__name__}")
        return response_model.model_validate(result)


def _build_chat(model: str, base_url: str, temperature: float) -> Any:
    """Import ChatOllama lazily so tests can inject a fake client."""
    from langchain_ollama import ChatOllama

    return ChatOllama(model=model, base_url=base_url, temperature=temperature)
