# Document Chunking

## Fixed windows

Fixed token windows split a document at regular intervals. Overlap preserves some context across boundaries but increases duplicate evidence and index size. Fixed windows are simple to reproduce, although they can split a coherent explanation.

## Section-aware chunks

Section-aware chunking keeps headings and their related content together, splitting large sections into bounded windows. Page and section provenance must survive parsing and chunking. Recursive chunking tries paragraph and sentence boundaries before falling back to fixed windows.

## Context selection

A context builder should remove near-duplicate evidence, enforce a token budget, and preserve coverage across documents. Including more chunks can crowd out useful evidence or repeat the same source. Measure retrieval recall and answer support for each chunking strategy rather than assuming semantic chunking always wins.
