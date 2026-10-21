"""Tests for retrieval filtering, empty chunks, and the phase-1 workflow."""

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from autosar_langgraph.graph import run_workflow  # noqa: E402
from autosar_langgraph.nodes.specs import build_collected_spec_item, collect_specs_for_target  # noqa: E402
from autosar_langgraph.retrieval import InMemorySpecRetriever, default_spec_chunks  # noqa: E402
from autosar_langgraph.state import SpecTarget  # noqa: E402


class RetrievalTests(unittest.TestCase):
    """Release and document filters must not leak other specifications."""

    def setUp(self) -> None:
        self.retriever = InMemorySpecRetriever(default_spec_chunks())

    def test_filters_by_release_and_element(self) -> None:
        chunks = self.retriever.search(
            release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            meta_model_element="SystemSignal",
            keywords=["length"],
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all("20-11" in chunk for chunk in chunks))
        self.assertFalse(any("R22-11" in chunk for chunk in chunks))

    def test_other_release_does_not_match(self) -> None:
        chunks = self.retriever.search(
            release="R22-11",
            document="AUTOSAR_TPS_SystemTemplate",
            meta_model_element="SystemSignal",
            keywords=["SystemSignal"],
        )
        self.assertEqual(chunks, [])


class SpecItemTests(unittest.TestCase):
    """Empty retrieval must be explicit, not invented."""

    def test_empty_chunks_are_reported(self) -> None:
        target = SpecTarget(
            autosar_release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            meta_model_element="SystemSignal",
        )
        item = build_collected_spec_item(target, [])
        self.assertEqual(item.content_summary, "No matching specification content found.")
        self.assertEqual(item.constraints, [])

    def test_collect_extracts_constraints_and_mandatory_attributes(self) -> None:
        target = SpecTarget(
            autosar_release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            chapter_or_section="SystemSignal",
            meta_model_element="SystemSignal",
            keywords=["length", "SystemSignal"],
        )
        item = collect_specs_for_target(target, InMemorySpecRetriever(default_spec_chunks()))
        self.assertTrue(any("constr_1234" in constraint for constraint in item.constraints))
        self.assertTrue(any("length" in attribute.lower() for attribute in item.mandatory_attributes))
        self.assertEqual(item.release, "20-11")


class WorkflowTests(unittest.TestCase):
    """The orchestrated path must produce a spec-agent-ready state."""

    def test_vehicle_speed_signal_20_11(self) -> None:
        state = run_workflow("Create a Signal for vehicle speed, 16-bit, in AUTOSAR 20-11.")
        self.assertEqual(state.current_node, "specs_agent")
        self.assertEqual(len(state.elements), 1)
        element = state.elements[0]
        self.assertEqual(element.kind, "SystemSignal")
        self.assertEqual(element.name, "VehicleSpeed")
        self.assertEqual(element.autosar_release, "20-11")
        self.assertEqual(element.attributes["length"], 16)
        self.assertEqual(element.spec_targets[0].document, "AUTOSAR_TPS_SystemTemplate")
        self.assertIsNotNone(state.collected_spec_items)
        assert state.collected_spec_items is not None
        self.assertIn("constr_1234", " ".join(state.collected_spec_items[0].constraints))

    def test_isignal_keeps_r22_11(self) -> None:
        state = run_workflow(
            "I need a Software Component with a required port that receives an ISignal "
            "of type VehicleSpeed according to R22-11."
        )
        kinds = {element.kind for element in state.elements}
        self.assertIn("ISignal", kinds)
        self.assertNotIn("SystemSignal", kinds)
        self.assertTrue(all(element.autosar_release == "R22-11" for element in state.elements))
        isignal_items = [
            item
            for item in state.collected_spec_items or []
            if item.section == "ISignal"
        ]
        self.assertTrue(isignal_items)
        self.assertTrue(any("constr_3082" in text for text in isignal_items[0].constraints))

    def test_empty_request_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_workflow("   ")


if __name__ == "__main__":
    unittest.main()
