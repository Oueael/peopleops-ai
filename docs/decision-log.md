# Engineering Decision Log

This document records key implementation decisions made while building the PeopleOps AI Assistant.

## 1. PostgreSQL with pgvector for retrieval

**Decision:** Store handbook chunks and their embeddings in PostgreSQL using pgvector.

**Reason:** This keeps document metadata and vector search in one database and provides a straightforward foundation for retrieval-augmented generation.

## 2. Role-based filtering before generation

**Decision:** Apply employee, manager, and HR access restrictions during document retrieval.

**Reason:** Access control should not depend solely on the language model following prompt instructions.

## 3. Private Slack responses

**Decision:** Send generated answers through direct messages rather than posting them in public channels.

**Reason:** This reduces the risk of exposing restricted or potentially sensitive workplace information.

## 4. Rule-based sensitive-topic escalation

**Decision:** Use keyword detection before retrieval and generation.

**Reason:** A simple rule-based implementation provides predictable handling for selected sensitive topics without relying entirely on an LLM.

**Tradeoff:** Keyword detection can miss relevant messages or produce false positives.

## 5. Citation validation

**Decision:** Validate citation references against retrieved documents and append readable document names and section headings.

**Reason:** Users need to identify the handbook material behind an answer.

**Tradeoff:** Reference validation does not prove that a cited passage supports every statement.

## 6. Synthetic handbook data

**Decision:** Use synthetic company policies rather than real employee or company records.

**Reason:** This allows the system to demonstrate retrieval, permissions, and escalation without exposing private organizational information.

## 7. Evaluation before expanding features

**Decision:** Maintain separate retrieval/policy and answer-generation evaluations.

**Reason:** Retrieval correctness and generated answer quality are different things and should be tested separately.

**Tradeoff:** The current evaluation set is small and does not establish production readiness.