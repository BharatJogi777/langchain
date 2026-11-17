# Advanced RAG and evaluation

## Retrieval improvements
Metadata filtering; hybrid lexical + vector search; query rewriting; multi-query retrieval; parent-child retrieval; contextual compression; reranking; MMR diversity; ensemble retrieval/rank fusion. Each stage adds latency and complexity; retain it only if evaluation proves improvement.

## Reranking
Retrieve a broad candidate set, rerank query-document pairs, and pass a smaller top set to the model. A reranker is different from an embedding model. Benchmark candidate count and final context size.

## Evaluation dimensions
Retrieval: Recall@k, Precision@k, MRR, nDCG. Answer: correctness, completeness, faithfulness, relevance. Citations: coverage and entailment. Operations: p50/p95 latency, token usage, cost, failure rate. Safety: cross-tenant leakage, injection resistance, abstention.

## Evaluation loop
Build a representative test set → baseline → change one variable → run retrieval and answer evaluations → inspect category regressions → promote measured improvements → monitor drift. Keep evaluation examples separate from prompt few-shot examples where possible.

## Lab
Compare vector-only, hybrid, and hybrid+reranker on the same corpus. Report Recall@5, MRR, faithfulness, p95 latency, and cost. Explain the deployment choice.