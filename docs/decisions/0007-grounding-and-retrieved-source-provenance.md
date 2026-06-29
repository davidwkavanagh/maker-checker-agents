# 0007 — Grounding and retrieved-source provenance

**Status:** Accepted — **design record.** This grounding design is **built and tested in
the production system** this engine descends from. It is deliberately **not reproduced**
in this public rebuild — copying it would mean exposing proprietary code and standing up
a real vector store. So this record makes the *engineering visible* without duplicating
it; the runnable proof is the production system, not this repo. (See *Where this runs*.)

## Context

Parametric bleed: an LLM asked to cite regulation will produce plausible-looking
article references from its training distribution — confidently, and sometimes
wrong. In a high-stakes classification ("which EU AI Act risk tier does this system
fall under?"), a hallucinated *Article 6* citation is worse than no citation: it
reads as authoritative. The fix is **grounding** — retrieve the actual regulatory
text relevant to a case, make the model reason from it, and attach provenance to
each retrieved item so a citation is *traceable*, not generated.

## Decision

In the production system, classifications are grounded in retrieved regulatory sources,
and every retrieved item carries **provenance** (its source reference) into the verdict
trail.

- **Domain-tuned embeddings, not general-purpose.** Regulatory text is a specialist
  register. A legal-domain-tuned embedding model (`voyage-law-2`) retrieves
  materially better on a legal corpus than a general-purpose model. The embedding
  choice is the single biggest lever on retrieval quality in this domain — so it's
  the decision that gets named, not defaulted.
- **Top-k with a similarity floor.** Retrieve the `k=3` most similar chunks, but
  apply a relevance threshold (`0.5`): below it, retrieval is marked **LOW**
  confidence rather than feeding weak context to the classifier as if it were
  strong. Zero results does **not** halt — the case proceeds to a human with empty
  context and a LOW signal (honest degradation, not a crash).
- **Framework-scoped retrieval.** Retrieval is filtered to the governing framework
  (e.g. EU AI Act), so a case is grounded only in the law that applies to it.
- **Provenance as a proof artefact.** Each retrieved chunk carries the clause/article
  it came from, and that reference travels with the classification. It's the
  difference between *"the model said Article 5"* and *"here is the Article 5 text
  the model was shown"* — the second is auditable; the first is a claim.

## Alternatives considered

- **No grounding (parametric only).** Rejected — the parametric-bleed failure mode
  above; citations can't be trusted in a high-stakes setting.
- **Full-context (put the whole regulation in the prompt).** Rejected — cost (every
  classification pays for the entire corpus in tokens, on *both* agents) and focus
  (the model reasons over noise). Retrieval pays only for what's relevant.
- **General-purpose embeddings.** Rejected — measurably weaker retrieval on
  specialist legal text than a domain-tuned model.
- **No similarity floor (always trust top-k).** Rejected — feeds weak matches to the
  classifier as if confident. The LOW signal is what keeps a thin retrieval honest.

## Cost — the line most people miss

Grounding is not free: retrieved context grows the prompt, so each classification
pays retrieval tokens **on both agents** (the pattern runs two). Bounding it with
`k=3` + a threshold — rather than full-context — keeps that cost predictable, but it
is real and belongs in the TCO method (README §4) as an explicit input, not a hidden
line.

## How it's built (the shape, without the internals)

The pattern, at architecture altitude — how the production system does it, enough to
replicate, without exposing its internals:

1. **Ingest** the regulatory corpus into chunks at a sensible semantic unit
   (clause / article), each tagged with its source reference for provenance.
2. **Embed** each chunk with a domain-tuned model; store the vectors in a vector
   store, keyed by framework.
3. **Retrieve** at classification time: embed a query built from the case's most
   predictive fields, similarity-search top-k within the framework filter, apply the
   relevance floor.
4. **Format + carry provenance:** hand the model the retrieved text *and* keep each
   source reference attached to the result.

The seam in this engine is a single signature — a retriever is
`case → list of retrieved sources, each with provenance`. Everything above plugs in
behind that signature; this record fixes the contract, the implementation lives where
it is tested.

*Deliberately not specified here:* the corpus extraction/normalisation pipeline, the
chunk metadata schema, and the extraction prompting. Those are the parent system's
engineering and out of scope for a public design record.

## Where this runs

This grounding runs in the production system this engine descends from (see the status
block above) — not a roadmap item. It is **not reproduced in this public rebuild**:
doing so would copy proprietary ingestion code and require a real vector store (the
"real corpus ingestion" deliberately cut in [0006]). So this repo records the *design
and reasoning*; the running, tested implementation lives in the production system. The
honesty spine reflects that — grounding is **built in the real product, documented (not
reproduced) here** — not "RUNS here" and not "NEXT". What *is* next for the real
product is grounding **hardening** (guarding the retrieval against drift, with the
evaluation method) — that's the honest forward line, not "build grounding".

## Consequences

- The thinking behind grounding (why, and the specific trade-offs) is captured and
  provable, without shipping a keyword-matcher that would demonstrate plumbing
  instead of judgement.
- Provenance is not modelled in this repo's code: with retrieval cut, nothing here
  produces a retrieved source to carry — a provenance field would dereference to
  nothing (the shelfware anti-pattern this repo argues against).
- A reader can replicate the pattern from the seam above; the proprietary ingestion
  engineering is named as out-of-scope rather than half-exposed.

## Lineage

Descends from the parent system's **ADR-017** (parametric bleed → grounding as the
fix; retrieved sources as proof) and **ADR-018** (retrieved-source provenance). Real
corpus ingestion is the cut boundary in [0006]. See [`adr-lineage.md`](adr-lineage.md).

[0006]: 0006-inherited-scope-boundaries.md
