"""Intent node: ask Ollama to structure the request, without translating it."""

import logging
from typing import Any

from autosar_langgraph.llm import StructuredLLM
from autosar_langgraph.parsing import release_hint
from autosar_langgraph.prompts import INTENT_SYSTEM_PROMPT
from autosar_langgraph.state import AutosarState, IntentResult

logger = logging.getLogger(__name__)


def intent_node(state: AutosarState, llm: StructuredLLM) -> dict[str, Any]:
    """
    Fill intent from the user request via the configured LLM.

    Args:
        state: Current LangGraph state.
        llm: Structured LLM, Ollama in production.

    Returns:
        Partial state with intent, messages, and current_node.
    """
    request = state["user_request"]
    hint = state.get("requested_autosar_release") or release_hint(request)
    errors = list(state.get("errors") or [])
    try:
        result = llm.extract(
            system_prompt=INTENT_SYSTEM_PROMPT,
            payload={"user_request": request, "release_hint": hint},
            response_model=IntentResult,
        )
        if not isinstance(result, IntentResult):
            result = IntentResult.model_validate(result)
        intent = result.model_dump()
    except Exception as exc:
        logger.warning("Intent LLM failed; keeping the explicit release hint: %s", exc)
        intent = {"request_type": "unknown", "entities": [], "autosar_release": hint, "notes": "LLM unavailable."}
        if hint is None:
            errors.append(f"intent_llm_failed: {exc}")

    release = hint
    if isinstance(intent, dict) and intent.get("autosar_release"):
        release = intent["autosar_release"]
    return {
        "intent": intent,
        "requested_autosar_release": release,
        "errors": errors,
        "messages": list(state.get("messages") or []) + [{"role": "user", "content": request}],
        "current_node": "intent",
    }
