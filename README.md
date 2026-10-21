# kcar_agent

Agentic workflow that turns a plain-language AUTOSAR request into a version-aware model and the matching specification items.

## Goal

Help an AUTOSAR project start from a sentence instead of a meta-model form.

1. Understand the request.
2. Translate it into AUTOSAR elements for one release (for example `20-11` or `R22-11`).
3. Collect the specification items for those elements: mandatory attributes, constraints, and related rules.

Phase 1 stops there. It does not generate ARXML.

The path is:

```text
request -> intent -> translator -> spec agent -> JSON state
```

## Run

Requires Python 3.10+ and `pydantic`.

```bash
pip install pydantic
python orchestrate_kcar.py "Create a Signal for vehicle speed, 16-bit, in AUTOSAR 20-11."
```

Optional release override:

```bash
python orchestrate_kcar.py "Create a required port for VehicleSpeed" --release R22-11
```

The command prints one JSON object. Important fields:

- `elements` — translated AUTOSAR elements
- `spec_targets` — what the spec agent should look up
- `collected_spec_items` — attributes and constraints that were found

## Tests

```bash
python -m unittest packages/autosar_langgraph/tests/test_workflow.py
```

## Layout

```text
orchestrate_kcar.py
packages/autosar_langgraph/src/autosar_langgraph/
  graph.py          workflow
  state.py          shared state
  nodes/            intent, translator, spec agent
  retrieval.py      release-filtered spec chunks
```

The default run is offline. It uses a small built-in chunk set and a rule-based translator. A real LLM or vector store can be passed into `run_workflow`.
