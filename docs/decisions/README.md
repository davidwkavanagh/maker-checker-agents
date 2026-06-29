# Decision records (ADR-lite)

Short records of the non-obvious calls behind this repo — the decision, the
alternatives considered, and why. They are lightweight on purpose: enough to
show the reasoning, not a ceremony. See [`../../PROCESS.md`](../../PROCESS.md)
for how decisions get made and recorded.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-cross-vendor-agent-independence.md) | Cross-vendor agent independence, enforced by state isolation | Accepted |
| [0002](0002-deterministic-config-driven-scope-gate.md) | Deterministic, config-driven scope gate — not a generative router | Accepted |
| [0003](0003-fail-open-on-gate-error.md) | The scope gate fails open, never closed | Accepted |
| [0004](0004-config-as-governance.md) | Governance lives in config, not code (on-deploy) | Accepted |
| [0005](0005-type-enforced-hitl.md) | Human-in-the-loop is enforced by the type system | Accepted |
| [0006](0006-inherited-scope-boundaries.md) | Inherited concerns deliberately not built | Accepted |
| [0007](0007-grounding-and-retrieved-source-provenance.md) | Grounding and retrieved-source provenance | Accepted (design record) |

Records 0001–0005 are a **backfill**: the decisions were made and the code was
already adversarially reviewed (commit `9cec880`) before they were written up.
From here, new decisions are recorded before or alongside the work, per
`PROCESS.md`.

## Lineage

This engine descends from a larger regulated-AI system. [`adr-lineage.md`](adr-lineage.md)
maps all 21 of that system's architecture decisions to their status here —
**covered** (one of the records above), **deferred** (written with the code that
implements it), or **cut** ([0006](0006-inherited-scope-boundaries.md) — including
things built in the parent system but deliberately not reproduced here to protect the
code; some carry a design record such as [0007](0007-grounding-and-retrieved-source-provenance.md)
showing the engineering). It exists
so the inheritance is provable: nothing was dropped by accident.
