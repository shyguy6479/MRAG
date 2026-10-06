# Engineering discussion guide

## Retrieval

BM25 measures lexical matching with inverse-document-frequency and length
normalization. Dense retrieval represents text as vectors. Local LSA learns a
low-rank representation from this corpus; MiniLM uses pretrained neural embeddings.
LSA coordinates change after refitting, so they must not be mixed across corpus
revisions in a persistent collection. Configuration therefore rejects LSA with Qdrant.

RRF adds `weight / (k + rank)` for each unique candidate in each ranked list.
Ranks start at one; duplicates within a list count once; ties break by chunk ID.
Channel scores survive fusion for inspection. The fused value is not a probability.

The cross-encoder jointly reads a query and candidate passage. It can improve
ordering but cannot recover evidence absent from the candidate set. The neural
experiment measures its latency cost; the tiny fixture does not prove a quality gain.

## Agent

The agent is a bounded workflow, not an unconstrained LLM loop. It classifies,
optionally rewrites/decomposes, retrieves, constructs context, generates, verifies,
optionally retrieves once more, and finishes. Trace records expose actions,
durations, and evidence IDs, not internal model chain-of-thought.

The calculator uses an AST allowlist rather than `eval`. Documents cannot choose
shell commands, arbitrary URLs, or tool schemas. LLM system instructions are
separate from serialized untrusted evidence; the writer has no execution tools.
This reduces attack surface without claiming prompt injection is solved.

## Consistency and recovery

The document and pending job commit together. Worker claims carry leases and
fencing tokens. Stable chunk IDs make retries repeatable. External vectors are
written before a document becomes ready. Orphaned vectors cannot be returned
because the database snapshot defines the allowed IDs. Corpus mutations use a
consistent revision-row lock order to serialize publication and deletion.

Retrieval cache keys include revision, query, filters, provider/model identity,
ranking parameters, and top-k. Deleted evidence is excluded from new queries;
historical conversations retain earlier snapshots. Cache retention is not erasure.

Cache failures log and recompute; the shared rate limiter fails closed. Reranker
failures explicitly fall back to hybrid retrieval. Database failures make readiness
fail. Provider failures return sanitized 503 errors. Steps/deadlines bound agent
work; worst-case token/cost reservations include all permitted retries.

## Grounding

Exact excerpts are checked against cited evidence. Missing/fabricated citation
numbers, unsupported numeric values, and suspicious instruction text are rejected.
Lexical overlap remains partial support rather than proven entailment. The default
verified writer corrects partial/unsupported output to exact quotes, sacrificing
some fluency for auditability.

An exact quote can still be false, out of context, or incomplete. Confidence
measures heuristic support, not calibrated correctness. A production verifier
needs independent entailment evaluation and human review.

## Evaluation

The dataset contains eight notes and twelve questions authored together, not
held-out real-world validation. Explain Precision@K's denominator K, recall's
relevant-set denominator, MRR's first relevant rank, and nDCG's logarithmic
discount. The tests check formulas against hand-calculated rankings.

Token F1, exact-source support, and citation existence are proxies rather than
semantic correctness. Extractive experiments incur zero LLM tokens/API cost;
compute is not free. Cold/warm latency and index construction are separate.
The short loopback HTTP run does not establish sustained service capacity.

Decomposition can hurt global ordering by introducing generic subqueries. The
saved neural experiment demonstrates this trade-off rather than assuming agentic
retrieval always wins. Read the measurement report before making a resume claim.

## Scaling

Separate API and model inference; batch embeddings and bound GPU concurrency.
Replace process-local sparse indexes with incremental search behind the interface.
Add user/tenant authorization before retrieval and cache-key creation. Deploy
managed data services with private networking, replication and tested backups.
Move blobs to scoped object storage and isolate parsers. Add durable trace storage
and infrastructure failure injection. Choose changes from observed bottlenecks.
