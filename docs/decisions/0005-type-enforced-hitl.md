# 0005 — Human-in-the-loop is enforced by the type system

**Status:** Accepted

## Context

The core invariant of this system is that **a human always makes the call** — the
human carries the decision and is never a fallback. The scope gate may skip the
expensive model pair, and a verdict may come back divergent or degraded, but in
no path does a case bypass the human. An invariant this important cannot be
guaranteed by a comment or a prose docstring.

## Decision

The HITL invariant is **enforced by the type system**. `ScopeResult` and
`VerdictResult` both carry `routed_to_human: Literal[True]` — it is *impossible to
construct* either result with the human skipped. Divergence does not gate whether
a human is involved; it only changes *what the human is told*.

This came directly out of the adversarial review (commit `9cec880`): the
invariant had been expressed as a comment and a prose string, which a refactor
could quietly violate. Making it a `Literal[True]` field that tests assert closed
the gap.

## Alternatives considered

- **Comment / docstring only.** Rejected — exactly what the review caught;
  documentation is not enforcement.
- **A `bool` defaulting to `True`.** Rejected — a `bool` can be set `False`; the
  type then permits the very state the invariant forbids.
- **Runtime assertion.** Weaker — fails at run time on a specific path; the
  `Literal[True]` makes the bad state unrepresentable at construction.

## Consequences

- The "human always decides" guarantee is checked by `mypy`, not trust.
- Mirrors the lesson in README §8: a prompt instruction (or a comment) is not a
  control; the guarantee has to live where it can be enforced.

## Evidence

- `src/maker_checker_agents/models.py` — `ScopeResult.routed_to_human` and
  `VerdictResult.routed_to_human`, both `Literal[True]`.
- `tests/` — assertions on the field.
- README §2 (graceful degradation → still reaches a human), §8.
