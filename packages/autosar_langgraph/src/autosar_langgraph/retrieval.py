"""Version-filtered retrieval of AUTOSAR specification chunks.

Phase 1 can use the built-in fixture or a directory of official PDFs.
The spec agent picks a PDF from the translator's release and document id.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, List, Optional, Protocol, Sequence


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
    source_pdf: str = ""


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


KIND_TO_DOCUMENT = {
    "SystemSignal": "AUTOSAR_TPS_SystemTemplate",
    "Signal": "AUTOSAR_TPS_SystemTemplate",
    "ISignal": "AUTOSAR_TPS_SystemTemplate",
    "Pdu": "AUTOSAR_TPS_SystemTemplate",
    "System": "AUTOSAR_TPS_SystemTemplate",
    "ECU": "AUTOSAR_TPS_SystemTemplate",
    "CommunicationCluster": "AUTOSAR_TPS_SystemTemplate",
    "SoftwareComponent": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "Port": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "Interface": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "DataElement": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "DataType": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "Runnable": "AUTOSAR_TPS_SoftwareComponentTemplate",
}

DOCUMENT_ALIASES = {
    "SYSTEMTEMPLATE": "AUTOSAR_TPS_SystemTemplate",
    "TPS_SYSTEMTEMPLATE": "AUTOSAR_TPS_SystemTemplate",
    "AUTOSAR_TPS_SYSTEMTEMPLATE": "AUTOSAR_TPS_SystemTemplate",
    "SOFTWARECOMPONENTTEMPLATE": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "TPS_SOFTWARECOMPONENTTEMPLATE": "AUTOSAR_TPS_SoftwareComponentTemplate",
    "AUTOSAR_TPS_SOFTWARECOMPONENTTEMPLATE": "AUTOSAR_TPS_SoftwareComponentTemplate",
}

_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z0-9]+)\s*$", re.MULTILINE)


class SpecPdfNotFound(FileNotFoundError):
    """No PDF matched the translator's document and release."""


def canonical_document(document: str, kind: str = "") -> str:
    """
    Map a translator document name onto the id used in the specs directory.

    Args:
        document: Name emitted by the translator. May be a short alias.
        kind: Meta-model kind, used when the document name is empty.

    Returns:
        A canonical document id such as ``AUTOSAR_TPS_SystemTemplate``.
    """
    key = re.sub(r"[^A-Za-z0-9]", "", document or "").upper()
    if key in DOCUMENT_ALIASES:
        return DOCUMENT_ALIASES[key]
    if not document and kind in KIND_TO_DOCUMENT:
        return KIND_TO_DOCUMENT[kind]
    return document or KIND_TO_DOCUMENT.get(kind, "")


class PdfSpecCatalog:
    """Pick and parse the PDF named by a translator SpecTarget."""

    def __init__(self, specs_dir: str | Path) -> None:
        self.specs_dir = Path(specs_dir)
        self._index = _index_pdfs(self.specs_dir)
        self._cache: dict[Path, list[SpecChunk]] = {}

    def available(self) -> list[tuple[str, str, str]]:
        """
        List indexed PDFs.

        Returns:
            Tuples of release, canonical document id, and path.
        """
        return [(release, document, str(path)) for (release, document), path in sorted(self._index.items())]

    def resolve(self, release: str, document: str) -> Optional[Path]:
        """
        Find the PDF for one release and document id.

        Args:
            release: AUTOSAR release from the translator.
            document: Document id from the translator.

        Returns:
            The matching path, or None.
        """
        wanted_doc = canonical_document(document)
        wanted_release = release.strip()
        exact = self._index.get((wanted_release, wanted_doc))
        if exact is not None:
            return exact
        same_document = [path for (found_release, found_doc), path in self._index.items() if found_doc == wanted_doc]
        if len(same_document) == 1:
            return same_document[0]
        return None

    def search(
        self,
        release: str,
        document: str,
        meta_model_element: str,
        keywords: List[str],
        limit: int = 5,
    ) -> List[str]:
        """
        Open the PDF selected by the translator and return matching sections.

        Args:
            release: Release on the SpecTarget.
            document: Document id on the SpecTarget.
            meta_model_element: Element to find inside that PDF.
            keywords: Optional ranking terms.
            limit: Maximum chunks.

        Returns:
            Chunk texts from the chosen PDF.

        Raises:
            SpecPdfNotFound: When the specs directory has no matching file.
        """
        path = self.resolve(release, document)
        if path is None:
            expected = f"{canonical_document(document)}_{release}.pdf"
            raise SpecPdfNotFound(
                f"No PDF for document {canonical_document(document)} release {release} "
                f"in {self.specs_dir}. Expected {expected}."
            )
        chunks = self._load(path, release, canonical_document(document))
        wanted = meta_model_element.casefold()
        keyword_set = {word.casefold() for word in keywords}
        ranked: list[tuple[int, SpecChunk]] = []
        for chunk in chunks:
            haystack = f"{chunk.section} {chunk.meta_model_element} {chunk.text}".casefold()
            if wanted and wanted not in haystack:
                continue
            overlap = sum(1 for word in chunk.keywords if word.casefold() in keyword_set)
            ranked.append((overlap, chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk.text for _, chunk in ranked[:limit]]

    def _load(self, path: Path, release: str, document: str) -> list[SpecChunk]:
        """Parse one PDF once and cache its chunks."""
        cached = self._cache.get(path)
        if cached is not None:
            return cached
        chunks = chunks_from_pdf(path, release=release, document=document)
        self._cache[path] = chunks
        return chunks


def chunks_from_pdf(path: str | Path, *, release: str, document: str) -> list[SpecChunk]:
    """
    Parse one AUTOSAR PDF into section chunks.

    Args:
        path: PDF path chosen from the specs directory.
        release: Release stored on every chunk.
        document: Canonical document id stored on every chunk.

    Returns:
        Chunks with a parent header so the spec agent can cite the file.

    Raises:
        RuntimeError: When pymupdf is not installed.
    """
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Install pymupdf to parse AUTOSAR specification PDFs.") from exc

    pdf_path = Path(path)
    doc = pymupdf.open(pdf_path)
    pages = [_page_body(page) for page in doc]
    sections = _sections_from_outline(doc.get_toc(), pages) or _sections_from_headings(pages)
    chunks: list[SpecChunk] = []
    for section, body in sections:
        element = _element_from_heading(section)
        header = (
            f"[release={release} | document={document} | section={section} | "
            f"meta_model_element={element} | source_pdf={pdf_path.name}]"
        )
        text = f"{header}\n\n{section}\n{body}".strip()
        chunks.append(
            SpecChunk(
                release=release,
                document=document,
                section=section,
                meta_model_element=element,
                chunk_type="definition",
                text=text,
                keywords=(element, section),
                source_pdf=str(pdf_path),
            )
        )
    return chunks


def _index_pdfs(specs_dir: Path) -> dict[tuple[str, str], Path]:
    """Index ``{document}_{release}.pdf`` and ``{release}/{document}.pdf``."""
    index: dict[tuple[str, str], Path] = {}
    if not specs_dir.is_dir():
        return index
    for path in specs_dir.rglob("*.pdf"):
        release, document = _ids_from_path(path, specs_dir)
        if release and document:
            index[(release, canonical_document(document))] = path
    return index


def _ids_from_path(path: Path, specs_dir: Path) -> tuple[str, str]:
    """Read release and document from a PDF path."""
    stem = path.stem
    parent = path.parent.name
    release_in_parent = _looks_like_release(parent)
    if release_in_parent:
        return parent, stem
    match = re.match(r"(.+?)_((?:R)?\d{2}-\d{2}|\d+\.\d+\.\d+)$", stem, re.IGNORECASE)
    if match:
        return _normalize_release(match.group(2)), match.group(1)
    return "*", stem


def _looks_like_release(value: str) -> bool:
    """Return True for folder names such as 20-11 or R22-11."""
    return re.fullmatch(r"(?:R)?\d{2}-\d{2}|\d+\.\d+\.\d+", value, re.IGNORECASE) is not None


def _normalize_release(value: str) -> str:
    """Keep R22-11 capitalised and leave 20-11 unchanged."""
    if value[:1].upper() == "R" and "-" in value:
        return "R" + value[1:]
    return value


def _page_body(page: Any) -> str:
    """Drop the header and footer bands from one page."""
    blocks = page.get_text("blocks")
    height = page.rect.height
    lines = [block[4].strip() for block in blocks if 60 < block[1] < height - 50 and block[4].strip()]
    return "\n".join(lines)


def _sections_from_outline(toc: list, pages: list[str]) -> list[tuple[str, str]]:
    """Cut the PDF on bookmark boundaries."""
    if not toc:
        return []
    sections = []
    for index, item in enumerate(toc):
        title = str(item[1]).strip()
        start = max(int(item[2]) - 1, 0)
        end = len(pages)
        if index + 1 < len(toc):
            end = max(int(toc[index + 1][2]) - 1, start + 1)
        body = "\n".join(pages[start:end]).strip()
        if title and body:
            sections.append((title, body))
    return sections


def _sections_from_headings(pages: list[str]) -> list[tuple[str, str]]:
    """Fall back to numbered headings when the PDF has no outline."""
    text = "\n".join(pages)
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [("document", text)] if text else []
    sections = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = f"{match.group(1)} {match.group(2)}"
        sections.append((title, text[start:end].strip()))
    return sections


def _element_from_heading(title: str) -> str:
    """Use the last CamelCase token in a heading as the meta-model element."""
    tokens = re.findall(r"[A-Z][A-Za-z0-9]+", title)
    return tokens[-1] if tokens else title

