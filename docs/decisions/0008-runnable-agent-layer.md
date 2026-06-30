# 0008 — The runnable agent layer: run-mode, citation honesty, agent degradation

**Status:** Accepted

## Context

Issue #3 builds the repo's first *runnable* core: the Maker and the Checker — two
agents on different vendors classifying the same case, state-isolated ([0001]).
Standing the agents up forced three decisions that the earlier records — written
before any agent ran — had deferred or assumed away. This record makes all three
together, because they share one tension: the repo must be **genuinely runnable**
*and* **honest about what it is** — a fresh, minimal rebuild descended from a
production system (Sandra) whose grounding it deliberately does not reproduce
([0006], [0007]).

The earlier records assumed the demo would run fully offline with no API keys
([0001] consequences, [0006], `PROCESS.md`, README). Building the real agents made
that assumption costly and, on reflection, unnecessary — see Decision 1.

## Decision 1 — Run-mode: live calls with your own keys, not an offline replay harness

The agents make **real cross-vendor API calls** (Google Maker, Anthropic Checker,
per `policy.models`), run with the caller's own keys via the `live`
optional-dependencies. There is **no offline fixture/replay mode.**

This **amends** the "runs offline, no keys" framing in [0001], [0006],
`PROCESS.md`, and the README — preserved-and-amended, not overwritten.

*Why:* requiring an API key is the normal, expected bar for this audience — every
comparable senior-AI repo runs that way. A capture-and-replay fixture harness
(provenance-stamped recordings, dual-mode CLI) is engineering the market does not
ask for — gold-plating against KISS/YAGNI. The "it works end-to-end, in production"
proof is carried by **Sandra (live)**, not by this repo simulating itself.

*Alternatives:* (a) **offline fixtures only** — rejected: the cross-vendor hero
never actually runs; fails the honesty spine and the mirror-test lesson. (b)
**dual-mode** (offline default + `--live`) — rejected: the fixture harness is the
gold-plating above, buying a self-imposed "no-keys" bar nobody asked for.

*Consequence — the mirror-test lesson still binds.* At least one test must hit the
real artifact. CI cannot make paid, non-deterministic calls, so: a `live`-marked
test (skipped in CI, run manually) exercises the real vendor path, and an adapter
**contract test** exercises the real dispatch/parse code in `agents.py` against a
stubbed transport. The honesty spine's RUNS column changes from "runs offline" to
**"runs with your own API keys."**

## Decision 2 — Citations: cite parametrically, name the gap, point to the production fix

The live agents **do** emit `articles_cited`, populated from the model's own
knowledge. The repo is **explicit — at the point of output and in the README —
that these citations are ungrounded**: the parametric-bleed failure mode [0007]
names, and **not how the production system (Sandra) does it.** Production grounds
each classification against retrieved regulatory text with provenance; the *design*
of that fix is [0007], the running implementation is Sandra.

*Why:* this keeps the richer demo (citations, and a second axis on which Maker and
Checker can diverge) while turning the gap into an **affirmative teaching point**
rather than a defensive caveat. It makes [0007] load-bearing — the running code
shows the naive version, the record shows the fix — and wires this public repo to
its production parent, which is the repo's actual identity (the public face of
private work). Disclosure stays inside the line [0007] already drew: the *shape* of
the fix is shown (domain-tuned embeddings, top-k + similarity floor,
framework-scoped retrieval, provenance); the corpus pipeline, chunk schema, and
extraction prompting are withheld. Grounded-RAG-over-legal-text is textbook —
naming it gives away no advantage.

*Alternatives:* (a) **cite with a bare "illustrative" caveat** — weaker: apologises
for the failure mode instead of teaching it, and never connects to production. (b)
**deliberately don't cite** (leave `articles_cited` empty) — rejected: thins the
demo, removes a divergence axis, reads as a gap unless the reader digs, and
over-applies [0007]'s *production* danger to a worked-example demo.

*Constraint:* `policy.prompts.maker_system` / `checker_system` keep requesting a
citation — config, not code; the honesty framing lives in the README and CLI
output, not by neutering the prompt. Tone is factual, not lecturing.

## Decision 3 — Agent degradation: an out-of-taxonomy or unparseable output is a *failure*, not a classification

An agent **succeeds** only if it returns a `risk_tier` in `policy.risk_tier_ids`
with a rationale. An API error, a timeout, an unparseable response, **or a tier
outside the loaded taxonomy** is an **agent failure**: that agent's output is
`None`, the result is marked `degraded`, and the case still proceeds to the human
(parent ADR-012; fail toward the human, never a silent drop — consistent with
[0003] and [0005]).

*Why:* the insidious case is a model that confidently returns a tier the taxonomy
doesn't contain, or prose instead of a tier. Letting that into the verdict
comparison (#4) means comparing garbage and calling it a divergence. Validating at
the **agent boundary**, against the loaded policy, keeps the bad state out of the
pipeline early — the same fail-fast discipline as config loading ([0004]).

*Alternative:* treat an out-of-taxonomy tier as a valid-but-divergent
classification — rejected: it launders a malformed output into a legitimate-looking
disagreement and corrupts the verdict.

## Consequences

- The repo has a genuinely runnable core (with keys), honestly labelled; Sandra
  carries the production proof.
- [0007] becomes load-bearing — referenced by an observable behaviour in the
  running code, not a side document.
- `agents.py` validates each agent's tier against the loaded policy, so the verdict
  layer (#4) can trust that any non-`None` `AgentOutput` carries an in-taxonomy tier.
- **Doc debt to settle in this issue** (lands with the code that makes it true):
  amend [0001], [0006], `PROCESS.md`, and the README ("offline / no-keys" → "with
  your own keys"); add the citation-honesty note to the README and CLI output;
  update [`adr-lineage.md`](adr-lineage.md) (ADR-012's agent-degradation half moves
  from *deferred* to *covered* here — parallelism stays deferred to #5).

## Evidence

- `src/maker_checker_agents/agents.py` — `run_maker`, `run_checker`, vendor adapter,
  tier validation (lands in #3).
- `config/policy.yaml` — `models`, `prompts`.
- `tests/` — `live`-marked real-call test + adapter contract test + degradation /
  out-of-taxonomy tests (land in #3).
- README §2 (runnable hero), §4 (TCO — grounding cost), honesty spine; [0007]
  (grounding design).

## Lineage

Run-mode and degradation descend from the parent's **ADR-012** (graceful
degradation — agent failure continues, never halts); the always-human floor from
**ADR-003 / ADR-014** survives via [0005]. Citation honesty descends from
**ADR-017 / ADR-018** (grounding as the parametric-bleed fix) — recorded as design
in [0007], its running implementation in Sandra. See
[`adr-lineage.md`](adr-lineage.md).

[0001]: 0001-cross-vendor-agent-independence.md
[0003]: 0003-fail-open-on-gate-error.md
[0004]: 0004-config-as-governance.md
[0005]: 0005-type-enforced-hitl.md
[0006]: 0006-inherited-scope-boundaries.md
[0007]: 0007-grounding-and-retrieved-source-provenance.md
