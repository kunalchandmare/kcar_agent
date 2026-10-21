"""Phase-1 LangGraph: intent -> translator -> spec agent.

Later phases are not wired yet:
- TODO: action planner node, once the translator state is reliable
- TODO: ARXML / artifact generator
- TODO: validator node against the collected spec items
- TODO: replace the in-memory chunk list with a versioned AUTOSAR index
- TODO: human confirmation interrupt before any file is written
"""

import logging
from typing import Optional

from langgraph.graph import END, START, StateGraph

from autosar_langgraph.llm import OllamaStructuredLLM, StructuredLLM
from autosar_langgraph.nodes.intent import intent_node
from autosar_langgraph.nodes.specs import specs_agent_node
from autosar_langgraph.nodes.translator import translator_node
from autosar_langgraph.retrieval import InMemorySpecRetriever, SpecRetriever, default_spec_chunks
from autosar_langgraph.state import AutosarState

logger = logging.getLogger(__name__)

PHASE = "phase-1"


def build_workflow(llm: StructuredLLM, retriever: SpecRetriever):
    """
    Compile the phase-1 graph.

    Args:
        llm: Structured LLM. Production uses OllamaStructuredLLM.
        retriever: Release-filtered specification retriever.

    Returns:
        A compiled LangGraph app.
    """
    builder = StateGraph(AutosarState)
    builder.add_node("intent", lambda state: intent_node(state, llm))
    builder.add_node("autosar_translator", lambda state: translator_node(state, llm))
    builder.add_node("specs_agent", lambda state: specs_agent_node(state, retriever, llm))
    builder.add_edge(START, "intent")
    builder.add_edge("intent", "autosar_translator")
    builder.add_edge("autosar_translator", "specs_agent")
    builder.add_edge("specs_agent", END)
    return builder.compile()


def initial_state(user_request: str, requested_release: Optional[str] = None) -> AutosarState:
    """
    Build the empty phase-1 state for one request.

    Args:
        user_request: Natural-language request. Must not be blank.
        requested_release: Optional release override such as ``20-11``.

    Returns:
        A fully populated AutosarState.

    Raises:
        ValueError: When user_request is empty.
    """
    if not user_request.strip():
        raise ValueError("user_request must not be empty")
    return {
        "user_request": user_request.strip(),
        "requested_autosar_release": requested_release,
        "intent": None,
        "elements": [],
        "translation_summary": "",
        "ambiguities": [],
        "missing_information": [],
        "spec_targets": [],
        "collected_spec_items": [],
        "current_node": "start",
        "errors": [],
        "messages": [],
    }


def run_workflow(
    user_request: str,
    *,
    requested_release: Optional[str] = None,
    retriever: Optional[SpecRetriever] = None,
    llm: Optional[StructuredLLM] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> AutosarState:
    """
    Run the phase-1 graph on one user request.

    Args:
        user_request: Natural-language request.
        requested_release: Optional release override.
        retriever: Spec retriever. Defaults to the small phase-1 corpus.
        llm: Structured LLM. Defaults to a local Ollama model.
        model: Ollama model name, used only when llm is omitted.
        base_url: Ollama server URL, used only when llm is omitted.

    Returns:
        The final LangGraph state.
    """
    active_retriever = retriever if retriever is not None else InMemorySpecRetriever(default_spec_chunks())
    active_llm = llm if llm is not None else OllamaStructuredLLM(model=model, base_url=base_url)
    app = build_workflow(active_llm, active_retriever)
    logger.info("Starting %s workflow", PHASE)
    return app.invoke(initial_state(user_request, requested_release))
