"""Helpers that only surface an explicit release token for the LLM payload."""

import re
from typing import Optional

_RELEASE_PATTERN = re.compile(
    r"\b(R\d{2}-\d{2}|\d{2}-\d{2}|\d+\.\d+\.\d+)\b",
    re.IGNORECASE,
)


def release_hint(text: str) -> Optional[str]:
    """
    Return a release token the user actually wrote.

    Args:
        text: Natural-language request.

    Returns:
        ``20-11``, ``R22-11``, ``4.4.0``, or None. This is a hint for the LLM,
        not a translation of the request.
    """
    match = _RELEASE_PATTERN.search(text)
    if match is None:
        return None
    token = match.group(1)
    if token[:1].upper() == "R" and "-" in token:
        return "R" + token[1:]
    return token
