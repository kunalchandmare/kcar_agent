# AUTOSAR Spec Chunking Strategy

**Author:** Chandmare, Kunal  
**Created:** 2026-10-21  
**Purpose:** Practical chunking strategy for feeding version-specific AUTOSAR specifications (e.g. SystemTemplate_TPS 20-11) into a Spec Agent via RAG.  
**Focus example:** SystemSignal

## Concepts Used

| Concept | Why we use it | Why it is better than common alternatives |
|---------|---------------|-------------------------------------------|
| **Hierarchical / structure-aware chunking** | AUTOSAR documents are organized by chapters, sections, and meta-model elements. We chunk along these natural boundaries. | Better than fixed-size (e.g. 500-token) chunking, which splits tables, constraints, or definitions mid-sentence and destroys meaning. |
| **Semantic / logical-unit chunking** | Each chunk covers one coherent idea (definition + attributes, or constraints, or related elements). | Better than pure page- or paragraph-based splitting, which often mixes unrelated content or cuts related rules apart. |
| **Rich metadata filtering** | Every chunk carries `release`, `document`, `section`, `meta_model_element`, `chunk_type`. Retrieval can filter exactly (e.g. only 20-11 SystemSignal). | Better than plain vector search alone, which can return chunks from the wrong release or wrong document. |
| **Parent-context headers** | Each chunk starts with a short header that repeats the section title and key identifiers. | Better than raw chunks with no context; the Spec Agent can always cite the correct section. |
| **Light overlap only when needed** | Overlap is used only when a large section must be split. | Better than heavy overlapping windows (costly and redundant) or zero overlap (risk of losing boundary context). |

These choices follow standard RAG best practices for technical standards: preserve document structure, attach filterable metadata, and keep chunks self-contained for extraction tasks.

## Chunking Rules (Summary)

1. Parse the document outline first (chapter → section → subsection).
2. Prefer one chunk per logical meta-model element or coherent subsection.
3. Target size: **400–1200 tokens**.
4. Never split a table, a single constraint, or a requirement ID across chunks.
5. Attach mandatory metadata to every chunk:
   - `release` (e.g. `"20-11"`)
   - `document` (e.g. `"AUTOSAR_TPS_SystemTemplate"`)
   - `section` (e.g. `"7.3.2 SystemSignal"`)
   - `meta_model_element` (e.g. `"SystemSignal"`)
   - `chunk_type` (`definition` \| `attributes` \| `constraints` \| `examples` \| `related`)
   - `keywords`
6. Add a short parent-context header at the start of each chunk.
7. Use light overlap (50–100 tokens) only when splitting an oversized section.

## Example: SystemSignal

### Simple user prompt (what the Translator / Spec Agent receives)

```text
Create a Signal for vehicle speed, 16-bit, in AUTOSAR 20-11.
```

This is turned by the Translator into a `SpecTarget` similar to:

```json
{
  "autosar_release": "20-11",
  "document": "AUTOSAR_TPS_SystemTemplate",
  "chapter_or_section": "SystemSignal",
  "meta_model_element": "SystemSignal",
  "required_items": ["mandatory attributes", "constraints", "related ISignal mapping rules"],
  "keywords": ["SystemSignal", "length", "SystemSignalGroup"]
}
```

### Source fragment (simplified illustration of typical System Template content)

```text
7.3.2 SystemSignal

A SystemSignal represents a signal in the system view.

Attributes:
- shortName: Identifier
- length: Length of the signal in bits (mandatory)
- systemSignalGroup: Optional reference to a group

Constraints:
[constr_1234] The length of a SystemSignal shall be greater than 0.
[constr_1235] If a SystemSignal is part of a SystemSignalGroup, its length must be consistent with the group definition.

Related:
SystemSignal can be mapped to ISignal in the communication view.
```

### Resulting chunks

**Chunk 1 – Definition + core attributes**  
*(chunk_type: definition)*

```text
[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | section=7.3.2 SystemSignal | meta_model_element=SystemSignal | chunk_type=definition]

7.3.2 SystemSignal
A SystemSignal represents a signal in the system view.

Attributes:
- shortName: Identifier
- length: Length of the signal in bits (mandatory)
- systemSignalGroup: Optional reference to a group
```

**Chunk 2 – Constraints**  
*(chunk_type: constraints)*

```text
[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | section=7.3.2 SystemSignal | meta_model_element=SystemSignal | chunk_type=constraints]

7.3.2 SystemSignal – Constraints
[constr_1234] The length of a SystemSignal shall be greater than 0.
[constr_1235] If a SystemSignal is part of a SystemSignalGroup, its length must be consistent with the group definition.
```

**Chunk 3 – Related elements**  
*(chunk_type: related)*

```text
[release=20-11 | document=AUTOSAR_TPS_SystemTemplate | section=7.3.2 SystemSignal | meta_model_element=SystemSignal | chunk_type=related]

7.3.2 SystemSignal – Related
SystemSignal can be mapped to ISignal in the communication view.
See also: ISignal, SystemSignalGroup.
```

### How retrieval uses these chunks

The Spec Agent (or its retrieval tool) filters on:

- `release == "20-11"`
- `document == "AUTOSAR_TPS_SystemTemplate"`
- `meta_model_element == "SystemSignal"`

It receives Chunk 1 + Chunk 2 (and optionally Chunk 3).  
The Spec Agent then extracts only from these chunks into a structured `CollectedSpecItem` (mandatory attributes, constraints, etc.) and cites the section.

## Why this is better than other common strategies (brief)

- **Fixed-size token chunking** (e.g. every 512 tokens with overlap): frequently cuts attribute tables or constraint lists in half → Spec Agent gets incomplete or confusing context.
- **Full-document or large-page stuffing**: exceeds practical context limits and is expensive; also mixes many unrelated meta-model elements.
- **Pure semantic search without metadata**: can return SystemSignal content from the wrong AUTOSAR release or from a different document (SWS vs TPS).
- **No parent headers**: Spec Agent cannot reliably cite the exact section.

The hierarchical + metadata approach keeps chunks meaningful, filterable by release and element, and cheap to retrieve.

## Next steps

1. Apply the same rules to other high-priority elements (ISignal, SenderReceiverInterface, ApplicationDataType, etc.).
2. Automate outline extraction + chunk generation from the official PDFs.
3. Store chunks in a vector store with the metadata fields above for filtered retrieval.
