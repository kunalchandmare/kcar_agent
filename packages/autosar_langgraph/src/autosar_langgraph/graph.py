"""Sequential phase-1 workflow: intent, translator, spec agent."""

import logging
from typing import Optional

from autosar_langgraph.llm import RuleBasedLLM, StructuredLLM
from autosar_langgraph.nodes.intent import intent_node
from autosar_langgraph.nodes.specs import specs_agent_node
from autosar_langgraph.nodes.translator import translator_node
from autosar_langgraph.retrieval import InMemorySpecRetriever, SpecRetriever, default_spec_chunks
from autosar_langgraph.state import AutosarState

logger = logging.getLogger(__name__)


def run_workflow(
    user_request: str,
    *,
    requested_release: Optional[str] = None,
    retriever: Optional[SpecRetriever] = None,
    llm_client: Optional[StructuredLLM] = None,
) -> AutosarState:
    """
    Run the phase-1 AUTOSAR workflow on one user request.

    Args:
        user_request: Natural-language request.
        requested_release: Optional release override such as ``20-11``.
        retriever: Spec chunk retriever. Defaults to the curated in-memory corpus.
        llm_client: Structured LLM. Defaults to the offline rule-based client.

    Returns:
        The final workflow state, including elements and collected spec items.
    """
    if not user_request.strip():
        raise ValueError("user_request must not be empty")

    active_retriever = retriever or InMemorySpecRetriever(default_spec_chunks())
    active_llm = llm_client or RuleBasedLLM()
    state = AutosarState(
        user_request=user_request.strip(),
        requested_autosar_release=requested_release,
    )
    logger.info("Starting workflow for release %s", requested_release or "auto")
    state = intent_node(state)
    state = translator_node(state, active_llm)
    state = specs_agent_node(state, active_retriever, active_llm)
    logger.info("Workflow finished at node %s", state.current_node)
    return state
