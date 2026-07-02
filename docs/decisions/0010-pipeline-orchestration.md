# 0010 — Pipeline orchestration: stdlib fan-out, an on-ramp to a framework

**Status:** Accepted

## Context

Issue #5 wires the four stages built so far — scope gate ([0002]), the two agents
([0008]), the deterministic verdict ([0009]) — into one end-to-end runner:

```
scope gate → (maker ‖ checker, concurrent) → verdict → human
```

This is the last piece of the S157 "runnable hero": the parts existed but nothing
composed them into a run. The one open decision the plan reserved for this issue
(§5, and the #5 body) is the **orchestration engine** — plain Python or a graph
framework (LangGraph). Parent **ADR-006** makes LangGraph the runtime for Sandra's
pipeline, so choosing plain Python here is a recorded *departure*, not an oversight.

## Decision 1 — Plain-Python (stdlib) orchestration, no framework

The runner is a plain function that composes the four stage functions. No
LangGraph, no orchestration dependency.

*Why:* the runtime here is a linear flow with a single fan-out (two agents) and a
single conditional (in scope or not). Every payoff a graph framework buys —
durable interrupt/resume, multi-node conditional routing, multi-framework fan-out
— maps to a capability this repo has **already, deliberately, cut** (persistence
[0006]; the semantic router is production-NEXT; multi-framework is out of scope).
Importing the framework to power seams that will not be built here is the exact
"reaches for the heavyweight tool" signal a code-quality reviewer reads as
over-engineering — the opposite of the intended read for a *product-leader* repo
whose edge is right-sized judgment.

*Alternative — LangGraph now (mirror fidelity):* rejected for this artifact.
Sandra genuinely runs on LangGraph, and mirror-fidelity is a real pull — but the
mirror is satisfied at the **behaviour** level (parallel fan-out, always-human),
and LangGraph is Sandra's *mechanism*, the same category as RAG / persistence /
LangSmith, all already cut and documented ([0006]). Using it while exercising none
of its distinguishing features (no durable interrupt, no conditional graph) would
claim a capability the run does not use. Departs from parent **ADR-006**.

## Decision 2 — The stages are discrete node-functions: the runner is an on-ramp

`run_scope_gate`, `run_maker`, `run_checker`, `run_verdict` are already separate,
independently-tested, module-level functions. `run_pipeline` only *composes* them;
it holds no stage logic of its own. Concurrency is isolated to one private helper.

*Why:* this structure **is** the LangGraph graph minus the wrapper — four nodes, a
fan-out from the gate to the two agents, a fan-in to the verdict. Moving to the
framework is a mechanical wrap (declare the nodes and edges), not a rewrite of any
stage. So the plain-Python choice is not a dead end: it is the readable spec of the
graph, and a user can move onto LangGraph from it. Keeping the stages pure is what
makes that true — the on-ramp is a property of the factoring, not a promise.

## Decision 3 — Concurrency via one `ThreadPoolExecutor` at the fan-out

Maker and Checker run at the same time in a two-worker `ThreadPoolExecutor`; the
runner blocks on both results. Everything else stays synchronous.

*Why:* the agent calls are **blocking network I/O**, which releases the GIL, so
threads give real wall-clock parallelism — the README §6 property ("pay the slower,
not the sum"). Independence is already structural ([0008]: neither agent function
can receive the other's output), so running them concurrently changes only timing,
never the result. A binding test proves the concurrency with a `threading.Barrier`
that only releases if both agents are in flight at once — not a mock that would
pass even if they ran sequentially ([mirror-tests-false-confidence lesson]).

*Alternative — `asyncio.to_thread` + `gather`:* equivalent runtime, rejected to
keep the whole stack synchronous. Async would infect the CLI (#6) entrypoint with
an event loop for a single one-shot fan-out, buying nothing. Sync stage functions
also map more directly onto LangGraph nodes (Decision 2).

## Decision 4 — Out of scope skips the spend, never the human

When the scope gate returns `proceed=False` it is confident the case matches no
governed framework, so the runner **does not call the agent pair at all** —
`PipelineResult.verdict` is `None`. The case still reaches a human
(`routed_to_human` is `Literal[True]` by type on both the scope result and the
pipeline result).

*Why:* this is the asymmetric-risk rule the scope gate already documents — it may
skip the *expensive model spend*, never the *human*. Realising it in the runner is
"route before you spend", shown running. It also keeps three states distinct that a
lazier design would merge: **out of scope** (agents never ran → `verdict=None`),
**in scope but one agent failed** (agents ran, one returned `None` → verdict
`INCONCLUSIVE`, [0009]), and **both agents failed** (a run failure, Decision 6).
Collapsing any of them would mislabel a deliberate skip, or a total failure, as a
routine review.

*Note:* the deterministic scope gate provides this skip today; the *semantic*
router that would skip more cases is the production-NEXT upgrade (README §7),
labelled, not built.

## Decision 5 — A degraded (fail-open) gate still runs the pair, and the verdict caps

If the scope gate fails open on an error it returns `proceed=True, degraded=True`
([0003]). The runner therefore **does** run the agents (fail toward doing the work),
and passes `degraded` through to `run_verdict`, which caps the outcome to
`INCONCLUSIVE` ([0009] Decision 2). No new logic — the cap already lives in the
verdict; the runner's job is only to forward the flag.

## Decision 6 — Both agents failing is a run failure, not a routed verdict

If **both** agents return `None`, `run_pipeline` raises `PipelineError`; it does not
return a result. A *single* agent failing still yields one classification →
`INCONCLUSIVE`, routed for human review ([0009], graceful degradation). Both failing
means both models were unavailable: there is no classification to review, so the run
cannot proceed.

*Ground truth (Sandra):* on a both-model failure Sandra shows the user an error and
"try again later" — **no path brute-forces a verdict through.** This repo mirrors
that guarantee *structurally*, not by convention: a `Verdict` is only ever built
inside `run_verdict`, which the runner reaches only *after* the both-`None` check
raises — so no failure can fabricate a verdict, and no catch-all should ever be
added that returns one (that is precisely the fix this record rejects, below).

*Why:* this is the FAILED state [0009] explicitly deferred to the runner ("a run
that failed outright — no verdict at all — is the runner's concern (#5)"). It stays
off the `Verdict` enum (still three-valued) and off the routed-to-human path, because
routing an empty case to a reviewer gives them nothing to act on. **A human initiates
every run synchronously** (the CLI, #6), so the error surfaces to exactly that
human — who retries. That same fact is why the runner does not wrap the fan-out to
"guard" the always-human floor: there is no async queue a case could vanish from, so
an error propagating to the initiating human *is* the safe outcome, not a dropped
case. (Sandra writes a `FAILED` pipeline *status* here because it persists runs
asynchronously; this repo has no persistence, so the synchronous raise is the
same behaviour at this repo's scope — mirror, not reproduction.)

*Alternative — return a `FAILED`-status result instead of raising:* rejected as
heavier for no gain. "Cannot proceed" is precisely what an exception expresses to a
synchronous caller; a status field would make every caller branch on it to produce
the same error.

*Alternative — wrap `run_pipeline` in a catch-all that returns a routed
`INCONCLUSIVE` result on any error (a cross-model reviewer proposed this to "guarantee
HITL"):* **rejected — it is the exact anti-pattern this decision forbids.** It would
brute-force a verdict through on a failed or misconfigured run, laundering a system
failure into a fabricated "human, please review" case. Sandra never does this (ground
truth above). The honest guarantee is the opposite: a failure *errors*, it does not
manufacture a verdict. HITL is enforced on every verdict the code *builds*, and no
verdict is built on failure — a stronger property than "every call returns something
routed".

## PipelineResult — the end-to-end outcome

A new frozen model carries the whole run: the `ScopeResult`, the `VerdictResult`
(or `None` when skipped), and `routed_to_human: Literal[True]`. It is the object
the CLI (#6) renders.

## Consequences

- The end-to-end pipeline genuinely runs; the S157 hero is complete (#4 + #5).
- **`adr-lineage.md` updates:** ADR-006 moves from *deferred* to **Departure** →
  this record (plain-Python, on-ramp documented). ADR-012's parallel fan-out moves
  from *deferred* to **covered** here. ADR-011's tiered end-to-end flow is now
  assembled here.
- **README §9 tradeoff owed (tracked to #7, not silently):** the "stdlib over
  LangGraph, and why production takes the framework (durable interrupt/resume +
  multi-framework routing this proof cuts)" row is the honest framing of Decision 1
  — it turns the departure into portfolio content rather than a gap.
- HITL: every *returned* result is type-enforced routed-to-human ([0005]); a both-fail
  run returns none — it raises, and the initiating human gets the error (Decision 6).
  The machine never makes a unilateral compliance call on a classified case.
- **Bounded fan-out (security review):** the wait on the two agents is capped at
  `_AGENT_TIMEOUT_SECONDS` — a hung vendor call degrades to `None` (the normal
  agent-failure path) rather than stalling the pipeline. The fix lives in the runner
  because the vendor-client seam (`_make_client`) is not exercised by CI (the live
  extras are optional). A client-side *request* timeout that also reaps the abandoned
  worker thread — only material once this is a long-lived service — is a tracked
  follow-up, not done blind against an un-pinned client version.

## Evidence

- `src/maker_checker_agents/pipeline.py` — `run_pipeline`, `_classify_concurrently`,
  `PipelineError`.
- `src/maker_checker_agents/models.py` — `PipelineResult`.
- `tests/test_pipeline.py` — in-scope run, out-of-scope skip (agents not called),
  degraded pass-through/cap, single-agent failure (INCONCLUSIVE) and both-agent
  failure (raises `PipelineError`), the `Barrier` concurrency test, routed-to-human
  parametrized across every returned path, real-gate wiring.
- `config/policy.yaml` — `framework_triggers` (drives in/out of scope).

## Lineage

Departs from parent **ADR-006** (LangGraph) — recorded, on-ramp preserved.
Assembles the tiered flow of **ADR-011**; completes **ADR-012**'s parallel fan-out;
carries the always-human floor of **ADR-003 / ADR-014** via [0005]; forwards the
degradation flag of **ADR-012** via [0003] / [0009]. See [`adr-lineage.md`](adr-lineage.md).

[0002]: 0002-deterministic-config-driven-scope-gate.md
[0003]: 0003-fail-open-on-gate-error.md
[0005]: 0005-type-enforced-hitl.md
[0006]: 0006-inherited-scope-boundaries.md
[0008]: 0008-runnable-agent-layer.md
[0009]: 0009-deterministic-verdict-and-cap.md
