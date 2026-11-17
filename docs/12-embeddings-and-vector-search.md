# Embeddings and vector search

## Embeddings
An embedding model maps text into a numeric vector. Similar meanings may map nearby, but similarity is not truth or authorization. Use the same embedding model and preprocessing for documents and queries. Record model/version/dimensions and normalization assumptions.

```python
from langchain_ollama import OllamaEmbeddings
embeddings = OllamaEmbeddings(model="nomic-embed-text")
query_vector = embeddings.embed_query("How do I restart a Kubernetes deployment?")
document_vectors = embeddings.embed_documents(["Deployment rollout guide", "Database backup guide"])
print(len(query_vector), len(document_vectors))
```

## Similarity metrics
Cosine compares vector direction. Inner product is dot product and depends on normalization. Euclidean is geometric distance. pgvector operators include cosine distance <=>, L2 distance <->, and negative inner product <#>. Lower distance means closer for distance operators. Scores from different models/metrics are not directly comparable.

## Vector stores
Common options include PostgreSQL/pgvector, Chroma, FAISS, and managed vector databases. Choose based on filtering, durability, scale, multi-tenancy, backups, operations, and query patterns.

```sql
SELECT chunk_id, content, metadata, embedding <=> :query_embedding AS distance
FROM document_chunks
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> :query_embedding
LIMIT :k;
```

Derive tenant filter from authenticated identity. Use parameterized SQL. Index choices include exact search, HNSW, and IVFFlat; approximate indexes trade recall for latency/memory. Benchmark against exact search with realistic data and inspect query plans.

## Lab
Record embedding model, dimensions, vector norm, and nearest neighbors. Compare cosine and L2 behavior and measure approximate-index recall.