"""Phase-1 graph tests. They inject a fake LLM so Ollama is not required."""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from pydantic import BaseModel  # noqa: E402

from autosar_langgraph.graph import build_workflow, run_workflow  # noqa: E402
from autosar_langgraph.nodes.specs import empty_spec_item  # noqa: E402
from autosar_langgraph.nodes.translator import normalize_translation  # noqa: E402
from autosar_langgraph.retrieval import InMemorySpecRetriever, PdfSpecCatalog, default_spec_chunks  # noqa: E402
from autosar_langgraph.state import (  # noqa: E402
    AutosarElement,
    CollectedSpecItem,
    IntentResult,
    SpecTarget,
    TranslationResult,
)


class FakeLLM:
    """Test double with the same extract contract as OllamaStructuredLLM."""

    def extract(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        response_model: type[BaseModel],
    ) -> BaseModel:
        del system_prompt
        if response_model is IntentResult:
            return IntentResult(
                request_type="create_signal",
                entities=["SystemSignal"],
                autosar_release=payload.get("release_hint"),
            )
        if response_model is TranslationResult:
            return _translation(str(payload.get("user_request", "")))
        if response_model is CollectedSpecItem:
            target = SpecTarget.model_validate(payload["target"])
            return _item_from_chunks(target, list(payload.get("chunks") or []))
        raise TypeError(response_model.__name__)


def _translation(user_request: str) -> TranslationResult:
    """Return a fixed translation so the graph can be tested without a model."""
    if "R22-11" in user_request:
        release = "R22-11"
        elements = [
            _element("RequestedSoftwareComponent", "SoftwareComponent", release, "AUTOSAR_TPS_SoftwareComponentTemplate"),
            _element("RequestedPort", "Port", release, "AUTOSAR_TPS_SoftwareComponentTemplate", {"direction": "required"}),
            _element("VehicleSpeed", "ISignal", release, "AUTOSAR_TPS_SystemTemplate"),
        ]
        return TranslationResult(
            elements=elements,
            translation_summary="Translated ISignal request for R22-11.",
        )
    release = "20-11"
    return TranslationResult(
        elements=[
            _element(
                "VehicleSpeed",
                "SystemSignal",
                release,
                "AUTOSAR_TPS_SystemTemplate",
                {"length": 16},
            )
        ],
        translation_summary="Translated SystemSignal VehicleSpeed for 20-11.",
    )


def _element(
    name: str,
    kind: str,
    release: str,
    document: str,
    attributes: dict | None = None,
) -> AutosarElement:
    section = "ApplicationDataType" if kind == "DataType" else kind
    return AutosarElement(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        autosar_release=release,
        attributes=attributes or {},
        spec_targets=[
            SpecTarget(
                autosar_release=release,
                document=document,
                chapter_or_section=section,
                meta_model_element=kind,
                required_items=["mandatory attributes", "constraints"],
                keywords=[kind, name],
            )
        ],
    )


def _item_from_chunks(target: SpecTarget, chunks: list[str]) -> CollectedSpecItem:
    """Mirror the spec prompt using only the supplied chunks."""
    from autosar_langgraph.nodes.specs import chunk_constraints, chunk_mandatory_attributes

    if not chunks:
        return empty_spec_item(target, "No matching specification content found.")
    related = [
        line.strip()
        for line in "\n".join(chunks).splitlines()
        if "mapped to" in line.lower() or line.lower().startswith("see also")
    ]
    return CollectedSpecItem(
        source_document=target.document,
        release=target.autosar_release,
        section=target.chapter_or_section,
        content_summary="Extracted from retrieved chunks only.",
        raw_excerpt=chunks[0][:500],
        constraints=chunk_constraints(chunks),
        mandatory_attributes=chunk_mandatory_attributes(chunks),
        related_requirements=related,
    )


class RetrievalTests(unittest.TestCase):
    """Release filters must not leak other specifications."""

    def test_filters_by_release(self) -> None:
        retriever = InMemorySpecRetriever(default_spec_chunks())
        chunks = retriever.search("20-11", "AUTOSAR_TPS_SystemTemplate", "SystemSignal", ["length"])
        self.assertTrue(chunks)
        self.assertTrue(all("20-11" in chunk for chunk in chunks))
        self.assertFalse(any("R22-11" in chunk for chunk in chunks))

    def test_catalog_picks_pdf_from_translator_document_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp) / "AUTOSAR_TPS_SystemTemplate_20-11.pdf"
            other = Path(tmp) / "AUTOSAR_TPS_SystemTemplate_R22-11.pdf"
            chosen.write_bytes(b"%PDF-1.4")
            other.write_bytes(b"%PDF-1.4")
            catalog = PdfSpecCatalog(tmp)
            self.assertEqual(catalog.resolve("20-11", "SystemTemplate"), chosen)
            self.assertEqual(catalog.resolve("R22-11", "AUTOSAR_TPS_SystemTemplate"), other)

    def test_single_system_template_pdf_is_used_without_release_in_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            only = Path(tmp) / "AUTOSAR_TPS_SystemTemplate.pdf"
            only.write_bytes(b"%PDF-1.4")
            catalog = PdfSpecCatalog(tmp)
            self.assertEqual(catalog.resolve("20-11", "AUTOSAR_TPS_SystemTemplate"), only)

    def test_translator_fills_document_the_spec_agent_can_select(self) -> None:
        result = TranslationResult(
            elements=[
                AutosarElement(
                    name="VehicleSpeed",
                    kind="SystemSignal",
                    autosar_release="",
                    spec_targets=[],
                )
            ]
        )
        normalized = normalize_translation(result, "20-11")
        target = normalized.elements[0].spec_targets[0]
        self.assertEqual(target.autosar_release, "20-11")
        self.assertEqual(target.document, "AUTOSAR_TPS_SystemTemplate")
        self.assertEqual(target.meta_model_element, "SystemSignal")


class WorkflowTests(unittest.TestCase):
    """The compiled graph is phase 1 and stops after the spec agent."""

    def test_graph_has_phase1_nodes_only(self) -> None:
        app = build_workflow(FakeLLM(), InMemorySpecRetriever(default_spec_chunks()))
        names = set(app.get_graph().nodes)
        self.assertTrue({"intent", "autosar_translator", "specs_agent"}.issubset(names))
        self.assertNotIn("planner", names)
        self.assertNotIn("generator", names)

    def test_vehicle_speed_signal_20_11(self) -> None:
        state = run_workflow(
            "Create a Signal for vehicle speed, 16-bit, in AUTOSAR 20-11.",
            llm=FakeLLM(),
        )
        self.assertEqual(state["current_node"], "specs_agent")
        self.assertEqual(state["elements"][0]["kind"], "SystemSignal")
        self.assertEqual(state["elements"][0]["name"], "VehicleSpeed")
        self.assertEqual(state["elements"][0]["autosar_release"], "20-11")
        self.assertEqual(state["elements"][0]["attributes"]["length"], 16)
        self.assertIn("constr_1234", " ".join(state["collected_spec_items"][0]["constraints"]))

    def test_isignal_keeps_r22_11(self) -> None:
        state = run_workflow(
            "I need a Software Component with a required port that receives an ISignal "
            "of type VehicleSpeed according to R22-11.",
            llm=FakeLLM(),
        )
        kinds = {element["kind"] for element in state["elements"]}
        self.assertIn("ISignal", kinds)
        self.assertNotIn("SystemSignal", kinds)
        self.assertTrue(all(element["autosar_release"] == "R22-11" for element in state["elements"]))
        isignal = next(item for item in state["collected_spec_items"] if item["section"] == "ISignal")
        self.assertTrue(any("constr_3082" in text for text in isignal["constraints"]))

    def test_empty_request_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_workflow("   ", llm=FakeLLM())

    def test_missing_chunks_do_not_invent_constraints(self) -> None:
        target = SpecTarget(
            autosar_release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            meta_model_element="SystemSignal",
        )
        item = empty_spec_item(target, "No matching specification content found.")
        self.assertEqual(item.constraints, [])
        self.assertEqual(item.content_summary, "No matching specification content found.")


if __name__ == "__main__":
    unittest.main()
