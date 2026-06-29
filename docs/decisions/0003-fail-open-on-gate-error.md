# 0003 — The scope gate fails open, never closed

**Status:** Accepted

## Context

The scope gate can skip the expensive model pair for out-of-scope cases. That
makes it a place where a bug could silently *drop* a case — exactly the failure
mode a high-stakes classifier cannot have. In a regulated setting, missing a case
that should have been reviewed is the expensive error, not spending two models on
a case that didn't need them.

## Decision

On any gate error the system **fails open**: it treats every configured framework
as applicable, sets `proceed=True`, marks the result `degraded=True`, logs the
error, and continues. It never silently drops a case. The asymmetry is
deliberate — the gate may skip *spend*, but never the *human* (see [0005]).

## Alternatives considered

- **Fail closed (drop / halt on error).** Rejected — a silent drop is the worst
  outcome for a high-stakes case; a halt blocks the human who carries the decision.
- **Raise and surface to the operator.** Reasonable for a service, but for this
  engine the degraded-but-proceeding path keeps the human in the loop and flags
  the degradation explicitly — closer to how the parent system handles node
  failures (graceful degradation, never a hard stop).

## Consequences

- A broken gate over-includes (wastes spend) rather than under-includes (drops a
  case) — the safe direction.
- `degraded=True` is visible downstream so the failure is never hidden.

## Evidence

- `src/maker_checker_agents/scope_gate.py` — the `except` branch returns all
  frameworks, `proceed=True`, `degraded=True`.
- `tests/test_scope_gate.py` — fail-open test.

[0005]: 0005-type-enforced-hitl.md
