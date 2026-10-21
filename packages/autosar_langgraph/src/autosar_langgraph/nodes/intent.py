"""Lightweight intent structuring before AUTOSAR translation."""

from autosar_langgraph.parsing import classify_request, detect_element_kinds, extract_release
from autosar_langgraph.state import AutosarState


def intent_node(state: AutosarState) -> AutosarState:
    """
    Fill intent with request type, element kinds, and any explicit release.

    Args:
        state: Current workflow state.

    Returns:
        A new state whose intent and current_node are updated.
    """
    request = state.user_request
    release = state.requested_autosar_release or extract_release(request)
    kinds = [kind for kind, _document in detect_element_kinds(request)]
    updated = state.model_copy(deep=True)
    updated.intent = {
        "request_type": classify_request(request),
        "entities": kinds,
        "autosar_release": release,
    }
    updated.requested_autosar_release = release
    updated.current_node = "intent"
    updated.messages.append({"role": "user", "content": request})
    return updated
