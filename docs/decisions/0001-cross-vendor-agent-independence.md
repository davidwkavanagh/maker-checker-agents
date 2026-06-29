# 0001 — Cross-vendor agent independence, enforced by state isolation

**Status:** Accepted

## Context

The whole point of a second opinion is that it is *independent*. A single model
asked to check its own answer tends to agree with itself, and two instances of
the *same* model share the same blind spots — their errors are correlated, so a
second pass adds confidence without adding safety.

## Decision

The Maker and the Checker run on **different model vendors** (Google for the
Maker, Anthropic for the Checker — set in `config/policy.yaml`, `models` block).
Independence is enforced by **state isolation**: the Checker classifies the same
case and never receives the Maker's output. The two agents emit the *same*
output shape (`AgentOutput`) — independence is about not sharing *data*, not
about having different schemas.

## Alternatives considered

- **One model, self-check (reflexion).** Rejected — a model grading its own
  homework. Cheapest, least independent.
- **Two instances of the same model.** Rejected — correlated errors defeat the
  purpose of a second judgement.
- **Sequential (Checker sees Maker).** Rejected — anchoring destroys
  independence; also pays latency twice (see [0002] and the README on parallelism).

## Consequences

- Two vendor SDKs and two API keys when running live; the offline demo avoids both.
- A real, uncorrelated second opinion — the property the product is selling.
- Vendor choice is config, swappable without code (see [0004]).

## Evidence

- `config/policy.yaml` — `models.maker` (google) vs `models.checker` (anthropic).
- `src/maker_checker_agents/config.py` — `ModelAssignments`, `Provider` Literal.
- `src/maker_checker_agents/models.py` — `AgentOutput` (shared shape).
- README §2, §9.

## Lineage

Descends from the parent system's ADR-015 (independence by state isolation,
Option B→C) and ADR-011 (cross-provider challenge). See [`adr-lineage.md`](adr-lineage.md).

[0002]: 0002-deterministic-config-driven-scope-gate.md
[0004]: 0004-config-as-governance.md
