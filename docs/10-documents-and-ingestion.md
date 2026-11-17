# Document loaders and ingestion

## Document abstraction
A Document contains page_content and metadata. Metadata supports filtering, citations, reprocessing, and access control. Preserve source, document ID/version, page/section, tenant scope, timestamps, content hash, parser version, and embedding model.

## Ingestion lifecycle
Discover/upload → authenticate → validate type/size/malware → extract text → normalize → attach provenance and access metadata → split → embed → store idempotently → record status/errors → reprocess when source or embedding model changes.

```python
from pathlib import Path
from langchain_core.documents import Document
path = Path("data/handbook.txt")
text = path.read_text(encoding="utf-8")
doc = Document(page_content=text, metadata={"source": str(path), "document_id": "handbook-v1"})
print(doc.metadata, len(doc.page_content))
```

LangChain integrations provide loaders for PDF, DOCX, HTML, cloud storage, and more. Choose based on trust and file type. Sandbox parsers and restrict remote URL fetching. Do not trust client-supplied metadata for authorization; derive tenant from authenticated server identity.

## Operations
Use content hashes and idempotent upserts for duplicate uploads. Queue large files. Record parser failures and safe error codes. Deletion must cover originals, chunks, vectors, caches, and derived data. Version ingestion and avoid mixing embedding dimensions.

## Lab
Recursively ingest TXT files, compute SHA-256 hashes, attach metadata, skip unchanged files, and test duplicates and empty documents.