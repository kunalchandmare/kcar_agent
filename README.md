# kcar_agent

Phase 1 of an AUTOSAR agent workflow. Later phases (planner, ARXML generation, validation) are not built yet.

## Goal

Turn one plain-language request into a version-aware AUTOSAR state.

```text
request -> intent -> translator -> spec agent -> JSON state
```

LangGraph runs the nodes. Every node calls an LLM through Ollama. The spec agent only reads chunks for the release named in the request.

## Run

Ollama must already be running and the model must be pulled.

```bash
pip install -r requirements.txt
ollama pull llama3.1
python orchestrate_kcar.py "Create a Signal for vehicle speed, 16-bit, in AUTOSAR 20-11."
```

Optional flags: `--release 20-11`, `--model llama3.1`, `--base-url http://127.0.0.1:11434`.

The same values can be set with `OLLAMA_MODEL` and `OLLAMA_BASE_URL`.

## Tests

```bash
python -m unittest packages/autosar_langgraph/tests/test_workflow.py
```

Tests use a fake LLM. They do not call Ollama.

## Not in this phase

- Action planner
- ARXML or code generation
- A validator
- A full AUTOSAR document index (the retriever still uses a small built-in chunk set)
