"""Small parsers shared by the intent and translator nodes."""

import re
from typing import List, Optional, Tuple

_RELEASE_PATTERN = re.compile(
    r"\b(R\d{2}-\d{2}|\d{2}-\d{2}|\d+\.\d+\.\d+)\b",
    re.IGNORECASE,
)
_BIT_LENGTH_PATTERN = re.compile(r"\b(\d+)\s*-?\s*bits?\b", re.IGNORECASE)
_NAME_AFTER_PATTERN = re.compile(
    r"\b(?:type|named|called|for)\s+([A-Za-z][\w .-]{0,48})",
    re.IGNORECASE,
)
_STOP_WORDS = {"a", "an", "the", "autosar", "in", "of", "with", "according"}

_KIND_RULES: Tuple[Tuple[str, str, str], ...] = (
    ("ISignal", r"\bi-?signals?\b", "AUTOSAR_TPS_SystemTemplate"),
    ("SystemSignal", r"\bsignals?\b", "AUTOSAR_TPS_SystemTemplate"),
    ("SoftwareComponent", r"\b(?:software\s+components?|swcs?)\b", "AUTOSAR_TPS_SoftwareComponentTemplate"),
    ("Port", r"\bports?\b", "AUTOSAR_TPS_SoftwareComponentTemplate"),
    ("Interface", r"\binterfaces?\b", "AUTOSAR_TPS_SoftwareComponentTemplate"),
    ("DataType", r"\b(?:application\s+)?data\s+types?\b", "AUTOSAR_TPS_SoftwareComponentTemplate"),
    ("Pdu", r"\bpdus?\b", "AUTOSAR_TPS_SystemTemplate"),
    ("Runnable", r"\brunnables?\b", "AUTOSAR_TPS_SoftwareComponentTemplate"),
)


def extract_release(text: str) -> Optional[str]:
    """
    Return the first AUTOSAR release token found in text.

    Args:
        text: Natural-language request.

    Returns:
        A release such as ``20-11``, ``R22-11``, or ``4.4.0``, or None.
    """
    match = _RELEASE_PATTERN.search(text)
    if match is None:
        return None
    token = match.group(1)
    if token[:1].upper() == "R" and "-" in token:
        return "R" + token[1:]
    return token


def extract_bit_length(text: str) -> Optional[int]:
    """
    Return a bit length mentioned in text.

    Args:
        text: Natural-language request.

    Returns:
        The integer bit length, or None when it is absent.
    """
    match = _BIT_LENGTH_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group(1))


def infer_element_name(text: str, fallback: str) -> str:
    """
    Infer a short PascalCase element name from the request.

    Args:
        text: Natural-language request.
        fallback: Name used when no candidate phrase is found.

    Returns:
        A PascalCase identifier.
    """
    match = _NAME_AFTER_PATTERN.search(text)
    if match is None:
        return fallback
    phrase = _BIT_LENGTH_PATTERN.sub("", match.group(1))
    phrase = re.split(r"\b(?:according|in|with)\b", phrase, maxsplit=1, flags=re.IGNORECASE)[0]
    parts = [part for part in re.split(r"[\s._-]+", phrase) if part]
    words = [part for part in parts if part.lower() not in _STOP_WORDS and part.isalpha()]
    if not words:
        return fallback
    return "".join(word[:1].upper() + word[1:] for word in words)


def detect_element_kinds(text: str) -> List[Tuple[str, str]]:
    """
    Detect AUTOSAR element kinds mentioned in text.

    Args:
        text: Natural-language request.

    Returns:
        Pairs of ``(kind, document)``. ISignal is preferred over a generic signal.
    """
    found: List[Tuple[str, str]] = []
    isignal_present = re.search(r"\bi-?signals?\b", text, re.IGNORECASE) is not None
    for kind, pattern, document in _KIND_RULES:
        if kind == "SystemSignal" and isignal_present:
            continue
        if re.search(pattern, text, re.IGNORECASE):
            found.append((kind, document))
    return found


def classify_request(text: str) -> str:
    """
    Classify a request into a small set of workflow types.

    Args:
        text: Natural-language request.

    Returns:
        A request type such as ``create_signal`` or ``unknown``.
    """
    lowered = text.lower()
    if "map" in lowered and "signal" in lowered:
        return "map_signal"
    if re.search(r"\bi-?signals?\b|\bsignals?\b", lowered):
        return "create_signal"
    if re.search(r"software\s+component|\bswc\b", lowered):
        return "create_swc"
    if "interface" in lowered:
        return "define_interface"
    return "unknown"
