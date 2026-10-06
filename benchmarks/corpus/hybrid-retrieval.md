# Hybrid Retrieval

## Dense and sparse search

BM25 ranks text using query term frequency, inverse document frequency, and document length normalization. Sparse retrieval is useful for exact terminology and rare identifiers. Dense embeddings represent text as vectors and can retrieve semantically related wording. Dense retrieval can miss exact identifiers and depends on the embedding model and its training distribution.

## Rank fusion

Reciprocal Rank Fusion combines ranked lists using the sum of one divided by a constant plus each document's rank. RRF uses rank positions rather than requiring dense and sparse scores to be calibrated. Duplicate document identifiers must be counted only once per input list. The fusion constant controls how strongly the highest ranks are favored.

## Reranking

A cross-encoder jointly processes a query and candidate passage to estimate relevance. Reranking a candidate shortlist can improve ordering but adds inference latency. Candidate recall places an upper bound on what a reranker can recover. Compare dense-only, sparse-only, hybrid, and reranked pipelines using the same relevance judgments.
