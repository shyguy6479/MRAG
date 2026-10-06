# Retrieval Caching

## Cache keys

Retrieval cache keys should include the corpus revision, normalized query, metadata filters, provider identity, and retrieval configuration. A document insertion or deletion changes the corpus revision, making earlier retrieval cache entries ineligible. Model changes also require cache namespace changes.

## Durable ingestion

Document ingestion should persist a pending job before processing begins. Workers claim jobs with a lease and use idempotent chunk identifiers. A document becomes searchable only after all required indexing writes succeed. A periodic scan can recover queued jobs after missed broker notifications.

## Trade-offs

Caching can reduce repeated computation but introduces invalidation and capacity management. Report cache hit rate separately from cold-query latency. Redis cache failures may fall back to recomputation, while loss of the authoritative document database should make the service unavailable.
