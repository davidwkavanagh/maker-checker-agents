# 0004 — Governance lives in config, not code (on-deploy)

**Status:** Accepted

## Context

The behaviour that a business owner cares about governing — what counts as
high-risk, which model does which job, how strict agreement must be, what framing
each agent gets, what's in scope — should be changeable by the person accountable
for it, not gated behind a developer and a code change. This is the most
product-leader-relevant asset in the repo: it turns a model pipeline into
something a compliance or risk lead can actually own.

## Decision

All of that behaviour lives in `config/policy.yaml`. A non-technical owner edits
the policy file; **no Python changes.** The config is loaded through a **typed,
fail-fast validator** (`config.py`) — a malformed policy is caught at startup
with a clear message, not mid-classification. Changes take effect **on the next
deploy** — stated honestly as config-not-code, *on-deploy* (not live, not
zero-deploy).

## Alternatives considered

- **Hardcoded taxonomy / model choice / thresholds in Python.** Rejected — every
  policy change becomes a developer ticket; the owner can't govern their own system.
- **Live / hot-reload config.** Rejected for now — adds moving parts and a
  consistency story that the honest "on-deploy" framing doesn't need. Overclaiming
  "live" would breach the honesty spine.
- **Untyped dict access of raw YAML.** Rejected — a typo in policy would surface
  as a runtime error deep in a classification run. Typed validation fails fast.

## Consequences

- The risk taxonomy is *not* a hardcoded enum — `risk_tier` is a validated string
  checked against the loaded policy (`models.py` documents this deliberately).
- A bad policy file fails loudly at load, not silently at use.
- This is the lesson the README §8 calls out: a governed document that no code
  reads is shelfware. Here the code fails if config and code disagree.

## Evidence

- `config/policy.yaml` — the full governance surface, commented for the owner.
- `src/maker_checker_agents/config.py` — `Policy`, `load_policy`, `ConfigError`,
  fail-fast validation, unique-tier-id validator.
- `src/maker_checker_agents/models.py` — risk tier as validated string, not enum.
- README §3, §8.

## Lineage

Descends from the parent system's ADR-016 Decision 1 (prompts in governed config,
not code) and ADR-011 (config-driven model selection). The state-integrity half of
ADR-016 (a write-once audit field via a custom reducer) is *echoed in spirit* here
by `frozen=True` Pydantic models — immutability after construction, not the same
mechanism, and there is no audit record in this engine yet. See
[`adr-lineage.md`](adr-lineage.md).

## Amendment — 2 Jul 2026 (issue #4, [0009])

When this record was written, `agreement.threshold` was declared in policy but read
by no code — a governed value that was, by this record's own §8 test, shelfware. The
verdict layer ([0009] Decision 4) now **consumes** it: `verdict.py` reads
`agreement.threshold` and dispatches on it, and an unrecognised strategy raises. So
strictness is now genuinely config-*governed*, not just config-*declared*.

One honest bound follows: `exact` is the **only supported strategy** — a deliberate
governance choice, not a limitation to be grown ([0009] Decision 4 rejects an
adjacent-tier setting as an anti-feature that would hide material disagreement). The
"thresholds" plural in this record's Context, and the README §3 line that an owner
could change *how strict* agreement is, therefore **overclaimed a dial**: there is one
validated strategy, not a knob to turn. The README §3 line was neutralised in #4 (the
overclaim removed); the richer §3 rewrite remains on #7. This amendment records the
true state.
