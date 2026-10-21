"""Command-line entry point for the KCAR AUTOSAR workflow."""

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


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI parser.

    Returns:
        A parser that accepts a request and an optional AUTOSAR release.
    """
    parser = argparse.ArgumentParser(
        description="Run the KCAR AUTOSAR translator and spec-agent workflow.",
    )
    parser.add_argument("request", help="Natural-language AUTOSAR request.")
    parser.add_argument(
        "--release",
        default=None,
        help="AUTOSAR release override, for example 20-11 or R22-11.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Run the workflow and write the JSON state to stdout.

    Args:
        argv: Optional argument list. Defaults to sys.argv.

    Returns:
        Process exit code. 0 on success, 1 on a handled failure.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        state = run_workflow(args.request, requested_release=args.release)
    except ValueError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
    json.dump(state.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
