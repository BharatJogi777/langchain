# Text splitting and chunking

## Why chunk
Large documents can exceed model limits and blur topics. Splitting creates retrievable units. Chunk size and overlap are experimental parameters, not universal truths.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
docs = [Document(page_content="Long document text...", metadata={"document_id": "runbook-1", "source": "runbook.md"})]
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120, separators=["\n\n", "\n", ". ", " ", ""])
chunks = splitter.split_documents(docs)
for index, chunk in enumerate(chunks):
    chunk.metadata["chunk_index"] = index
    print(index, len(chunk.page_content), chunk.metadata)
```

By default chunk_size is measured by the configured length function, commonly characters—not tokens. Use a tokenizer-aware function or token splitter when token limits matter.

## Strategies
Recursive character; token-based; Markdown/header-aware; sentence/paragraph-aware; semantic; parent-child; code-aware; table-aware. Preserve section context, code syntax, table headers, and provenance.

## Overlap trade-off
Overlap preserves boundary context but increases storage, embedding cost, duplicate retrieval, and prompt tokens. Start modestly and measure.

## Metadata and IDs
Every chunk retains document ID/version, source, tenant scope, page/section, chunk index. Chunk index repeats across documents; use a unique chunk ID or unique constraint such as (document_id, document_version, chunk_index).

## Evaluation lab
Compare chunk sizes and strategies on a fixed set of questions. Measure Recall@k, Precision@k, MRR/nDCG, faithfulness, context tokens, latency, and cost.