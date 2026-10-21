"""Version-filtered retrieval of AUTOSAR specification chunks.

Phase 1 uses an in-memory list. TODO: replace it with a versioned vector index
of the real AUTOSAR specifications once those documents are available.
"""

from dataclasses import dataclass
from typing import Any, List, Protocol, Sequence


@dataclass(frozen=True)
class SpecChunk:
    """One indexed piece of an AUTOSAR specification."""

    release: str
    document: str
    section: str
    meta_model_element: str
    chunk_type: str
    text: str
    keywords: tuple[str, ...] = ()


class SpecRetriever(Protocol):
    """Interface for retrieving AUTOSAR specification chunks."""

    def search(
        self,
        release: str,
        document: str,
        meta_model_element: str,
        keywords: List[str],
        limit: int = 5,
    ) -> List[str]:
        """Return relevant text chunks for the given target."""
        ...


class InMemorySpecRetriever:
    """Retriever over an in-memory, metadata-filtered chunk list."""

    def __init__(self, chunks: Sequence[SpecChunk]) -> None:
        self._chunks = list(chunks)

    def search(
        self,
        release: str,
        document: str,
        meta_model_element: str,
        keywords: List[str],
        limit: int = 5,
    ) -> List[str]:
        """
        Return chunks for one release, document, and meta-model element.

        Args:
            release: AUTOSAR release, matched exactly.
            document: Specification document id, matched exactly.
            meta_model_element: Meta-model class name, matched case-insensitively.
            keywords: Optional terms used only to rank matches.
            limit: Maximum number of chunks to return.

        Returns:
            Chunk texts, highest keyword overlap first.
        """
        wanted = meta_model_element.casefold()
        keyword_set = {word.casefold() for word in keywords}
        ranked: List[tuple[int, str]] = []
        for chunk in self._chunks:
            if chunk.release != release or chunk.document != document:
                continue
            if chunk.meta_model_element.casefold() != wanted:
                continue
            overlap = sum(1 for word in chunk.keywords if word.casefold() in keyword_set)
            ranked.append((overlap, chunk.text))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [text for _, text in ranked[:limit]]


class VectorSpecRetriever:
    """Retriever backed by any store that exposes similarity_search."""

    def __init__(self, vector_store: Any) -> None:
        self._vector_store = vector_store

    def search(
        self,
        release: str,
        document: str,
        meta_model_element: str,
        keywords: List[str],
        limit: int = 5,
    ) -> List[str]:
        """
        Search chunks filtered by release, document, and meta-model element.

        Args:
            release: AUTOSAR release filter.
            document: Document id filter.
            meta_model_element: Meta-model class filter.
            keywords: Query terms. The element name is used when empty.
            limit: Maximum number of chunks.

        Returns:
            Page contents from the vector store.
        """
        query = " ".join(keywords) or meta_model_element
        documents = self._vector_store.similarity_search(
            query=query,
            filter={
                "release": release,
                "document": document,
                "meta_model_element": meta_model_element,
            },
            k=limit,
        )
        return [_page_text(document) for document in documents]


def _page_text(document: Any) -> str:
    """Read text from a LangChain-style document or a plain string."""
    if isinstance(document, str):
        return document
    page_content = getattr(document, "page_content", None)
    if isinstance(page_content, str):
        return page_content
    return str(document)


def default_spec_chunks() -> List[SpecChunk]:
    """
    Return a small curated corpus so the workflow can run without PDFs.

    Returns:
        Chunks for SystemSignal 20-11, ISignal R22-11, and ApplicationDataType 4.4.0.
    """
    return [
        SpecChunk(
            release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            section="7.3.2 SystemSignal",
            meta_model_element="SystemSignal",
            chunk_type="definition",
            keywords=("SystemSignal", "length", "shortName"),
            text=(
                "[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | "
                "section=7.3.2 SystemSignal | meta_model_element=SystemSignal]\n"
                "A SystemSignal represents a signal in the system view.\n"
                "Attributes:\n"
                "- shortName: Identifier (mandatory)\n"
                "- length: Length of the signal in bits (mandatory)\n"
                "- systemSignalGroup: Optional reference to a group"
            ),
        ),
        SpecChunk(
            release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            section="7.3.2 SystemSignal",
            meta_model_element="SystemSignal",
            chunk_type="constraints",
            keywords=("SystemSignal", "constraint", "length"),
            text=(
                "[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | "
                "section=7.3.2 SystemSignal | meta_model_element=SystemSignal]\n"
                "[constr_1234] The length of a SystemSignal shall be greater than 0.\n"
                "[constr_1235] If a SystemSignal is part of a SystemSignalGroup, "
                "its length must be consistent with the group definition."
            ),
        ),
        SpecChunk(
            release="20-11",
            document="AUTOSAR_TPS_SystemTemplate",
            section="7.3.2 SystemSignal",
            meta_model_element="SystemSignal",
            chunk_type="related",
            keywords=("SystemSignal", "ISignal"),
            text=(
                "[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | "
                "section=7.3.2 SystemSignal | meta_model_element=SystemSignal]\n"
                "SystemSignal can be mapped to ISignal in the communication view.\n"
                "See also: ISignal, SystemSignalGroup."
            ),
        ),
        SpecChunk(
            release="R22-11",
            document="AUTOSAR_TPS_SystemTemplate",
            section="ISignal",
            meta_model_element="ISignal",
            chunk_type="definition",
            keywords=("ISignal", "SystemSignal", "length"),
            text=(
                "[release=R22-11 | document=AUTOSAR_TPS_SystemTemplate | "
                "section=ISignal | meta_model_element=ISignal]\n"
                "An ISignal is the interaction-layer representation of a system signal.\n"
                "Attributes:\n"
                "- shortName: Identifier (mandatory)\n"
                "- length: Signal length in bits (mandatory)\n"
                "- systemSignal: Reference to the SystemSignal (mandatory)"
            ),
        ),
        SpecChunk(
            release="R22-11",
            document="AUTOSAR_TPS_SystemTemplate",
            section="ISignal",
            meta_model_element="ISignal",
            chunk_type="constraints",
            keywords=("ISignal", "constraint"),
            text=(
                "[release=R22-11 | document=AUTOSAR_TPS_SystemTemplate | "
                "section=ISignal | meta_model_element=ISignal]\n"
                "[constr_3082] An ISignal shall reference exactly one SystemSignal.\n"
                "[constr_3083] The ISignal length shall match the referenced SystemSignal length."
            ),
        ),
        SpecChunk(
            release="4.4.0",
            document="AUTOSAR_TPS_SoftwareComponentTemplate",
            section="ApplicationDataType",
            meta_model_element="DataType",
            chunk_type="definition",
            keywords=("ApplicationDataType", "DataType", "compuMethod"),
            text=(
                "[release=4.4.0 | document=AUTOSAR_TPS_SoftwareComponentTemplate | "
                "section=ApplicationDataType | meta_model_element=DataType]\n"
                "An ApplicationDataType describes data as seen by the application.\n"
                "Attributes:\n"
                "- shortName: Identifier (mandatory)\n"
                "- category: Application primitive category (mandatory)\n"
                "- compuMethod: Optional computation method"
            ),
        ),
        SpecChunk(
            release="4.4.0",
            document="AUTOSAR_TPS_SoftwareComponentTemplate",
            section="ApplicationDataType",
            meta_model_element="DataType",
            chunk_type="constraints",
            keywords=("ApplicationDataType", "constraint"),
            text=(
                "[release=4.4.0 | document=AUTOSAR_TPS_SoftwareComponentTemplate | "
                "section=ApplicationDataType | meta_model_element=DataType]\n"
                "[constr_2501] An ApplicationDataType shall have a category.\n"
                "A CompuMethod, when present, shall be consistent with the category."
            ),
        ),
    ]
