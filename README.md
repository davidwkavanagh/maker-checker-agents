# maker-checker-agents

**Independent dual-agent verification for high-stakes AI classification.** Two models from different vendors classify the same case without seeing each other's work; a deterministic check surfaces where they disagree; a human always makes the call. The rules that govern the AI live in configuration, not code.

> 🚧 **Private build in progress.** This README is written spec-first — the arc below describes the *target* product, and the honesty-spine table is its launch state. Every claim in the *RUNS* column is validated against working code **before this repository is made public**; during the private build some are still being wired.

---

## 1. The problem

When you ask a single model to classify something high-stakes — and then ask the same model whether it got it right — it tends to agree with itself. One model can't grade its own homework. In domains where being wrong is expensive (regulated industries, legal exposure, real money), "the model said so" is not a defensible answer.

The need isn't a smarter single model. It's a *process* that produces an independent second judgement, makes disagreement visible, and keeps a human accountable for the decision.

## 2. What runs — the Maker-Checker engine *(runnable hero)*

Two agents on **different model vendors** classify the same case:

- **Maker** proposes a classification.
- **Checker** classifies the same input **without ever seeing the Maker's output** — independence is enforced by state isolation, not by asking the model nicely.
- A **deterministic, non-LLM verdict** compares the two: *consistent*, *divergent*, or *inconclusive*. The comparison is code, not a third model — it can't hallucinate its own conclusion.
- **Graceful degradation:** if one agent fails, the pipeline doesn't. The case proceeds to a human with the verdict marked degraded.

This is not an invention. It's the **pragmatic application of an established control pattern** — maker-checker / four-eyes, long used in finance and audit — to the specific failure modes of LLMs. The contribution is the engineering that makes it real: hard independence, a deterministic verdict, and honest failure handling.

> **On the citations it emits.** Each agent returns article references from the model's own training knowledge — these are **ungrounded**, the parametric-bleed failure mode named in [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md). That is deliberately **not** how the production parent does it: production grounds every classification against retrieved regulatory text, with provenance. The ungrounded version runs here on purpose — it makes the gap visible and keeps the fix ([0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) concrete rather than abstract.

> _[visual: demo GIF — Maker-Checker running on a sample case, terminal output]_

## 3. The digital-enablement layer — governance in config, not code

The behaviour of the system — the risk taxonomy, the model assignments, the thresholds, the prompts that frame each agent — lives in a **YAML configuration layer**, not in the Python.

A non-technical owner (a compliance or risk lead) can change *what the system considers high-risk*, *which model does which job*, or *how strict the agreement threshold is* by editing config — **config, not code**. The change takes effect **on the next deploy** (not live, not zero-deploy — stated honestly).

This is the most product-leader-relevant asset in the repo: it turns a model pipeline into something a business owner can actually govern.

> _[visual: clip — edit a YAML value, behaviour changes]_

## 4. What it costs — a TCO method *(not a number on a random Tuesday)*

Running two models instead of one has a cost, and a serious buyer will ask what it is. This section is a **costing method**, not a hardcoded figure: token overhead of the second agent, context-window growth from retrieved grounding (a grounded-system input — grounding runs in the parent, not in this rebuild; see [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)), retry logic, and — the line most people miss — **the cost of the human-in-the-loop cycles that divergence triggers.**

The output is a model you can point at *your* volumes to project a P&L line item at scale.

## 5. How it's measured — an evaluation framework *(method, not published accuracy %s)*

Claiming an accuracy number on a small set looks fabricated. Instead this describes the **evaluation pipeline architecture**: drift tracking over time, precision/recall against a golden set, and the **single-vs-dual delta threshold** — the measured question of whether the second agent actually earns its cost.

A method for knowing whether it works beats a number that asks you to take it on faith.

## 6. Latency — a decision, not a gap

Two models sound like double the wait. They aren't. Maker and Checker run **in parallel** (fan-out / fan-in) — independence is held by state isolation, not by running them in sequence. You pay the **slower** of the two models, not the sum. The honest latency floor is *(slower model + the explanation step; add retrieval in the grounded parent system)*; divergent cases add human wall-clock, which is accounted for in the TCO method above, not hidden here.

## 7. What's next — route before you spend *(designed, not shipped — labelled)*

A cheap, config-driven router that triages cases up front, so you don't pay two frontier models to classify inputs that obviously don't apply. **Designed, not built** — it's on the roadmap, called out honestly rather than implied.

## 8. What I learned building it

- **Mirror tests give false confidence.** A test that re-implements the logic it's testing proves nothing about the shipping artifact — at least one test has to hit the real thing.
- **A prompt instruction is not a data-integrity control.** "Please don't include X" is not enforcement; the guarantee has to live in code, after the model returns.
- **A governed document no code reads is shelfware.** A config file that's the "source of truth" drifts silently unless something actually fails when it and the code disagree.

## 9. Tradeoffs

| Decision | Why |
|---|---|
| Two vendors, not two of the same model | Correlated errors defeat the point of a second opinion |
| Deterministic verdict, not an LLM judge | The thing that decides agreement can't be allowed to hallucinate |
| Config-driven router (next), not an LLM router | Triage should be cheap and predictable |
| RAG grounding, not full-context *(built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md))* | Cost and focus — retrieve what's relevant, don't pay for the whole corpus |
| Parallel, not sequential | Independence without paying latency twice |

---

## Honesty spine

*This table is the **target launch state** — the bar this repo must clear before it
goes public. Every RUNS claim is validated against working code first (see the
banner at the top); it is not a snapshot of the in-progress private build. Current
build status is tracked precisely in [`docs/decisions/adr-lineage.md`](docs/decisions/adr-lineage.md).*

| RUNS at launch (validated against code first) | DESIGNED / NEXT (honest roadmap) |
|---|---|
| Maker-Checker independent verification | Route-before-you-spend router |
| Human always decides — type-enforced | Multi-framework activation |
| Governance in config (config-not-code, validated at startup) | Grounding *hardening* + drift detection (base grounding built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) |
| | Cost-optimised expansion |

*If a claim can't sit cleanly on the left, it goes on the right with the tense to match.*

*RUNS = with your own Google + Anthropic API keys; there is no offline mode ([0008](docs/decisions/0008-runnable-agent-layer.md)).*

---

## Worked example

The configuration and sample cases in this repo use the **EU AI Act** as the worked example — public law, and a genuinely high-stakes classification problem (what risk tier does an AI system fall under). The engine is domain-agnostic; the EU AI Act is how it's shown working, not what it's limited to.

## Run it

> _Quickstart lands here once the CLI is built — one command, runs with your own Google + Anthropic API keys (no offline mode)._

## License

MIT — see [LICENSE](LICENSE).
