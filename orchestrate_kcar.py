"""Command-line entry point for the phase-1 KCAR LangGraph workflow."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

_SRC = Path(__file__).resolve().parent / "packages" / "autosar_langgraph" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from autosar_langgraph.graph import run_workflow  # noqa: E402
from autosar_langgraph.llm import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI parser.

    Returns:
        A parser for the request, release, and Ollama connection.
    """
    parser = argparse.ArgumentParser(
        description="Phase 1: translate an AUTOSAR request with LangGraph and Ollama.",
    )
    parser.add_argument("request", help="Natural-language AUTOSAR request.")
    parser.add_argument("--release", default=None, help="Release override, for example 20-11.")
    parser.add_argument("--model", default=None, help=f"Ollama model. Default: {DEFAULT_OLLAMA_MODEL}.")
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Ollama server. Default: {DEFAULT_OLLAMA_BASE_URL}.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Run the graph and write the JSON state to stdout.

    Args:
        argv: Optional argument list. Defaults to sys.argv.

    Returns:
        Process exit code. 0 on success, 1 on a handled failure.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        state = run_workflow(
            args.request,
            requested_release=args.release,
            model=args.model,
            base_url=args.base_url,
        )
    except ValueError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
    json.dump(state, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if not state.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
