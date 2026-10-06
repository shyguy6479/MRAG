# Authored evaluation fixture

The eight Markdown files are short, manually authored engineering notes, not copies
of research papers and not a representative production corpus. Questions and
relevance judgments were authored alongside the notes. There is no training split
and no claim of held-out generalization. All timing and score results must be
computed by the runner; never fill in a result manually.

Retrieval judgments are at **document level**. Deduplicate retrieved document IDs
before Recall@5, Precision@5, MRR, and nDCG@5. Generation measurements are explicitly
named proxies: token F1 against a reference, exact-source claim support, citation
existence, and relevant-document context fraction. They are not LLM-judge ratings,
semantic entailment accuracy, or calibrated answer-correctness estimates.
